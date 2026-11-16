"""Pin public navigation outputs to a fixed, reviewed-query fixture."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.legal import topics

SCOPES = (
    ("constitution-1999",),
    ("acja-2015", "police-act-2020"),
    ("constitution-1999", "acja-2015", "police-act-2020"),
    (),
)


def public_outputs(query: str) -> dict[str, Any]:
    return {
        "tokens": topics.tokens(query),
        "matches": [asdict(match) for match in topics.match_topics(query)],
        "statute_matches": [
            asdict(match)
            for match in topics.match_topics(
                query, limit=5, topics=topics.STATUTE_TOPICS
            )
        ],
        "sections": [
            topics.topic_sections(query, instrument_slugs=scope) for scope in SCOPES
        ],
        "titles": [
            topics.title_sections(query, instrument_slugs=scope) for scope in SCOPES
        ],
        "demoted": sorted(topics.demoted_sections(query)),
        "rights": topics.rights_question(query),
        "laws": [
            topics.related_laws(query, instrument_slugs=scope) for scope in SCOPES
        ],
        "section_number": topics.section_number(query),
        "section_target": topics.section_target(query),
        "section_title": topics.section_title(query),
        "companions": topics.companion_sections(query),
    }


def test_public_outputs_match_golden() -> None:
    fixture = json.loads(
        Path(__file__).with_suffix(".json").read_text(encoding="utf-8")
    )
    assert len(fixture["cases"]) >= 300
    actual_topics = [asdict(topic) for topic in (*topics.TOPICS, *topics.STATUTE_TOPICS)]
    assert json.loads(json.dumps(actual_topics)) == fixture["topics"]
    assert json.loads(json.dumps(dict(topics.COMPANIONS))) == fixture["companions"]
    for case in fixture["cases"]:
        # JSON normalises the public tuple values while retaining their order.
        actual = json.loads(json.dumps(public_outputs(case["query"])))
        assert actual == case["outputs"], case["query"]
