"""Capture bounded live explanation runs for human review in an isolated stack.

Run against a local API backed by a disposable database, with the chat worker's
daily spending cap set for the validation run. The output contains model answers
and canonical evidence; keep it under ignored backend/storage/evaluations/.
"""

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx


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
            if answer is not None:
                return answer
        await asyncio.sleep(0.75)
    raise TimeoutError("Explanation did not finish within 150 seconds")


async def _capture_case(
    base_url: str,
    case: dict[str, Any],
    release_version: str,
    *,
    inline_worker: bool = False,
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
    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(30, connect=10),
        trust_env=False,
    ) as client:
        response = await client.post(
            "/api/v1/conversations", json={"release_version": release_version}
        )
        response.raise_for_status()
        conversation = response.json()
        if conversation["release_version"] != release_version:
            raise ValueError("API selected a different corpus release")
        row["conversation_id"] = conversation["id"]
        for question in case["turns"]:
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
                from app.chat import worker

                expected = uuid.UUID(accepted["run_id"])
                worker_id = f"review-{uuid.uuid4()}"
                claimed = await asyncio.to_thread(
                    worker._claim_run, worker_id, run_id=expected
                )
                if claimed != expected:
                    raise RuntimeError(
                        "The API run was not found in the isolated review database"
                    )
                await worker.process_run(expected, worker_id)
            answer = await _completed_answer(
                client, conversation["id"], accepted["user_message_id"]
            )
            row["turns"].append(
                {
                    "question": question,
                    "run_id": accepted["run_id"],
                    "answer": answer["answer_content"],
                }
            )
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
                )
            except (
                httpx.HTTPError,
                KeyError,
                ValueError,
                TimeoutError,
                RuntimeError,
            ) as exc:
                row = {"id": case["id"], "error": f"{type(exc).__name__}: {exc}"}
                failures += 1
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            print(f"{case['id']}: {'error' if 'error' in row else 'captured'}")  # noqa: T201
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
    if args.inline_worker:
        from sqlalchemy.engine import make_url

        from app.core.config import settings

        database_name = make_url(str(settings.DATABASE_URL)).database or ""
        if not database_name.startswith("app_live_validation_"):
            parser.error("Inline review requires a disposable validation database")
        if (
            not settings.CHAT_ENABLED
            or not settings.CHAT_GENERATION_ENABLED
            or settings.CHAT_GENERATION_KILL_SWITCH
            or settings.CHAT_MAX_ACTIVE_GENERATIONS != 1
            or settings.CHAT_DAILY_BUDGET_USD > 2
            or not settings.DEEPSEEK_API_KEY
            or urlparse(settings.DEEPSEEK_BASE_URL).hostname != "api.deepseek.com"
        ):
            parser.error("Inline review requires capped local DeepSeek settings")
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
