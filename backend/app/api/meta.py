"""Catalog endpoint: GET /meta/options.

Exposes the countries, study fields and report currencies that actually exist in
the seeded data, so the frontend never has to hardcode them — adding a university
to the dataset makes its country/field show up in the UI automatically.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.db import get_session
from app.data.models import Country, Program, University

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/options")
def options(session: Session = Depends(get_session)) -> dict:
    """Return the distinct countries (with a programme) and study fields in the DB."""
    # Countries that actually have at least one programme to plan against
    # (Program -> University -> Country).
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

    fields = list(session.scalars(select(Program.field).distinct().order_by(Program.field)))
    return {"countries": countries, "fields": fields}
