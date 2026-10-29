import pytest

from app.core.config import Settings
from app.ingestion.pgvector_repository import lexical_tsquery
from app.languages.codes import Language, parse_language
from app.languages.detect import detect
from app.languages.normalize import fold, nfc
from app.legal.topics import tokens


def test_fold_strips_tone_marks_dots_and_hausa_hooks() -> None:
    assert fold("Ẹ̀tọ́ ọmọnìyàn") == "Eto omoniyan"
    assert fold("haƙƙi ɗan ɓarawo ƴanci") == "hakki dan barawo yanci"
    assert fold("ịkịkẹ ụlọ ṅ") == "ikike ulo n"


def test_nfc_gives_one_stored_form() -> None:
    assert nfc("ẹ́") == nfc("ẹ́")


def test_folded_words_are_not_split_into_fragments() -> None:
    assert tokens("haƙƙi") == ["hakki"]
    assert lexical_tsquery("haƙƙi") == "hakki:*"


def test_english_tokens_and_keyword_query_are_unchanged() -> None:
    assert tokens("Can police search my phone’s data?") == tokens(
        "Can police search my phones data?"
    )
    assert lexical_tsquery("can police search my phone") == (
        "police:* | search:* | phone:*"
    )


@pytest.mark.parametrize(
    "question",
    ["Can police search my phone?", "What does Section 37 say?"],
)
def test_clear_english_needs_no_model_call(question: str) -> None:
    assert detect(question).language == Language.ENGLISH
    assert detect(question).confident


@pytest.mark.parametrize(
    ("question", "language"),
    [
        ("wetin constitution talk about police checking my phone?", Language.PIDGIN),
        ("Ṣé ọlọ́pàá lè yẹ fóònù mi wò?", Language.YORUBA),
        ("Shin 'yan sanda za su iya bincika wayata? Ina hakki na?", Language.HAUSA),
        ("Ndị uwe ojii nwere ike nyochaa ekwentị m?", Language.IGBO),
    ],
)
def test_other_languages_are_guessed_but_never_confident(
    question: str, language: Language
) -> None:
    detection = detect(question)
    assert detection.language == language
    assert not detection.confident


def test_parse_language_accepts_regions_and_rejects_unknown() -> None:
    assert parse_language("YO-NG") == Language.YORUBA
    assert parse_language("pcm") == Language.PIDGIN
    assert parse_language("fr") is None
    assert parse_language(None) is None


def test_english_is_always_an_enabled_language() -> None:
    enabled = Settings.model_validate(
        {"CHAT_LANGUAGES_ENABLED": ["yo", "en", "pcm"]}
    ).CHAT_LANGUAGES_ENABLED
    assert enabled == [Language.ENGLISH, Language.YORUBA, Language.PIDGIN]


@pytest.mark.parametrize(
    "question",
    ["Sections 37 and 33", "Explain ACJA s.9", "Explain it", "I don't know"],
)
def test_questions_without_nigerian_language_signals_are_english(
    question: str,
) -> None:
    assert detect(question) == detect("Can police search my phone?")


def test_one_pidgin_marker_outweighs_english_loanwords() -> None:
    detection = detect("wetin constitution talk about police checking my phone?")
    assert detection.language == Language.PIDGIN
    assert not detection.confident


@pytest.mark.parametrize(
    ("question", "language"),
    [
        ("sirri", Language.HAUSA),
        ("nzuzo", Language.IGBO),
        ("ipamo", Language.YORUBA),
        ("Kedu ihe Section 37 kwuru banyere nzuzo?", Language.IGBO),
        ("police fit search my phone?", Language.PIDGIN),
        ("I fit change my religion?", Language.PIDGIN),
        ("Police no fit arrest me?", Language.PIDGIN),
    ],
)
def test_content_words_and_contextual_pidgin_do_not_skip_understanding(
    question: str, language: Language
) -> None:
    detection = detect(question)
    assert detection.language == language
    assert not detection.confident


@pytest.mark.parametrize(
    "question",
    [
        "Am I fit for office?",
        "Can I keep fit in prison?",
        "I don’t know",
        "I donʼt know",
        "my right to bail",
    ],
)
def test_english_collisions_and_curly_apostrophes_remain_english(question: str) -> None:
    assert detect(question).language == Language.ENGLISH
    assert detect(question).confident
