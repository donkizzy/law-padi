"""Reader-language edges around the English evidence pipeline.

Retrieval, drafting and both grounding checks run in English. A question in
another language is rendered in English first, and a verified English answer
is translated afterwards. Every translation is checked here; any failure falls
back to the English answer rather than failing it.
"""

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from app.chat.prompts import judge, translation, understanding
from app.chat.provider import ProviderResult
from app.chat.schemas import AnswerTranslation, ExplanationAnswer, ExplanationBlock
from app.languages.codes import DISPLAY_NAMES, Language, parse_language
from app.languages.detect import detect
from app.legal.instruments import law_mentions

# Languages without native review get an independent meaning check.
JUDGED_LANGUAGES = frozenset({Language.YORUBA, Language.HAUSA, Language.IGBO})
_GLOSSARY_DIR = Path(__file__).resolve().parents[1] / "languages" / "data"
_NUMBER = re.compile(r"\d+[A-Za-z]?")
_QUOTE = re.compile(r"[\"“”«»]")
_LIST_ITEM = re.compile(r"^- ", re.M)
_HEADING = "What you can do:"
# A faithful translation is rarely under half or over four times as long.
_MIN_RATIO = 0.4
_MAX_RATIO = 4.0

Call = Callable[[str, str, dict[str, Any], int], Awaitable[ProviderResult]]


class TranslationRejected(ValueError):
    pass


@dataclass(frozen=True)
class Understanding:
    language: Language | None
    english_question: str


@cache
def glossary(language: Language) -> tuple[str | None, tuple[dict[str, Any], ...]]:
    path = _GLOSSARY_DIR / f"glossary-{language.value}.json"
    if not path.exists():
        return None, ()
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("version"), tuple(data.get("terms", []))


def _relevant_terms(language: Language, text: str) -> dict[str, str]:
    """Only the terms used in this answer, so each call stays small."""
    lowered = text.casefold()
    _, terms = glossary(language)
    selected: dict[str, str] = {}
    for term in terms:
        english = str(term.get("en", ""))
        if not english:
            continue
        if english == _HEADING or re.search(
            rf"(?<!\w){re.escape(english.casefold())}(?!\w)", lowered
        ):
            selected[english] = english if term.get("locked") else term["target"]
    return selected


def parse_understanding(value: dict[str, Any], question: str) -> Understanding:
    english = value.get("english_question")
    if not isinstance(english, str) or not english.strip():
        raise TranslationRejected("The English question is missing")
    english = english.strip()
    if len(english) > 2000:
        raise TranslationRejected("The English question is too long")
    if not set(_NUMBER.findall(question)) <= set(_NUMBER.findall(english)):
        raise TranslationRejected("The English question changed a number")
    language = parse_language(str(value.get("language") or ""))
    return Understanding(language=language, english_question=english)


async def understand(call: Call, question: str, max_tokens: int) -> Understanding:
    result = await call(
        "understanding",
        understanding.TEXT,
        {"question": question},
        max_tokens,
    )
    return parse_understanding(result.value, question)


def _strings(value: Any, count: int, field: str) -> list[str]:
    if not isinstance(value, list) or len(value) != count:
        raise TranslationRejected(f"The translation has the wrong number of {field}")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise TranslationRejected(f"The translation has an empty item in {field}")
    return [item.strip() for item in value]


def _check_text(english: str, translated: str, language: Language) -> None:
    if set(_NUMBER.findall(english)) != set(_NUMBER.findall(translated)):
        raise TranslationRejected("The translation dropped or changed a number")
    english_laws = {mention.slug for mention in law_mentions(english)}
    if not english_laws <= {mention.slug for mention in law_mentions(translated)}:
        raise TranslationRejected("The translation dropped a law name")
    if _QUOTE.search(translated) and not _QUOTE.search(english):
        raise TranslationRejected("The translation added quotation marks")
    if len(_LIST_ITEM.findall(english)) != len(_LIST_ITEM.findall(translated)):
        raise TranslationRejected("The translation changed the list items")
    ratio = len(translated) / max(len(english), 1)
    if not _MIN_RATIO <= ratio <= _MAX_RATIO:
        raise TranslationRejected("The translation length is implausible")
    if language in JUDGED_LANGUAGES and detect(translated).confident:
        raise TranslationRejected("The translation is still in English")


def check_translation(
    answer: ExplanationAnswer,
    value: dict[str, Any],
    language: Language,
    *,
    model: str,
) -> AnswerTranslation:
    """Deterministic checks; raises TranslationRejected on any failure."""
    blocks = _strings(value.get("blocks"), len(answer.blocks), "blocks")
    missing = _strings(
        value.get("missing_facts", []), len(answer.missing_facts), "missing_facts"
    )
    follow_ups = _strings(
        value.get("follow_up_questions", []),
        len(answer.follow_up_questions),
        "follow_up_questions",
    )
    for source, translated in zip(answer.blocks, blocks, strict=True):
        _check_text(source.text, translated, language)
    for source_text, translated in zip(
        [*answer.missing_facts, *answer.follow_up_questions],
        [*missing, *follow_ups],
        strict=True,
    ):
        _check_text(source_text, translated, language)
    version, _ = glossary(language)
    return AnswerTranslation(
        language=language,
        blocks=[
            ExplanationBlock(text=text, evidence_ids=source.evidence_ids)
            for source, text in zip(answer.blocks, blocks, strict=True)
        ],
        missing_facts=missing,
        follow_up_questions=follow_ups,
        model=model,
        prompt_version=translation.VERSION,
        glossary_version=version,
    )


def check_judgment(value: dict[str, Any], count: int) -> None:
    checks = value.get("checks")
    if not isinstance(checks, list) or len(checks) != count:
        raise TranslationRejected("The translation check is incomplete")
    for index, row in enumerate(checks):
        if not isinstance(row, dict) or row.get("index") != index:
            raise TranslationRejected("The translation check is out of order")
        if row.get("language_matches") is not True:
            raise TranslationRejected(
                "A translated item is not in the requested language"
            )
        if row.get("meaning_preserved") is not True:
            raise TranslationRejected("A translated block changed the meaning")
        if row.get("conditions_preserved") is not True:
            raise TranslationRejected("A translated block dropped a condition")


async def translate_answer(
    call: Call,
    answer: ExplanationAnswer,
    language: Language,
    *,
    max_tokens: int,
    judge_max_tokens: int,
) -> AnswerTranslation:
    texts = [
        *(block.text for block in answer.blocks),
        *answer.missing_facts,
        *answer.follow_up_questions,
    ]
    payload: dict[str, Any] = {
        "glossary": _relevant_terms(language, "\n".join(texts)),
        "blocks": [block.text for block in answer.blocks],
        "missing_facts": answer.missing_facts,
        "follow_up_questions": answer.follow_up_questions,
    }
    # Repair at most once. Every call still passes through the worker's spend
    # reservation and deadline; provider failures/uncertain charges are not retried.
    for attempt in range(2):
        result = await call(
            "translation", translation.render(language), payload, max_tokens
        )
        try:
            translated = check_translation(
                answer, result.value, language, model=result.model
            )
            if language in JUDGED_LANGUAGES:
                target_texts = [
                    *(block.text for block in translated.blocks),
                    *translated.missing_facts,
                    *translated.follow_up_questions,
                ]
                judged = await call(
                    "translation_check",
                    judge.TEXT,
                    {
                        "language": DISPLAY_NAMES[language],
                        "pairs": [
                            {"index": index, "english": source, "translated": target}
                            for index, (source, target) in enumerate(
                                zip(texts, target_texts, strict=True)
                            )
                        ],
                    },
                    judge_max_tokens,
                )
                check_judgment(judged.value, len(texts))
            return translated
        except TranslationRejected as error:
            if attempt:
                raise
            payload = {**payload, "revision_reason": str(error)}
    raise AssertionError("Translation repair loop did not terminate")
