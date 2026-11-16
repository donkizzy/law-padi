import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest

from app.chat import EXPLANATION_PROMPT_VERSION, runs, worker
from app.core.config import settings
from scripts import collect_explanation_review as collector
from scripts.evaluate_explanations import _check_captures

_RUN = "00000000-0000-0000-0000-000000000001"
_CASE = {
    "id": "e001",
    "kind": "topic",
    "prompt": "privacy",
    "expected_paths": [],
    "expected_outcome": "supported",
    "turns": ["privacy"],
}


@pytest.mark.parametrize(
    ("daily", "monthly", "overall", "embeddings", "safe"),
    [
        (2.5, 4.0, 5.0, False, True),
        (2.51, 4.0, 5.0, False, False),
        (2.5, 5.01, 5.01, False, False),
        (2.5, 4.0, 5.0, True, False),
        (2.5, 4.0, 6.0, False, True),
    ],
)
def test_review_spend_guard_enforces_daily_monthly_and_embedding_limits(
    monkeypatch: pytest.MonkeyPatch,
    daily: float,
    monthly: float,
    overall: float,
    embeddings: bool,
    safe: bool,
) -> None:
    values = {
        "CHAT_ENABLED": True,
        "CHAT_GENERATION_ENABLED": True,
        "CHAT_GENERATION_KILL_SWITCH": False,
        "CHAT_MAX_ACTIVE_GENERATIONS": 1,
        "CHAT_DAILY_BUDGET_USD": daily,
        "CHAT_MONTHLY_BUDGET_USD": monthly,
        "AI_MONTHLY_BUDGET_USD": overall,
        "EMBEDDING_QUERY_ENABLED": embeddings,
        "DEEPSEEK_API_KEY": "test-not-a-provider-key",
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
    }
    for key, value in values.items():
        monkeypatch.setattr(settings, key, value)
    if safe:
        collector._validate_review_settings()
    else:
        with pytest.raises(ValueError, match="capped local DeepSeek"):
            collector._validate_review_settings()


def _mock_capture(
    monkeypatch: pytest.MonkeyPatch,
    *,
    actual_mode: str = "lexical",
    change_after_generation: str | None = None,
    server_build: str = "source-test",
    render_metadata: dict[str, Any] | None = None,
    render_change_after_submission: str | None = None,
    expected_origin_secret: str | None = None,
    answer_outcome: str = "completed",
) -> list[str]:
    calls: list[str] = []
    generated = False
    real_client = httpx.AsyncClient
    monkeypatch.setattr(settings, "BUILD_REVISION", "source-test")
    monkeypatch.setattr(settings, "EMBEDDING_QUERY_ENABLED", False)

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal generated
        assert request.headers.get("X-Origin-Proxy-Secret") == expected_origin_secret
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path.endswith("/capabilities"):
            capabilities = {
                "prompt_version": EXPLANATION_PROMPT_VERSION,
                "build_revision": server_build,
            }
            if generated and change_after_generation:
                capabilities[change_after_generation] = "changed"
            return httpx.Response(200, json=capabilities)
        if request.url.path == "/api/v1/deployment/runtime":
            if render_metadata is None:
                return httpx.Response(404)
            metadata = dict(render_metadata)
            if generated and render_change_after_submission:
                metadata[render_change_after_submission] = "changed"
            return httpx.Response(200, json=metadata)
        if request.method == "POST" and request.url.path.endswith("/conversations"):
            return httpx.Response(
                200, json={"id": "conversation", "release_version": "release-test"}
            )
        if request.method == "POST" and request.url.path.endswith("/messages"):
            generated = True
            return httpx.Response(
                202, json={"run_id": _RUN, "user_message_id": "question"}
            )
        if request.url.path.endswith("/events"):
            assert request.url.params["run_id"] == _RUN
            return httpx.Response(
                200,
                text="event: retrieval.complete\r\ndata: "
                + json.dumps({"retrieval_mode": actual_mode})
                + "\r\n\r\n",
            )
        return httpx.Response(
            200,
            json={
                "messages": [
                    {"id": "question", "role": "user"},
                    {
                        "id": "answer",
                        "role": "assistant",
                        "answer_content": {
                            "outcome": answer_outcome,
                            "evidence": [],
                            "blocks": [],
                        },
                    },
                ]
            },
        )

    monkeypatch.setattr(
        collector.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handle), **kwargs),
    )
    monkeypatch.setattr(runs, "claim_run", lambda *_args, **_kwargs: UUID(_RUN))

    async def fake_process(*_args: Any) -> None:
        nonlocal generated
        generated = True
        calls.append("simulated_generation")

    monkeypatch.setattr(worker, "process_run", fake_process)
    return calls


@pytest.mark.parametrize("actual_mode", ["exact", "lexical"])
def test_inline_capture_records_verified_configuration_and_actual_run_mode(
    monkeypatch: pytest.MonkeyPatch, actual_mode: str
) -> None:
    calls = _mock_capture(monkeypatch, actual_mode=actual_mode)
    capture = asyncio.run(
        collector._capture_case(
            "http://localhost", _CASE, "release-test", inline_worker=True
        )
    )
    assert capture["prompt_version"] == EXPLANATION_PROMPT_VERSION
    assert capture["build_revision"] == "source-test"
    assert capture["retrieval_mode"] == "lexical"
    assert capture["retrieval_mode_source"] == "inline_worker_settings"
    assert capture["turns"][0]["retrieval_mode"] == actual_mode
    assert calls.count("simulated_generation") == 1
    assert calls.count("GET /api/v1/conversations/capabilities") >= 3


def _render_metadata() -> dict[str, Any]:
    return {
        "prompt_version": EXPLANATION_PROMPT_VERSION,
        "build_revision": "source-test",
        "retrieval_mode": "lexical",
        "worker_dispatch": "request_woken",
        "metadata_source": "render_worker_settings",
    }


def test_render_capture_uses_actual_worker_metadata_and_private_origin_header(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    secret = "private-review-secret"
    monkeypatch.setenv("REVIEW_ORIGIN_PROXY_SECRET", secret)
    calls = _mock_capture(
        monkeypatch,
        render_metadata=_render_metadata(),
        expected_origin_secret=secret,
    )
    output = tmp_path / "captures.jsonl"
    count, failures = asyncio.run(
        collector.collect(
            "http://localhost",
            {"release_version": "release-test", "cases": [_CASE]},
            output,
            1,
        )
    )
    capture = json.loads(output.read_text())
    assert (count, failures) == (1, 0)
    assert capture["retrieval_mode"] == "lexical"
    assert capture["retrieval_mode_source"] == "render_worker_settings"
    assert capture["worker_dispatch"] == "request_woken"
    assert capture["prompt_version"] == EXPLANATION_PROMPT_VERSION
    assert capture["build_revision"] == "source-test"
    assert capture["turns"][0]["retrieval_mode"] == "lexical"
    assert "simulated_generation" not in calls
    assert calls.count("GET /api/v1/deployment/runtime") >= 4


@pytest.mark.parametrize(
    "outcome",
    ["provider_failure", "budget_exhausted", "capacity_exhausted", "cancelled"],
)
def test_unavailable_run_stops_before_follow_up_or_next_case(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, outcome: str
) -> None:
    calls = _mock_capture(
        monkeypatch, render_metadata=_render_metadata(), answer_outcome=outcome
    )
    output = tmp_path / "captures.jsonl"
    dataset = {
        "release_version": "release-test",
        "cases": [
            {**_CASE, "turns": ["privacy", "What are the limits?"]},
            {**_CASE, "id": "e002"},
        ],
    }
    count, failures = asyncio.run(
        collector.collect("http://localhost", dataset, output, 2)
    )
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert (count, failures) == (1, 1)
    assert len(rows) == 1
    assert outcome in rows[0]["error"]
    assert calls.count("POST /api/v1/conversations/conversation/messages") == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("prompt_version", "old-prompt"),
        ("build_revision", "old-build"),
        ("retrieval_mode", "exact"),
        ("worker_dispatch", "poll"),
        ("metadata_source", "operator_settings"),
    ],
)
def test_render_mismatched_metadata_stops_before_submission(
    monkeypatch: pytest.MonkeyPatch, field: str, value: str
) -> None:
    metadata = {**_render_metadata(), field: value}
    calls = _mock_capture(monkeypatch, render_metadata=metadata)
    with pytest.raises(collector.CaptureConfigurationChanged, match="Render worker"):
        asyncio.run(collector._capture_case("http://localhost", _CASE, "release-test"))
    assert not any(call.startswith("POST") for call in calls)


@pytest.mark.parametrize("field", list(_render_metadata()))
def test_render_missing_metadata_stops_before_submission(
    monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    metadata = _render_metadata()
    del metadata[field]
    calls = _mock_capture(monkeypatch, render_metadata=metadata)
    with pytest.raises(collector.CaptureConfigurationChanged, match="Render worker"):
        asyncio.run(collector._capture_case("http://localhost", _CASE, "release-test"))
    assert not any(call.startswith("POST") for call in calls)


def test_other_runtime_without_worker_metadata_remains_unconfirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_capture(monkeypatch)

    async def configuration() -> dict[str, Any]:
        async with collector._client(base_url="http://localhost") as client:
            return await collector._configuration(client, inline_worker=False)

    metadata = asyncio.run(configuration())
    assert metadata["retrieval_mode"] == "unknown"
    assert metadata["retrieval_mode_source"] == "unknown"


@pytest.mark.parametrize("field", list(_render_metadata()))
def test_render_mid_case_configuration_change_invalidates_capture(
    monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    _mock_capture(
        monkeypatch,
        render_metadata=_render_metadata(),
        render_change_after_submission=field,
    )
    with pytest.raises(collector.CaptureConfigurationChanged):
        asyncio.run(collector._capture_case("http://localhost", _CASE, "release-test"))


@pytest.mark.parametrize("changed_field", ["prompt_version", "build_revision"])
def test_mid_case_configuration_change_invalidates_capture(
    monkeypatch: pytest.MonkeyPatch, changed_field: str
) -> None:
    _mock_capture(monkeypatch, change_after_generation=changed_field)
    with pytest.raises(collector.CaptureConfigurationChanged):
        asyncio.run(
            collector._capture_case(
                "http://localhost", _CASE, "release-test", inline_worker=True
            )
        )


def test_worker_api_mismatch_stops_before_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _mock_capture(monkeypatch, server_build="different-build")
    with pytest.raises(collector.CaptureConfigurationChanged, match="differ"):
        asyncio.run(
            collector._capture_case(
                "http://localhost", _CASE, "release-test", inline_worker=True
            )
        )
    assert "simulated_generation" not in calls
    assert not any(call.startswith("POST") for call in calls)


def test_hybrid_run_conflicts_with_disabled_query_embeddings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_capture(monkeypatch, actual_mode="hybrid")
    with pytest.raises(collector.CaptureConfigurationChanged, match="hybrid"):
        asyncio.run(
            collector._capture_case(
                "http://localhost", _CASE, "release-test", inline_worker=True
            )
        )


def test_collector_refuses_to_resume_metadata_free_captures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = _mock_capture(monkeypatch)
    output = tmp_path / "captures.jsonl"
    output.write_text(json.dumps({"id": "e000", "turns": []}) + "\n")
    with pytest.raises(
        collector.CaptureConfigurationChanged, match="Existing captures"
    ):
        asyncio.run(
            collector.collect(
                "http://localhost",
                {"release_version": "release-test", "cases": [_CASE]},
                output,
                1,
                inline_worker=True,
            )
        )
    assert "simulated_generation" not in calls


@pytest.mark.parametrize(
    ("field", "value", "failure"),
    [
        ("prompt_version", "old-prompt", "captured prompt"),
        ("build_revision", "old-build", "captured build"),
        ("retrieval_mode", "hybrid", "query retrieval policy"),
        ("retrieval_mode_source", "unknown", "query retrieval policy"),
    ],
)
def test_evaluator_rejects_stale_or_unconfirmed_configuration(
    tmp_path: Path, field: str, value: str, failure: str
) -> None:
    capture = {
        "id": "e001",
        "release_version": "release-test",
        "prompt_version": EXPLANATION_PROMPT_VERSION,
        "build_revision": "source-test",
        "retrieval_mode": "lexical",
        "retrieval_mode_source": "inline_worker_settings",
        "turns": [
            {"retrieval_mode": "lexical", "answer": {"evidence": [], "blocks": []}}
        ],
        field: value,
    }
    path = tmp_path / "captures.jsonl"
    path.write_text(json.dumps(capture) + "\n")
    failures = _check_captures(
        {"release_version": "release-test", "cases": [_CASE]},
        path,
        expected_build_revision="source-test",
        expected_retrieval_mode="lexical",
    )
    assert any(failure in item for item in failures)


@pytest.mark.parametrize("worker_dispatch", ["request_woken", "poll", None])
def test_evaluator_accepts_only_confirmed_render_worker_dispatch(
    tmp_path: Path, worker_dispatch: str | None
) -> None:
    capture = {
        "id": "e001",
        **_render_metadata(),
        "release_version": "release-test",
        "retrieval_mode_source": "render_worker_settings",
        "worker_dispatch": worker_dispatch,
        "turns": [
            {
                "question": "privacy",
                "retrieval_mode": "lexical",
                "answer": {"evidence": [], "blocks": []},
            }
        ],
    }
    path = tmp_path / "captures.jsonl"
    path.write_text(json.dumps(capture) + "\n")
    failures = _check_captures(
        {"release_version": "release-test", "cases": [_CASE]},
        path,
        expected_build_revision="source-test",
        expected_retrieval_mode="lexical",
    )
    if worker_dispatch == "request_woken":
        assert failures == []
    else:
        assert any("query retrieval policy" in failure for failure in failures)
