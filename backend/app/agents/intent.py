"""Intent Extraction — turn a free-text chat message into a (partial) PlanningRequest.

Uses the LLM when configured; otherwise a deterministic parser (country synonyms incl.
Azerbaijani, budget/currency regex, lifestyle keywords) so chat works without a key.
"""
from __future__ import annotations

import re

from app.core.config import settings
from app.core.llm_client import llm
from app.core.schemas import PlanningRequest
from app.core.text import fold

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

FIELD_TOKENS = {
    "Computer Science": ["computer science", "cs", "kompüter", "komputer", "informatika",
                          "informatics", "software", "proqramlaşdırma"],
}


def _fallback(message: str, report_currency: str) -> tuple[PlanningRequest | None, dict]:
    text = fold(message)

    country = None
    for token, canonical in COUNTRY_SYNONYMS.items():
        if re.search(rf"\b{re.escape(fold(token))}", text):
            country = canonical
            break

    field = None
    for canonical, tokens in FIELD_TOKENS.items():
        if any(fold(t) in text for t in tokens):
            field = canonical
            break

    # Currency: first currency token present
    currency = None
    for code, tokens in CURRENCY_TOKENS.items():
        if any(fold(t) in text for t in tokens):
            currency = code
            break

    # Budget: first number that looks like an amount (>= 100). Treat '.'/',' as
    # thousands separators (e.g. "8.000" / "8,000" -> 8000).
    budget = None
    for raw in re.findall(r"\d[\d.,]*", text):
        digits = re.sub(r"[.,]", "", raw)
        if digits.isdigit() and float(digits) >= 100:
            budget = float(digits)
            break

    lifestyle = "moderate"
    if any(fold(w) in text for w in ["frugal", "cheap", "qənaət", "ucuz", "budget"]):
        lifestyle = "frugal"
    elif any(fold(w) in text for w in ["comfortable", "rahat", "premium"]):
        lifestyle = "comfortable"

    extracted = {"country": country, "field": field, "budget_amount": budget,
                 "budget_currency": currency or report_currency, "lifestyle": lifestyle}

    if budget is None:
        return None, extracted  # not enough for a full plan
    return (
        PlanningRequest(
            country=country,
            field=field or "Computer Science",
            budget_amount=budget,
            budget_currency=currency or report_currency,
            report_currency=report_currency,
            lifestyle=lifestyle,
        ),
        extracted,
    )


def extract_intent(message: str, report_currency: str | None = None) -> tuple[PlanningRequest | None, dict]:
    """Return (PlanningRequest or None if budget missing, extracted-fields dict)."""
    report_currency = (report_currency or settings.default_report_currency).upper()

    if llm.enabled:
        data = llm.complete_json(
            system="Extract study-abroad planning fields from the student's message. "
            "Keys: country (full English name or null), field (e.g. 'Computer Science' or null), "
            "budget_amount (number or null), budget_currency (ISO code or null), "
            "lifestyle ('frugal'|'moderate'|'comfortable').",
            user=message,
        )
        if data and data.get("budget_amount"):
            try:
                return (
                    PlanningRequest(
                        country=data.get("country") or None,
                        field=data.get("field") or "Computer Science",
                        budget_amount=float(data["budget_amount"]),
                        budget_currency=(data.get("budget_currency") or report_currency).upper(),
                        report_currency=report_currency,
                        lifestyle=data.get("lifestyle") or "moderate",
                    ),
                    data,
                )
            except (ValueError, TypeError):
                pass  # fall through to deterministic parser

    return _fallback(message, report_currency)
