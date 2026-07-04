"""Text folding so matching is robust to Azerbaijani diacritics.

Users often type without diacritics ("tehsil haqqi" vs "təhsil haqqı"). Folding both
the message and the keyword tokens to ASCII makes keyword detection work either way.
"""
from __future__ import annotations

import re

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


# Control chars (incl. newlines/tabs) let a user-supplied value break out of the
# instruction it is embedded in when we build an LLM prompt. Strip them.
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def sanitize_prompt_field(value: str | None, max_len: int = 120) -> str:
    """Neutralise prompt-injection vectors in a short free-text field before it is
    interpolated into an LLM prompt.

    Removes control characters and newlines (the primary way a value escapes its
    surrounding instruction), collapses runs of whitespace, and truncates to
    ``max_len``. Legitimate country/field/degree names are unchanged.
    """
    if not value:
        return ""
    cleaned = _CONTROL_RE.sub(" ", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_len]
