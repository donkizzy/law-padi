"""Provider-independent JSON completion contract and result types."""

from dataclasses import dataclass
from typing import Any, Protocol

type JsonObject = dict[str, Any]


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int


class ProviderError(RuntimeError):
    """A completion that failed.

    ``uncertain_charge`` means the provider may have billed the call without
    reporting usage. ``usage`` is the usage it did report for a response that
    was then rejected, and ``retry_after`` is the pause it asked for.
    """

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        uncertain_charge: bool = False,
        retry_after: float | None = None,
        usage: TokenUsage | None = None,
    ):
        super().__init__(message)
        self.retryable = retryable
        self.uncertain_charge = uncertain_charge
        self.retry_after = retry_after
        self.usage = usage


@dataclass(frozen=True)
class ProviderResult:
    value: JsonObject
    prompt_tokens: int
    completion_tokens: int
    model: str

    @property
    def usage(self) -> TokenUsage:
        return TokenUsage(self.prompt_tokens, self.completion_tokens)


class ChatModel(Protocol):
    async def complete_json(
        self,
        *,
        system: str,
        payload: JsonObject,
        max_tokens: int,
        thinking: bool = False,
    ) -> ProviderResult: ...
