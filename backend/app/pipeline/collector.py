"""Collect step: pick target universities, web-search each, write staging.

One paid call per university, hard-capped by settings.pipeline_max_calls.
Universities already covered (in the DB, or recorded in the staging file with
any status) are never searched again — re-runs are free until you add targets.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.text import sanitize_prompt_field
from app.data.models import City, Country, Program, University
from app.data.seed import SEED_DIR
from app.pipeline.validate import country_tuition_bands, validate_entry

logger = logging.getLogger(__name__)

_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)
SCHEMA_VERSION = 1


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "field"


def staging_dir() -> Path:
    path = SEED_DIR / "staging"
    path.mkdir(parents=True, exist_ok=True)
    return path


def staging_path(field: str, degree: str | None) -> Path:
    name = slugify(field) + (f"-{degree}" if degree else "")
    return staging_dir() / f"{name}.json"


def load_staging(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _staged_universities(staging: dict) -> set[str]:
    return {e.get("university", "") for e in staging.get("entries", [])}


def plan_targets(
    session: Session,
    *,
    field: str,
    degree: str | None,
    country_iso: str | None,
    limit: int | None,
    staging: dict,
) -> list[dict]:
    """Universities to search: everything in scope minus those already covered
    (existing program with the field in the DB, or any staging record)."""
    stmt = (
        select(University, City.name, Country.name, Country.iso_code, Country.default_currency)
        .join(City, University.city_id == City.id)
        .join(Country, University.country_id == Country.id)
        .order_by(Country.name, University.name)
    )
    if country_iso:
        stmt = stmt.where(Country.iso_code == country_iso.upper())

    staged = _staged_universities(staging)
    field_l = field.strip().lower()
    targets: list[dict] = []
    for uni, city_name, country_name, iso, currency in session.execute(stmt).all():
        if uni.name in staged:
            continue
        existing = session.execute(
            select(Program.id).where(
                Program.university_id == uni.id,
                Program.field.ilike(field_l),
                *( [Program.degree_level == degree] if degree else [] ),
            )
        ).first()
        if existing:
            continue
        targets.append(
            {
                "university": uni.name,
                "official_url": uni.official_url,
                "city": city_name,
                "country": country_name,
                "country_iso": iso,
                "default_currency": currency,
            }
        )
    if limit is not None:
        targets = targets[:limit]
    return targets


def _build_prompt(target: dict, field: str, degree: str | None) -> str:
    uni = sanitize_prompt_field(target["university"], max_len=160)
    city = sanitize_prompt_field(target["city"], max_len=80)
    country = sanitize_prompt_field(target["country"], max_len=80)
    field_s = sanitize_prompt_field(field, max_len=120)
    degree_s = sanitize_prompt_field(degree or "", max_len=20)
    currency = sanitize_prompt_field(target["default_currency"], max_len=3)
    degree_txt = f"{degree_s} " if degree_s else "bachelor or master "
    return (
        f"Find the single most relevant {degree_txt}degree program in {field_s} taught at "
        f"{uni} in {city}, {country}, open to international students. Search the web, "
        f"preferring the university's own official tuition/program pages. Return ONLY one "
        f"JSON object (no prose) with these keys: "
        f'"program_name" (official name), "degree_level" ("bachelor" or "master"), '
        f'"language" (language of instruction), "duration_years" (number), '
        f'"tuition_amount" (tuition for NON-EU international students as a plain number, '
        f"no symbols; 0 if tuition-free), "
        f'"tuition_currency" (3-letter code, prefer {currency}), '
        f'"tuition_period" ("annual", "monthly" or "one_time" — what the amount covers; '
        f'per-semester amounts must be converted to annual), '
        f'"source_url" (the page where you found the tuition figure), '
        f'"source_title" (that page\'s title), '
        f'"note" (one short sentence of context, e.g. which student group the fee applies to). '
        f"If {uni} does not offer any such program to international students, return exactly "
        f'{{"not_offered": true}}. Never invent a program or a figure.'
    )


def _to_number(value) -> float | None:
    if value in (None, "", "null"):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    digits = re.sub(r"[^0-9.]", "", str(value).replace(",", ""))
    try:
        return float(digits)
    except ValueError:
        return None


def _parse_result(raw: str) -> dict | None:
    match = _JSON_OBJ_RE.search(raw or "")
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    if data.get("not_offered") is True:
        return {"not_offered": True}
    data["tuition_amount"] = _to_number(data.get("tuition_amount"))
    data["duration_years"] = _to_number(data.get("duration_years"))
    return data


def _fetch_one(prompt: str) -> str:
    """One web-search call (same client pattern as the live scholarship search).
    Kept tiny so tests monkeypatch it. Returns '' on failure."""
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
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
        )
        return resp.choices[0].message.content or ""
    except Exception as exc:
        logger.warning("Pipeline search failed: %s", exc)
        return ""


def collect(
    session: Session,
    *,
    field: str,
    degree: str | None = None,
    country_iso: str | None = None,
    limit: int | None = None,
    plan_only: bool = False,
) -> dict:
    """Run one collect pass. Returns a summary dict for the CLI to print:
    {targets, entries (new this run), staging_file, calls_made, truncated}."""
    field = field.strip()
    path = staging_path(field, degree)
    staging = load_staging(path)

    targets = plan_targets(
        session, field=field, degree=degree, country_iso=country_iso, limit=limit, staging=staging
    )
    if plan_only:
        return {"targets": targets, "entries": [], "staging_file": str(path), "calls_made": 0, "truncated": False}

    if not targets:
        return {"targets": [], "entries": [], "staging_file": str(path), "calls_made": 0, "truncated": False}

    if not settings.use_openai:
        raise RuntimeError("Pipeline needs an OpenAI key (OPENAI_API_KEY) — set it in .env")

    truncated = len(targets) > settings.pipeline_max_calls
    targets = targets[: settings.pipeline_max_calls]

    if not staging:
        staging = {
            "schema_version": SCHEMA_VERSION,
            "mode": "new_field",
            "field": field,
            "degree_level": degree,
            "model": settings.openai_search_model,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "entries": [],
        }

    bands = country_tuition_bands(session)
    new_entries: list[dict] = []
    calls = 0
    for target in targets:
        raw_text = _fetch_one(_build_prompt(target, field, degree))
        calls += 1
        parsed = _parse_result(raw_text)

        entry = {
            "country": target["country"],
            "country_iso": target["country_iso"],
            "university": target["university"],
            "collected_at": date.today().isoformat(),
            "validation": {"errors": [], "warnings": []},
            "raw": parsed if parsed is not None else {"unparseable": (raw_text or "")[:2000]},
        }
        if parsed is None:
            entry["status"] = "rejected"
            entry["validation"]["errors"] = ["model returned no parseable JSON object"]
        elif parsed.get("not_offered"):
            entry["status"] = "not_offered"
        else:
            program, errors, warnings = validate_entry(
                parsed,
                field=field,
                country_iso=target["country_iso"],
                default_currency=target["default_currency"],
                university_name=target["university"],
                official_url=target["official_url"],
                bands=bands,
            )
            entry["validation"] = {"errors": errors, "warnings": warnings}
            if program is None:
                entry["status"] = "rejected"
                entry["program"] = None
            else:
                entry["status"] = "pending"
                entry["program"] = program
        new_entries.append(entry)

    staging["entries"] = staging.get("entries", []) + new_entries
    staging["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    from app.pipeline.merge import atomic_write_json  # local import: avoid cycle

    atomic_write_json(path, staging)
    return {
        "targets": targets,
        "entries": new_entries,
        "staging_file": str(path),
        "calls_made": calls,
        "truncated": truncated,
    }
