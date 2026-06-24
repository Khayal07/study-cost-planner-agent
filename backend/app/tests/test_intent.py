"""Unit tests for intent extraction fallback and diacritic folding."""
from __future__ import annotations

from app.agents.intent import extract_intent
from app.core.text import fold


def test_fold_strips_azerbaijani_diacritics():
    assert fold("təhsil haqqı") == "tehsil haqqi"
    assert fold("Polşa") == "polsa"
    assert fold("Almaniyada") == "almaniyada"


def test_full_plan_intent_english():
    req, extracted = extract_intent("I want to study CS in Germany, budget is 8000 EUR", "EUR")
    assert req is not None
    assert req.country == "Germany"
    assert req.budget_amount == 8000.0
    assert req.budget_currency == "EUR"


def test_full_plan_intent_azerbaijani_no_diacritics():
    req, _ = extract_intent("Almaniyada Computer Science, budcem 8000 avro", "EUR")
    assert req is not None
    assert req.country == "Germany"
    assert req.budget_amount == 8000.0
    assert req.budget_currency == "EUR"


def test_budget_with_thousands_separator():
    req, _ = extract_intent("budget 12.000 eur in Poland", "EUR")
    assert req is not None
    assert req.budget_amount == 12000.0
    assert req.country == "Poland"


def test_no_budget_returns_none():
    req, extracted = extract_intent("I want to study in Hungary", "EUR")
    assert req is None
    assert extracted["country"] == "Hungary"
