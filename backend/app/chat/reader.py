"""Question understanding and checked reader-language translation stages."""

import asyncio
import time
import uuid
from dataclasses import dataclass

from sqlmodel import Session

from app.chat import runs
from app.chat.budget import BudgetExhausted
from app.chat.llm import budgeted
from app.chat.llm.protocol import ChatModel, JsonObject, ProviderError, ProviderResult
from app.chat.schemas import ExplanationAnswer
from app.chat.translation import TranslationRejected, translate_answer, understand
from app.core.config import settings
from app.core.db import engine
from app.languages.codes import Language, parse_language
from app.languages.detect import detect
from app.legal.models import (
    ConversationMessage,
    GenerationRun,
)


@dataclass(frozen=True)
class ReaderQuestion:
    message_id: uuid.UUID
    question: str
    detected_language: str | None
    answer_language: str | None
    explains_selected_provision: bool


def reader_question(run_id: uuid.UUID) -> ReaderQuestion:
    with Session(engine) as session:
        run = session.get(GenerationRun, run_id)
        message = session.get(ConversationMessage, run.user_message_id) if run else None
        if run is None or message is None:
            raise runs.RunNotFound("Generation run was not found")
        return ReaderQuestion(
            message_id=message.id,
            question=message.content,
            detected_language=message.detected_language,
            answer_language=run.answer_language,
            explains_selected_provision=run.selected_provision_version_id is not None,
        )


def record_understanding(
    message_id: uuid.UUID, language: Language | None, english_text: str | None
) -> None:
    with Session(engine) as session:
        message = session.get(ConversationMessage, message_id)
        if message is None:
            return
        message.detected_language = language.value if language else "other"
        message.english_text = english_text
        session.add(message)
        session.commit()


async def reader_languages(
    provider: ChatModel,
    run_id: uuid.UUID,
    reader: ReaderQuestion,
    telemetry: JsonObject,
) -> tuple[Language | None, Language]:
    """Return the question's language and the language to answer in.

    A question that is not clearly English is rendered in English once, before
    retrieval, and stored so retries and follow-ups reuse it. Nothing changes
    while English is the only enabled language.
    """
    enabled = settings.CHAT_LANGUAGES_ENABLED
    explicit = parse_language(reader.answer_language)
    if explicit not in enabled:
        explicit = None
    language = parse_language(reader.detected_language)
    if (
        reader.detected_language is None
        and not reader.explains_selected_provision
        and len(enabled) > 1
    ):
        detection = detect(reader.question)
        language = detection.language
        english: str | None = None
        if not detection.confident:

            async def call(
                purpose: str, system: str, payload: JsonObject, max_tokens: int
            ) -> ProviderResult:
                return await budgeted.call(
                    provider, run_id, purpose, system, payload, max_tokens=max_tokens
                )

            try:
                understood = await understand(
                    call, reader.question, settings.DEEPSEEK_MAX_OUTPUT_TOKENS
                )
            except (ProviderError, TranslationRejected) as exc:
                # Retrieval still runs on the original wording.
                telemetry["understanding"] = "fallback"
                telemetry["understanding_reason"] = str(exc)[:200]
            else:
                telemetry["understanding"] = "completed"
                language = understood.language
                if language != Language.ENGLISH:
                    english = understood.english_question
        await asyncio.to_thread(
            record_understanding, reader.message_id, language, english
        )
    telemetry["question_language"] = language.value if language else None
    target = explicit or (language if language in enabled else Language.ENGLISH)
    return language, target


async def translate(
    provider: ChatModel,
    run_id: uuid.UUID,
    answer: ExplanationAnswer,
    language: Language,
    telemetry: JsonObject,
    *,
    timeout_seconds: float = 60.0,
) -> None:
    """Attach a checked translation; on any failure the English answer stands."""

    async def call(
        purpose: str, system: str, payload: JsonObject, max_tokens: int
    ) -> ProviderResult:
        return await budgeted.call(
            provider, run_id, purpose, system, payload, max_tokens=max_tokens
        )

    await asyncio.to_thread(runs.emit_progress, run_id, "translation.started")
    started = time.perf_counter()
    try:
        async with asyncio.timeout(timeout_seconds):
            answer.translation = await translate_answer(
                call,
                answer,
                language,
                max_tokens=settings.TRANSLATION_MAX_OUTPUT_TOKENS,
                judge_max_tokens=settings.DEEPSEEK_VERIFIER_MAX_OUTPUT_TOKENS,
            )
    except (ProviderError, BudgetExhausted, ValueError, TimeoutError) as exc:
        telemetry["translation"] = "fallback"
        telemetry["translation_reason"] = (
            "Translation timed out" if isinstance(exc, TimeoutError) else str(exc)[:200]
        )
    else:
        telemetry["translation"] = "completed"
    telemetry["translation_ms"] = round((time.perf_counter() - started) * 1000)
