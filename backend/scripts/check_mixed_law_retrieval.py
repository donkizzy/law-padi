"""Compare Constitution retrieval with synthetic Act members in a disposable DB.

The configured database is read only. This command creates a uniquely named
*_test database, migrates it, copies the active Constitution index, measures a
baseline, adds synthetic Act provisions, measures again, then drops only that
new database. Query embeddings are requested once and replayed for comparison.
No real Act text, source approval or application publication is performed.
"""

import json
import os
import subprocess
import uuid
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.config import settings
from app.core.db import engine
from app.ingestion.embedding import EmbeddingBatch
from app.ingestion.pgvector_repository import (
    active_target,
    write_embeddings,
    write_segments,
)
from app.ingestion.retrieval import build_retrieval_documents
from app.legal.enums import (
    CorpusReleaseStatus,
    InstrumentType,
    LegalStatus,
    ProvisionKind,
)
from app.legal.models import (
    ActiveRetrievalTarget,
    CorpusRelease,
    CorpusReleaseEntry,
    EmbeddingProfile,
    EmbeddingRun,
    LegalInstrument,
    Provision,
    ProvisionVersion,
    RetrievalEmbedding,
    RetrievalIndexBuild,
    RetrievalSegment,
)
from app.legal.parser import legal_text_sha256
from app.legal.public_corpus import load_public_corpus
from app.legal.titles import catalogue_titles
from scripts import retrieval_benchmark as benchmark


def copy_row(row: SQLModel, **changes: Any) -> SQLModel:
    return type(row).model_validate(
        {**row.model_dump(exclude={"search_vector"}), **changes}
    )


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    datasets = [
        json.loads((root / "docs" / name).read_text())
        for name in (
            "plain-language-retrieval-benchmark-v1.json",
            "plain-language-retrieval-heldout-v1.json",
        )
    ]
    # All application reads, including the snapshot, use a read-only transaction.
    with Session(engine) as source:
        source.exec(text("SET TRANSACTION READ ONLY"))
        target = active_target(source)
        release = source.get(CorpusRelease, target.release_id)
        profile = source.get(EmbeddingProfile, target.profile_id)
        assert release and profile
        corpus = load_public_corpus(source, release)
        assert {law.slug for law in corpus.instruments.values()} == {
            "constitution-1999"
        }, "This regression harness expects a Constitution-only baseline"
        snapshot: list[list[SQLModel]] = [
            [copy_row(row) for row in corpus.instruments.values()],
            [
                copy_row(row, verified_by=None, created_by=None)
                for row in corpus.sources.values()
            ],
            [copy_row(release, status=CorpusReleaseStatus.BUILDING, approved_by=None)],
        ]
        by_depth: dict[int, list[SQLModel]] = {}
        for row in corpus.provisions.values():
            by_depth.setdefault(row.canonical_path.count("."), []).append(copy_row(row))
        snapshot.extend(by_depth[depth] for depth in sorted(by_depth))
        snapshot.extend(
            [
                [
                    copy_row(row, supersedes_id=None, created_by_amendment_id=None)
                    for row in corpus.versions.values()
                ],
                [
                    copy_row(row)
                    for row in source.exec(
                        select(CorpusReleaseEntry).where(
                            CorpusReleaseEntry.release_id == target.release_id
                        )
                    ).all()
                ],
                [copy_row(profile)],
                [copy_row(source.get(EmbeddingRun, target.embedding_run_id))],
                [
                    copy_row(row)
                    for row in source.exec(
                        select(RetrievalSegment).where(
                            RetrievalSegment.release_id == target.release_id
                        )
                    ).all()
                ],
                [
                    copy_row(row)
                    for row in source.exec(
                        select(RetrievalEmbedding).where(
                            RetrievalEmbedding.release_id == target.release_id,
                            RetrievalEmbedding.embedding_run_id
                            == target.embedding_run_id,
                        )
                    ).all()
                ],
                [
                    copy_row(
                        source.get(RetrievalIndexBuild, target.retrieval_index_build_id)
                    )
                ],
            ]
        )
        # Correlated synthetic vectors stress crowding around privacy/liberty,
        # without representing or embedding unverified statutory legal text.
        vectors = {
            slug: list(
                source.exec(
                    select(RetrievalEmbedding.embedding)
                    .join(
                        RetrievalSegment,
                        RetrievalEmbedding.segment_id == RetrievalSegment.id,
                    )
                    .where(
                        RetrievalSegment.release_id == target.release_id,
                        RetrievalSegment.canonical_path.endswith(f".section{number}"),
                        RetrievalEmbedding.embedding_run_id == target.embedding_run_id,
                    )
                ).first()
            )
            for slug, number in (("acja-2015", "37"), ("police-act-2020", "35"))
        }
        source_release = release.version
        profile_copy = EmbeddingProfile.model_validate(profile.model_dump())
        target_copy = ActiveRetrievalTarget.model_validate(target.model_dump())

    # Cache the same query vectors for both measurements; no live LLM calls.
    provider = benchmark.default_embedding_provider(profile_copy)
    query_vectors: dict[str, list[float]] = {}
    for dataset in datasets:
        queries = [case["query"] for case in dataset["cases"]]
        query_vectors.update(zip(queries, provider.embed(queries).vectors, strict=True))

    class ReplayProvider:
        def embed(self, texts: Sequence[str]) -> EmbeddingBatch:
            return EmbeddingBatch(
                provider="replay",
                model_name=profile_copy.model_name,
                model_revision=profile_copy.model_revision,
                vectors=[query_vectors[value] for value in texts],
            )

    original_provider = benchmark.default_embedding_provider
    benchmark.default_embedding_provider = lambda _profile: ReplayProvider()
    configured_url = make_url(str(settings.DATABASE_URL))
    database = f"statute_review_{uuid.uuid4().hex}_test"
    assert database.endswith("_test") and database != configured_url.database
    temporary_url = configured_url.set(database=database)
    admin_dsn = (
        configured_url.set(database="postgres")
        .render_as_string(hide_password=False)
        .replace("postgresql+psycopg://", "postgresql://", 1)
    )
    temporary_engine = None
    created = False
    try:
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            connection.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database))
            )
        created = True
        env = {
            **os.environ,
            "DATABASE_URL": temporary_url.render_as_string(hide_password=False),
            "FASTAPI_ENV": "development",
        }
        migrated = subprocess.run(
            ["alembic", "upgrade", "head"],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if migrated.returncode:
            raise RuntimeError(
                "Disposable test database migration failed: " + migrated.stderr
            )
        temporary_engine = create_engine(temporary_url)
        with Session(temporary_engine) as session:
            for rows in snapshot:
                session.add_all(rows)
                session.flush()
            release = session.get(CorpusRelease, target_copy.release_id)
            release.status = CorpusReleaseStatus.PRODUCTION
            session.add(release)
            session.add(target_copy)
            session.commit()
            before = {
                dataset["version"]: benchmark.run_dataset(session, dataset["cases"])
                for dataset in datasets
            }
            release.status = CorpusReleaseStatus.BUILDING
            session.add(release)
            session.commit()
            run = session.get(EmbeddingRun, target_copy.embedding_run_id)
            profile = session.get(EmbeddingProfile, target_copy.profile_id)
            instruments, provisions, versions, entries = {}, {}, {}, []
            source_template = next(iter(corpus.sources.values()))
            for slug in ("acja-2015", "police-act-2020"):
                instrument = LegalInstrument(
                    slug=slug,
                    title=f"Synthetic {slug}",
                    short_title=slug,
                    instrument_type=InstrumentType.ACT,
                )
                session.add(instrument)
                session.flush()
                instruments[instrument.id] = instrument
                document = copy_row(
                    source_template,
                    id=uuid.uuid4(),
                    legal_instrument_id=instrument.id,
                    sha256=legal_text_sha256(slug),
                    title=f"Synthetic {slug}",
                    verified_by=None,
                    created_by=None,
                    verification_status="unverified",
                )
                session.add(document)
                session.flush()
                for number, title in catalogue_titles(slug, "sections").items():
                    provision = Provision(
                        instrument_id=instrument.id,
                        canonical_path=f"{slug}.section{number}",
                        number=number,
                        heading=title,
                        kind=ProvisionKind.SECTION,
                        sort_key=number.zfill(3),
                    )
                    session.add(provision)
                    session.flush()
                    wording = f"Synthetic fixture only: {title}."
                    version = ProvisionVersion(
                        provision_id=provision.id,
                        source_document_id=document.id,
                        text=wording,
                        normalized_text=wording.lower(),
                        text_sha256=legal_text_sha256(wording),
                        valid_from=date(2020, 1, 1),
                        legal_status=LegalStatus.HISTORICAL,
                    )
                    session.add(version)
                    session.flush()
                    entry = CorpusReleaseEntry(
                        release_id=release.id,
                        provision_version_id=version.id,
                        source_document_id=document.id,
                    )
                    session.add(entry)
                    entries.append(entry)
                    provisions[provision.id], versions[version.id] = provision, version
            session.flush()
            documents = build_retrieval_documents(
                release_version=release.version,
                entries=entries,
                versions_by_id=versions,
                provisions_by_id=provisions,
                instruments_by_id=instruments,
            )
            segments = write_segments(
                session, release_id=release.id, documents=documents
            )
            write_embeddings(
                session,
                release_id=release.id,
                embedding_run=run,
                profile=profile,
                segments=segments,
                vectors=[
                    vectors[row.canonical_path.partition(".")[0]] for row in segments
                ],
            )
            release.status = CorpusReleaseStatus.PRODUCTION
            session.add(release)
            session.commit()
            after = {
                dataset["version"]: benchmark.run_dataset(session, dataset["cases"])
                for dataset in datasets
            }
            comparison = {
                name: {
                    signal: {
                        metric: {
                            "before": value,
                            "after": after[name]["signals"][signal][metric],
                            "not_lower": after[name]["signals"][signal][metric]
                            >= value,
                        }
                        for metric, value in result["signals"][signal].items()
                    }
                    for signal in ("fused", "fallback")
                }
                for name, result in before.items()
            }
            no_drop = all(
                metric["not_lower"]
                for result in comparison.values()
                for signal in result.values()
                for metric in signal.values()
            )
            report = {
                "date": "2026-10-20",
                "source_release": source_release,
                "source_database_read_only": True,
                "temporary_database_suffix": "_test",
                "synthetic_act_sections": len(segments),
                "synthetic_vectors": "Copied Constitution privacy/liberty vectors to stress Act crowding; no real Act accuracy claim",
                "cases": sum(len(dataset["cases"]) for dataset in datasets),
                "no_fused_or_fallback_metric_drop": no_drop,
                "comparison": comparison,
                "before": before,
                "after": after,
            }
    finally:
        benchmark.default_embedding_provider = original_provider
        if temporary_engine:
            temporary_engine.dispose()
        if created:
            with psycopg.connect(admin_dsn, autocommit=True) as connection:
                connection.execute(
                    sql.SQL("DROP DATABASE {}").format(sql.Identifier(database))
                )
    report["temporary_database_removed"] = True
    print(json.dumps(report, indent=2))  # noqa: T201
    if not no_drop:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
