"""Deterministic OpenAI-compatible response simulator for isolated load tests.

Run only on a private interface: uv run uvicorn scripts.chat_provider_simulator:app
--host 127.0.0.1 --port 8089. Point DEEPSEEK_BASE_URL at that address in an
isolated test environment; never use this simulator for user answers.
"""

import asyncio
import json
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Request

app = FastAPI(title="constitution.ng chat provider simulator")


def simulated_answer(system: str, payload: dict[str, Any]) -> dict[str, Any]:
    if "verdicts" in system:
        blocks = payload.get("blocks", [])
        return {
            "verdicts": [
                {
                    "index": index,
                    "supported": True,
                    "qualifications_preserved": True,
                    **({"answers_question": True} if index == 0 else {}),
                }
                for index, _ in enumerate(blocks)
            ]
        }
    evidence = payload.get("evidence", [])
    if not evidence or not isinstance(evidence[0].get("id"), str):
        raise ValueError("Generation payload has no evidence identifier")
    return {
        "direct_answer": "depends",
        "blocks": [
            {
                "text": "The Constitution deals with this in the section shown below.",
                "evidence_ids": [evidence[0]["id"]],
            }
        ],
        "missing_facts": [],
    }


@app.post("/chat/completions")
async def chat_completion(request: Request) -> dict[str, Any]:
    if request.headers.get("authorization") != "Bearer simulator-test":
        raise HTTPException(status_code=401, detail="Simulator credential required")
    body = await request.json()
    try:
        system = body["messages"][0]["content"]
        payload = json.loads(body["messages"][1]["content"])
        answer = simulated_answer(system, payload)
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail="Malformed simulator request"
        ) from exc
    await asyncio.sleep(float(os.environ.get("CHAT_SIMULATOR_DELAY_SECONDS", "10")))
    return {
        "model": "chat-provider-simulator",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)},
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 40},
    }
