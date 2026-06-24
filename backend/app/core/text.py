"""Text folding so matching is robust to Azerbaijani diacritics.

Users often type without diacritics ("tehsil haqqi" vs "təhsil haqqı"). Folding both
the message and the keyword tokens to ASCII makes keyword detection work either way.
"""
from __future__ import annotations

_FOLD = str.maketrans(
    {
        "ə": "e", "Ə": "e",
        "ı": "i", "İ": "i", "I": "i",
        "ş": "s", "Ş": "s",
        "ç": "c", "Ç": "c",
        "ğ": "g", "Ğ": "g",
        "ö": "o", "Ö": "o",
        "ü": "u", "Ü": "u",
        "â": "a", "î": "i", "û": "u",
    }
)


def fold(text: str) -> str:
    return text.translate(_FOLD).lower()
