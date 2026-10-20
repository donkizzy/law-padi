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
