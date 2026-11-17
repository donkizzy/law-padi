from dataclasses import replace

from sqlmodel import Session, col, select

from app.core.config import settings
from app.ingestion.common import enum_value
from app.ingestion.embedding import (
    DenseEmbeddingProvider,
    shared_embedding_provider,
)
from app.ingestion.evaluation import (
    BENCHMARK_VERSION_SEPARATOR,
    RetrievalEvaluationQuery,
    active_evaluation_item_count,
    active_retrieval_benchmark,
    active_retrieval_benchmark_versions,
    load_retrieval_evaluation_queries,
)
from app.ingestion.runtime.errors import IngestionWorkerError
from app.legal.enums import (
    EmbeddingProviderKind,
    EmbeddingRunStatus,
    EvaluationDatasetKind,
    EvaluationItemKind,
)
from app.legal.models import (
    RECORDED_BENCHMARK_VERSIONS_MAX_LENGTH,
    CorpusRelease,
    EmbeddingProfile,
    EmbeddingRun,
    IngestionRun,
)
from app.legal.release_scope import release_instruments


def auto_start_embedding(run: IngestionRun) -> bool:
    return bool((run.pipeline_config or {}).get("auto_start_embedding"))


def active_embedding_profiles(session: Session) -> list[EmbeddingProfile]:
    return list(
        session.exec(
            select(EmbeddingProfile)
            .where(EmbeddingProfile.is_active == True)  # noqa: E712
            .order_by(col(EmbeddingProfile.created_at))
        ).all()
    )


def benchmark_dataset_for_embedding_profiles(
    session: Session, profiles: list[EmbeddingProfile], release: CorpusRelease
) -> tuple[str, list[RetrievalEvaluationQuery]]:
    profile_versions = [
        profile_string(profile, "benchmark_dataset_version") for profile in profiles
    ]
    if any(version is None for version in profile_versions):
        raise IngestionWorkerError(
            "Every active embedding profile must identify a benchmark dataset version"
        )
    versions = {str(version) for version in profile_versions}
    if len(versions) != 1:
        raise IngestionWorkerError(
            "Active embedding profiles must use the same benchmark dataset version"
        )
    pinned_version = next(iter(versions))
    dataset_versions = benchmark_versions_for_release(session, release, pinned_version)
    recorded = BENCHMARK_VERSION_SEPARATOR.join(dataset_versions)
    if len(recorded) > RECORDED_BENCHMARK_VERSIONS_MAX_LENGTH:
        raise IngestionWorkerError(
            f"Benchmark dataset versions are too long to record: {recorded}"
        )
    queries: list[RetrievalEvaluationQuery] = []
    for dataset_version in dataset_versions:
        query_count = active_evaluation_item_count(
            session,
            dataset_version,
            dataset_kind=EvaluationDatasetKind.RETRIEVAL_BENCHMARK,
            item_kind=EvaluationItemKind.RETRIEVAL_QUERY,
        )
        if query_count <= 0:
            raise IngestionWorkerError(
                f"Embedding benchmark dataset {dataset_version} is not active or has no retrieval queries"
            )
        loaded = load_retrieval_evaluation_queries(session, dataset_version)
        if len(loaded) != query_count:
            raise IngestionWorkerError(
                "Embedding benchmark query count changed during run"
            )
        if len(dataset_versions) > 1:
            # Item keys are only unique within a dataset.
            loaded = [
                replace(query, item_key=f"{dataset_version}/{query.item_key}")
                for query in loaded
            ]
        queries.extend(loaded)
    return recorded, queries


def benchmark_versions_for_release(
    session: Session, release: CorpusRelease, pinned_version: str
) -> list[str]:
    pinned = active_retrieval_benchmark(session, pinned_version)
    if pinned is None or pinned.instrument_slug is None:
        # A dataset not tied to one instrument benchmarks every release.
        return [pinned_version]
    # Each instrument in the release is graded by its own dataset: the profile's
    # pinned dataset for its instrument, otherwise the instrument's one active
    # retrieval benchmark. The profile stays unchanged, so its fingerprint and
    # vector reuse are unaffected when another instrument gains a benchmark.
    slugs = sorted(
        instrument.slug
        for instrument in release_instruments(session, release.id).values()
    )
    if not slugs:
        raise IngestionWorkerError("Release does not identify any legal instrument")
    dataset_versions: list[str] = []
    for slug in slugs:
        if slug == pinned.instrument_slug:
            dataset_versions.append(pinned_version)
            continue
        candidates = active_retrieval_benchmark_versions(session, slug)
        if len(candidates) != 1:
            raise IngestionWorkerError(
                f"Release instrument {slug} needs exactly one active retrieval "
                f"benchmark dataset; found {len(candidates)}"
            )
        dataset_versions.append(candidates[0])
    return dataset_versions


def embedding_run_for_profile(
    session: Session, release: CorpusRelease, profile: EmbeddingProfile
) -> EmbeddingRun:
    embedding_run = session.exec(
        select(EmbeddingRun).where(
            EmbeddingRun.release_id == release.id,
            EmbeddingRun.profile_id == profile.id,
        )
    ).first()
    if embedding_run:
        return embedding_run
    embedding_run = EmbeddingRun(
        release_id=release.id,
        profile_id=profile.id,
        status=EmbeddingRunStatus.PENDING,
    )
    session.add(embedding_run)
    session.flush()
    return embedding_run


def embedding_provider_for_profile(
    profile: EmbeddingProfile,
) -> DenseEmbeddingProvider:
    provider = enum_value(profile.provider)
    if provider not in {
        EmbeddingProviderKind.OPENAI.value,
        EmbeddingProviderKind.HUGGINGFACE_TEI.value,
    }:
        raise IngestionWorkerError(f"Unsupported embedding provider: {provider}")
    return shared_embedding_provider(
        profile_id=profile.id,
        provider=EmbeddingProviderKind(provider),
        api_key=settings.OPENAI_API_KEY,
        endpoint_url=settings.HUGGINGFACE_TEI_ENDPOINT_URL,
        api_token=settings.HUGGINGFACE_API_TOKEN,
        model_name=profile.model_name,
        model_revision=profile.model_revision,
        timeout_seconds=30
        if provider == EmbeddingProviderKind.OPENAI.value
        else profile_float(profile, "timeout_seconds") or 120,
    )


def profile_string(profile: EmbeddingProfile, key: str) -> str | None:
    value = (profile.configuration or {}).get(key)
    return value if isinstance(value, str) else None


def profile_float(profile: EmbeddingProfile, key: str) -> float | None:
    value = (profile.configuration or {}).get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def profile_int(profile: EmbeddingProfile, key: str, *, default: int) -> int:
    value = (profile.configuration or {}).get(key)
    if isinstance(value, bool):
        return default
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, float) and value > 0:
        return int(value)
    return default


def sum_optional_costs(*costs: float | None) -> float | None:
    present = [cost for cost in costs if cost is not None]
    if not present:
        return None
    return round(sum(present), 6)
