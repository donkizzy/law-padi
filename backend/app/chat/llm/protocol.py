"""Provider-independent JSON completion contract and result types."""

from dataclasses import dataclass
from typing import Any, Protocol

type JsonObject = dict[str, Any]


class ProviderError(RuntimeError):
    def __init__(
        self, message: str, *, retryable: bool = False, uncertain_charge: bool = False
    ):
        super().__init__(message)
        self.retryable = retryable
        self.uncertain_charge = uncertain_charge


@dataclass(frozen=True)
class ProviderResult:
    value: JsonObject
    prompt_tokens: int
    completion_tokens: int
    model: str


class ChatModel(Protocol):
    async def complete_json(
        self,
        *,
        system: str,
        payload: JsonObject,
        max_tokens: int,
        thinking: bool = False,
    ) -> ProviderResult: ...
