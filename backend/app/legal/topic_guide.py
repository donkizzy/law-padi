"""Validate and load the curated navigation guide once per process."""

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


def build_topic_guide(data: GuideData) -> TopicGuide:
    def topic(entry: TopicEntry) -> Topic:
        return Topic(
            entry.slug, entry.targets, entry.phrases, entry.broad, entry.related_laws
        )

    topics = tuple(map(topic, data.constitution_topics))
    statutes = tuple(map(topic, data.statute_topics))
    parts = tuple(map(topic, data.part_topics))
    companions = dict(data.companions)
    companion_topics = []
    # Later explicit profiles retain precedence when topics share a target.
    for entry in (*data.constitution_topics, *data.statute_topics, *data.part_topics):
        if entry.companion_profile is not None:
            companion_topics.append(topic(entry))
            for target in entry.targets:
                companions[target] = data.companion_profiles[entry.companion_profile]
    return TopicGuide(
        topics=topics,
        statute_topics=statutes + parts,
        part_topics=parts,
        companion_topics=tuple(companion_topics),
        companions=MappingProxyType(companions),
        rights_sections=data.rights_sections,
        rights_noise=frozenset(data.rights_noise),
        title_context=data.title_context,
        generic_titles=frozenset(data.generic_titles),
        stopwords=frozenset(data.stopwords),
        lemmas=MappingProxyType(data.lemmas),
    )


@cache
def load_topic_guide() -> TopicGuide:
    path = Path(__file__).parent / "data" / "topic-guide.json"
    return build_topic_guide(
        GuideData.model_validate_json(path.read_text(encoding="utf-8"))
    )
