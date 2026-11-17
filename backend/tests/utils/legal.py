"""Citation metadata for synthetic instruments used by release fixtures."""

from dataclasses import replace

from app.ingestion.admin import release_gates
from app.legal.instruments import CONSTITUTION_SLUG


def register_fixture_citation_names(slug: str) -> None:
    registry = release_gates.instrument_names()
    registry[slug] = replace(registry[CONSTITUTION_SLUG], slug=slug)
