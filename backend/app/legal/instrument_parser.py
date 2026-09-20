"""Instrument-type plugin boundary for structural parsing.

V1 supports Constitution PDFs only. Parsers accept normalized page spans and
return a provider-neutral DocumentGraph so pipeline stages never depend on a
single parser implementation.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.legal.parser import (
    PARSER_VERSION,
    ParsedProvision,
    parse_constitution_pages,
)
from app.legal.parser import (
    SourcePage as ParserSourcePage,
)


@dataclass(frozen=True)
class DocumentNode:
    kind: str
    number: str | None
    heading: str | None
    canonical_path: str
    sort_key: str
    parent_path: str | None
    page_start: int
    page_end: int
    text: str | None
    parser_confidence: float | None
    parser_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DocumentGraph:
    instrument_slug: str
    instrument_type: str
    nodes: list[DocumentNode]
    parser_version: str = PARSER_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def node_by_path(self) -> dict[str, DocumentNode]:
        return {node.canonical_path: node for node in self.nodes}


class InstrumentParser(Protocol):
    instrument_types: tuple[str, ...]

    def parse(
        self, pages: list[ParserSourcePage], instrument_slug: str
    ) -> DocumentGraph:
        """Parse normalized pages into a provider-neutral document graph."""


class ConstitutionParser:
    instrument_types: tuple[str, ...] = ("constitution",)

    def parse(
        self, pages: list[ParserSourcePage], instrument_slug: str
    ) -> DocumentGraph:
        parsed: list[ParsedProvision] = parse_constitution_pages(pages, instrument_slug)
        nodes = [
            DocumentNode(
                kind=str(node.kind.value if hasattr(node.kind, "value") else node.kind),
                number=node.number,
                heading=node.heading,
                canonical_path=node.canonical_path,
                sort_key=node.sort_key,
                parent_path=node.parent_path,
                page_start=node.page_start or 1,
                page_end=node.page_end or node.page_start or 1,
                text=node.text,
                parser_confidence=node.parser_confidence,
                parser_metadata=dict(node.parser_metadata or {}),
            )
            for node in parsed
        ]
        return DocumentGraph(
            instrument_slug=instrument_slug,
            instrument_type="constitution",
            nodes=nodes,
            metadata={"node_count": len(nodes)},
        )


_PARSERS: tuple[InstrumentParser, ...] = (ConstitutionParser(),)


def instrument_parser_for(instrument_type: str) -> InstrumentParser:
    normalized = (instrument_type or "").strip().lower()
    for parser in _PARSERS:
        if normalized in parser.instrument_types:
            return parser
    raise ValueError(
        f"No instrument parser registered for type: {instrument_type!r}. "
        f"V1 supports: constitution."
    )


def parse_instrument_pages(
    *,
    instrument_type: str,
    instrument_slug: str,
    pages: list[ParserSourcePage],
) -> DocumentGraph:
    return instrument_parser_for(instrument_type).parse(pages, instrument_slug)


def parsed_provisions_from_graph(graph: DocumentGraph) -> list[ParsedProvision]:
    from app.legal.enums import ProvisionKind

    provisions: list[ParsedProvision] = []
    for node in graph.nodes:
        try:
            kind = ProvisionKind(node.kind)
        except ValueError:
            kind = ProvisionKind.SECTION
        provisions.append(
            ParsedProvision(
                kind=kind,
                number=node.number,
                heading=node.heading,
                canonical_path=node.canonical_path,
                sort_key=node.sort_key,
                parent_path=node.parent_path,
                page_start=node.page_start,
                page_end=node.page_end,
                text=node.text,
                parser_confidence=node.parser_confidence,
                parser_metadata=dict(node.parser_metadata),
            )
        )
    return provisions
