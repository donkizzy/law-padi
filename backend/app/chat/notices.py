"""Reader-facing run notices and localisation fields."""

from app.chat.evidence_packet import Prepared
from app.chat.llm.protocol import JsonObject

NOTICE = {
    "cancelled": "You stopped this answer.",
    "disabled": "Explanations are switched off at the moment. You can still search and read the published laws.",
    "too_large": "That question covers too much to explain at once. Try asking about one law, section or issue.",
    "no_match": "We couldn't find a published section that answers this. Try rephrasing, or name a law and section.",
    "not_covered": "The published provisions don't seem to answer this directly. These are the closest sections we found.",
    "budget": "We've reached the available budget for explanations. You can still read the relevant sections below.",
    "unverified": "We couldn't confirm that the explanation matches the published provisions, so here are the sections themselves.",
    "unavailable": "Explanations aren't available right now. Here are the relevant published sections.",
    "stalled": "This answer took too long. Please try again.",
}


def with_coverage(message: str, prepared: Prepared | None) -> str:
    labels = [law["label"] for law in prepared.covered_laws] if prepared else []
    if not labels:
        return message
    names = (
        labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " and " + labels[-1]
    )
    return f"{message} This edition includes {names}."


def notice(key: str, prepared: Prepared | None = None) -> str:
    return with_coverage(NOTICE[key], prepared)


def notice_fields(key: str, prepared: Prepared | None = None) -> JsonObject:
    """English notice plus the key and values a client needs to translate it."""
    laws = [law["label"] for law in prepared.covered_laws] if prepared else []
    return {
        "notice": notice(key, prepared),
        "notice_code": key,
        "notice_params": {"laws": laws} if laws else {},
    }
