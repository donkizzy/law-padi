from collections import Counter
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.legal.enums import MessageRole
from app.legal.models import Conversation, ConversationMessage, GenerationRun
from app.main import app


def _finished_run(
    db: Session,
    outcome: str,
    validation_result: dict[str, Any] | None = None,
    *,
    with_answer: bool = True,
) -> None:
    conversation = Conversation(anonymous_session_id=uuid4().hex)
    db.add(conversation)
    db.flush()
    question = ConversationMessage(
        conversation_id=conversation.id, role=MessageRole.USER, content="Section 37"
    )
    db.add(question)
    db.flush()
    answer = ConversationMessage(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content="",
        validation_result=validation_result,
    )
    if with_answer:
        db.add(answer)
        db.flush()
    db.add(
        GenerationRun(
            conversation_id=conversation.id,
            user_message_id=question.id,
            assistant_message_id=answer.id if with_answer else None,
            idempotency_key=uuid4().hex,
            status="failed",
            outcome=outcome,
        )
    )
    db.commit()


def _metrics(headers: dict[str, str]) -> dict[str, Any]:
    with TestClient(app) as client:
        response = client.get("/api/v1/conversations/metrics", headers=headers)
    assert response.status_code == 200
    return response.json()


def test_internal_errors_are_counted_apart_from_provider_failures(
    db: Session, superuser_token_headers: dict[str, str]
) -> None:
    before = _metrics(superuser_token_headers)

    _finished_run(db, "provider_failure", {"failure_stage": "internal"})
    _finished_run(db, "provider_failure", {"failure_stage": "internal"})
    _finished_run(db, "provider_failure", {"failure_stage": "interrupted"})
    _finished_run(db, "provider_failure", with_answer=False)
    _finished_run(db, "completed", {"supported": True})
    # Only a provider failure can be an internal error.
    _finished_run(db, "validation_failed", {"failure_stage": "internal"})

    after = _metrics(superuser_token_headers)
    added = Counter(after["outcomes"]) - Counter(before["outcomes"])

    assert added == Counter(
        {
            "internal_error": 2,
            "provider_failure": 2,
            "completed": 1,
            "validation_failed": 1,
        }
    )
    assert after["accepted_questions"] - before["accepted_questions"] == 6
    assert after["finished_answers"] - before["finished_answers"] == 6
    assert after["explained_answers"] - before["explained_answers"] == 1
