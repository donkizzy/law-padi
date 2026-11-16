"""Canonical evidence expansion, packing, fitting and reader source selection."""

import json
import re
import uuid
from dataclasses import dataclass, field

from sqlmodel import Session, col, select

from app.chat.llm.protocol import JsonObject
from app.legal.enums import (
    InstrumentType,
    ProvisionKind,
)
from app.legal.evidence import (
    evidence_item,
)
from app.legal.instruments import ACJA_SLUG, instrument_label
from app.legal.models import (
    CorpusReleaseEntry,
    Provision,
    ProvisionVersion,
    SourceDocument,
)
from app.legal.public_corpus import (
    PublicCorpus,
    load_reference_corpus,
)
from app.legal.references import (
    CONSTITUTION_SLUG,
    SectionReference,
    matches_reference,
    source_reference_groups,
)
from app.legal.release_scope import release_instruments
from app.legal.schemas import EvidenceItem, LegalSearchResponse
from app.legal.topics import companion_sections, section_target


@dataclass
class Prepared:
    run_id: uuid.UUID
    conversation_id: uuid.UUID
    release_id: uuid.UUID
    question: str
    previous_question: str | None
    lookup: LegalSearchResponse
    selected: list[EvidenceItem]
    all_evidence: list[EvidenceItem]
    prompt_evidence: list[JsonObject]
    too_large: bool
    conversation_context: list[JsonObject] = field(default_factory=list)
    clarification_choices: list[str] = field(default_factory=list)
    related_laws: list[str] = field(default_factory=list)
    covered_laws: list[dict[str, str]] = field(default_factory=list)


def edition_notice(evidence: list[EvidenceItem]) -> str | None:
    """One caveat per cited historical instrument, preserving legacy copy."""
    historical = [item for item in evidence if item.legal_status == "historical"]
    if not historical:
        return None
    notices: list[str] = []
    seen: set[str] = set()
    for item in historical:
        if item.instrument_slug in seen:
            continue
        seen.add(item.instrument_slug)
        if item.instrument_slug == CONSTITUTION_SLUG:
            years = EDITION_YEAR.findall(item.edition_label)
            published = (
                f"as published in {years[-1]}" if years else "from an earlier edition"
            )
            notices.append(
                f"Based on the 1999 Constitution {published}. Later amendments aren't included yet, so check whether a section has changed before relying on it."
            )
        else:
            label = (
                item.instrument_short_title
                or item.instrument_title
                or instrument_label(item.instrument_slug)
            )
            notices.append(f"{label}: As enacted, may have been amended.")
    return "\n\n".join(notices)


def source_crossrefs(
    text: str, instrument_slug: str = CONSTITUTION_SLUG
) -> list[SectionReference]:
    groups = source_reference_groups(text, instrument_slug=instrument_slug)
    # Keep each marker's first reference before expanding long lists/ranges.
    # A list in Section 45 must not crowd out its later s.33, s.36(8), s.305.
    primary = [group[0] for group in groups]
    extra = [reference for group in groups for reference in group[1:]]
    return list(dict.fromkeys([*primary, *extra]))[:5]


def expand_context(
    session: Session,
    corpus: PublicCorpus,
    selected: list[EvidenceItem],
) -> list[EvidenceItem]:
    """Load published parents and a few unambiguous cross-references."""
    result: list[EvidenceItem] = []
    seen = {item.provision_version_id for item in selected}
    parent_ids: set[uuid.UUID] = set()
    for item in selected:
        provision = corpus.provisions.get(item.provision_id) or session.get(
            Provision, item.provision_id
        )
        while provision and provision.parent_id:
            provision = corpus.provisions.get(provision.parent_id) or session.get(
                Provision, provision.parent_id
            )
            if provision and provision.kind in (
                ProvisionKind.SECTION,
                ProvisionKind.SUBSECTION,
            ):
                parent_ids.add(provision.id)
    if parent_ids:
        rows = session.exec(
            select(ProvisionVersion, Provision, SourceDocument)
            .join(Provision, col(Provision.id) == col(ProvisionVersion.provision_id))
            .join(
                SourceDocument,
                col(SourceDocument.id) == col(ProvisionVersion.source_document_id),
            )
            .join(
                CorpusReleaseEntry,
                col(CorpusReleaseEntry.provision_version_id)
                == col(ProvisionVersion.id),
            )
            .where(
                CorpusReleaseEntry.release_id == corpus.release.id,
                col(Provision.id).in_(parent_ids),
            )
        ).all()
        for version, provision, source in rows:
            if version.id in seen:
                continue
            seen.add(version.id)
            corpus.provisions[provision.id] = provision
            corpus.versions[provision.id] = version
            corpus.sources[source.id] = source
            public = corpus.result(provision)
            result.append(
                evidence_item(corpus, public, f"E{len(selected) + len(result) + 1}")
            )
    crossrefs: list[SectionReference] = []
    # Provisions that limit or pair with the selected ones come first, so
    # restrictions such as Section 45 reach the explanation.
    for item in selected:
        number = section_target(item.canonical_path)
        for companion in companion_sections(number) if number else ():
            slug, _, section = companion.partition(":")
            reference = SectionReference(section, instrument_slug=slug)
            if reference not in crossrefs:
                crossrefs.append(reference)
    available_slugs = {
        instrument.slug
        for instrument in release_instruments(
            session, corpus.release.id, index_kind=corpus.index_kind
        ).values()
    }
    crossrefs = [
        reference
        for reference in crossrefs
        if reference.instrument_slug in available_slugs
    ]
    act_slugs = {
        item.instrument_slug
        for item in selected
        if item.instrument_type == InstrumentType.ACT
    } | {
        reference.instrument_slug
        for reference in crossrefs
        if reference.instrument_slug != CONSTITUTION_SLUG
    }
    # Reserve two extra context slots for canonical scope/supremacy text,
    # including when an Act first enters the answer through a companion.
    scope_references = [SectionReference("1")] if act_slugs else []
    if ACJA_SLUG in act_slugs:
        scope_references.append(SectionReference("2", instrument_slug=ACJA_SLUG))
    crossrefs = list(dict.fromkeys([*scope_references, *crossrefs]))
    crossref_limit = 7 if act_slugs else 5
    for item in selected:
        for reference in source_crossrefs(
            item.authoritative_text, item.instrument_slug
        ):
            if reference not in crossrefs:
                crossrefs.append(reference)
            if len(crossrefs) >= crossref_limit:
                break
        if len(crossrefs) >= crossref_limit:
            break
    if crossrefs:
        focused = load_reference_corpus(
            session,
            corpus.release,
            crossrefs[:crossref_limit],
            index_kind=corpus.index_kind,
        )
        for reference in crossrefs[:crossref_limit]:
            matches = [
                provision
                for provision in focused.provisions.values()
                if provision.id in focused.versions
                and matches_reference(provision.canonical_path, reference)
            ]
            if len(matches) != 1:
                continue
            provision = matches[0]
            version = focused.versions[provision.id]
            if version.id in seen:
                continue
            seen.add(version.id)
            result.append(
                evidence_item(
                    focused,
                    focused.result(provision),
                    f"E{len(selected) + len(result) + 1}",
                )
            )
    return result


def prompt_items(evidence: list[EvidenceItem]) -> list[JsonObject]:
    """Represent contained text once while keeping each citation ID addressable."""
    ordered = sorted(
        evidence, key=lambda item: len(item.authoritative_text), reverse=True
    )
    included: list[EvidenceItem] = []
    values: dict[str, JsonObject] = {}
    for item in ordered:
        container = next(
            (
                other
                for other in included
                if item.instrument_slug == other.instrument_slug
                and item.authoritative_text in other.authoritative_text
            ),
            None,
        )
        values[item.evidence_id] = {
            "id": item.evidence_id,
            "canonical_path": item.canonical_path,
            "citation": item.citation,
            "instrument_slug": item.instrument_slug,
            "instrument_title": item.instrument_title,
            "instrument_short_title": item.instrument_short_title,
            "instrument_type": item.instrument_type,
            "title": item.title,
            "ancestor_citations": item.ancestor_citations,
            "status": item.legal_status,
            "edition": item.edition_label,
            "text": item.authoritative_text if container is None else None,
            "text_in": container.evidence_id if container else None,
        }
        if container is None:
            included.append(item)
    return [values[item.evidence_id] for item in evidence]


def shown_evidence(prepared: Prepared, cited_ids: set[str]) -> list[EvidenceItem]:
    """Sources behind a delivered explanation: what it cited or was asked about.

    Retrieval also pulls near matches and context the explanation never used;
    listing them beside the answer padded it with unrelated sections.
    """
    asked = {
        identifier
        for row in prepared.lookup.citation_outcomes
        for identifier in row.evidence_ids
    }
    shown = [
        item
        for item in prepared.all_evidence
        if item.evidence_id in cited_ids or item.evidence_id in asked
    ]
    return shown or prepared.all_evidence


def prompt_bytes(base: JsonObject, prompt_evidence: list[JsonObject]) -> int:
    return len(
        json.dumps({**base, "evidence": prompt_evidence}, ensure_ascii=False).encode()
    )


def fit_prompt(
    selected: list[EvidenceItem],
    context: list[EvidenceItem],
    base: JsonObject,
    limit: int,
) -> tuple[list[EvidenceItem], list[EvidenceItem], list[JsonObject], int]:
    """Shrink the evidence packet to the budget instead of refusing the question.

    Broad questions pull in long sections, and refusing them looked like a
    failure to understand. The lowest-ranked matches go first, because the
    context carries the restrictions and scope rules that change an answer.
    Then context is trimmed from the end; a question is only too large when its
    single best match is.
    """
    selected = list(selected)
    context = list(context)

    def measure() -> tuple[list[JsonObject], int]:
        items = prompt_items([*selected, *context])
        return items, prompt_bytes(base, items)

    items, size = measure()
    while size > limit and len(selected) > KEEP_MATCHES:
        selected.pop()
        items, size = measure()
    while size > limit and context:
        context.pop()
        items, size = measure()
    while size > limit and len(selected) > 1:
        selected.pop()
        items, size = measure()
    return selected, context, items, size


EDITION_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")

KEEP_MATCHES = 4
