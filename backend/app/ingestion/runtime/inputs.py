from typing import Any

from sqlmodel import Session, col, select

from app.ingestion.common import enum_value
from app.legal.enums import IngestionStage
from app.legal.models import IngestionRun, IngestionTask

PIPELINE_IDENTITIES = ("release_id", "embedding_run_id", "retrieval_index_build_id")


def retain_pipeline_inputs(
    session: Session, run: IngestionRun, inputs: dict[str, Any]
) -> None:
    retained = {key: inputs[key] for key in PIPELINE_IDENTITIES if inputs.get(key)}
    if retained:
        run.pipeline_config = {**(run.pipeline_config or {}), **retained}
        session.add(run)


def task_input(session: Session, task: IngestionTask, key: str) -> Any:
    run = session.get(IngestionRun, task.run_id)
    return ((run.pipeline_config or {}).get(key) if run else None) or task.payload.get(
        key
    )


def recovery_payload(
    session: Session, run: IngestionRun, stage: IngestionStage
) -> dict[str, Any]:
    # Merge partial control-task payloads instead of letting a recent resume
    # hide inputs from the original task. This also recovers older runs that
    # predate retained run-level identities.
    payload: dict[str, Any] = {}
    for previous in session.exec(
        select(IngestionTask.payload)
        .where(
            IngestionTask.run_id == run.id, IngestionTask.task_type == enum_value(stage)
        )
        .order_by(col(IngestionTask.created_at), col(IngestionTask.id))
    ).all():
        payload.update(
            {
                key: value
                for key, value in (previous or {}).items()
                if key not in {"retry", "resume"} and value is not None
            }
        )
    config = run.pipeline_config or {}
    payload.update(config.get("stage_inputs", {}).get(enum_value(stage), {}))
    payload.update({key: config[key] for key in PIPELINE_IDENTITIES if config.get(key)})
    if run.source_document_id:
        payload.setdefault("source_document_id", str(run.source_document_id))
    if run.source_upload_id:
        payload.setdefault("source_upload_id", str(run.source_upload_id))
    retain_pipeline_inputs(session, run, payload)
    return payload
