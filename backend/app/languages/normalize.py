"""Unicode normalisation for storage and for ASCII-only matching."""

import unicodedata

# Hausa hooked letters and similar forms have no decomposition to ASCII.
_LETTER_FOLDS = str.maketrans(
    {
        "ɓ": "b",
        "Ɓ": "B",
        "ɗ": "d",
        "Ɗ": "D",
        "ƙ": "k",
        "Ƙ": "K",
        "ƴ": "y",
        "Ƴ": "Y",
        "ŋ": "n",
        "Ŋ": "N",
        "ɛ": "e",
        "Ɛ": "E",
        "ɔ": "o",
        "Ɔ": "O",
        "’": "'",
        "‘": "'",
    }
)


def nfc(text: str) -> str:
    """Compose characters so equal text has one stored form."""
    return unicodedata.normalize("NFC", text)


def fold(text: str) -> str:
    """Strip tone marks, dots below and hooks: "Ẹ̀tọ́ haƙƙi" -> "Eto hakki".

    Only for matching. Never display or store folded text, because tone marks
    change meaning in Yorùbá and Igbo.
    """
    decomposed = unicodedata.normalize("NFKD", text.translate(_LETTER_FOLDS))
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))
