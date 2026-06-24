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

from app.data.db import SessionLocal
from app.data.models import (
    CONFIDENCE,
    COST_TYPES,
    PERIODS,
    City,
    CostItem,
    Country,
    Program,
    Source,
    University,
)

SEED_PATH = Path(__file__).resolve().parent.parent.parent / "db" / "seed" / "data.json"


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

        data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        counts = {"countries": 0, "cities": 0, "universities": 0, "programs": 0, "cost_items": 0, "sources": 0}

        for c in data["countries"]:
            country = Country(name=c["name"], iso_code=c["iso_code"], default_currency=c["default_currency"])
            session.add(country)
            session.flush()
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
                    _make_cost(session, raw=item, cost_type=item["cost_type"],
                               scope_level="city", scope_id=city.id, source_id=living_src.id)
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
                counts["universities"] += 1
                for pd in ud.get("programs", []):
                    prog = Program(university_id=uni.id, name=pd["name"], field=pd["field"],
                                   degree_level=pd["degree_level"], language=pd["language"],
                                   duration_years=pd["duration_years"])
                    session.add(prog)
                    session.flush()
                    counts["programs"] += 1
                    _make_cost(session, raw=pd["tuition"], cost_type="tuition",
                               scope_level="program", scope_id=prog.id, source_id=fee_src.id)
                    counts["cost_items"] += 1

        session.commit()
        return {"status": "seeded", **counts}
    finally:
        if own_session:
            session.close()
