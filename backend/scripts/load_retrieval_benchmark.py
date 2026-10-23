"""Load a reviewed retrieval benchmark file as an evaluation dataset.

Defaults to a dry run. Each query names its expected provision by `path` or by
`section` number, resolved against the materialized provisions of one legal
instrument. An existing dataset version is never changed: loading it again is
accepted only when its stored content hash matches.
"""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from sqlmodel import Session, col, select

from app.core.db import engine
from app.legal.enums import (
    EvaluationDatasetKind,
    EvaluationItemKind,
    ProvisionKind,
    VerificationStatus,
)
from app.legal.models import (
    EvaluationDataset,
    EvaluationItem,
    LegalInstrument,
    Provision,
    SourceDocument,
)


def query_rows(
    session: Session, instrument: LegalInstrument, queries: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    provisions = session.exec(
        select(Provision).where(Provision.instrument_id == instrument.id)
    ).all()
    paths = {provision.canonical_path for provision in provisions}
    rows = []
    for index, query in enumerate(queries, start=1):
        if query.get("path"):
            matches = [query["path"]] if query["path"] in paths else []
        else:
            matches = [
                provision.canonical_path
                for provision in provisions
                if provision.kind == ProvisionKind.SECTION
                and provision.number == query["section"]
            ]
        if len(matches) != 1:
            raise ValueError(f"Benchmark identity is missing or ambiguous: {query}")
        rows.append(
            {
                "item_key": f"q{index:03}",
                "query_text": query["query"],
                "expected_canonical_paths": matches,
            }
        )
    return rows


def load(session: Session, args: argparse.Namespace) -> dict[str, Any]:
    benchmark = json.loads(args.benchmark.read_text())
    slug = args.instrument or benchmark.get("instrument_slug")
    instrument = session.exec(
        select(LegalInstrument).where(LegalInstrument.slug == slug)
    ).one()
    rows = query_rows(session, instrument, benchmark["queries"])
    content_sha256 = hashlib.sha256(
        json.dumps(rows, sort_keys=True).encode()
    ).hexdigest()
    report: dict[str, Any] = {
        "version": benchmark["version"],
        "instrument_slug": instrument.slug,
        "query_count": len(rows),
        "content_sha256": content_sha256,
        "applied": False,
    }
    existing = session.exec(
        select(EvaluationDataset).where(
            EvaluationDataset.version == benchmark["version"]
        )
    ).first()
    if existing:
        if existing.content_sha256 != content_sha256:
            raise ValueError(
                f"Dataset {existing.version} already exists with different content"
            )
        report["already_loaded"] = True
        return report
    if not args.apply:
        return report
    # Record the verified source the benchmark was written against, when unique.
    sources = session.exec(
        select(SourceDocument).where(
            SourceDocument.legal_instrument_id == instrument.id,
            col(SourceDocument.verification_status) == VerificationStatus.VERIFIED,
        )
    ).all()
    dataset = EvaluationDataset(
        version=benchmark["version"],
        name=args.name
        or benchmark.get("name")
        or f"{instrument.title} retrieval benchmark",
        dataset_kind=EvaluationDatasetKind.RETRIEVAL_BENCHMARK,
        source_document_id=sources[0].id if len(sources) == 1 else None,
        instrument_slug=instrument.slug,
        description=benchmark["description"],
        content_sha256=content_sha256,
    )
    session.add(dataset)
    session.flush()
    for row in rows:
        session.add(
            EvaluationItem(
                dataset_id=dataset.id,
                item_kind=EvaluationItemKind.RETRIEVAL_QUERY,
                **row,
            )
        )
    session.commit()
    report["applied"] = True
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--instrument", help="Defaults to the file's instrument_slug")
    parser.add_argument("--name", help="Dataset name; defaults to the file or title")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with Session(engine) as session:
        print(json.dumps(load(session, args), indent=2, sort_keys=True))  # noqa: T201


if __name__ == "__main__":
    main()
