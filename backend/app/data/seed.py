"""Idempotent loader for the curated seed dataset (``db/seed/data.json``).

Resolves the nested, human-readable seed structure into normalized rows, creating
one `Source` per inline source object and attaching every `CostItem` to it. Safe to
run repeatedly: it skips if the database already contains countries.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.data.db import SessionLocal
from app.data.models import (
    CONFIDENCE,
    COST_TYPES,
    COVERAGE_TYPES,
    PERIODS,
    City,
    CostItem,
    Country,
    Program,
    Scholarship,
    Source,
    University,
)

SEED_DIR = Path(__file__).resolve().parent.parent.parent / "db" / "seed"
# Available datasets. "real" = web-sourced figures (default); "mock" = original demo data.
SEED_FILES = {"real": "data.real.json", "mock": "data.mock.json"}


def _seed_path() -> Path:
    """Resolve the active seed file from settings, falling back to mock if the
    real dataset has not been generated yet."""
    name = SEED_FILES.get(settings.seed_dataset, SEED_FILES["real"])
    path = SEED_DIR / name
    if not path.exists() and settings.seed_dataset == "real":
        path = SEED_DIR / SEED_FILES["mock"]
    return path


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _make_source(session: Session, raw: dict) -> Source:
    src = Source(
        url=raw.get("url"),
        title=raw["title"],
        publisher=raw["publisher"],
        source_type=raw["source_type"],
        accessed_date=_parse_date(raw.get("accessed_date")),
    )
    session.add(src)
    session.flush()
    return src


def _make_cost(
    session: Session,
    *,
    raw: dict,
    cost_type: str,
    scope_level: str,
    scope_id: int,
    source_id: int,
) -> None:
    assert cost_type in COST_TYPES, f"bad cost_type {cost_type}"
    assert raw["period"] in PERIODS, f"bad period {raw['period']}"
    assert raw["confidence"] in CONFIDENCE, f"bad confidence {raw['confidence']}"
    session.add(
        CostItem(
            cost_type=cost_type,
            amount=raw["amount"],
            currency=raw["currency"],
            period=raw["period"],
            scope_level=scope_level,
            scope_id=scope_id,
            confidence=raw["confidence"],
            note=raw.get("note"),
            source_id=source_id,
            valid_as_of=_parse_date(raw.get("valid_as_of")),
        )
    )


def load_seed(session: Session | None = None) -> dict:
    """Load the seed file into the database. Returns a small summary dict."""
    own_session = session is None
    session = session or SessionLocal()
    try:
        if session.scalar(select(Country).limit(1)) is not None:
            return {"status": "skipped", "reason": "countries already present"}

        path = _seed_path()
        data = json.loads(path.read_text(encoding="utf-8"))
        counts = {"countries": 0, "cities": 0, "universities": 0, "programs": 0, "cost_items": 0, "scholarships": 0, "sources": 0, "dataset": path.name}

        # Name -> id maps so the (optional) scholarships block can resolve its scope.
        country_ids: dict[str, int] = {}
        university_ids: dict[str, int] = {}
        program_ids: dict[str, int] = {}

        for c in data["countries"]:
            country = Country(name=c["name"], iso_code=c["iso_code"], default_currency=c["default_currency"])
            session.add(country)
            session.flush()
            country_ids[c["name"]] = country.id
            counts["countries"] += 1

            # Country-scoped costs: visa, insurance, hidden
            for cost_type, key in (("visa", "visa"), ("insurance", "insurance")):
                if c.get(key):
                    src = _make_source(session, c[key]["source"])
                    counts["sources"] += 1
                    _make_cost(session, raw=c[key], cost_type=cost_type,
                               scope_level="country", scope_id=country.id, source_id=src.id)
                    counts["cost_items"] += 1
            for hidden in c.get("hidden", []):
                src = _make_source(session, hidden["source"])
                counts["sources"] += 1
                _make_cost(session, raw=hidden, cost_type=hidden["cost_type"],
                           scope_level="country", scope_id=country.id, source_id=src.id)
                counts["cost_items"] += 1

            # Cities + city-scoped living costs (one source per city)
            city_by_name: dict[str, City] = {}
            for cd in c.get("cities", []):
                city = City(country_id=country.id, name=cd["name"])
                session.add(city)
                session.flush()
                city_by_name[cd["name"]] = city
                counts["cities"] += 1
                living_src = _make_source(session, cd["living_source"])
                counts["sources"] += 1
                for item in cd.get("living", []):
                    # Each item may carry its own source (e.g. a semester fee cited to
                    # the university, a transit pass cited to the transport authority);
                    # otherwise it inherits the city's shared living source.
                    if item.get("source"):
                        item_src = _make_source(session, item["source"])
                        counts["sources"] += 1
                    else:
                        item_src = living_src
                    _make_cost(session, raw=item, cost_type=item["cost_type"],
                               scope_level="city", scope_id=city.id, source_id=item_src.id)
                    counts["cost_items"] += 1

            # Universities + programs + program-scoped tuition
            for ud in c.get("universities", []):
                fee_src = _make_source(session, ud["fee_source"])
                counts["sources"] += 1
                city = city_by_name[ud["city"]]
                uni = University(country_id=country.id, city_id=city.id, name=ud["name"],
                                 official_url=ud.get("official_url"), source_id=fee_src.id)
                session.add(uni)
                session.flush()
                university_ids[ud["name"]] = uni.id
                counts["universities"] += 1
                for pd in ud.get("programs", []):
                    prog = Program(university_id=uni.id, name=pd["name"], field=pd["field"],
                                   degree_level=pd["degree_level"], language=pd["language"],
                                   duration_years=pd["duration_years"])
                    session.add(prog)
                    session.flush()
                    program_ids[pd["name"]] = prog.id
                    counts["programs"] += 1
                    _make_cost(session, raw=pd["tuition"], cost_type="tuition",
                               scope_level="program", scope_id=prog.id, source_id=fee_src.id)
                    counts["cost_items"] += 1

        # Optional top-level scholarships block (cited like every other figure).
        for sch in data.get("scholarships", []):
            scope_level = sch["scope_level"]
            assert scope_level in {"global", "country", "university", "program"}, \
                f"bad scope_level {scope_level}"
            assert sch["coverage_type"] in COVERAGE_TYPES, f"bad coverage_type {sch['coverage_type']}"
            assert sch["period"] in PERIODS, f"bad period {sch['period']}"
            assert sch["confidence"] in CONFIDENCE, f"bad confidence {sch['confidence']}"

            scope_id = None
            if scope_level == "country":
                scope_id = country_ids[sch["scope_name"]]
            elif scope_level == "university":
                scope_id = university_ids[sch["scope_name"]]
            elif scope_level == "program":
                scope_id = program_ids[sch["scope_name"]]

            src = _make_source(session, sch["source"])
            counts["sources"] += 1
            docs = sch.get("documents_required")
            session.add(
                Scholarship(
                    name=sch["name"],
                    provider=sch["provider"],
                    scope_level=scope_level,
                    scope_id=scope_id,
                    coverage_type=sch["coverage_type"],
                    amount=sch.get("amount"),
                    coverage_pct=sch.get("coverage_pct"),
                    currency=sch["currency"],
                    period=sch["period"],
                    degree_levels=sch.get("degree_levels"),
                    fields=sch.get("fields"),
                    nationality_rule=sch.get("nationality_rule"),
                    min_gpa=sch.get("min_gpa"),
                    language_requirement=sch.get("language_requirement"),
                    renewable=sch.get("renewable", False),
                    deadline=_parse_date(sch.get("deadline")),
                    application_url=sch.get("application_url"),
                    documents_required=",".join(docs) if isinstance(docs, list) else docs,
                    confidence=sch["confidence"],
                    source_id=src.id,
                    valid_as_of=_parse_date(sch.get("valid_as_of")),
                )
            )
            counts["scholarships"] += 1

        session.commit()
        return {"status": "seeded", **counts}
    finally:
        if own_session:
            session.close()
