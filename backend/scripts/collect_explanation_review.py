"""Capture bounded live explanation runs for human review in an isolated stack.

Run against a local API backed by a disposable database, with the chat worker's
daily spending cap set for the validation run. The output contains model answers
and canonical evidence; keep it under ignored backend/storage/evaluations/.
"""

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx


class CaptureConfigurationChanged(RuntimeError):
    """Stop collection rather than mix answers from different packaged builds."""


class CaptureRunStopped(RuntimeError):
    """Stop paid work after an unavailable run, without attempting another turn."""


def _validate_review_settings() -> None:
    from app.core.config import settings

    if (
        not settings.CHAT_ENABLED
        or not settings.CHAT_GENERATION_ENABLED
        or settings.CHAT_GENERATION_KILL_SWITCH
        or settings.CHAT_MAX_ACTIVE_GENERATIONS != 1
        or settings.CHAT_DAILY_BUDGET_USD > 2.5
        or min(settings.CHAT_MONTHLY_BUDGET_USD, settings.AI_MONTHLY_BUDGET_USD) > 5
        or settings.EMBEDDING_QUERY_ENABLED
        or not settings.DEEPSEEK_API_KEY
        or urlparse(settings.DEEPSEEK_BASE_URL).hostname != "api.deepseek.com"
    ):
        raise ValueError("Live review requires capped local DeepSeek settings")


def _client(base_url: str, **kwargs: Any) -> httpx.AsyncClient:
    """Keep private-origin access in the environment, out of CLI arguments."""
    secret = os.environ.get("REVIEW_ORIGIN_PROXY_SECRET")
    headers = {"X-Origin-Proxy-Secret": secret} if secret else {}
    return httpx.AsyncClient(
        base_url=base_url, headers=headers, trust_env=False, **kwargs
    )


async def _capabilities(client: httpx.AsyncClient) -> dict[str, str]:
    response = await client.get("/api/v1/conversations/capabilities")
    response.raise_for_status()
    body = response.json()
    metadata = {key: body.get(key) for key in ("prompt_version", "build_revision")}
    if any(not isinstance(value, str) or not value for value in metadata.values()):
        raise CaptureConfigurationChanged("API build/prompt metadata is missing")
    if metadata["build_revision"] == "development":
        raise CaptureConfigurationChanged("A packaged build revision is required")
    return metadata


def _worker_configuration(capabilities: dict[str, str]) -> dict[str, Any]:
    from app.chat import EXPLANATION_PROMPT_VERSION
    from app.core.config import settings

    if (
        settings.BUILD_REVISION != capabilities["build_revision"]
        or EXPLANATION_PROMPT_VERSION != capabilities["prompt_version"]
    ):
        raise CaptureConfigurationChanged("Inline worker and API build/prompt differ")
    return {
        **capabilities,
        "retrieval_mode": "hybrid" if settings.EMBEDDING_QUERY_ENABLED else "lexical",
        "retrieval_mode_source": "inline_worker_settings",
    }


async def _configuration(
    client: httpx.AsyncClient, *, inline_worker: bool
) -> dict[str, Any]:
    capabilities = await _capabilities(client)
    if inline_worker:
        return _worker_configuration(capabilities)
    response = await client.get("/api/v1/deployment/runtime")
    if response.status_code != 404:
        response.raise_for_status()
        runtime = response.json()
        if (
            not isinstance(runtime, dict)
            or runtime.get("build_revision") != capabilities["build_revision"]
            or runtime.get("prompt_version") != capabilities["prompt_version"]
            or runtime.get("retrieval_mode") not in ("lexical", "hybrid")
            or runtime.get("worker_dispatch") != "request_woken"
            or runtime.get("metadata_source") != "render_worker_settings"
        ):
            raise CaptureConfigurationChanged(
                "Render worker metadata is incomplete or differs from the API"
            )
        return {
            **capabilities,
            "retrieval_mode": runtime["retrieval_mode"],
            "retrieval_mode_source": runtime["metadata_source"],
            "worker_dispatch": runtime["worker_dispatch"],
        }
    return {
        **capabilities,
        "retrieval_mode": "unknown",
        "retrieval_mode_source": "unknown",
    }


async def _retrieval_mode(
    client: httpx.AsyncClient, conversation_id: str, run_id: str
) -> str:
    # A terminal run replays persisted events and closes immediately. This
    # records the actual retrieval path rather than guessing from answer text.
    response = await client.get(
        f"/api/v1/conversations/{conversation_id}/events", params={"run_id": run_id}
    )
    response.raise_for_status()
    modes: list[str] = []
    for event in response.text.replace("\r\n", "\n").split("\n\n"):
        event_type = next(
            (
                line[6:].strip()
                for line in event.splitlines()
                if line.startswith("event:")
            ),
            None,
        )
        if event_type != "retrieval.complete":
            continue
        data = "\n".join(
            line[5:].lstrip() for line in event.splitlines() if line.startswith("data:")
        )
        mode = json.loads(data).get("retrieval_mode")
        if mode not in {"exact", "lexical", "hybrid"}:
            raise ValueError("Run retrieval event has no supported retrieval mode")
        modes.append(mode)
    if len(modes) != 1:
        raise ValueError("Run requires exactly one persisted retrieval completion")
    return modes[0]


async def _completed_answer(
    client: httpx.AsyncClient, conversation_id: str, user_message_id: str
) -> dict[str, Any]:
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        response = await client.get(f"/api/v1/conversations/{conversation_id}")
        response.raise_for_status()
        detail = response.json()
        messages = detail["messages"]
        user_index = next(
            (
                index
                for index, row in enumerate(messages)
                if row["id"] == user_message_id
            ),
            None,
        )
        if user_index is not None:
            answer = next(
                (
                    row
                    for row in messages[user_index + 1 :]
                    if row["role"] == "assistant"
                ),
                None,
            )
            if isinstance(answer, dict):
                return answer
        await asyncio.sleep(0.75)
    raise TimeoutError("Explanation did not finish within 150 seconds")


async def _capture_case(
    base_url: str,
    case: dict[str, Any],
    release_version: str,
    *,
    inline_worker: bool = False,
    expected_configuration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "id": case["id"],
        "kind": case["kind"],
        "prompt": case["prompt"],
        "expected_paths": case["expected_paths"],
        "expected_outcome": case["expected_outcome"],
        "release_version": release_version,
        "turns": [],
    }
    async with _client(
        base_url=base_url,
        timeout=httpx.Timeout(30, connect=10),
    ) as client:
        configuration = await _configuration(client, inline_worker=inline_worker)
        if (
            expected_configuration is not None
            and configuration != expected_configuration
        ):
            raise CaptureConfigurationChanged(
                "Capture API/worker configuration changed"
            )
        row.update(configuration)
        response = await client.post(
            "/api/v1/conversations", json={"release_version": release_version}
        )
        response.raise_for_status()
        conversation = response.json()
        if conversation["release_version"] != release_version:
            raise ValueError("API selected a different corpus release")
        row["conversation_id"] = conversation["id"]
        for question in case["turns"]:
            if (
                await _configuration(client, inline_worker=inline_worker)
                != configuration
            ):
                raise CaptureConfigurationChanged("Configuration changed before a turn")
            response = await client.post(
                f"/api/v1/conversations/{conversation['id']}/messages",
                json={
                    "question": question,
                    "idempotency_key": str(uuid.uuid4()),
                },
            )
            response.raise_for_status()
            accepted = response.json()
            if inline_worker:
                from app.chat import runs, worker

                expected = uuid.UUID(accepted["run_id"])
                worker_id = f"review-{uuid.uuid4()}"
                claimed = await asyncio.to_thread(
                    runs.claim_run, worker_id, run_id=expected
                )
                if claimed != expected:
                    raise RuntimeError(
                        "The API run was not found in the isolated review database"
                    )
                await worker.process_run(expected, worker_id)
            answer = await _completed_answer(
                client, conversation["id"], accepted["user_message_id"]
            )
            outcome = (answer.get("answer_content") or {}).get("outcome")
            if outcome in {
                "provider_failure",
                "budget_exhausted",
                "capacity_exhausted",
                "cancelled",
            }:
                raise CaptureRunStopped(f"{outcome}; run_id={accepted['run_id']}")
            retrieval_mode = await _retrieval_mode(
                client, conversation["id"], accepted["run_id"]
            )
            if (
                configuration["retrieval_mode"] == "lexical"
                and retrieval_mode == "hybrid"
            ):
                raise CaptureConfigurationChanged(
                    "Disabled embeddings produced hybrid retrieval"
                )
            if (
                await _configuration(client, inline_worker=inline_worker)
                != configuration
            ):
                raise CaptureConfigurationChanged("Configuration changed during a turn")
            row["turns"].append(
                {
                    "question": question,
                    "run_id": accepted["run_id"],
                    "answer": answer["answer_content"],
                    "retrieval_mode": retrieval_mode,
                }
            )
        if await _configuration(client, inline_worker=inline_worker) != configuration:
            raise CaptureConfigurationChanged("Configuration changed during capture")
    return row


async def collect(
    base_url: str,
    dataset: dict[str, Any],
    output: Path,
    max_cases: int,
    *,
    inline_worker: bool = False,
) -> tuple[int, int]:
    output.parent.mkdir(parents=True, exist_ok=True)
    existing = (
        [json.loads(line) for line in output.read_text().splitlines() if line.strip()]
        if output.exists()
        else []
    )
    captured = {row["id"] for row in existing}
    if len(captured) != len(existing):
        raise ValueError("Capture file has duplicate case IDs")
    async with _client(base_url=base_url) as client:
        configuration = await _configuration(client, inline_worker=inline_worker)
    for row in existing:
        if any(row.get(key) != value for key, value in configuration.items()):
            raise CaptureConfigurationChanged(
                "Existing captures use a different configuration"
            )
    count = 0
    failures = 0
    with output.open("a") as stream:
        for case in dataset["cases"]:
            if case["id"] in captured:
                continue
            if count >= max_cases:
                break
            count += 1
            try:
                row = await _capture_case(
                    base_url,
                    case,
                    dataset["release_version"],
                    inline_worker=inline_worker,
                    expected_configuration=configuration,
                )
            except (
                httpx.HTTPError,
                KeyError,
                ValueError,
                TimeoutError,
                RuntimeError,
            ) as exc:
                row = {
                    "id": case["id"],
                    **configuration,
                    "error": f"{type(exc).__name__}: {exc}",
                }
                failures += 1
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            print(f"{case['id']}: {'error' if 'error' in row else 'captured'}")  # noqa: T201
            if "error" in row:
                break
    return count, failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-cases", type=int, default=1)
    parser.add_argument("--isolated-deployment", action="store_true")
    parser.add_argument("--inline-worker", action="store_true")
    args = parser.parse_args()
    hostname = urlparse(args.base_url).hostname
    if hostname not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("The review collector only accepts a local API endpoint")
    if not args.isolated_deployment:
        parser.error("Confirm a disposable, budget-capped deployment")
    if args.max_cases < 1:
        parser.error("--max-cases must be positive")
    try:
        _validate_review_settings()
    except ValueError as exc:
        parser.error(str(exc))
    if args.inline_worker:
        from sqlalchemy.engine import make_url

        from app.core.config import settings

        database_name = make_url(str(settings.DATABASE_URL)).database or ""
        if not database_name.startswith("app_live_validation_"):
            parser.error("Inline review requires a disposable validation database")
    dataset = json.loads(args.dataset.read_text())
    count, failures = asyncio.run(
        collect(
            args.base_url,
            dataset,
            args.output,
            args.max_cases,
            inline_worker=args.inline_worker,
        )
    )
    print(f"Captured {count} cases; errors: {failures}")  # noqa: T201
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
