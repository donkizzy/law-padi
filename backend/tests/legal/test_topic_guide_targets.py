"""Check guide targets against offline catalogues without inventing headings."""

import re
from collections import Counter

import pytest

from app.legal.titles import catalogue_titles, title_catalog
from app.legal.topic_guide import load_topic_guide

# These schedule suffixes have no corresponding offline navigation catalogue.
UNCATALOGUED_SCHEDULE_TARGETS = frozenset(
    {
        "constitution-1999:oath-allegiance",
        "constitution-1999:oath-governor",
        "constitution-1999:oath-judicial",
        "constitution-1999:oath-legislator",
        "constitution-1999:oath-president",
    }
)
EXPECTED_COUNTS = {
    "constitution-1999": (163, 5),
    "acja-2015": (9, 137),
    "police-act-2020": (14, 51),
}


def guide_targets() -> set[str]:
    guide = load_topic_guide()
    return (
        {
            target
            for topic in (*guide.topics, *guide.statute_topics)
            for target in topic.sections
        }
        | set(guide.companions)
        | {target for companions in guide.companions.values() for target in companions}
    )


@pytest.mark.parametrize("slug", sorted(EXPECTED_COUNTS))
def test_topic_guide_targets_resolve_where_catalogues_exist(slug: str) -> None:
    targets = {target for target in guide_targets() if target.partition(":")[0] == slug}
    catalog = title_catalog(slug)
    sections = catalogue_titles(slug, "sections")
    expected_section_count = catalog.get("expected_section_count")
    partial = (
        isinstance(expected_section_count, int)
        and len(sections) < expected_section_count
    )
    checked, unchecked = set(), set()
    for target in sorted(targets):
        number = target.partition(":")[2]
        if number in sections:
            assert sections[number].strip(), target
            checked.add(target)
        elif target in UNCATALOGUED_SCHEDULE_TARGETS:
            unchecked.add(target)
        elif not sections:
            unchecked.add(target)
        elif partial:
            # A partial arrangement cannot prove existence. Its source count
            # can still reject a section outside that instrument's range.
            assert re.fullmatch(r"[1-9][0-9]*[a-z]?", number), target
            assert (
                0
                < int(number.rstrip("abcdefghijklmnopqrstuvwxyz"))
                <= expected_section_count
            ), target
            unchecked.add(target)
        else:
            pytest.fail(f"Target missing from the complete section catalogue: {target}")
    occurrences = Counter(
        target
        for topic in (*load_topic_guide().topics, *load_topic_guide().statute_topics)
        for target in topic.sections
        if target.partition(":")[0] == slug
    )
    unchecked_occurrences = sum(occurrences[target] for target in unchecked)
    print(  # noqa: T201
        f"{slug}: checked={len(checked)} unique targets; "
        f"not checkable offline={len(unchecked)} unique targets "
        f"({unchecked_occurrences} topic target occurrences)"
    )
    assert (len(checked), len(unchecked)) == EXPECTED_COUNTS[slug]


def test_target_validation_accounts_for_every_law_and_schedule_suffix() -> None:
    targets = guide_targets()
    assert {target.partition(":")[0] for target in targets} == set(EXPECTED_COUNTS)
    assert {
        target for target in targets if ":oath-" in target
    } == UNCATALOGUED_SCHEDULE_TARGETS
