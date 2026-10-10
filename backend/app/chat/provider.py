"""HTTPX adapter for DeepSeek JSON completions."""

import json
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings


class ProviderError(RuntimeError):
    def __init__(
        self, message: str, *, retryable: bool = False, uncertain_charge: bool = False
    ):
        super().__init__(message)
        self.retryable = retryable
        self.uncertain_charge = uncertain_charge


@dataclass(frozen=True)
class ProviderResult:
    value: dict[str, Any]
    prompt_tokens: int
    completion_tokens: int
    model: str


class DeepSeekClient:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def complete_json(
        self,
        *,
        system: str,
        payload: dict[str, Any],
        max_tokens: int | None = None,
    ) -> ProviderResult:
        if not settings.DEEPSEEK_API_KEY:
            raise ProviderError("DeepSeek is not configured")
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=httpx.Timeout(45.0, connect=10.0)
        )
        try:
            try:
                response = await client.post(
                    f"{settings.DEEPSEEK_BASE_URL.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"},
                    json={
                        "model": settings.DEEPSEEK_MODEL,
                        "messages": [
                            {"role": "system", "content": system},
                            {
                                "role": "user",
                                "content": json.dumps(payload, ensure_ascii=False),
                            },
                        ],
                        "thinking": {"type": "disabled"},
                        "response_format": {"type": "json_object"},
                        "max_tokens": max_tokens or settings.DEEPSEEK_MAX_OUTPUT_TOKENS,
                    },
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                raise ProviderError(
                    "DeepSeek request did not complete",
                    retryable=True,
                    uncertain_charge=True,
                ) from exc
            if response.status_code == 429 or response.status_code >= 500:
                raise ProviderError(
                    "DeepSeek is temporarily unavailable",
                    retryable=True,
                    uncertain_charge=True,
                )
            if response.status_code >= 400:
                raise ProviderError("DeepSeek rejected the request")
            try:
                data = response.json()
                choice = data["choices"][0]
                if choice["finish_reason"] != "stop":
                    raise ProviderError("DeepSeek response was incomplete")
                content = choice["message"]["content"]
                value = json.loads(content)
                if not isinstance(value, dict):
                    raise ValueError("Expected JSON object")
                usage = data["usage"]
                return ProviderResult(
                    value=value,
                    prompt_tokens=int(usage["prompt_tokens"]),
                    completion_tokens=int(usage["completion_tokens"]),
                    model=str(data.get("model") or settings.DEEPSEEK_MODEL),
                )
            except (
                KeyError,
                IndexError,
                TypeError,
                ValueError,
                json.JSONDecodeError,
            ) as exc:
                raise ProviderError(
                    "DeepSeek returned an invalid JSON response"
                ) from exc
        finally:
            if owns_client:
                await client.aclose()
