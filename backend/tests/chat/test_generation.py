import asyncio
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.chat import worker
from app.chat.provider import ProviderResult
from app.core.config import settings
from app.legal.models import ConversationMessage, GenerationRun, ProvisionVersion
from app.main import app

pytest_plugins = ["tests.api.routes.test_legal_search"]


class FakeProvider:
    def __init__(self, *, supported: bool = True, fabricated: bool = False):
        self.supported = supported
        self.fabricated = fabricated
        self.calls: list[str] = []
        self.payloads: list[dict[str, Any]] = []

    async def complete_json(
        self, *, system: str, payload: dict[str, Any], max_tokens: int
    ) -> ProviderResult:
        assert max_tokens > 0
        self.calls.append(system)
        self.payloads.append(payload)
        if "verdicts" in system:
            value = {
                "verdicts": [
                    {
                        "index": 0,
                        "supported": self.supported,
                        "qualifications_preserved": self.supported,
                    }
                ]
            }
        else:
            value = {
                "blocks": [
                    {
                        "text": "The stored wording protects privacy.",
                        "evidence_ids": ["E999" if self.fabricated else "E1"],
                    }
                ],
                "missing_facts": [],
            }
        return ProviderResult(
            value=value, prompt_tokens=100, completion_tokens=40, model="test"
        )


def test_review_worker_claims_only_the_requested_run(
    corpus, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert corpus
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    with TestClient(app) as client:
        run_ids: list[UUID] = []
        for index in range(2):
            conversation_id = client.post("/api/v1/conversations", json={}).json()["id"]
            accepted = client.post(
                f"/api/v1/conversations/{conversation_id}/messages",
                json={
                    "question": "Section 37",
                    "idempotency_key": f"review-{index}",
                },
            )
            assert accepted.status_code == 202
            run_ids.append(UUID(accepted.json()["run_id"]))
        assert worker._claim_run("review-worker", run_id=uuid4()) is None
        assert worker._claim_run("review-worker", run_id=run_ids[1]) == run_ids[1]
        db.expire_all()
        first = db.get(GenerationRun, run_ids[0])
        second = db.get(GenerationRun, run_ids[1])
        assert first is not None and first.status == "pending"
        assert second is not None and second.status == "running"


@pytest.mark.parametrize(
    ("question", "supported", "fabricated", "expected"),
    [
        ("Section 37", True, False, "completed"),
        ("Sections 37 and 168", True, False, "partial_evidence"),
        ("Section 37", False, False, "validation_failed"),
        ("Section 37", True, True, "validation_failed"),
    ],
)
def test_worker_only_persists_validated_explanations(
    corpus,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    question: str,
    supported: bool,
    fabricated: bool,
    expected: str,
) -> None:
    assert corpus
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    provider = FakeProvider(supported=supported, fabricated=fabricated)
    with TestClient(app) as client:
        conversation = client.post("/api/v1/conversations", json={}).json()
        accepted = client.post(
            f"/api/v1/conversations/{conversation['id']}/messages",
            json={"question": question, "idempotency_key": "one"},
        )
        assert accepted.status_code == 202
        run_id = UUID(accepted.json()["run_id"])
        assert worker._claim_run("test-worker") == run_id
        asyncio.run(worker.process_run(run_id, "test-worker", provider))  # type: ignore[arg-type]
        db.expire_all()
        run = db.get(GenerationRun, run_id)
        assert run is not None
        assert run.outcome == expected
        assistant = db.get(ConversationMessage, run.assistant_message_id)
        assert assistant is not None
        assert assistant.answer_content["outcome"] == expected
        assert assistant.validation_result is not None
        assert assistant.validation_result["retrieval_ms"] >= 0
        assert assistant.validation_result["total_ms"] >= 0
        assert assistant.validation_result["retrieval_fallback"] is False
        if expected == "validation_failed":
            assert assistant.content == ""
            assert "The stored wording" not in str(assistant.answer_content)
            assert assistant.validation_result["failure_stage"] == (
                "deterministic" if fabricated else "verification"
            )
            assert assistant.validation_result["expected_verdict_count"] == (
                None if fabricated else 1
            )
            assert assistant.validation_result["failure_reason"] in {
                "A block references fabricated evidence",
                "Explanation was not supported by its cited evidence",
            }
        else:
            assert assistant.content == "The stored wording protects privacy."
            assert assistant.evidence_snapshot
        if expected == "partial_evidence":
            assert (
                assistant.answer_content["citation_outcomes"][1]["status"] == "missing"
            )
        if expected == "completed":
            assert provider.payloads[1]["blocks"][0]["index"] == 0
            events = client.get(f"/api/v1/conversations/{conversation['id']}/events")
            assert events.status_code == 200
            assert "event: retrieval.complete" in events.text
            assert "event: answer.complete" in events.text
            assert events.text.index("event: retrieval.complete") < events.text.index(
                "event: answer.complete"
            )
            assert "event: answer.delta" not in events.text
            last_id = [
                line.removeprefix("id: ")
                for line in events.text.splitlines()
                if line.startswith("id: ")
            ][-1]
            replay = client.get(
                f"/api/v1/conversations/{conversation['id']}/events",
                headers={"Last-Event-ID": last_id},
            )
            assert replay.status_code == 200
            assert "event: answer.complete" not in replay.text


def test_selected_ambiguous_identity_is_pinned_and_run_events_are_scoped(
    corpus, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _release, _source, nodes, _pdf = corpus
    selected = db.exec(
        select(ProvisionVersion).where(
            ProvisionVersion.provision_id == nodes["chapter6.part2.section189"].id
        )
    ).one()
    wrong = db.exec(
        select(ProvisionVersion).where(
            ProvisionVersion.provision_id == nodes["chapter4.section37"].id
        )
    ).one()
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    provider = FakeProvider()
    with TestClient(app) as client:
        conversation_id = client.post("/api/v1/conversations", json={}).json()["id"]
        endpoint = f"/api/v1/conversations/{conversation_id}/messages"
        assert (
            client.post(
                endpoint,
                json={
                    "question": "Section 189",
                    "idempotency_key": "wrong",
                    "selected_provision_version_id": str(wrong.id),
                },
            ).status_code
            == 422
        )
        first = client.post(
            endpoint,
            json={"question": "Section 37", "idempotency_key": "first"},
        )
        assert first.status_code == 202
        first_id = UUID(first.json()["run_id"])
        assert worker._claim_run("test-worker") == first_id
        asyncio.run(worker.process_run(first_id, "test-worker", provider))  # type: ignore[arg-type]

        second = client.post(
            endpoint,
            json={
                "question": "Section 189",
                "idempotency_key": "second",
                "selected_provision_version_id": str(selected.id),
            },
        )
        assert second.status_code == 202
        second_id = UUID(second.json()["run_id"])
        assert (
            client.post(
                endpoint,
                json={"question": "Section 189", "idempotency_key": "second"},
            ).status_code
            == 409
        )
        assert worker._claim_run("test-worker") == second_id
        asyncio.run(worker.process_run(second_id, "test-worker", provider))  # type: ignore[arg-type]
        db.expire_all()
        second_run = db.get(GenerationRun, second_id)
        assert second_run is not None
        assert second_run.selected_provision_version_id == selected.id
        message = db.get(ConversationMessage, second_run.assistant_message_id)
        assert message is not None
        answer = message.answer_content
        assert answer is not None
        assert answer["citation_outcomes"][0]["status"] == "resolved"
        assert answer["evidence"][0]["canonical_path"].endswith(
            "chapter6.part2.section189"
        )
        events = client.get(
            f"/api/v1/conversations/{conversation_id}/events",
            params={"run_id": str(second_id)},
        )
        assert events.status_code == 200
        assert events.text.count("event: answer.complete") == 1
        assert str(first_id) not in events.text
        assert (
            client.get(
                f"/api/v1/conversations/{conversation_id}/events",
                params={"run_id": "00000000-0000-0000-0000-000000000001"},
            ).status_code
            == 404
        )


def test_elliptical_followup_reuses_one_resolved_identity(
    corpus, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert corpus
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    provider = FakeProvider()
    with TestClient(app) as client:
        conversation_id = client.post("/api/v1/conversations", json={}).json()["id"]
        endpoint = f"/api/v1/conversations/{conversation_id}/messages"
        for key, question in [("first", "Section 37"), ("second", "Why?")]:
            accepted = client.post(
                endpoint, json={"question": question, "idempotency_key": key}
            )
            assert accepted.status_code == 202
            run_id = UUID(accepted.json()["run_id"])
            assert worker._claim_run("test-worker") == run_id
            asyncio.run(worker.process_run(run_id, "test-worker", provider))  # type: ignore[arg-type]
            db.expire_all()
            run = db.get(GenerationRun, run_id)
            assert run is not None and run.outcome == "completed"
            message = db.get(ConversationMessage, run.assistant_message_id)
            assert message is not None and message.answer_content is not None
            assert message.answer_content["evidence"][0]["citation"] == "Section 37"
        assert provider.payloads[2]["previous_question"] == "Section 37"
