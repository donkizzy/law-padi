"""Plain-language navigation hints for release-scoped legal search.

People rarely ask in the Constitution's own words: they ask whether police can
search a phone, not about "telegraphic communications". This module maps
everyday phrasing to section numbers so retrieval can rank the right provision
even when dense or keyword search misses it. It only steers ranking; every
returned provision is still loaded from the published release.

Section titles come from the source PDF's "Arrangement of sections" and are
navigation aids, not legal text.
"""

import difflib
import itertools
import re
from collections.abc import Collection
from dataclasses import dataclass
from functools import cache

from app.languages.normalize import fold
from app.legal.instruments import ACJA_SLUG, CONSTITUTION_SLUG, POLICE_SLUG
from app.legal.titles import catalogue_titles
from app.legal.topic_guide import Topic, load_topic_guide

_SECTION_IN_PATH = re.compile(r"\.section(\d+[a-z]?)(?=\.|$)")
_CHAPTER_IN_PATH = re.compile(r"\.chapter(\d+)(?=\.|$)")
_TOKEN = re.compile(r"[a-z0-9]+")
# A question naming a section's title outranks a broad topic match.
_TITLE_WEIGHT = 3.5
_TITLE_MIN_COVERAGE = 0.75
_TITLE_MAX_SECTIONS = 4
# Chapter IV, fundamental rights, through enforcement in Section 46.
_GUIDE = load_topic_guide()
_RIGHTS_SECTIONS = _GUIDE.rights_sections
# Police establishment and control, and legislative investigation powers.
_RIGHTS_NOISE = _GUIDE.rights_noise
# Asking what to do about a wrong is asking about enforcement (Section 46),
# even though the words themselves are all filler.
_REMEDY_INTENT = re.compile(
    r"\bwhat (?:can|should|do) (?:i|we|you|one) do\b"
    r"|\bwhere (?:can|do|should) (?:i|we) (?:go|report|complain)\b"
    r"|\bhow (?:can|do|should) (?:i|we) (?:complain|report|sue|challenge|seek)\b",
    re.I,
)

# Function words and conversational filler, including common Nigerian Pidgin.
# Topic words such as "law", "state" and "nigeria" stay meaningful.
STOPWORDS = _GUIDE.stopwords
_LEMMAS = _GUIDE.lemmas


def _stem(word: str) -> str:
    word = _LEMMAS.get(word, word)
    if len(word) > 4 and word.endswith("ies"):
        word = word[:-3] + "y"
    elif len(word) > 4 and word.endswith(("sses", "xes", "zes", "ches", "shes")):
        word = word[:-2]
    elif len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        word = word[:-1]
    for suffix in ("ing", "ied", "ed"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[: -len(suffix)] + ("y" if suffix == "ied" else "")
            if len(word) > 3 and word[-1] == word[-2] and word[-1] not in "aeioulsz":
                word = word[:-1]
            break
    # Drop a final "e" so "leave", "leaving" and "leaves" agree.
    if len(word) > 3 and word.endswith("e") and not word.endswith("ee"):
        word = word[:-1]
    return word


def tokens(text: str) -> list[str]:
    """Normalise text to comparable content tokens."""
    return [
        _stem(word)
        for word in _TOKEN.findall(fold(text).lower().replace("'", ""))
        if word not in STOPWORDS
    ]


def _same(phrase_token: str, query_token: str) -> bool:
    if phrase_token == query_token:
        return True
    shorter, longer = sorted((phrase_token, query_token), key=len)
    return len(shorter) >= 6 and longer.startswith(shorter)


def _span(phrase_tokens: list[str], query_tokens: list[str]) -> int | None:
    """Smallest window of the query containing every phrase token, in any order."""
    positions = [
        [index for index, token in enumerate(query_tokens) if _same(word, token)]
        for word in phrase_tokens
    ]
    if any(not found for found in positions):
        return None
    if len(positions) == 1:
        return 1
    return min(
        max(combo) - min(combo) + 1
        for combo in itertools.islice(itertools.product(*positions), 256)
    )


@dataclass(frozen=True)
class TopicMatch:
    slug: str
    sections: tuple[str, ...]
    score: float
    phrase: str


TOPICS = _GUIDE.topics
STATUTE_TOPICS = _GUIDE.statute_topics
_PART_TOPICS = _GUIDE.part_topics
_COMPANION_TOPICS = _GUIDE.companion_topics
COMPANIONS = _GUIDE.companions
_TITLE_CONTEXT = _GUIDE.title_context
_GENERIC_TITLES = _GUIDE.generic_titles


@cache
def _titles(instrument_slug: str = "constitution-1999") -> dict[str, dict[str, str]]:
    return {
        kind: catalogue_titles(instrument_slug, kind)
        for kind in ("sections", "chapters", "parts")
    }


def section_number(canonical_path: str) -> str | None:
    match = _SECTION_IN_PATH.search(canonical_path)
    return match.group(1) if match else None


def section_target(canonical_path: str) -> str | None:
    number = section_number(canonical_path)
    return f"{canonical_path.partition('.')[0]}:{number}" if number else None


def section_title(
    canonical_path: str, instrument_slug: str | None = None
) -> str | None:
    """Plain title for a section, or for the section containing a sub-provision."""
    slug = instrument_slug or canonical_path.partition(".")[0]
    if not canonical_path.startswith(f"{slug}."):
        return None
    number = section_number(canonical_path)
    if number is None:
        chapter = _CHAPTER_IN_PATH.search(canonical_path)
        if chapter and canonical_path.endswith(f".chapter{chapter.group(1)}"):
            return _titles(slug)["chapters"].get(chapter.group(1))
        return None
    title = _titles(slug)["sections"].get(number)
    if title is None:
        return None
    if (
        slug == "constitution-1999"
        and title.casefold() in _GENERIC_TITLES
        and number.isdigit()
    ):
        value = int(number)
        for start, end, context in _TITLE_CONTEXT:
            if start <= value <= end:
                return f"{title} ({context})"
    return title


@cache
def _vocabulary() -> frozenset[str]:
    return frozenset(
        word
        for topic in (*TOPICS, *STATUTE_TOPICS)
        for phrase in topic.phrases
        for word in tokens(phrase)
        if len(word) >= 5
    )


def _correct_typos(query_tokens: list[str]) -> list[str]:
    """Repair obvious misspellings against the guide's own vocabulary.

    Only longer words are touched, and only when exactly one guide word is a
    very close match, so ordinary words are never rewritten.
    """
    vocabulary = _vocabulary()
    corrected: list[str] = []
    for token in query_tokens:
        if len(token) >= 5 and token not in vocabulary:
            close = difflib.get_close_matches(token, vocabulary, n=2, cutoff=0.8)
            if len(close) == 1 or (
                len(close) == 2
                and difflib.SequenceMatcher(None, token, close[0]).ratio()
                - difflib.SequenceMatcher(None, token, close[1]).ratio()
                >= 0.08
            ):
                token = close[0]
        corrected.append(token)
    return corrected


def match_topics(
    query: str, *, limit: int = 3, topics: tuple[Topic, ...] = TOPICS
) -> list[TopicMatch]:
    """Rank topics by how much of the question their matched phrases explain.

    A phrase matches when all its words appear close together, in any order.
    """
    query_tokens = _correct_typos(tokens(query))
    if not query_tokens:
        return []
    matches: list[TopicMatch] = []
    for topic in topics:
        covered: set[int] = set()
        best = ""
        for phrase in topic.phrases:
            phrase_tokens = list(dict.fromkeys(tokens(phrase)))
            if not phrase_tokens:
                continue
            span = _span(phrase_tokens, query_tokens)
            # Allow one unrelated word inside a phrase ("search my house").
            if span is None or span > len(phrase_tokens) + 1:
                continue
            covered.update(
                index
                for index, token in enumerate(query_tokens)
                if any(_same(word, token) for word in phrase_tokens)
            )
            if len(phrase_tokens) >= len(tokens(best) or [""]):
                best = phrase
        if covered:
            score = len(covered) - (0.5 if topic.broad else 0.0)
            matches.append(
                TopicMatch(
                    slug=topic.slug,
                    sections=topic.sections,
                    score=score,
                    phrase=best,
                )
            )
    # Stable sort keeps the curated order for ties.
    matches.sort(key=lambda item: -item.score)
    return matches[:limit]


@cache
def _title_tokens(
    instrument_slug: str = CONSTITUTION_SLUG,
) -> tuple[tuple[str, frozenset[str]], ...]:
    return tuple(
        (
            f"{instrument_slug}:{number}",
            frozenset(
                tokens(
                    # The source repeats "Disqualifications" for different
                    # offices. Use the same contextual title the reader sees,
                    # or "governor disqualification" only matches s.183's
                    # different rule about holding another job.
                    section_title(f"{instrument_slug}.section{number}") or title
                    if title.casefold() == "disqualifications"
                    else title
                )
            ),
        )
        for number, title in _titles(instrument_slug)["sections"].items()
    )


def title_sections(
    query: str, *, instrument_slugs: Collection[str] = (CONSTITUTION_SLUG,)
) -> list[str]:
    """Sections whose own title covers the question, such as "grand kadi".

    Titles are not in the search index, so a question phrased in the
    Constitution's own words could lose to a broad topic. Only the best
    coverage counts, and a phrase shared by many titles is ignored.
    """
    query_tokens = list(dict.fromkeys(tokens(query)))
    if len(query_tokens) < 2:
        return []
    best = 0.0
    found: list[str] = []
    for number, title_tokens in itertools.chain.from_iterable(
        _title_tokens(slug) for slug in sorted(instrument_slugs)
    ):
        matched = sum(
            1
            for token in query_tokens
            if any(_same(word, token) for word in title_tokens)
        )
        coverage = matched / len(query_tokens)
        if matched < 2 or coverage < _TITLE_MIN_COVERAGE:
            continue
        if coverage > best:
            best, found = coverage, [number]
        elif coverage == best:
            found.append(number)
    return found if len(found) <= _TITLE_MAX_SECTIONS else []


def topic_sections(
    query: str, *, instrument_slugs: Collection[str] = (CONSTITUTION_SLUG,)
) -> list[tuple[str, float]]:
    """Section numbers for a query with a fusion weight for each.

    Multi-word matches are specific enough to lead the ranking; single-word
    matches only nudge it, so dense and keyword search can still win. A
    section named by several topics, or by its own title, collects each boost.
    """
    weights: dict[str, float] = {}
    matches = match_topics(query)
    # Match statutes separately so new topics cannot displace established
    # Constitution hints in the three-topic window.
    matches += match_topics(query, topics=STATUTE_TOPICS)
    for match in matches:
        weight = 2.5 if match.score >= 2 else 1.5
        for number in match.sections:
            if number.partition(":")[0] not in instrument_slugs:
                continue
            weights[number] = weights.get(number, 0.0) + weight
    for number in title_sections(query, instrument_slugs=instrument_slugs):
        weights[number] = weights.get(number, 0.0) + _TITLE_WEIGHT
    remedy = f"{CONSTITUTION_SLUG}:46"
    if (
        CONSTITUTION_SLUG in instrument_slugs
        and _REMEDY_INTENT.search(query)
        and remedy not in weights
    ):
        weights[remedy] = 1.5
    # Stable sort keeps the curated order for equal weights.
    return sorted(weights.items(), key=lambda item: -item[1])


def _is_rights_topic(match: TopicMatch) -> bool:
    return all(
        slug == CONSTITUTION_SLUG
        and number.isdigit()
        and _RIGHTS_SECTIONS[0] <= int(number) <= _RIGHTS_SECTIONS[1]
        for slug, _, number in (target.partition(":") for target in match.sections)
    )


def related_laws(
    query: str, *, instrument_slugs: Collection[str] = (CONSTITUTION_SLUG,)
) -> list[str]:
    """Other laws on the subjects a question matches, most relevant first."""
    by_slug = {topic.slug: topic for topic in TOPICS}
    laws: list[str] = []
    for match in match_topics(query):
        for law in by_slug[match.slug].related_laws:
            if (
                ACJA_SLUG in instrument_slugs
                and law.startswith("Administration of Criminal Justice Act")
            ) or (POLICE_SLUG in instrument_slugs and law.startswith("Police Act")):
                continue
            if law not in laws:
                laws.append(law)
    return laws[:3]


def demoted_sections(query: str) -> frozenset[str]:
    """Sections that share a rights question's words but not its subject.

    "Can police search my phone?" shares "police" with the sections that set
    up the police force, and "warrant" with the legislature's power to summon
    witnesses. Neither says anything about the reader's rights, so a rights
    question pushes them down unless the question is about them.
    """
    matches = match_topics(query)
    if not any(_is_rights_topic(match) for match in matches):
        return frozenset()
    named = {number for match in matches for number in match.sections}
    named.update(title_sections(query))
    return (
        frozenset(f"{CONSTITUTION_SLUG}:{number}" for number in _RIGHTS_NOISE) - named
    )


def rights_question(query: str) -> bool:
    return any(_is_rights_topic(match) for match in match_topics(query))


def companion_sections(number: str) -> tuple[str, ...]:
    return COMPANIONS.get(number, ())
