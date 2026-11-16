import asyncio

import httpx
import pytest

from app.chat.prompts import explanation, verifier
from app.chat.provider import DeepSeekClient
from app.core.config import settings
from scripts.chat_provider_simulator import app


def test_simulator_matches_provider_json_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "simulator-test")
    monkeypatch.setattr(settings, "DEEPSEEK_BASE_URL", "http://simulator.test")
    monkeypatch.setenv("CHAT_SIMULATOR_DELAY_SECONDS", "0")

    async def exercise() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://simulator.test"
        ) as client:
            provider = DeepSeekClient(client)
            generated = await provider.complete_json(
                system=explanation.TEXT, payload={"evidence": [{"id": "E1"}]}
            )
            assert generated.value["blocks"][0]["evidence_ids"] == ["E1"]
            verified = await provider.complete_json(
                system=verifier.TEXT,
                payload={"blocks": generated.value["blocks"]},
            )
            assert verified.value["verdicts"] == [
                {
                    "index": 0,
                    "supported": True,
                    "qualifications_preserved": True,
                    "answers_question": True,
                }
            ]

    asyncio.run(exercise())
