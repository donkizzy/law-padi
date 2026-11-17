"""Typed stage outcomes and diagnostics retained while a run is processed."""

from dataclasses import dataclass, field
from enum import StrEnum

from app.chat.evidence_packet import Prepared
from app.chat.llm.protocol import JsonObject, ProviderResult
from app.chat.schemas import ExplanationAnswer
from app.languages.codes import Language


class ValidationStage(StrEnum):
    PREPARATION = "preparation"
    GENERATION = "generation"
    GENERATION_SCHEMA = "generation_schema"
    DETERMINISTIC = "deterministic"
    VERIFICATION = "verification"


@dataclass
class RunState:
    started: float
    telemetry: JsonObject = field(default_factory=dict)
    prepared: Prepared | None = None
    validation_stage: ValidationStage = ValidationStage.PREPARATION
    expected_verdict_count: int | None = None
    verifier_verdict_count: int | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def add_usage(self, result: ProviderResult) -> None:
        self.prompt_tokens += result.prompt_tokens
        self.completion_tokens += result.completion_tokens


@dataclass(frozen=True)
class Understood:
    question_language: Language | None
    answer_language: Language


@dataclass(frozen=True)
class Generated:
    answer: ExplanationAnswer
    provider_result: ProviderResult


@dataclass(frozen=True)
class Translated:
    answer: ExplanationAnswer
