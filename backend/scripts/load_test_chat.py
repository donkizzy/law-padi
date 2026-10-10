"""Exercise conversation admission and replayable SSE on an isolated deployment.

Each simulated guest owns one conversation and SSE connection. The target API
must use a disposable database and the controlled chat_provider_simulator;
this command creates records and must never point at a user database.
"""

import argparse
import asyncio
import json
import statistics
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class Guest:
    client: httpx.AsyncClient
    conversation_id: str


async def run(base_url: str, target: int, timeout: float) -> dict[str, Any]:
    guests: list[Guest] = []
    errors: list[str] = []
    admission_ms: list[float] = []
    accepted = 0
    opened = 0
    completed = 0
    connected = 0
    peak_connections = 0
    started = time.perf_counter()
    creation_limit = asyncio.Semaphore(100)
    admission_limit = asyncio.Semaphore(100)

    async def create_guest(index: int) -> Guest | None:
        async with creation_limit:
            client = httpx.AsyncClient(
                base_url=base_url,
                timeout=httpx.Timeout(timeout, connect=10),
                limits=httpx.Limits(max_connections=2),
                trust_env=False,
            )
            try:
                response = await client.post("/api/v1/conversations", json={})
                response.raise_for_status()
                if response.status_code != 201:
                    raise ValueError(
                        f"Unexpected creation status {response.status_code}"
                    )
                return Guest(client=client, conversation_id=response.json()["id"])
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                errors.append(f"create {index}: {type(exc).__name__}: {exc}")
                await client.aclose()
                return None

    try:
        created = await asyncio.gather(
            *(create_guest(index) for index in range(target))
        )
        guests = [guest for guest in created if guest is not None]

        async def submit(guest: Guest, index: int) -> bool:
            nonlocal accepted
            async with admission_limit:
                began = time.perf_counter()
                body = {
                    "question": "Section 37",
                    "idempotency_key": f"load-{index}-{uuid.uuid4()}",
                }
                for attempt in range(4):
                    try:
                        response = await guest.client.post(
                            f"/api/v1/conversations/{guest.conversation_id}/messages",
                            json=body,
                        )
                        admission_ms.append((time.perf_counter() - began) * 1000)
                        if response.status_code != 202:
                            errors.append(
                                f"submit {index}: HTTP {response.status_code}"
                            )
                            return False
                        accepted += 1
                        return True
                    except httpx.TransportError as exc:
                        if attempt == 3:
                            errors.append(
                                f"submit {index}: {type(exc).__name__}: {exc}"
                            )
                            return False
                        await asyncio.sleep(min(2, 0.2 * 2**attempt))
                return False

        admitted = await asyncio.gather(
            *(submit(guest, index) for index, guest in enumerate(guests))
        )

        async def read_events(guest: Guest, index: int) -> None:
            nonlocal opened, completed, connected, peak_connections
            last_event_id: str | None = None
            was_opened = False
            for attempt in range(5):
                is_connected = False
                try:
                    async with guest.client.stream(
                        "GET",
                        f"/api/v1/conversations/{guest.conversation_id}/events",
                        headers={"Last-Event-ID": last_event_id}
                        if last_event_id
                        else None,
                    ) as response:
                        response.raise_for_status()
                        if not was_opened:
                            opened += 1
                            was_opened = True
                        connected += 1
                        is_connected = True
                        peak_connections = max(peak_connections, connected)
                        async for line in response.aiter_lines():
                            if line.startswith("id: "):
                                last_event_id = line.removeprefix("id: ")
                            if line == "event: answer.complete":
                                completed += 1
                                return
                except httpx.HTTPError as exc:
                    if attempt == 4:
                        errors.append(f"events {index}: {type(exc).__name__}: {exc}")
                finally:
                    if is_connected:
                        connected -= 1
                if attempt < 4:
                    await asyncio.sleep(min(2, 0.2 * 2**attempt))
            if was_opened and not any(
                error.startswith(f"events {index}:") for error in errors
            ):
                errors.append(f"events {index}: stream ended without a terminal event")

        await asyncio.gather(
            *(
                read_events(guest, index)
                for index, (guest, ok) in enumerate(zip(guests, admitted, strict=True))
                if ok
            )
        )
    finally:
        await asyncio.gather(*(guest.client.aclose() for guest in guests))

    p95_ms = (
        sorted(admission_ms)[min(len(admission_ms) - 1, int(len(admission_ms) * 0.95))]
        if admission_ms
        else None
    )
    return {
        "target": target,
        "created": len(guests),
        "accepted": accepted,
        "sse_opened": opened,
        "terminal_events": completed,
        "peak_sse_connections": peak_connections,
        "p95_admission_ms": round(p95_ms, 1) if p95_ms is not None else None,
        "mean_admission_ms": round(statistics.mean(admission_ms), 1)
        if admission_ms
        else None,
        "elapsed_seconds": round(time.perf_counter() - started, 1),
        "errors": errors[:20],
        "error_count": len(errors),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--target", type=int, default=1000)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--disposable-environment", action="store_true")
    args = parser.parse_args()
    if args.target < 1 or args.timeout <= 0:
        parser.error("target and timeout must be positive")
    if not args.disposable_environment:
        parser.error(
            "Use --disposable-environment only for an isolated test deployment"
        )
    result = asyncio.run(run(args.base_url, args.target, args.timeout))
    print(json.dumps(result, indent=2))  # noqa: T201
    return (
        0
        if result["accepted"] == args.target
        and result["terminal_events"] == args.target
        and result["peak_sse_connections"] == args.target
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
