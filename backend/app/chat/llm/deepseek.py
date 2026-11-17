"""HTTPX adapter for DeepSeek JSON completions."""

import json
import math
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.chat.llm.protocol import JsonObject, ProviderError, ProviderResult, TokenUsage
from app.core.config import settings

# Rate limiting and the server errors the provider reports itself mean nothing
# was generated, so the call is not charged and may be retried.
_UNCHARGED_STATUSES = frozenset({429, 500, 503})


def _retry_after(response: httpx.Response) -> float | None:
    """Seconds named by a Retry-After header, in either of its two forms."""
    value = response.headers.get("retry-after")
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            when = parsedate_to_datetime(value)
        except TypeError, ValueError:
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        seconds = (when - datetime.now(UTC)).total_seconds()
    return max(0.0, seconds) if math.isfinite(seconds) else None


def _usage(data: Any) -> TokenUsage | None:
    usage = data.get("usage") if isinstance(data, dict) else None
    if not isinstance(usage, dict):
        return None
    try:
        prompt_tokens = int(usage["prompt_tokens"])
        completion_tokens = int(usage["completion_tokens"])
    except KeyError, TypeError, ValueError:
        return None
    if prompt_tokens < 0 or completion_tokens < 0:
        return None
    return TokenUsage(prompt_tokens, completion_tokens)


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
            if response.status_code in _UNCHARGED_STATUSES:
                raise ProviderError(
                    "DeepSeek is temporarily unavailable",
                    retryable=True,
                    retry_after=_retry_after(response),
                )
            if response.status_code >= 500:
                # A gateway error (502, 504) can arrive while the provider is
                # still generating, so the call may yet be charged.
                raise ProviderError(
                    "DeepSeek is temporarily unavailable",
                    retryable=True,
                    uncertain_charge=True,
                )
            if response.status_code >= 400:
                raise ProviderError("DeepSeek rejected the request")
            try:
                data = response.json()
            except ValueError as exc:
                raise ProviderError(
                    "DeepSeek returned an invalid JSON response", uncertain_charge=True
                ) from exc
            # A rejected response that reports its usage settles at that cost;
            # only one without usage keeps its worst-case reservation.
            usage = _usage(data)
            try:
                choice = data["choices"][0]
                if choice["finish_reason"] != "stop":
                    raise ProviderError(
                        "DeepSeek response was incomplete",
                        uncertain_charge=usage is None,
                        usage=usage,
                    )
                value = json.loads(choice["message"]["content"])
                if not isinstance(value, dict):
                    raise ValueError("Expected JSON object")
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise ProviderError(
                    "DeepSeek returned an invalid JSON response",
                    uncertain_charge=usage is None,
                    usage=usage,
                ) from exc
            if usage is None:
                raise ProviderError(
                    "DeepSeek returned an invalid JSON response", uncertain_charge=True
                )
            return ProviderResult(
                value=value,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                model=str(data.get("model") or settings.DEEPSEEK_MODEL),
            )
        finally:
            if owns_client:
                await client.aclose()
