"""Validate and load the curated navigation guide once per process."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.languages.normalize import fold

_TOKEN = re.compile(r"[a-z0-9]+")

Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]
Target = Annotated[
    str,
    Field(
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*:(?:[1-9][0-9]*[a-z]?|oath-[a-z]+(?:-[a-z]+)*)$"
    ),
]
Text = Annotated[str, Field(min_length=1)]
Profile = Literal["rights", "search"]


class GuideModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TopicEntry(GuideModel):
    slug: Slug
    targets: Annotated[tuple[Target, ...], Field(min_length=1)]
    # The source guide has one ordered phrase list, without language labels.
    phrases: Annotated[tuple[Text, ...], Field(min_length=1)]
    broad: bool
    related_laws: tuple[Text, ...]
    companion_profile: Profile | None


class GuideData(GuideModel):
    constitution_topics: tuple[TopicEntry, ...]
    statute_topics: tuple[TopicEntry, ...]
    part_topics: tuple[TopicEntry, ...]
    companions: dict[Target, tuple[Target, ...]]
    companion_profiles: dict[Profile, tuple[Target, ...]]
    rights_sections: tuple[int, int]
    rights_noise: tuple[Annotated[str, Field(pattern=r"^[1-9][0-9]*$")], ...]
    title_context: tuple[tuple[int, int, Text], ...]
    generic_titles: tuple[Text, ...]
    stopwords: tuple[Text, ...]
    lemmas: dict[Text, Text]

    @model_validator(mode="after")
    def validate_guide(self) -> Self:
        entries = (*self.constitution_topics, *self.statute_topics, *self.part_topics)
        slugs = [topic.slug for topic in entries]
        if len(slugs) != len(set(slugs)):
            raise ValueError("Topic slugs must be unique across all groups")
        for topic in entries:
            if (
                topic.companion_profile is not None
                and topic.companion_profile not in self.companion_profiles
            ):
                raise ValueError(f"Missing companion profile for {topic.slug}")
        if not 0 < self.rights_sections[0] <= self.rights_sections[1]:
            raise ValueError("Invalid rights section range")
        if any(not 0 < start <= end for start, end, _ in self.title_context):
            raise ValueError("Invalid title context range")
        return self


@dataclass(frozen=True)
class Topic:
    slug: str
    sections: tuple[str, ...]
    phrases: tuple[str, ...]
    broad: bool = False
    related_laws: tuple[str, ...] = ()


@dataclass(frozen=True)
class PreparedPhrase:
    text: str
    tokens: tuple[str, ...]
    token_count: int


def prepare_phrase(
    text: str, stopwords: frozenset[str], lemmas: Mapping[str, str]
) -> PreparedPhrase:
    words = tokenize(text, stopwords, lemmas)
    return PreparedPhrase(text, tuple(dict.fromkeys(words)), len(words))


def stem(word: str, lemmas: Mapping[str, str]) -> str:
    word = lemmas.get(word, word)
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


def tokenize(
    text: str, stopwords: frozenset[str], lemmas: Mapping[str, str]
) -> list[str]:
    """Normalise text to comparable content tokens."""
    return [
        stem(word, lemmas)
        for word in _TOKEN.findall(fold(text).lower().replace("'", ""))
        if word not in stopwords
    ]


@dataclass(frozen=True)
class TopicGuide:
    topics: tuple[Topic, ...]
    statute_topics: tuple[Topic, ...]
    part_topics: tuple[Topic, ...]
    companion_topics: tuple[Topic, ...]
    companions: Mapping[str, tuple[str, ...]]
    rights_sections: tuple[int, int]
    rights_noise: frozenset[str]
    title_context: tuple[tuple[int, int, str], ...]
    generic_titles: frozenset[str]
    stopwords: frozenset[str]
    lemmas: Mapping[str, str]
    prepared: Mapping[Topic, tuple[PreparedPhrase, ...]]
    vocabulary: frozenset[str]


def build_topic_guide(data: GuideData) -> TopicGuide:
    def topic(entry: TopicEntry) -> Topic:
        return Topic(
            entry.slug, entry.targets, entry.phrases, entry.broad, entry.related_laws
        )

    topics = tuple(map(topic, data.constitution_topics))
    statutes = tuple(map(topic, data.statute_topics))
    parts = tuple(map(topic, data.part_topics))
    stopwords = frozenset(data.stopwords)
    lemmas = MappingProxyType(dict(data.lemmas))
    prepared = {
        item: tuple(
            prepare_phrase(phrase, stopwords, lemmas) for phrase in item.phrases
        )
        for item in (*topics, *statutes, *parts)
    }
    companions = dict(data.companions)
    profiled = tuple(
        entry
        for entry in (
            *data.constitution_topics,
            *data.statute_topics,
            *data.part_topics,
        )
        if entry.companion_profile is not None
    )
    # Search context includes arrest rights too, and takes precedence for
    # shared targets regardless of the topics' editorial ordering.
    search_targets = {
        target
        for entry in profiled
        if entry.companion_profile == "search"
        for target in entry.targets
    }
    for entry in profiled:
        if (profile := entry.companion_profile) is not None:
            for target in entry.targets:
                companions[target] = data.companion_profiles[
                    "search" if target in search_targets else profile
                ]
    return TopicGuide(
        topics=topics,
        statute_topics=statutes + parts,
        part_topics=parts,
        companion_topics=tuple(map(topic, profiled)),
        companions=MappingProxyType(companions),
        rights_sections=data.rights_sections,
        rights_noise=frozenset(data.rights_noise),
        title_context=data.title_context,
        generic_titles=frozenset(data.generic_titles),
        stopwords=stopwords,
        lemmas=lemmas,
        prepared=MappingProxyType(prepared),
        vocabulary=frozenset(
            word
            for phrases in prepared.values()
            for phrase in phrases
            for word in phrase.tokens
            if len(word) >= 5
        ),
    )


@cache
def load_topic_guide() -> TopicGuide:
    path = Path(__file__).parent / "data" / "topic-guide.json"
    return build_topic_guide(
        GuideData.model_validate_json(path.read_text(encoding="utf-8"))
    )
