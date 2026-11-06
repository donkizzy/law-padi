from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.api.routes import search
from app.chat import search_language
from app.chat.budget import BudgetExhausted
from app.chat.provider import ProviderError, ProviderResult
from app.core.config import settings
from app.languages.codes import Language
from app.legal.evidence import NOT_IN_CONSTITUTION_MESSAGE, message_code
from app.legal.models import GenerationReservation

pytest_plugins = ["tests.api.routes.test_legal_search"]

_YORUBA = "Kí ni Section 37 sọ nípa ìpamọ́ ẹni?"


class SearchProvider:
    def __init__(
        self,
        *,
        language: str = "yo",
        english: str = "What does Section 37 say about privacy?",
        fails: bool = False,
    ):
        self.language = language
        self.english = english
        self.fails = fails
        self.calls = 0

    async def complete_json(
        self,
        *,
        system: str,
        payload: dict[str, Any],
        max_tokens: int,
        thinking: bool = False,
    ) -> ProviderResult:
        assert system == search_language.UNDERSTANDING_SYSTEM
        assert max_tokens == settings.SEARCH_TRANSLATION_MAX_OUTPUT_TOKENS
        self.calls += 1
        if self.fails:
            raise ProviderError("DeepSeek is temporarily unavailable")
        return ProviderResult(
            value={"language": self.language, "english_question": self.english},
            prompt_tokens=50,
            completion_tokens=20,
            model="test",
        )


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> SearchProvider:
    fake = SearchProvider()
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_KILL_SWITCH", False)
    monkeypatch.setattr(
        settings, "CHAT_LANGUAGES_ENABLED", [Language.ENGLISH, Language.YORUBA]
    )
    monkeypatch.setattr(settings, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(search_language, "DeepSeekClient", lambda: fake)
    return fake


def test_yoruba_search_is_ranked_in_english_and_cached(
    db: Session, provider: SearchProvider
) -> None:
    first = search_language.search_query(_YORUBA)
    second = search_language.search_query(_YORUBA)
    assert first == search_language.SearchQuery(
        "What does Section 37 say about privacy?", Language.YORUBA, translated=True
    )
    assert second == first
    assert provider.calls == 1
    reservation = db.exec(
        select(GenerationReservation).where(
            GenerationReservation.purpose == "search_understanding"
        )
    ).first()
    assert reservation is not None
    assert reservation.run_id is None
    assert reservation.status == "settled"


def test_english_and_long_queries_make_no_call(provider: SearchProvider) -> None:
    assert search_language.search_query("Can police search my phone?") == (
        search_language.SearchQuery("Can police search my phone?", Language.ENGLISH)
    )
    long_query = "ẹ " * settings.SEARCH_TRANSLATION_MAX_CHARS
    assert not search_language.search_query(long_query).translated
    assert provider.calls == 0


def test_provider_failure_searches_the_query_as_typed(
    provider: SearchProvider,
) -> None:
    provider.fails = True
    assert search_language.search_query(_YORUBA) == search_language.SearchQuery(
        _YORUBA, Language.YORUBA
    )
    # Failures are not cached; the next search tries again.
    provider.fails = False
    assert search_language.search_query(_YORUBA).translated


def test_exhausted_budget_searches_the_query_as_typed(
    provider: SearchProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    def exhausted(*_args: Any, **_kwargs: Any) -> None:
        raise BudgetExhausted("Daily generation budget is exhausted")

    monkeypatch.setattr(search_language, "reserve", exhausted)
    assert not search_language.search_query(_YORUBA).translated
    assert provider.calls == 0


def test_search_route_reports_the_language_and_english_query(
    client: TestClient, corpus, provider: SearchProvider, monkeypatch
) -> None:
    assert corpus
    monkeypatch.setattr(
        search,
        "_query_embedding_provider",
        lambda _: pytest.fail("Exact lookup must not embed"),
    )
    body = client.post("/api/v1/legal/search", json={"query": _YORUBA}).json()
    assert provider.calls == 1
    assert body["outcome"] == "exact"
    assert body["data"][0]["citation"] == "Section 37"
    assert body["query_language"] == "yo"
    assert body["searched_query"] == "What does Section 37 say about privacy?"


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("CHAT_ENABLED", False),
        ("CHAT_GENERATION_ENABLED", False),
        ("CHAT_GENERATION_KILL_SWITCH", True),
    ],
)
def test_search_route_keeps_query_local_when_explanations_are_disabled(
    client: TestClient,
    corpus,
    db: Session,
    provider: SearchProvider,
    monkeypatch: pytest.MonkeyPatch,
    setting: str,
    value: bool,
) -> None:
    assert corpus
    monkeypatch.setattr(settings, setting, value)
    monkeypatch.setattr(
        search,
        "_query_embedding_provider",
        lambda _: pytest.fail("Exact lookup must not embed"),
    )
    response = client.post("/api/v1/legal/search", json={"query": _YORUBA})
    assert response.status_code == 200
    body = response.json()
    assert body["data"][0]["citation"] == "Section 37"
    assert body["query_language"] == "yo"
    assert body["searched_query"] is None
    assert provider.calls == 0
    assert db.exec(select(GenerationReservation)).first() is None


def test_search_messages_carry_stable_codes(client: TestClient, corpus) -> None:
    assert corpus
    missing = client.post("/api/v1/legal/search", json={"query": "Section 168"}).json()
    assert missing["message"] == NOT_IN_CONSTITUTION_MESSAGE
    assert missing["message_code"] == "section_not_found"
    assert missing["query_language"] == "en"
    assert missing["searched_query"] is None
    unsupported = client.post(
        "/api/v1/legal/search", json={"query": "Section 33(2)(a)(i)"}
    ).json()
    assert unsupported["message_code"] == "reference_format"
    assert message_code("A message without a code") is None
