import asyncio
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.chat import translation, worker
from app.chat.llm.protocol import ProviderError, ProviderResult
from app.chat.prompts import judge, understanding
from app.chat.schemas import ExplanationAnswer, ExplanationBlock
from app.core.config import settings
from app.languages.codes import Language
from app.legal.models import ConversationMessage, GenerationRun
from app.main import app

_ENGLISH_BLOCK = "The Constitution protects privacy."
_YORUBA_BLOCK = "Constitution ṣe ààbò fún ìpamọ́ ẹni."
_YORUBA_FOLLOW_UP = "Ṣé ọlọ́pàá lè yẹ fóònù mi wò lábẹ́ Section 37?"


class LanguageProvider:
    """Routes each call by its system prompt, like the real pipeline."""

    def __init__(
        self,
        *,
        language: str = "yo",
        english_question: str = "What does Section 37 say about privacy?",
        translated_blocks: list[str] | None = None,
        meaning_preserved: bool = True,
        understanding_fails: bool = False,
    ):
        self.language = language
        self.english_question = english_question
        self.translated_blocks = translated_blocks or [_YORUBA_BLOCK]
        self.meaning_preserved = meaning_preserved
        self.understanding_fails = understanding_fails
        self.purposes: list[str] = []
        self.payloads: list[dict[str, Any]] = []

    async def complete_json(
        self,
        *,
        system: str,
        payload: dict[str, Any],
        max_tokens: int,
        thinking: bool = False,
    ) -> ProviderResult:
        assert max_tokens > 0
        self.payloads.append(payload)
        value: dict[str, Any]
        if system == understanding.TEXT:
            self.purposes.append("understanding")
            if self.understanding_fails:
                raise ProviderError("DeepSeek is temporarily unavailable")
            value = {
                "language": self.language,
                "english_question": self.english_question,
            }
        elif system.startswith("You translate"):
            self.purposes.append("translation")
            value = {
                "blocks": self.translated_blocks,
                "missing_facts": [],
                "follow_up_questions": [_YORUBA_FOLLOW_UP]
                * len(payload["follow_up_questions"]),
            }
        elif system == judge.TEXT:
            self.purposes.append("translation_check")
            value = {
                "checks": [
                    {
                        "index": pair["index"],
                        "back_translation": _ENGLISH_BLOCK,
                        "language_matches": True,
                        "meaning_preserved": self.meaning_preserved,
                        "conditions_preserved": True,
                    }
                    for pair in payload["pairs"]
                ]
            }
        elif "verdicts" in system:
            self.purposes.append("verification")
            value = {
                "verdicts": [
                    {
                        "index": index,
                        "supported": True,
                        "qualifications_preserved": True,
                        "answers_question": True,
                    }
                    for index in range(len(payload["blocks"]))
                ]
            }
        else:
            self.purposes.append("generation")
            value = {
                "direct_answer": "explain",
                "blocks": [{"text": _ENGLISH_BLOCK, "evidence_ids": ["E1"]}],
                "missing_facts": [],
                "follow_up_questions": ["Can police search my phone under Section 37?"],
            }
        return ProviderResult(
            value=value, prompt_tokens=100, completion_tokens=40, model="test"
        )


def _ask(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    provider: LanguageProvider,
    question: str,
    *,
    languages: list[Language],
    answer_language: str | None = None,
) -> tuple[ConversationMessage, ConversationMessage]:
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_LANGUAGES_ENABLED", languages)
    body: dict[str, Any] = {"question": question, "idempotency_key": "one"}
    if answer_language:
        body["answer_language"] = answer_language
    with TestClient(app) as client:
        conversation = client.post("/api/v1/conversations", json={}).json()
        accepted = client.post(
            f"/api/v1/conversations/{conversation['id']}/messages", json=body
        )
        assert accepted.status_code == 202, accepted.text
        run_id = UUID(accepted.json()["run_id"])
        assert worker._claim_run("test-worker") == run_id
        asyncio.run(worker.process_run(run_id, "test-worker", provider))
    db.expire_all()
    run = db.get(GenerationRun, run_id)
    assert run is not None
    question_message = db.get(ConversationMessage, run.user_message_id)
    answer_message = db.get(ConversationMessage, run.assistant_message_id)
    assert question_message is not None and answer_message is not None
    return question_message, answer_message


@pytest.mark.usefixtures("corpus")
def test_yoruba_question_is_answered_in_english_then_translated(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = LanguageProvider()
    question, answer = _ask(
        db,
        monkeypatch,
        provider,
        "Kí ni Section 37 sọ nípa ìpamọ́ ẹni?",
        languages=[Language.ENGLISH, Language.YORUBA],
    )
    assert provider.purposes == [
        "understanding",
        "generation",
        "verification",
        "translation",
        "translation_check",
    ]
    # Retrieval and drafting saw the English question; the reader's wording stays.
    assert question.content == "Kí ni Section 37 sọ nípa ìpamọ́ ẹni?"
    assert question.detected_language == "yo"
    assert question.english_text == "What does Section 37 say about privacy?"
    assert provider.payloads[1]["question"] == question.english_text
    content = answer.answer_content
    assert content is not None
    assert content["outcome"] == "completed"
    assert content["question_language"] == "yo"
    assert content["answer_language"] == "yo"
    assert content["blocks"][0]["text"] == _ENGLISH_BLOCK
    assert answer.content == _ENGLISH_BLOCK
    translated = content["translation"]
    assert translated["language"] == "yo"
    assert translated["blocks"] == [
        {"text": _YORUBA_BLOCK, "evidence_ids": ["E1"], "quotation": None}
    ]
    assert translated["follow_up_questions"] == [_YORUBA_FOLLOW_UP]
    assert translated["glossary_version"] == "glossary-yo-v1"
    assert answer.validation_result is not None
    assert answer.validation_result["translation"] == "completed"


@pytest.mark.usefixtures("corpus")
def test_failed_meaning_check_keeps_the_english_answer(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, answer = _ask(
        db,
        monkeypatch,
        LanguageProvider(meaning_preserved=False),
        "Kí ni Section 37 sọ nípa ìpamọ́ ẹni?",
        languages=[Language.ENGLISH, Language.YORUBA],
    )
    content = answer.answer_content
    assert content is not None
    assert content["outcome"] == "completed"
    assert content["answer_language"] == "yo"
    assert content["translation"] is None
    assert answer.validation_result is not None
    assert answer.validation_result["translation"] == "fallback"
    assert "meaning" in answer.validation_result["translation_reason"]


@pytest.mark.usefixtures("corpus")
def test_failed_understanding_falls_back_to_the_original_question(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = LanguageProvider(understanding_fails=True)
    question, answer = _ask(
        db,
        monkeypatch,
        provider,
        "Kí ni Section 37 sọ nípa ìpamọ́ ẹni?",
        languages=[Language.ENGLISH, Language.YORUBA],
    )
    assert question.english_text is None
    # The letter signature still identifies Yorùbá, so the answer is translated.
    assert question.detected_language == "yo"
    assert answer.answer_content is not None
    assert answer.answer_content["outcome"] == "completed"
    assert answer.answer_content["translation"]["language"] == "yo"
    assert answer.validation_result is not None
    assert answer.validation_result["understanding"] == "fallback"


@pytest.mark.usefixtures("corpus")
def test_english_only_deployments_make_no_language_calls(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = LanguageProvider()
    question, answer = _ask(
        db,
        monkeypatch,
        provider,
        "Kí ni Section 37 sọ nípa ìpamọ́ ẹni?",
        languages=[Language.ENGLISH],
        answer_language="yo",
    )
    assert provider.purposes == ["generation", "verification"]
    assert question.detected_language is None
    assert question.english_text is None
    assert answer.answer_content is not None
    assert answer.answer_content["answer_language"] == "en"
    assert answer.answer_content["translation"] is None


@pytest.mark.usefixtures("corpus")
def test_explicit_answer_language_translates_an_english_question(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = LanguageProvider()
    question, answer = _ask(
        db,
        monkeypatch,
        provider,
        "What does Section 37 say?",
        languages=[Language.ENGLISH, Language.YORUBA],
        answer_language="yo",
    )
    # Clear English skips the understanding call.
    assert provider.purposes[0] == "generation"
    assert question.detected_language == "en"
    assert answer.answer_content is not None
    assert answer.answer_content["question_language"] == "en"
    assert answer.answer_content["translation"]["language"] == "yo"


@pytest.mark.usefixtures("corpus")
def test_unknown_answer_language_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_GENERATION_ENABLED", True)
    with TestClient(app) as client:
        conversation = client.post("/api/v1/conversations", json={}).json()
        response = client.post(
            f"/api/v1/conversations/{conversation['id']}/messages",
            json={
                "question": "Section 37",
                "idempotency_key": "one",
                "answer_language": "fr",
            },
        )
    assert response.status_code == 422


@pytest.mark.usefixtures("corpus")
def test_capabilities_and_conversations_report_languages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "CHAT_ENABLED", True)
    monkeypatch.setattr(
        settings, "CHAT_LANGUAGES_ENABLED", [Language.ENGLISH, Language.PIDGIN]
    )
    with TestClient(app) as client:
        capabilities = client.get("/api/v1/conversations/capabilities").json()
        conversation = client.post(
            "/api/v1/conversations", json={"preferred_language": "pcm"}
        ).json()
    assert capabilities["answer_languages"] == ["en", "pcm"]
    assert capabilities["supported_languages"] == ["English", "Naijá (Pidgin)"]
    assert conversation["preferred_language"] == "pcm"


def _answer(*blocks: str, follow_ups: tuple[str, ...] = ()) -> ExplanationAnswer:
    return ExplanationAnswer(
        outcome="completed",
        blocks=[ExplanationBlock(text=text, evidence_ids=["E1"]) for text in blocks],
        follow_up_questions=list(follow_ups),
    )


def _translate(
    answer: ExplanationAnswer, blocks: list[str], language: Language = Language.YORUBA
) -> None:
    translation.check_translation(
        answer,
        {
            "blocks": blocks,
            "missing_facts": [],
            "follow_up_questions": ["?"] * len(answer.follow_up_questions),
        },
        language,
        model="test",
    )


def test_translation_keeps_numbers_law_names_and_lists() -> None:
    english = _answer(
        "Section 35 of the Constitution limits detention:\n- 24 hours\n- 48 hours"
    )
    _translate(
        english,
        ["Section 35 ti Constitution dín àtìmọ́lé kù:\n- wákàtí 24\n- wákàtí 48"],
    )


@pytest.mark.parametrize(
    ("translated", "reason"),
    [
        ("Section 35 ti Constitution:\n- wákàtí 24\n- wákàtí 4", "number"),
        ("Section 35 ti òfin ìpìlẹ̀:\n- wákàtí 24\n- wákàtí 48", "law name"),
        ("Section 35 ti Constitution:\n- wákàtí 24 àti wákàtí 48", "list items"),
        ("Section 35 ti Constitution “dín” kù:\n- wákàtí 24\n- wákàtí 48", "quotation"),
        (
            "Section 35 of the Constitution limits detention:\n- 24 hours\n- 48 hours",
            "still in English",
        ),
    ],
)
def test_translation_checks_reject_unfaithful_output(
    translated: str, reason: str
) -> None:
    english = _answer(
        "Section 35 of the Constitution limits detention:\n- 24 hours\n- 48 hours"
    )
    with pytest.raises(translation.TranslationRejected, match=reason):
        _translate(english, [translated])


def test_translation_must_match_every_block() -> None:
    with pytest.raises(translation.TranslationRejected, match="number of blocks"):
        _translate(_answer("One.", "Two."), ["Ọ̀kan."])


def test_judgment_requires_one_passing_check_per_block() -> None:
    translation.check_judgment(
        {
            "checks": [
                {
                    "index": 0,
                    "language_matches": True,
                    "meaning_preserved": True,
                    "conditions_preserved": True,
                }
            ]
        },
        1,
    )
    with pytest.raises(translation.TranslationRejected, match="incomplete"):
        translation.check_judgment({"checks": []}, 1)
    with pytest.raises(translation.TranslationRejected, match="condition"):
        translation.check_judgment(
            {
                "checks": [
                    {
                        "index": 0,
                        "language_matches": True,
                        "meaning_preserved": True,
                        "conditions_preserved": False,
                    }
                ]
            },
            1,
        )


def test_understanding_must_keep_section_numbers() -> None:
    understood = translation.parse_understanding(
        {"language": "ha", "english_question": "What does Section 35 say?"},
        "Me sashe na 35 ke cewa?",
    )
    assert understood.language == Language.HAUSA
    with pytest.raises(translation.TranslationRejected, match="number"):
        translation.parse_understanding(
            {"language": "ha", "english_question": "What does Section 53 say?"},
            "Me sashe na 35 ke cewa?",
        )


def test_glossary_terms_are_limited_to_the_answer() -> None:
    terms = translation._relevant_terms(
        Language.YORUBA, "The Constitution protects your right to privacy."
    )
    assert terms["What you can do:"] == "Ohun tí o lè ṣe:"
    assert terms["Constitution"] == "Constitution"
    assert "right" in terms
    assert "bail" not in terms


def test_rejected_translation_is_repaired_once_and_every_text_is_judged() -> None:
    answer = _answer(_ENGLISH_BLOCK, follow_ups=("What does Section 37 say?",))
    answer.missing_facts = ["Whether you were arrested"]
    calls: list[tuple[str, dict[str, Any]]] = []

    async def call(
        purpose: str, _system: str, payload: dict[str, Any], _tokens: int
    ) -> ProviderResult:
        calls.append((purpose, payload))
        if purpose == "translation_check":
            assert len(payload["pairs"]) == 3
            assert payload["pairs"][1]["english"] == answer.missing_facts[0]
            assert payload["pairs"][2]["english"] == answer.follow_up_questions[0]
            value = {
                "checks": [
                    {
                        "index": i,
                        "language_matches": True,
                        "meaning_preserved": True,
                        "conditions_preserved": True,
                    }
                    for i in range(3)
                ]
            }
        else:
            value = {
                "blocks": [_ENGLISH_BLOCK if len(calls) == 1 else _YORUBA_BLOCK],
                "missing_facts": ["Bóyá wọ́n ti mú ọ"],
                "follow_up_questions": ["Kí ni Section 37 sọ?"],
            }
        return ProviderResult(
            value=value, model="test", prompt_tokens=10, completion_tokens=10
        )

    result = asyncio.run(
        translation.translate_answer(
            call, answer, Language.YORUBA, max_tokens=1000, judge_max_tokens=1000
        )
    )
    assert result.blocks[0].text == _YORUBA_BLOCK
    assert [purpose for purpose, _ in calls] == [
        "translation",
        "translation",
        "translation_check",
    ]
    assert "still in English" in calls[1][1]["revision_reason"]


def test_wrong_language_or_unchecked_conditions_are_never_accepted() -> None:
    with pytest.raises(translation.TranslationRejected, match="requested language"):
        translation.check_judgment(
            {
                "checks": [
                    {
                        "index": 0,
                        "language_matches": False,
                        "meaning_preserved": True,
                        "conditions_preserved": True,
                    }
                ]
            },
            1,
        )
    with pytest.raises(translation.TranslationRejected, match="number"):
        _translate(
            _answer("Section 35 of the Constitution protects liberty."),
            ["Section 35 ti Constitution ṣe ààbò fún òmìnira fún 48 wákàtí."],
        )


def test_translation_deadline_preserves_verified_english(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def slow_translation(*_args: Any, **_kwargs: Any) -> None:
        await asyncio.sleep(1)

    monkeypatch.setattr(worker, "translate_answer", slow_translation)
    monkeypatch.setattr(worker, "_emit_progress", lambda *_args: None)
    answer = _answer(_ENGLISH_BLOCK)
    telemetry: dict[str, Any] = {}
    asyncio.run(
        worker._translate(
            LanguageProvider(),
            UUID(int=0),
            answer,
            Language.YORUBA,
            telemetry,
            timeout_seconds=0.001,
        )
    )
    assert answer.blocks[0].text == _ENGLISH_BLOCK
    assert answer.translation is None
    assert telemetry["translation"] == "fallback"
    assert telemetry["translation_reason"] == "Translation timed out"
