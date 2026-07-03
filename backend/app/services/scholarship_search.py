"""Live (web) scholarship search via OpenAI's built-in web-search model.

This is the *only* feature that reaches the internet at query time. Everything
else in the planner runs off the curated dataset. To keep a small paid credit
alive we guard every call:

- **Cache**: a repeat query for the same (country, field, degree_level) within
  ``settings.scholarship_cache_hours`` is served from the DB, no API call.
- **Daily cap**: at most ``settings.scholarship_search_daily_limit`` real calls
  per day (counted from cache rows fetched since midnight UTC).
- **Small + cheap**: ``gpt-4o-mini-search-preview``, capped result count, short
  output, defensive JSON parsing (search models can wrap JSON in prose).

When no OpenAI key is configured the search is disabled and returns an empty
result with an explanatory note, so the rest of the app is unaffected.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.schemas import LiveScholarship, LiveScholarshipSearchResponse
from app.data.models import ScholarshipSearchCache

logger = logging.getLogger(__name__)

# Search models can return the JSON array with surrounding commentary / citations.
_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def _cache_lookup(session: Session, country: str, field: str, degree: str) -> list[dict] | None:
    row = session.execute(
        select(ScholarshipSearchCache).where(
            ScholarshipSearchCache.country == country,
            ScholarshipSearchCache.field == field,
            ScholarshipSearchCache.degree_level == degree,
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    age_hours = (datetime.utcnow() - row.fetched_at).total_seconds() / 3600
    if age_hours > settings.scholarship_cache_hours:
        return None
    try:
        return json.loads(row.payload)
    except (json.JSONDecodeError, TypeError):
        return None


def _cache_store(session: Session, country: str, field: str, degree: str, results: list[dict]) -> None:
    row = session.execute(
        select(ScholarshipSearchCache).where(
            ScholarshipSearchCache.country == country,
            ScholarshipSearchCache.field == field,
            ScholarshipSearchCache.degree_level == degree,
        )
    ).scalar_one_or_none()
    payload = json.dumps(results, ensure_ascii=False)
    if row is None:
        session.add(
            ScholarshipSearchCache(
                country=country, field=field, degree_level=degree,
                payload=payload, fetched_at=datetime.utcnow(),
            )
        )
    else:
        row.payload = payload
        row.fetched_at = datetime.utcnow()
    session.commit()


def _calls_today(session: Session) -> int:
    """Count real API calls made today (cache rows refreshed since midnight UTC)."""
    midnight = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return int(
        session.execute(
            select(func.count(ScholarshipSearchCache.id)).where(
                ScholarshipSearchCache.fetched_at >= midnight
            )
        ).scalar_one()
    )


def _build_prompt(country: str, field: str, degree: str, currency: str) -> str:
    degree_txt = f" {degree}" if degree else ""
    return (
        f"Find real, currently-open scholarships for international students who want to "
        f"study{degree_txt} {field} in {country}. Search the web for official scholarship "
        f"pages (universities, governments, foundations). Return ONLY a JSON array (no prose) "
        f"of up to {settings.scholarship_search_max_results} items. Each item MUST be an object "
        f"with these string keys: "
        f'"name", "provider", "amount" (award value, prefer {currency} or note the currency), '
        f'"coverage_type" (e.g. full tuition / partial / stipend), "deadline", '
        f'"eligibility" (one short sentence), "official_url" (the real application/info page). '
        f"Only include scholarships you found a real source URL for. If unsure of a field, use null."
    )


def _parse_results(raw: str) -> list[dict]:
    match = _JSON_ARRAY_RE.search(raw)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    allowed = {"name", "provider", "amount", "coverage_type", "deadline", "eligibility", "official_url"}
    for item in data:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        clean = {k: (str(item[k]).strip() if item.get(k) not in (None, "", "null") else None) for k in allowed}
        clean["name"] = str(item["name"]).strip()
        out.append(clean)
        if len(out) >= settings.scholarship_search_max_results:
            break
    return out


def _fetch_from_web(country: str, field: str, degree: str, currency: str) -> list[dict]:
    """Call the OpenAI web-search model. Returns [] on any failure (caller degrades)."""
    from openai import OpenAI

    client = OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        timeout=settings.scholarship_search_timeout_seconds,
        max_retries=0,
    )
    try:
        # Note: search-preview models do not accept a temperature parameter.
        resp = client.chat.completions.create(
            model=settings.openai_search_model,
            messages=[{"role": "user", "content": _build_prompt(country, field, degree, currency)}],
            max_tokens=900,
        )
        content = resp.choices[0].message.content or ""
    except Exception as exc:
        logger.warning("Live scholarship search failed: %s", exc)
        return []
    return _parse_results(content)


def search_live_scholarships(
    session: Session,
    country: str,
    field: str,
    degree_level: str | None = None,
    report_currency: str = "EUR",
) -> LiveScholarshipSearchResponse:
    country = country.strip()
    field = field.strip()
    degree = _norm(degree_level)
    currency = (report_currency or settings.default_report_currency).upper()

    if not settings.use_openai:
        return LiveScholarshipSearchResponse(
            note="Live search is unavailable — no OpenAI key is configured. "
            "Showing dataset scholarships only.",
        )

    # 1. Serve from cache (no API call).
    cached = _cache_lookup(session, country, field, degree)
    if cached is not None:
        return LiveScholarshipSearchResponse(
            results=[LiveScholarship(**r) for r in cached], cached=True,
        )

    # 2. Enforce the daily call cap.
    if _calls_today(session) >= settings.scholarship_search_daily_limit:
        return LiveScholarshipSearchResponse(
            limited=True,
            note="Daily live-search limit reached (protecting API credit). "
            "Try again tomorrow or use the dataset scholarships.",
        )

    # 3. Real web search, then cache.
    results = _fetch_from_web(country, field, degree, currency)
    if results:
        _cache_store(session, country, field, degree, results)
    return LiveScholarshipSearchResponse(
        results=[LiveScholarship(**r) for r in results],
        note=None if results else "No live scholarships found for this search.",
    )
