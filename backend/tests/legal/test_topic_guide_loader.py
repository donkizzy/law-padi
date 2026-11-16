"""Validate editorial data and preserve the guide's immutable public values."""

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.legal import topics
from app.legal.topic_guide import GuideData, build_topic_guide, load_topic_guide


def guide_data() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "app/legal/data/topic-guide.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_loaded_tables_equal_public_tables() -> None:
    guide = load_topic_guide()
    assert guide is load_topic_guide()
    assert guide.topics == topics.TOPICS
    assert guide.statute_topics == topics.STATUTE_TOPICS
    assert guide.part_topics == topics._PART_TOPICS
    assert guide.companion_topics == topics._COMPANION_TOPICS
    assert guide.companions == topics.COMPANIONS
    assert guide.rights_sections == topics._RIGHTS_SECTIONS
    assert guide.rights_noise == topics._RIGHTS_NOISE
    assert guide.title_context == topics._TITLE_CONTEXT
    assert guide.generic_titles == topics._GENERIC_TITLES
    assert guide.stopwords == topics.STOPWORDS
    assert guide.lemmas == topics._LEMMAS


@pytest.mark.parametrize(
    "defect",
    [
        "unknown_root",
        "unknown_topic",
        "duplicate_slug",
        "target",
        "slug",
        "empty_phrases",
        "profile",
        "missing_profile",
        "rights_range",
        "context_range",
    ],
)
def test_invalid_editorial_data_is_rejected(defect: str) -> None:
    data = guide_data()
    entry = data["constitution_topics"][0]
    if defect == "unknown_root":
        data["unknown"] = True
    elif defect == "unknown_topic":
        entry["unknown"] = True
    elif defect == "duplicate_slug":
        data["statute_topics"][0]["slug"] = entry["slug"]
    elif defect == "target":
        entry["targets"] = ["constitution-1999:../37"]
    elif defect == "slug":
        entry["slug"] = "Not a slug"
    elif defect == "empty_phrases":
        entry["phrases"] = []
    elif defect == "profile":
        entry["companion_profile"] = "unknown"
    elif defect == "missing_profile":
        del data["companion_profiles"]["rights"]
    elif defect == "rights_range":
        data["rights_sections"] = [46, 33]
    else:
        data["title_context"][0] = [89, 47, "National Assembly"]
    with pytest.raises(ValidationError):
        GuideData.model_validate(data)


def test_companion_profiles_do_not_depend_on_topic_position() -> None:
    data = GuideData.model_validate(guide_data())
    reordered = data.model_copy(
        update={"statute_topics": tuple(reversed(data.statute_topics))}
    )
    assert build_topic_guide(reordered).companions == load_topic_guide().companions
    entries = list(data.statute_topics)
    no_profile = next(entry for entry in entries if entry.companion_profile is None)
    entries.remove(no_profile)
    entries.insert(0, no_profile)
    moved = data.model_copy(update={"statute_topics": tuple(entries)})
    assert build_topic_guide(moved).companions == load_topic_guide().companions
    assert {
        entry.slug: entry.companion_profile for entry in reordered.statute_topics
    } == {entry.slug: entry.companion_profile for entry in data.statute_topics}


def test_loaded_mappings_are_read_only() -> None:
    with pytest.raises(TypeError):
        load_topic_guide().companions["constitution-1999:37"] = ()  # type: ignore[index]
    with pytest.raises(TypeError):
        load_topic_guide().lemmas["test"] = "test"  # type: ignore[index]
    assert replace(topics.TOPICS[0], broad=True).broad
