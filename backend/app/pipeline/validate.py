"""Validation for pipeline-collected entries (pure logic; DB used read-only).

The model's output is untrusted: every entry passes vocabulary, currency,
plausibility-band and URL checks before it can become a staging "pending"
entry, and again before apply. Errors reject the entry; warnings keep it
pending but are surfaced for the human review.
"""
from __future__ import annotations

from datetime import date
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.text import fold
from app.data.models import CostItem, Country, PERIODS, Program, University

# Plausibility fallback when a country has no tuition history yet (annual, any currency).
GLOBAL_TUITION_BAND = (0.0, 60_000.0)
DEGREE_LEVELS = {"bachelor", "master"}
# Default duration (years) per degree when the source page doesn't state one.
DEFAULT_DURATION = {"bachelor": 3.0, "master": 2.0}
DURATION_RANGE = (0.5, 8.0)


def _annualized(amount: float, period: str) -> float:
    return amount * 12 if period == "monthly" else amount


def country_tuition_bands(session: Session) -> dict[str, tuple[float, float]]:
    """Per-country plausibility band derived from existing program tuition:
    (min×0.3 floored at 0, max×3.0). Countries without data fall back to the
    global band at validation time."""
    rows = session.execute(
        select(Country.iso_code, CostItem.amount, CostItem.period)
        .join(University, University.country_id == Country.id)
        .join(Program, Program.university_id == University.id)
        .join(
            CostItem,
            (CostItem.scope_level == "program")
            & (CostItem.scope_id == Program.id)
            & (CostItem.cost_type == "tuition"),
        )
    ).all()
    per_country: dict[str, list[float]] = {}
    for iso, amount, period in rows:
        per_country.setdefault(iso, []).append(_annualized(float(amount), period))
    return {
        iso: (max(0.0, min(vals) * 0.3), max(vals) * 3.0)
        for iso, vals in per_country.items()
    }


def _host(url: str | None) -> str:
    try:
        return (urlsplit(url or "").hostname or "").lower()
    except ValueError:
        return ""


def _registrable(host: str) -> str:
    """Last two labels of a hostname — good enough to match uni subdomains
    (www.tum.de ≈ portal.tum.de) without a full public-suffix list."""
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def valid_http_url(url: str | None) -> bool:
    if not url:
        return False
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def classify_source_type(url: str, official_url: str | None, uni_name: str) -> str:
    """official_university when the URL clearly belongs to the university,
    else statistical_portal (third-party listing sites)."""
    host = _host(url)
    if official_url and _registrable(host) == _registrable(_host(official_url)):
        return "official_university"
    # Significant folded name tokens (skip generic words) appearing in the host.
    generic = {"university", "of", "the", "and", "technical", "national", "state", "school"}
    tokens = [t for t in fold(uni_name).split() if len(t) >= 4 and t not in generic]
    if any(t in host for t in tokens):
        return "official_university"
    return "statistical_portal"


def validate_entry(
    raw: dict,
    *,
    field: str,
    country_iso: str,
    default_currency: str,
    university_name: str,
    official_url: str | None,
    bands: dict[str, tuple[float, float]],
) -> tuple[dict | None, list[str], list[str]]:
    """Normalize a parsed model result into the seed-JSON program shape.

    Returns (program_dict | None, errors, warnings) — errors mean rejection.
    """
    errors: list[str] = []
    warnings: list[str] = []
    today = date.today().isoformat()

    name = str(raw.get("program_name") or "").strip()
    if not name:
        errors.append("missing program_name")
    elif len(name) > 200:
        errors.append("program_name over 200 chars")

    degree = str(raw.get("degree_level") or "").strip().lower()
    if degree not in DEGREE_LEVELS:
        errors.append(f"degree_level must be one of {sorted(DEGREE_LEVELS)}, got {degree!r}")

    language = str(raw.get("language") or "").strip()
    if not language:
        language = "English"
        warnings.append("language missing — defaulted to English")

    duration = raw.get("duration_years")
    try:
        duration = float(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration = None
    if duration is None and degree in DEFAULT_DURATION:
        duration = DEFAULT_DURATION[degree]
        warnings.append(f"duration_years missing — defaulted to {duration}")
    if duration is None or not (DURATION_RANGE[0] <= duration <= DURATION_RANGE[1]):
        errors.append(f"duration_years out of range {DURATION_RANGE}, got {duration!r}")

    amount = raw.get("tuition_amount")
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        amount = None
    if amount is None or amount < 0:
        errors.append(f"tuition_amount missing or negative: {raw.get('tuition_amount')!r}")

    currency = str(raw.get("tuition_currency") or "").strip().upper()
    allowed = {default_currency.upper(), "EUR", "USD"}
    if len(currency) != 3 or not currency.isalpha():
        errors.append(f"tuition_currency must be a 3-letter code, got {currency!r}")
    elif currency not in allowed:
        errors.append(f"currency {currency} not in whitelist {sorted(allowed)}")

    period = str(raw.get("tuition_period") or "annual").strip().lower()
    if period not in PERIODS:
        errors.append(f"tuition_period must be one of {sorted(PERIODS)}, got {period!r}")

    # Plausibility band (compared in-currency; cross-currency nuance is accepted —
    # bands are wide and the whitelist keeps currencies close to the country's own).
    range_ok = False
    if amount is not None and period in PERIODS:
        lo, hi = bands.get(country_iso, GLOBAL_TUITION_BAND)
        annual = _annualized(amount, period)
        # A widened band can still exclude legitimate free/cheap programs; only
        # the upper bound rejects, the lower bound warns.
        if annual > hi:
            errors.append(f"tuition {annual:.0f}/yr above plausibility band ({lo:.0f}-{hi:.0f})")
        else:
            range_ok = True
            if annual < lo:
                warnings.append(f"tuition {annual:.0f}/yr below the country's usual range — verify")

    url = str(raw.get("source_url") or "").strip() or None
    if url and not valid_http_url(url):
        warnings.append(f"source_url invalid, dropped: {url!r}")
        url = None

    confidence = "sourced" if (url and range_ok) else "estimate"
    if confidence == "estimate":
        warnings.append("confidence downgraded to estimate (missing URL or range check failed)")

    if errors:
        return None, errors, warnings

    source_type = classify_source_type(url, official_url, university_name) if url else "estimate"
    title = str(raw.get("source_title") or "").strip() or f"Tuition — {university_name}"
    publisher = university_name if source_type == "official_university" else (_host(url) or "estimate")

    program = {
        "name": name,
        "field": field,
        "degree_level": degree,
        "language": language,
        "duration_years": duration,
        "tuition": {
            "amount": amount,
            "currency": currency,
            "period": period,
            "confidence": confidence,
            "valid_as_of": today,
            "note": (str(raw.get("note") or "").strip() or None),
            "source": {
                "url": url,
                "title": title[:300],
                "publisher": publisher[:200],
                "source_type": source_type,
                "accessed_date": today,
            },
        },
    }
    return program, [], warnings
