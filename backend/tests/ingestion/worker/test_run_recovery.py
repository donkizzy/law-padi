import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.ingestion.embedding import EmbeddingBatch
from app.ingestion.runtime.queue import enqueue_task
from app.ingestion.runtime.runner import run_once, run_until_idle
from app.legal.enums import IngestionRunStatus, IngestionStage, IngestionTaskStatus
from app.legal.models import IngestionTask
from tests.ingestion.worker.conftest import _release_with_retrieval_documents


@pytest.mark.parametrize(
    "stage",
    [
        IngestionStage.BUILDING_RETRIEVAL_DOCUMENTS,
        IngestionStage.EMBEDDING,
        IngestionStage.INDEXING,
        IngestionStage.VALIDATING_INDEX,
        IngestionStage.PUBLISHING,
    ],
)
def test_cancel_and_resume_release_pipeline_through_api(
    db: Session,
    client: TestClient,
    superuser_token_headers: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: IngestionStage,
) -> None:
    monkeypatch.setattr(settings, "INGESTION_STORAGE_DIR", str(tmp_path))
    _source, run, release, _profile = _release_with_retrieval_documents(
        db, tmp_path=tmp_path
    )

    class Provider:
        def embed(self, texts: list[str]) -> EmbeddingBatch:
            return EmbeddingBatch(
                provider="test",
                model_name="test",
                model_revision="pinned",
                vectors=[[1.0] + [0.0] * 1023 for _ in texts],
            )

    monkeypatch.setattr(
        "app.ingestion.stages.embedding.embedding_provider_for_profile",
        lambda _profile: Provider(),
    )
    run.status = IngestionRunStatus.QUEUED
    run.current_stage = IngestionStage.BUILDING_RETRIEVAL_DOCUMENTS
    run.pipeline_config = {**run.pipeline_config, "auto_start_embedding": True}
    db.add(run)
    db.commit()
    enqueue_task(
        db,
        run=run,
        step=None,
        task_type=IngestionStage.BUILDING_RETRIEVAL_DOCUMENTS.value,
        idempotency_key=f"{run.id}:initial",
        payload={"release_id": str(release.id)},
    )
    for _ in range(5):
        db.refresh(run)
        if run.current_stage == stage:
            break
        result = run_once(db, worker_id="recovery-worker")
        assert (
            result is not None and result.task_status == IngestionTaskStatus.SUCCEEDED
        )
    assert run.current_stage == stage
    base = f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}"
    cancelled = client.post(
        base + "/cancel",
        headers=superuser_token_headers,
        json={
            "expected_version": run.lock_version,
            "idempotency_key": uuid.uuid4().hex,
            "reason": "Restart worker",
        },
    )
    assert cancelled.status_code == 200
    db.refresh(run)
    resumed = client.post(
        base + "/resume",
        headers=superuser_token_headers,
        json={
            "expected_version": run.lock_version,
            "idempotency_key": uuid.uuid4().hex,
        },
    )
    assert resumed.status_code == 200
    if stage in {
        IngestionStage.EMBEDDING,
        IngestionStage.INDEXING,
        IngestionStage.VALIDATING_INDEX,
    }:
        # Retained run identities are sufficient even if the control task's
        # payload is absent.
        for task in db.exec(
            select(IngestionTask).where(
                IngestionTask.run_id == run.id,
                IngestionTask.status == IngestionTaskStatus.PENDING,
            )
        ).all():
            task.payload = {}
            db.add(task)
        db.commit()
    results = run_until_idle(db, worker_id="recovery-worker", max_tasks=8)
    assert all(
        result.task_status == IngestionTaskStatus.SUCCEEDED for result in results
    )
    db.refresh(run)
    assert run.status == IngestionRunStatus.READY_TO_PUBLISH
    assert run.pipeline_config["release_id"] == str(release.id)
    assert run.pipeline_config["embedding_run_id"]
    assert run.pipeline_config["retrieval_index_build_id"]
    assert not db.exec(
        select(IngestionTask).where(
            IngestionTask.run_id == run.id,
            IngestionTask.status == IngestionTaskStatus.PENDING,
        )
    ).all()
