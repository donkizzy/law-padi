"""Supported reader languages."""

from enum import StrEnum


class Language(StrEnum):
    ENGLISH = "en"
    PIDGIN = "pcm"
    YORUBA = "yo"
    HAUSA = "ha"
    IGBO = "ig"


DISPLAY_NAMES: dict[Language, str] = {
    Language.ENGLISH: "English",
    Language.PIDGIN: "Naijá (Pidgin)",
    Language.YORUBA: "Yorùbá",
    Language.HAUSA: "Hausa",
    Language.IGBO: "Igbo",
}


def parse_language(value: str | None) -> Language | None:
    """Return the supported language for a code, ignoring case and region."""
    if not value:
        return None
    try:
        return Language(value.strip().lower().split("-")[0].split("_")[0])
    except ValueError:
        return None
