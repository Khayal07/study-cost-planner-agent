"""Intent Extraction — turn a free-text chat message into a (partial) PlanningRequest.

Uses the LLM when configured; otherwise a deterministic parser (country synonyms incl.
Azerbaijani, budget/currency regex, lifestyle keywords) so chat works without a key.
"""
from __future__ import annotations

import re

from app.core.config import settings
from app.core.llm_client import llm
from app.core.schemas import PlanningRequest
from app.core.text import fold, sanitize_prompt_field

# Map local/native country names to the canonical names used in the DB.
COUNTRY_SYNONYMS = {
    "germany": "Germany", "german": "Germany", "almaniya": "Germany", "almaniyada": "Germany",
    "netherlands": "Netherlands", "holland": "Netherlands", "hollandiya": "Netherlands",
    "niderland": "Netherlands", "dutch": "Netherlands",
    "poland": "Poland", "polsha": "Poland", "polşa": "Poland", "polша": "Poland",
    "hungary": "Hungary", "macarstan": "Hungary", "macarıstan": "Hungary",
    "turkey": "Turkey", "turkiye": "Turkey", "türkiyə": "Turkey", "turkiyə": "Turkey",
}

CURRENCY_TOKENS = {
    "EUR": ["eur", "euro", "avro", "€"],
    "USD": ["usd", "dollar", "dolar", "$"],
    "TRY": ["try", "lira", "₺"],
    "PLN": ["pln", "zloty", "zł", "zl"],
    "AZN": ["azn", "manat", "₼"],
    "GBP": ["gbp", "pound", "funt", "£"],
}

# The dataset stores every program under field "Computer Science" (incl. the Data
# Science / AI specializations), so all CS-adjacent tokens map to that one canonical
# field — otherwise a "Data Science" filter would match zero rows.
FIELD_TOKENS = {
    "Computer Science": ["computer science", "cs", "kompüter", "komputer", "informatika",
                         "informatics", "software", "proqramlaşdırma", "coding",
                         "data science", "data-science", "machine learning", "ml", "ai",
                         "artificial intelligence"],
}

DEGREE_TOKENS = {
    "master": ["master", "masters", "master's", "msc", "m.sc", "magistr", "graduate",
               "postgraduate"],
    "bachelor": ["bachelor", "bachelors", "bachelor's", "bsc", "b.sc", "undergrad",
                 "undergraduate", "bakalavr"],
    "phd": ["phd", "ph.d", "doctorate", "doctoral", "doktorant"],
}


def _detect_country(text: str) -> str | None:
    for token, canonical in COUNTRY_SYNONYMS.items():
        if re.search(rf"\b{re.escape(fold(token))}", text):
            return canonical
    return None


def _detect_field(text: str) -> str | None:
    for canonical, tokens in FIELD_TOKENS.items():
        if any(fold(t) in text for t in tokens):
            return canonical
    return None


def _detect_degree(text: str) -> str | None:
    for canonical, tokens in DEGREE_TOKENS.items():
        if any(fold(t) in text for t in tokens):
            return canonical
    return None


def _detect_currency(text: str) -> str | None:
    for code, tokens in CURRENCY_TOKENS.items():
        if any(fold(t) in text for t in tokens):
            return code
    return None


def _detect_budget(text: str) -> float | None:
    # First number that looks like an amount (>= 100). Treat '.'/',' as thousands
    # separators (e.g. "8.000" / "8,000" -> 8000); supports "15k" style.
    for raw in re.findall(r"\d[\d.,]*\s*k?\b", text):
        token = raw.strip()
        mult = 1
        if token.endswith("k"):
            mult = 1000
            token = token[:-1]
        digits = re.sub(r"[.,\s]", "", token)
        if digits.isdigit():
            value = float(digits) * mult
            if value >= 100:
                return value
    return None


def _detect_lifestyle(text: str) -> str | None:
    if any(fold(w) in text for w in ["frugal", "cheap", "qənaət", "ucuz", "cheapest"]):
        return "frugal"
    if any(fold(w) in text for w in ["comfortable", "rahat", "premium", "luxury"]):
        return "comfortable"
    return None


def _detect_gpa(text: str) -> float | None:
    # "gpa 3.5", "gpa of 3.5", "3.5/4". GPA is on a 0-4 scale, so it never collides
    # with budget numbers (which are >= 100).
    m = re.search(r"gpa[^\d]{0,6}([0-4](?:\.\d{1,2})?)", text)
    if m:
        value = float(m.group(1))
        if 0 <= value <= 4:
            return value
    m = re.search(r"\b([0-4]\.\d{1,2})\s*/\s*4(?:\.0)?\b", text)
    if m:
        return float(m.group(1))
    return None


def _detect_language(text: str) -> str | None:
    m = re.search(r"\b(ielts|toefl|duolingo|pte)\b\s*:?\s*(\d{1,3}(?:\.\d)?)?", text)
    if m:
        name = m.group(1).upper()
        score = m.group(2)
        return f"{name} {score}".strip()
    return None


def _detect_nationality(message: str) -> str | None:
    # Read from the original (cased) message so we keep the proper noun. Only fires on
    # explicit nationality cues so a destination ("study in Germany") isn't mistaken.
    m = re.search(
        r"(?:i am from|i'm from|im from|citizen of|national of|"
        r"nationality\s*(?:is|:)?)\s+([A-Za-z][A-Za-z .'-]{2,40})",
        message, re.IGNORECASE,
    )
    if m:
        return m.group(1).strip().title()
    m = re.search(r"\b([A-Z][a-zA-Z]+)\s+citizen\b", message)
    if m:
        return m.group(1).title()
    return None


def extract_slots(message: str, report_currency: str | None = None) -> dict:
    """Detect every planning slot present in a message; absent slots are None.

    Deterministic; safe to call on every turn. The advisor merges the non-null
    results into its running profile so the user never repeats themselves. When the
    LLM is enabled it is consulted first and its values fill any gaps the regexes miss.
    """
    report_currency = (report_currency or settings.default_report_currency).upper()
    text = fold(message)

    slots: dict = {
        "country": _detect_country(text),
        "field": _detect_field(text),
        "degree_level": _detect_degree(text),
        "budget_amount": _detect_budget(text),
        "budget_currency": _detect_currency(text),
        "lifestyle": _detect_lifestyle(text),
        # Eligibility slots for the scholarship layer (all optional).
        "nationality": _detect_nationality(message),
        "gpa": _detect_gpa(text),
        "language_test": _detect_language(text),
    }

    if llm.enabled:
        data = llm.complete_json(
            system="Extract study-abroad planning fields from the student's message. "
            "Keys: country (full English name or null), field (e.g. 'Computer Science' or null), "
            "degree_level ('bachelor'|'master'|'phd' or null), "
            "budget_amount (number or null), budget_currency (ISO code or null), "
            "lifestyle ('frugal'|'moderate'|'comfortable' or null), "
            "nationality (country of citizenship or null), gpa (number 0-4 or null), "
            "language_test (e.g. 'IELTS 6.5' or null).",
            # Strip control chars/newlines so the message can't inject instructions;
            # slot extraction is unaffected for normal single-line prose.
            user=sanitize_prompt_field(message, max_len=4000),
        )
        if data:
            # LLM fills gaps but never overrides a confident regex hit.
            for key in slots:
                if slots[key] is None and data.get(key) not in (None, "", "null"):
                    slots[key] = data[key]
            if slots["budget_amount"] is not None:
                try:
                    slots["budget_amount"] = float(slots["budget_amount"])
                except (ValueError, TypeError):
                    slots["budget_amount"] = _detect_budget(text)
            if slots["gpa"] is not None:
                try:
                    slots["gpa"] = float(slots["gpa"])
                    if not 0 <= slots["gpa"] <= 4:
                        slots["gpa"] = _detect_gpa(text)
                except (ValueError, TypeError):
                    slots["gpa"] = _detect_gpa(text)
            # The LLM can hallucinate a field/degree the dataset doesn't use, which then
            # filters retrieval down to nothing. Constrain to canonical values: re-map an
            # unsupported value (e.g. "Software Engineering" -> "Computer Science") or drop it.
            if slots["field"] and slots["field"] not in FIELD_TOKENS:
                slots["field"] = _detect_field(fold(str(slots["field"])))
            if slots["degree_level"] and slots["degree_level"] not in DEGREE_TOKENS:
                slots["degree_level"] = _detect_degree(fold(str(slots["degree_level"])))

    if slots["budget_currency"]:
        slots["budget_currency"] = str(slots["budget_currency"]).upper()
    return slots


def extract_intent(message: str, report_currency: str | None = None) -> tuple[PlanningRequest | None, dict]:
    """Return (PlanningRequest or None if budget missing, extracted-fields dict).

    Backward-compatible wrapper around :func:`extract_slots` for the single-shot
    form/plan path and existing tests.
    """
    report_currency = (report_currency or settings.default_report_currency).upper()
    slots = extract_slots(message, report_currency)

    extracted = {
        "country": slots["country"],
        "field": slots["field"],
        "degree_level": slots["degree_level"],
        "budget_amount": slots["budget_amount"],
        "budget_currency": slots["budget_currency"] or report_currency,
        "lifestyle": slots["lifestyle"] or "moderate",
    }
    if slots["budget_amount"] is None:
        return None, extracted

    return (
        PlanningRequest(
            country=slots["country"],
            field=slots["field"] or "Computer Science",
            degree_level=slots["degree_level"],
            budget_amount=float(slots["budget_amount"]),
            budget_currency=slots["budget_currency"] or report_currency,
            report_currency=report_currency,
            lifestyle=slots["lifestyle"] or "moderate",
        ),
        extracted,
    )
