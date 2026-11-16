"""HTTPX adapter for DeepSeek JSON completions."""

import json

import httpx

from app.chat.llm.protocol import JsonObject, ProviderError, ProviderResult
from app.core.config import settings


class DeepSeekClient:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def complete_json(
        self,
        *,
        system: str,
        payload: JsonObject,
        max_tokens: int | None = None,
        thinking: bool = False,
    ) -> ProviderResult:
        if not settings.DEEPSEEK_API_KEY:
            raise ProviderError("DeepSeek is not configured")
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=httpx.Timeout(settings.DEEPSEEK_TIMEOUT_SECONDS, connect=10.0)
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
                        # Reasoning text is never read, stored or shown.
                        "thinking": {"type": "enabled" if thinking else "disabled"},
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
                    raise ProviderError(
                        "DeepSeek response was incomplete", uncertain_charge=True
                    )
                content = choice["message"]["content"]
                value = json.loads(content)
                if not isinstance(value, dict):
                    raise ValueError("Expected JSON object")
                usage = data["usage"]
                prompt_tokens = int(usage["prompt_tokens"])
                completion_tokens = int(usage["completion_tokens"])
                if prompt_tokens < 0 or completion_tokens < 0:
                    raise ValueError("Provider usage cannot be negative")
                return ProviderResult(
                    value=value,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
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
                    "DeepSeek returned an invalid JSON response", uncertain_charge=True
                ) from exc
        finally:
            if owns_client:
                await client.aclose()
