"""Review the explicitly authorized historical source edition, with replay checks.

Defaults to a dry run. This source-specific command preserves the known PDF
defects; it never publishes a release or certifies current consolidated law.
"""

import argparse
import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.ingestion.extraction import NativePdfExtractor
from app.ingestion.normalization import normalize_page_text
from app.ingestion.service import (
    decide_review_candidate,
    update_review_issue,
    verify_source_document,
)
from app.ingestion.storage import get_blob_store
from app.ingestion.text_alignment import compact_text
from app.legal.enums import (
    EmbeddingProviderKind,
    EvaluationDatasetKind,
    EvaluationItemKind,
    ExtractionCandidateStatus,
    IngestionArtifactType,
    LegalStatus,
    PageInclusionStatus,
    ReviewDecisionType,
    ReviewIssueStatus,
    VerificationStatus,
)
from app.legal.models import (
    AuditEvent,
    EmbeddingProfile,
    EvaluationDataset,
    EvaluationItem,
    ExtractionCandidate,
    IngestionArtifact,
    IngestionRun,
    LegalInstrument,
    ReviewIssue,
    SourceDocument,
    SourcePage,
)
from app.legal.parser import SourcePage as ParserPage
from app.legal.parser import parse_constitution_pages
from app.legal.schemas import ReviewDecisionCreate, ReviewIssueUpdate
from app.models import User

SOURCE_SHA256 = "26c1b7f15fb6eae02aa2064e5cc2c3fa5d84f6c7c0b04a0f4e94a8183df3e838"
MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
KNOWN_PUNCTUATION_PATHS = {
    "constitution-1999.chapter5.part1.section54",
    "constitution-1999.chapter5.part1.section54.subsection3",
    "constitution-1999.chapter6.part2.section188",
    "constitution-1999.chapter6.part2.section188.subsection3",
    "constitution-1999.chapter8.part2.section305",
    "constitution-1999.chapter8.part2.section305.subsection1",
    "constitution-1999.schedule1.part2.item1",
}


def review(session: Session, args: argparse.Namespace) -> dict[str, Any]:
    run = session.get(IngestionRun, args.run_id)
    if run is None:
        raise ValueError("Run not found")
    source = session.get(SourceDocument, run.source_document_id)
    if source is None or source.sha256 != SOURCE_SHA256:
        raise ValueError("This review policy applies only to the verified source hash")
    reviewer = session.get(User, run.created_by)
    if reviewer is None or not reviewer.is_superuser:
        raise ValueError("The authorized run uploader must be a local superuser")
    instrument = session.get(LegalInstrument, source.legal_instrument_id)
    if instrument is None:
        raise ValueError("Source instrument missing")
    candidates = list(
        session.exec(
            select(ExtractionCandidate)
            .where(ExtractionCandidate.run_id == run.id)
            .order_by(ExtractionCandidate.sort_key)
        ).all()
    )
    pages = session.exec(select(SourcePage).where(SourcePage.run_id == run.id)).all()
    included_pages = {
        page.page_number
        for page in pages
        if page.inclusion_status == PageInclusionStatus.INCLUDED
    }
    content = get_blob_store().read_bytes(source.storage_key)
    if hashlib.sha256(content).hexdigest() != SOURCE_SHA256:
        raise ValueError("Stored original hash mismatch")
    extractions = NativePdfExtractor().extract(content, included_pages=included_pages)
    nodes = parse_constitution_pages(
        [
            ParserPage(page.page_number, normalize_page_text(page.text).text)
            for page in extractions
        ],
        instrument.slug,
    )
    by_path = {node.canonical_path: node for node in nodes}
    by_id = {candidate.id: candidate for candidate in candidates}
    originals = {
        (page.page_number, span.reading_order): span
        for page in extractions
        for span in page.spans
    }
    if set(by_path) != {candidate.canonical_path for candidate in candidates}:
        raise ValueError("Replayed structure differs from the candidate set")
    for candidate in candidates:
        node = by_path[candidate.canonical_path]
        parent = by_id.get(candidate.parent_candidate_id)
        if (
            compact_text(node.text or "")[0]
            != compact_text(candidate.raw_text or "")[0]
            or node.number != candidate.number
            or node.kind != candidate.kind
            or node.heading != candidate.heading
            or node.parent_path != (parent.canonical_path if parent else None)
        ):
            raise ValueError(f"Replayed candidate mismatch: {candidate.canonical_path}")
        spans = candidate.source_spans or []
        if (
            candidate.raw_text
            and compact_text(candidate.raw_text)[0]
            != compact_text("\n".join(str(span.get("text") or "") for span in spans))[0]
        ):
            raise ValueError(f"Span mismatch: {candidate.canonical_path}")
        for span in spans:
            original = originals.get(
                (span.get("page_number"), span.get("reading_order"))
            )
            if original is None or original.bbox != span.get("bbox"):
                raise ValueError(
                    f"Coordinate replay failed: {candidate.canonical_path}"
                )
            original_text = span.get("original_span_text", span.get("text"))
            start = span.get("source_text_start", 0)
            end = span.get("source_text_end", len(original.text))
            if original.text != original_text or original.text[start:end] != span.get(
                "text"
            ):
                raise ValueError(
                    f"Original span replay failed: {candidate.canonical_path}"
                )

    issues = list(
        session.exec(
            select(ReviewIssue)
            .join(
                ExtractionCandidate, ExtractionCandidate.id == ReviewIssue.candidate_id
            )
            .where(ExtractionCandidate.run_id == run.id)
        ).all()
    )
    for issue in issues:
        path = by_id[issue.candidate_id].canonical_path
        if (
            issue.issue_type == "unbalanced_punctuation"
            and path in KNOWN_PUNCTUATION_PATHS
        ):
            continue
        if issue.issue_type == "low_parser_confidence":
            continue
        if issue.issue_type == "graph_numbering_gap" and issue.evidence == {
            "current_number": "169",
            "previous_number": "167",
        }:
            continue
        raise ValueError(f"Unclassified finding requires review: {issue.id}")
    benchmark = json.loads(args.benchmark.read_text())
    query_rows = []
    for index, query in enumerate(benchmark["queries"], start=1):
        matches = [
            candidate.canonical_path
            for candidate in candidates
            if (
                candidate.canonical_path == query.get("path")
                if query.get("path")
                else candidate.kind == "section"
                and candidate.number == query["section"]
            )
        ]
        if len(matches) != 1:
            raise ValueError(f"Benchmark identity is ambiguous: {query}")
        query_rows.append(
            {
                "item_key": f"q{index:03}",
                "query_text": query["query"],
                "expected_canonical_paths": matches,
            }
        )
    endpoint = settings.HUGGINGFACE_TEI_ENDPOINT_URL
    if not endpoint or "/pipeline/feature-extraction" not in endpoint:
        raise ValueError(
            "Review requires the configured Hugging Face feature-extraction endpoint"
        )
    evidence = {
        "source_sha256": SOURCE_SHA256,
        "source_replay": "Original PDF hash, candidate structure/text and original coordinate spans reproduced",
        "edition": "Historical/source Constitution compilation (LFN 2004)",
        "known_exceptions": "Printed duplicate 189; missing 168; punctuation retained on PDF pages 44, 87, 124 and 138",
        "substantive_wording": "Preserved as printed, including source typographical anomalies",
        "authorization": "User authorized source-preserving exceptions and automated source-matching approval on 2026-10-05",
        "appendices": "Retained in original; parser stops at separate rules on page 172",
        "model_revision": MODEL_REVISION,
        "provider_revision_pinned": False,
    }
    report = {
        "run_id": str(run.id),
        "candidate_count": len(candidates),
        "coordinate_replay_passed": True,
        "issue_count": len(issues),
        "benchmark_query_count": len(query_rows),
        "evidence": evidence,
        "applied": args.apply,
    }
    if not args.apply:
        return report

    blob = get_blob_store().put_artifact(
        run_id=str(run.id),
        artifact_type=IngestionArtifactType.VALIDATION_REPORT.value,
        filename="historical-source-review-v1.json",
        content=json.dumps(report, sort_keys=True).encode(),
        content_type="application/json",
    )
    existing_artifact = session.exec(
        select(IngestionArtifact).where(
            IngestionArtifact.run_id == run.id,
            IngestionArtifact.storage_key == blob.key,
        )
    ).first()
    if not existing_artifact:
        session.add(
            IngestionArtifact(
                run_id=run.id,
                artifact_type=IngestionArtifactType.VALIDATION_REPORT,
                storage_key=blob.key,
                sha256=blob.sha256,
                mime_type="application/json",
                artifact_metadata=evidence,
            )
        )
    dataset = session.exec(
        select(EvaluationDataset).where(
            EvaluationDataset.version == benchmark["version"]
        )
    ).first()
    if not dataset:
        dataset = EvaluationDataset(
            version=benchmark["version"],
            name="Constitution source-edition retrieval benchmark",
            dataset_kind=EvaluationDatasetKind.RETRIEVAL_BENCHMARK,
            source_document_id=source.id,
            instrument_slug=instrument.slug,
            description=benchmark["description"],
            content_sha256=hashlib.sha256(
                json.dumps(query_rows, sort_keys=True).encode()
            ).hexdigest(),
        )
        session.add(dataset)
        session.flush()
        for row in query_rows:
            session.add(
                EvaluationItem(
                    dataset_id=dataset.id,
                    item_kind=EvaluationItemKind.RETRIEVAL_QUERY,
                    **row,
                )
            )
    profile_name = "bge-m3-constitution-source-edition-v1"
    profile = session.exec(
        select(EmbeddingProfile).where(EmbeddingProfile.name == profile_name)
    ).first()
    if not profile:
        session.add(
            EmbeddingProfile(
                name=profile_name,
                provider=EmbeddingProviderKind.HUGGINGFACE_TEI,
                model_name="BAAI/bge-m3",
                model_revision=MODEL_REVISION,
                vector_dimensions=1024,
                configuration={
                    "batch_size": 16,
                    "benchmark_dataset_version": dataset.version,
                    "provider_revision_pinned": False,
                },
            )
        )
    run.pipeline_config = {
        **run.pipeline_config,
        "corpus_legal_status": LegalStatus.HISTORICAL.value,
        "auto_start_embedding": True,
        "source_edition_review": evidence,
    }
    session.add(run)
    session.add(
        AuditEvent(
            actor_user_id=reviewer.id,
            action="ingestion.historical_source_review",
            entity_type="ingestion_run",
            entity_id=run.id,
            reason=evidence["authorization"],
            payload=evidence,
        )
    )
    session.commit()
    for issue in issues:
        if issue.status != ReviewIssueStatus.OPEN:
            continue
        candidate = by_id[issue.candidate_id]
        is_exception = issue.issue_type != "low_parser_confidence"
        reason = (
            "Verified source defect accepted for this historical edition; original wording and printed numbers preserved."
            if is_exception
            else "Short provision received heuristic confidence 0.78; original PDF structure, text, parent and coordinate spans replayed exactly."
        )
        update_review_issue(
            session,
            issue.id,
            ReviewIssueUpdate(
                idempotency_key=f"historical-source-review-v1:{issue.id}",
                expected_version=candidate.lock_version,
                reason=reason,
                evidence={
                    **evidence,
                    "canonical_path": candidate.canonical_path,
                    "source_pages": [
                        candidate.source_page_start,
                        candidate.source_page_end,
                    ],
                },
                superuser_override_reason=reason if issue.blocking else None,
            ),
            reviewer,
        )
    if source.verification_status != VerificationStatus.VERIFIED:
        verify_source_document(
            session,
            source.id,
            expected_version=source.lock_version,
            idempotency_key=f"historical-source-verify-v1:{source.id}",
            reason="Original PDF hash and extraction replay verified for the uploaded historical edition; known source defects retained. This is not current consolidated-law certification.",
            current_user=reviewer,
        )
    for index, candidate in enumerate(candidates, start=1):
        if candidate.status in {
            ExtractionCandidateStatus.APPROVED,
            ExtractionCandidateStatus.MATERIALIZED,
        }:
            continue
        decide_review_candidate(
            session,
            candidate.id,
            ReviewDecisionCreate(
                idempotency_key=f"historical-source-approve-v1:{candidate.id}",
                expected_version=candidate.lock_version,
                decision=ReviewDecisionType.APPROVE,
                reason="Authorized automated historical-source review: candidate structure, text and PDF coordinates replayed exactly; known source exceptions retained in run audit.",
            ),
            reviewer,
        )
        if index % 250 == 0:
            print(f"Approved {index}/{len(candidates)}", flush=True)  # noqa: T201
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", type=uuid.UUID, required=True)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    arguments = parser.parse_args()
    with Session(engine) as db:
        print(json.dumps(review(db, arguments), indent=2))  # noqa: T201
