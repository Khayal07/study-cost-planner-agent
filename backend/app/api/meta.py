"""Catalog endpoints: GET /meta/options and GET /meta/stats.

Exposes the countries, study fields, report currencies and live dataset counts
that actually exist in the seeded data, so the frontend never has to hardcode
them — adding a university to the dataset makes its country/field/currency show
up (and the homepage counters update) automatically.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.data.db import get_session
from app.data.models import (
    Country,
    CostItem,
    Program,
    Scholarship,
    University,
)

router = APIRouter(prefix="/meta", tags=["meta"])

# Currencies users can always pick as a report target, on top of whatever the
# dataset itself uses. The FX layer can resolve these via frankfurter/fallback.
_BASE_REPORT_CURRENCIES = ["EUR", "USD", "GBP", "AZN"]


def _countries_with_programs(session: Session) -> list[str]:
    """Countries that have at least one programme to plan against."""
    countries = list(
        session.scalars(
            select(Country.name)
            .join(University, University.country_id == Country.id)
            .join(Program, Program.university_id == University.id)
            .distinct()
            .order_by(Country.name)
        )
    )
    # Fall back to a plain country list if nothing matched (defensive).
    if not countries:
        countries = list(session.scalars(select(Country.name).order_by(Country.name)))
    return countries


@router.get("/options")
def options(session: Session = Depends(get_session)) -> dict:
    """Distinct countries (with a programme), study fields and report currencies."""
    countries = _countries_with_programs(session)
    fields = list(session.scalars(select(Program.field).distinct().order_by(Program.field)))

    # Report currencies = configured base set ∪ every currency present in the data,
    # so newly seeded countries' currencies appear without a frontend change.
    seeded = set(session.scalars(select(Country.default_currency).distinct()))
    seeded |= set(session.scalars(select(CostItem.currency).distinct()))
    ordered = list(dict.fromkeys([*_BASE_REPORT_CURRENCIES, *sorted(c for c in seeded if c)]))

    return {
        "countries": countries,
        "fields": fields,
        "report_currencies": ordered,
        "default_report_currency": settings.default_report_currency,
    }


@router.get("/stats")
def stats(session: Session = Depends(get_session)) -> dict:
    """Live dataset counters for the homepage hero (never hardcoded)."""
    countries = session.scalar(
        select(func.count(func.distinct(Country.id)))
        .select_from(Country)
        .join(University, University.country_id == Country.id)
        .join(Program, Program.university_id == University.id)
    ) or 0
    universities = session.scalar(select(func.count(University.id))) or 0
    programs = session.scalar(select(func.count(Program.id))) or 0
    # Every cost figure is cited (sourced OR flagged-estimate); `sourced_figures` is the
    # subset backed by an official source. The hero shows the honest total (cited_figures).
    cited_figures = session.scalar(select(func.count(CostItem.id))) or 0
    sourced_figures = session.scalar(
        select(func.count(CostItem.id)).where(CostItem.confidence == "sourced")
    ) or 0
    scholarships = session.scalar(select(func.count(Scholarship.id))) or 0

    return {
        "countries": int(countries),
        "universities": int(universities),
        "programs": int(programs),
        "cited_figures": int(cited_figures),
        "sourced_figures": int(sourced_figures),
        "scholarships": int(scholarships),
    }
