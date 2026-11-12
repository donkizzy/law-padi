"""English rendering of non-English search queries.

Search ranks English provisions, so a query that is not clearly English is
rendered in English with one budgeted call before ranking. Successful
renderings are cached per process, so repeated searches cost nothing. Any
failure, including an exhausted budget, searches the query as typed.
"""

import asyncio
import json
import logging
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Any

from sqlmodel import Session

from app.chat.budget import SEARCH_UNDERSTANDING, BudgetExhausted, reserve, settle
from app.chat.provider import DeepSeekClient, ProviderError, ProviderResult
from app.chat.translation import (
    UNDERSTANDING_SYSTEM,
    TranslationRejected,
    Understanding,
    parse_understanding,
)
from app.core.config import settings
from app.core.db import engine
from app.languages.codes import Language
from app.languages.detect import detect

_logger = logging.getLogger(__name__)
_CACHE_SIZE = 1024
_cache: OrderedDict[str, Understanding] = OrderedDict()
_cache_lock = Lock()


@dataclass(frozen=True)
class SearchQuery:
    text: str
    language: Language | None
    translated: bool = False


def _cached(query: str) -> Understanding | None:
    with _cache_lock:
        value = _cache.get(query)
        if value is not None:
            _cache.move_to_end(query)
        return value


def _remember(query: str, value: Understanding) -> None:
    with _cache_lock:
        _cache[query] = value
        _cache.move_to_end(query)
        while len(_cache) > _CACHE_SIZE:
            _cache.popitem(last=False)


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def _understand(query: str, provider: DeepSeekClient) -> Understanding | None:
    payload: dict[str, Any] = {"question": query}
    with Session(engine) as session:
        try:
            reservation = reserve(
                session,
                run_id=None,
                purpose=SEARCH_UNDERSTANDING,
                prompt_chars=len(UNDERSTANDING_SYSTEM.encode())
                + len(json.dumps(payload, ensure_ascii=False).encode())
                + 128,
                max_output_tokens=settings.SEARCH_TRANSLATION_MAX_OUTPUT_TOKENS,
            )
            session.commit()
        except BudgetExhausted:
            session.rollback()
            return None
        reservation_id = reservation.id
    result: ProviderResult | None = None
    uncertain = False
    try:
        result = asyncio.run(
            provider.complete_json(
                system=UNDERSTANDING_SYSTEM,
                payload=payload,
                max_tokens=settings.SEARCH_TRANSLATION_MAX_OUTPUT_TOKENS,
            )
        )
        return parse_understanding(result.value, query)
    except ProviderError as exc:
        uncertain = exc.uncertain_charge
        _logger.info("search_understanding_failed %s", exc)
        return None
    except TranslationRejected as exc:
        _logger.info("search_understanding_rejected %s", exc)
        return None
    finally:
        with Session(engine) as session:
            settle(
                session,
                reservation_id,
                prompt_tokens=result.prompt_tokens if result else None,
                completion_tokens=result.completion_tokens if result else None,
                uncertain=uncertain,
            )
            session.commit()


def search_query(
    query: str,
    provider: DeepSeekClient | None = None,
    *,
    may_translate: Callable[[], bool] | None = None,
) -> SearchQuery:
    """The text to rank with, and the language the reader searched in.

    ``may_translate`` is asked only before a paid call, so cached renderings
    and confidently detected queries never count against the caller.
    """
    if len(settings.CHAT_LANGUAGES_ENABLED) == 1:
        return SearchQuery(query, None)
    detection = detect(query)
    if (
        detection.confident
        or len(query) > settings.SEARCH_TRANSLATION_MAX_CHARS
        or not settings.DEEPSEEK_API_KEY
        or not settings.explanations_enabled
    ):
        return SearchQuery(query, detection.language)
    understood = _cached(query)
    if understood is None:
        if may_translate is not None and not may_translate():
            return SearchQuery(query, detection.language)
        understood = _understand(query, provider or DeepSeekClient())
        if understood is None:
            return SearchQuery(query, detection.language)
        _remember(query, understood)
    language = understood.language or detection.language
    if language == Language.ENGLISH:
        return SearchQuery(query, language)
    return SearchQuery(understood.english_question, language, translated=True)
