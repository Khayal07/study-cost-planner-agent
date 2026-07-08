"""Static per-country cost inflation assumptions for the /forecast endpoint.

These are deliberately conservative planning assumptions (annual %), not live
figures: the forecast is a "what should I budget for" projection, so the exact
rate matters less than being explicit about it. Every response carries the
assumption + note so the user can judge it. Unknown countries fall back to a
generic default.
"""
from __future__ import annotations

DEFAULT_RATES: dict = {
    "tuition_pct": 3.0,
    "living_pct": 4.0,
    "note": "Generic assumption — no country-specific rates available.",
}

# Keyed by ISO code (matches Country.iso_code in the seed data).
INFLATION_RATES: dict[str, dict] = {
    "DE": {"tuition_pct": 1.5, "living_pct": 3.0, "note": "Public tuition is mostly semester fees and moves slowly; living costs track general inflation."},
    "NL": {"tuition_pct": 3.0, "living_pct": 3.5, "note": "Statutory tuition is indexed annually; housing pressure keeps living-cost growth above inflation."},
    "PL": {"tuition_pct": 5.0, "living_pct": 5.5, "note": "PLN-priced tuition and living costs have grown faster than the euro-area average."},
    "HU": {"tuition_pct": 6.0, "living_pct": 6.5, "note": "HUF inflation has run high; budget extra buffer."},
    "TR": {"tuition_pct": 12.0, "living_pct": 15.0, "note": "High TRY inflation is partly offset by depreciation when budgeting in EUR/USD — treat with extra caution."},
    "CZ": {"tuition_pct": 4.0, "living_pct": 4.5, "note": "CZK-priced costs grow moderately; Prague rents rise faster than the national average."},
    "IT": {"tuition_pct": 2.0, "living_pct": 3.0, "note": "Income-banded public tuition moves slowly; living costs track euro-area inflation."},
    "EE": {"tuition_pct": 3.5, "living_pct": 4.5, "note": "Baltic inflation has run above the euro-area average."},
    "ES": {"tuition_pct": 2.0, "living_pct": 3.5, "note": "Regulated public tuition is stable; big-city rents rise faster."},
    "FR": {"tuition_pct": 2.0, "living_pct": 3.0, "note": "Regulated public tuition moves slowly; Paris housing is the main growth driver."},
    "SE": {"tuition_pct": 2.5, "living_pct": 3.0, "note": "SEK-priced tuition for non-EU students is set by universities and moves moderately."},
    "IE": {"tuition_pct": 3.0, "living_pct": 4.5, "note": "Dublin housing pressure keeps living-cost growth above the euro-area average."},
}


def rates_for(iso_code: str | None) -> dict:
    return INFLATION_RATES.get((iso_code or "").strip().upper(), DEFAULT_RATES)
