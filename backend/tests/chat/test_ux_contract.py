from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.legal.enums import MessageRole
from app.legal.models import ConversationMessage, MessageFeedback
from app.main import app

pytest_plugins = ["tests.api.routes.test_legal_search"]


@pytest.mark.parametrize(
    ("chat", "generation", "kill", "enabled"),
    [
        (False, True, False, False),
        (True, False, False, False),
        (True, True, True, False),
        (True, True, False, True),
    ],
)
def test_capabilities_are_available_when_history_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
    chat: bool,
    generation: bool,
    kill: bool,
    enabled: bool,
) -> None:
    monkeypatch.setattr(settings, "CHAT_ENABLED", chat)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", generation)
    monkeypatch.setattr(settings, "CHAT_GENERATION_KILL_SWITCH", kill)
    with TestClient(app) as client:
        response = client.get("/api/v1/conversations/capabilities")
    assert response.status_code == 200
    assert response.json()["conversations_enabled"] == chat
    assert response.json()["explanations_enabled"] == enabled
    assert response.json()["supported_languages"] == ["English"]
    assert response.json()["question_max_length"] == 2000
    assert "key" not in response.json()


def test_history_search_is_owner_scoped_and_escapes_wildcards(
    corpus, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert corpus
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    with TestClient(app) as owner, TestClient(app) as stranger:
        owner.post("/api/v1/conversations", json={"title": "Privacy 100%"})
        owner.post("/api/v1/conversations", json={"title": "Right to life"})
        stranger.post(
            "/api/v1/conversations", json={"title": "Private privacy question"}
        )
        result = owner.get("/api/v1/conversations", params={"q": "%"}).json()
        assert result["count"] == 1
        assert result["data"][0]["title"] == "Privacy 100%"
        result = owner.get("/api/v1/conversations", params={"q": "privacy"}).json()
        assert result["count"] == 1
        assert result["data"][0]["title"] == "Privacy 100%"


def test_feedback_is_durable_owner_scoped_and_does_not_change_validation(
    corpus, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert corpus
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    with TestClient(app) as owner, TestClient(app) as stranger:
        conversation = owner.post("/api/v1/conversations", json={}).json()
        message = ConversationMessage(
            conversation_id=UUID(conversation["id"]),
            role=MessageRole.ASSISTANT,
            content="",
            answer_content={"outcome": "completed"},
            validation_result={"supported": True},
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        endpoint = (
            f"/api/v1/conversations/{conversation['id']}/messages/{message.id}/feedback"
        )
        assert stranger.post(endpoint, json={"helpful": False}).status_code == 404
        response = owner.post(endpoint, json={"helpful": True})
        assert response.status_code == 200
        assert response.json()["helpful"] is True
        assert owner.post(endpoint, json={"helpful": False}).json()["helpful"] is False
        detail = owner.get(f"/api/v1/conversations/{conversation['id']}").json()
        assert detail["messages"][0]["helpful"] is False
        db.expire_all()
        assert db.get(MessageFeedback, message.id) is not None
        stored = db.get(ConversationMessage, message.id)
        assert stored is not None and stored.validation_result == {"supported": True}
        assert owner.get("/api/v1/conversations/metrics").status_code == 401


def test_quality_metrics_are_admin_only_and_contain_no_question_text(
    superuser_token_headers: dict[str, str],
) -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/conversations/metrics", headers=superuser_token_headers
        )
    assert response.status_code == 200
    metrics = response.json()
    assert metrics["window_hours"] == 24
    assert metrics["accepted_questions"] >= metrics["finished_answers"]
    assert set(metrics) == {
        "window_hours",
        "accepted_questions",
        "finished_answers",
        "explained_answers",
        "average_finish_ms",
        "outcomes",
        "helpful_ratings",
        "unhelpful_ratings",
    }
