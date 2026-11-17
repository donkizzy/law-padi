import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app import crud
from app.core.config import settings
from app.core.db import engine
from app.core.errors import DomainError, ErrorCode
from app.ingestion.admin.pages import update_page_selection
from app.legal.enums import (
    IngestionRunStatus,
    IngestionStage,
    IngestionStepStatus,
    IngestionTaskStatus,
    PageInclusionStatus,
    PageRole,
)
from app.legal.models import (
    IngestionEvent,
    IngestionStep,
    IngestionTask,
    SourcePage,
)
from app.legal.schemas import PageSelectionUpdate
from app.models import User
from tests.api.routes.admin.conftest import _source_and_run


def test_page_selection_records_admin_confirmation(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    source, run = _source_and_run(db)
    pages = [
        SourcePage(
            run_id=run.id,
            source_document_id=source.id,
            page_number=1,
            role=PageRole.FRONT_MATTER,
            inclusion_status=PageInclusionStatus.SUGGESTED_EXCLUDE,
            inclusion_reason="cover page",
        ),
        SourcePage(
            run_id=run.id,
            source_document_id=source.id,
            page_number=2,
            role=PageRole.LEGAL_BODY,
            inclusion_status=PageInclusionStatus.SUGGESTED_INCLUDE,
        ),
    ]
    db.add_all(pages)
    run.status = IngestionRunStatus.WAITING_FOR_INPUT
    run.current_stage = IngestionStage.AWAITING_PAGE_CONFIRMATION
    db.add(run)
    db.commit()
    for page_item in pages:
        db.refresh(page_item)

    selection_body = {
        "idempotency_key": f"pages-{uuid.uuid4().hex}",
        "expected_run_version": run.lock_version,
        "pages": [
            {
                "page_number": 1,
                "inclusion_status": PageInclusionStatus.EXCLUDED,
                "inclusion_reason": "front matter excluded",
                "expected_version": pages[0].lock_version,
            },
            {
                "page_number": 2,
                "inclusion_status": PageInclusionStatus.INCLUDED,
                "inclusion_reason": "legal body",
                "expected_version": pages[1].lock_version,
            },
        ],
    }
    response = client.patch(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/page-selection",
        headers=superuser_token_headers,
        json=selection_body,
    )

    assert response.status_code == 200
    assert [page["inclusion_status"] for page in response.json()["data"]] == [
        PageInclusionStatus.EXCLUDED,
        PageInclusionStatus.INCLUDED,
    ]
    db.refresh(run)
    assert run.status == IngestionRunStatus.RUNNING
    assert run.current_stage == IngestionStage.NATIVE_EXTRACTION
    native_task = db.exec(
        select(IngestionTask).where(
            IngestionTask.run_id == run.id,
            IngestionTask.task_type == IngestionStage.NATIVE_EXTRACTION.value,
        )
    ).one()
    assert native_task.status == IngestionTaskStatus.PENDING
    repeated_response = client.patch(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/page-selection",
        headers=superuser_token_headers,
        json=selection_body,
    )
    assert repeated_response.status_code == 200
    assert [page["inclusion_status"] for page in repeated_response.json()["data"]] == [
        PageInclusionStatus.EXCLUDED,
        PageInclusionStatus.INCLUDED,
    ]
    assert (
        db.exec(
            select(func.count())
            .select_from(IngestionTask)
            .where(
                IngestionTask.run_id == run.id,
                IngestionTask.task_type == IngestionStage.NATIVE_EXTRACTION.value,
            )
        ).one()
        == 1
    )
    event = db.exec(
        select(IngestionEvent)
        .where(IngestionEvent.run_id == run.id)
        .order_by(IngestionEvent.sequence.desc())
    ).first()
    assert event
    assert event.event_type == "page_selection_confirmed"


def test_concurrent_page_selection_has_one_winner_and_one_conflict(
    db: Session,
) -> None:
    source, run = _source_and_run(db)
    pages = [
        SourcePage(
            run_id=run.id,
            source_document_id=source.id,
            page_number=1,
            role=PageRole.LEGAL_BODY,
            inclusion_status=PageInclusionStatus.SUGGESTED_INCLUDE,
        ),
        SourcePage(
            run_id=run.id,
            source_document_id=source.id,
            page_number=2,
            role=PageRole.LEGAL_BODY,
            inclusion_status=PageInclusionStatus.SUGGESTED_INCLUDE,
        ),
    ]
    db.add_all(pages)
    db.commit()
    for page in pages:
        db.refresh(page)
    expected_run_version = run.lock_version
    expected_page_versions = {page.page_number: page.lock_version for page in pages}
    admin = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    assert admin
    barrier = threading.Barrier(2)

    def confirm_once(index: int) -> int:
        with Session(engine) as concurrent_session:
            current_user = concurrent_session.get(User, admin.id)
            assert current_user
            body = PageSelectionUpdate(
                idempotency_key=f"concurrent-pages-{index}-{uuid.uuid4().hex}",
                expected_run_version=expected_run_version,
                pages=[
                    {
                        "page_number": page_number,
                        "inclusion_status": PageInclusionStatus.INCLUDED,
                        "inclusion_reason": "Concurrent confirmation test",
                        "expected_version": expected_page_versions[page_number],
                    }
                    for page_number in sorted(expected_page_versions)
                ],
            )
            barrier.wait()
            try:
                update_page_selection(concurrent_session, run.id, body, current_user)
            except DomainError as exc:
                concurrent_session.rollback()
                assert exc.code == ErrorCode.CONFLICT
                return 409
            return 200

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(confirm_once, range(2)))

    assert sorted(statuses) == [200, 409]
    db.expire_all()
    db.refresh(run)
    assert run.current_stage == IngestionStage.NATIVE_EXTRACTION
    assert (
        db.exec(
            select(func.count())
            .select_from(IngestionTask)
            .where(
                IngestionTask.run_id == run.id,
                IngestionTask.task_type == IngestionStage.NATIVE_EXTRACTION.value,
            )
        ).one()
        == 1
    )


def test_resume_cancelled_page_confirmation_reopens_admin_gate(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    source, run = _source_and_run(db)
    page = SourcePage(
        run_id=run.id,
        source_document_id=source.id,
        page_number=1,
        role=PageRole.LEGAL_BODY,
        inclusion_status=PageInclusionStatus.SUGGESTED_INCLUDE,
        inclusion_reason="Suggested legal body page",
    )
    db.add(page)
    db.commit()
    db.refresh(run)
    db.refresh(page)
    awaiting_step = db.exec(
        select(IngestionStep).where(
            IngestionStep.run_id == run.id,
            IngestionStep.stage == IngestionStage.AWAITING_PAGE_CONFIRMATION,
        )
    ).one()

    cancel_response = client.post(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/cancel",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"cancel-{uuid.uuid4().hex}",
            "expected_version": run.lock_version,
            "reason": "Operator cancelled run",
        },
    )
    assert cancel_response.status_code == 200
    db.refresh(run)
    db.refresh(awaiting_step)
    assert run.status == IngestionRunStatus.CANCELLED
    assert awaiting_step.status == IngestionStepStatus.CANCELLED

    resume_response = client.post(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/resume",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"resume-{uuid.uuid4().hex}",
            "expected_version": run.lock_version,
        },
    )
    assert resume_response.status_code == 200
    db.refresh(run)
    db.refresh(awaiting_step)
    assert run.status == IngestionRunStatus.WAITING_FOR_INPUT
    assert run.current_stage == IngestionStage.AWAITING_PAGE_CONFIRMATION
    assert run.error_details is None
    assert run.completed_at is None
    assert awaiting_step.status == IngestionStepStatus.BLOCKED
    assert awaiting_step.completed_at is None
    assert not db.exec(
        select(IngestionTask).where(
            IngestionTask.run_id == run.id,
            IngestionTask.task_type == IngestionStage.AWAITING_PAGE_CONFIRMATION.value,
        )
    ).first()

    page_selection_response = client.patch(
        f"{settings.API_V1_STR}/admin/ingestion-runs/{run.id}/page-selection",
        headers=superuser_token_headers,
        json={
            "idempotency_key": f"pages-{uuid.uuid4().hex}",
            "expected_run_version": run.lock_version,
            "pages": [
                {
                    "page_number": page.page_number,
                    "inclusion_status": PageInclusionStatus.INCLUDED,
                    "inclusion_reason": "Confirmed legal body page",
                    "expected_version": page.lock_version,
                }
            ],
        },
    )
    assert page_selection_response.status_code == 200
