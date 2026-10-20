"""Cheap, conservative reader-language detection.

The heuristic only needs to decide whether a question is clearly English, so
the worker can skip the translation call. Anything else is resolved by the
question-understanding model call, which also reports the language.
"""

import re
from dataclasses import dataclass

from app.languages.codes import Language
from app.languages.normalize import fold, nfc

_WORD = re.compile(r"[a-z]+")
# Letters that rarely occur outside the Nigerian languages we support.
_SIGNATURE_LETTERS: dict[Language, frozenset[str]] = {
    Language.HAUSA: frozenset("ɓɗƙƴƁƊƘƳ"),
    Language.IGBO: frozenset("ịụṅỊỤṄ"),
    Language.YORUBA: frozenset("ẹọṣẸỌṢ"),
}
# Frequent function words. Small on purpose: false positives cost a model call,
# false negatives skip translation, so English words never appear here.
_LEXICONS: dict[Language, frozenset[str]] = {
    Language.PIDGIN: frozenset(
        "wetin dey abeg una wey na oga dem don sabi pikin wahala comot "
        "abi sef shey wan go fit make e im waka chop".split()
    ),
    Language.YORUBA: frozenset(
        "ni ti se je ati mo o won kini bawo nibo eto ofin olopa ijoba "
        "omo ile ko si fun lati wa".split()
    ),
    Language.HAUSA: frozenset(
        "da ba ne ce shi ita su mu ku wannan yaya menene ina akwai "
        "hakki doka yan sanda gwamnati kotu zan iya".split()
    ),
    Language.IGBO: frozenset(
        "na nke ka ya ha anyi unu gini olee ebe ikike iwu ndi uwe "
        "ochie gomenti nwere bu ga enwe".split()
    ),
}
# Words that collide with English ("e", "make", "go", "na") are ignored when
# deciding that a question is English.
_ENGLISH = frozenset(
    "the a an is are was were do does did can could should would will what "
    "which who when where why how of to in on for with my your police "
    "section constitution right rights law court arrest search".split()
)


@dataclass(frozen=True)
class Detection:
    language: Language | None
    confident: bool


def detect(text: str) -> Detection:
    """Return a language guess; ``confident`` only when no model call is needed."""
    composed = nfc(text)
    for language, letters in _SIGNATURE_LETTERS.items():
        if any(ch in letters for ch in composed):
            return Detection(language, confident=False)
    words = _WORD.findall(fold(composed).lower())
    if not words:
        return Detection(None, confident=False)
    scores = {
        language: sum(word in lexicon for word in words)
        for language, lexicon in _LEXICONS.items()
    }
    best, hits = max(scores.items(), key=lambda item: item[1])
    english = sum(word in _ENGLISH for word in words)
    if hits >= 2 and hits >= english:
        return Detection(best, confident=False)
    if hits == 0 and english:
        return Detection(Language.ENGLISH, confident=True)
    if english >= 2 * hits + 2:
        return Detection(Language.ENGLISH, confident=True)
    return Detection(best if hits else None, confident=False)
