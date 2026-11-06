"""Instrument labels shared by public evidence and derived retrieval documents."""

import re

from app.legal.enums import InstrumentType
from app.legal.models import LegalInstrument


def qualify_citation(citation: str, instrument: LegalInstrument) -> str:
    if instrument.instrument_type == InstrumentType.CONSTITUTION:
        return citation
    return f"{citation}, {instrument.short_title or instrument.title}"


def short_citation(citation: str, instrument: LegalInstrument) -> str:
    label = instrument.short_title or instrument.title
    if instrument.instrument_type == InstrumentType.CONSTITUTION:
        label = "Constitution"
    else:
        label = re.sub(r",?\s+\d{4}$", "", label)
    return f"{label} {citation.replace('Section ', 's.', 1)}"


_RULE_PATH = re.compile(
    r"\.(?:order([ivxl]+)\.rule(\d+)|preamble\.rule(\d+))((?:\.paragraph[a-z]+)*)$"
)
_ORDER_PATH = re.compile(r"\.order([ivxl]+)$")
_APPENDIX_PATH = re.compile(r"\.schedule([ab])(?:\.item(\d+))?$")


def rules_citation(canonical_path: str) -> str | None:
    """Court rules are cited by Order and Rule, not by section."""
    if match := _RULE_PATH.search(canonical_path):
        order, rule, preamble, paragraphs = match.groups()
        suffix = "".join(f"({item})" for item in paragraphs.split(".paragraph")[1:])
        if preamble:
            return f"Preamble, paragraph {preamble}{suffix}"
        return f"Order {order.upper()}" + (
            f" Rule {rule}{suffix}" if rule != "0" else suffix
        )
    if match := _ORDER_PATH.search(canonical_path):
        return f"Order {match.group(1).upper()}"
    if canonical_path.endswith(".preamble"):
        return "Preamble"
    if match := _APPENDIX_PATH.search(canonical_path):
        appendix, form = match.groups()
        return f"Appendix {appendix.upper()}" + (f", Form {form}" if form else "")
    return None
