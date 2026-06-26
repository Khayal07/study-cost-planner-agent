"""Read helpers over the cost database, plus the Source -> Citation mapper."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from sqlalchemy import or_, tuple_

from app.core.schemas import Citation
from app.data.models import CostItem, Scholarship, Source


def to_citation(source: Source) -> Citation:
    return Citation(
        publisher=source.publisher,
        url=source.url,
        accessed_date=source.accessed_date,
        source_type=source.source_type,
    )


def tuition_items(session: Session, program_id: int) -> list[CostItem]:
    return list(
        session.scalars(
            select(CostItem).where(
                CostItem.scope_level == "program",
                CostItem.scope_id == program_id,
                CostItem.cost_type == "tuition",
            )
        )
    )


def living_items(session: Session, city_id: int) -> list[CostItem]:
    return list(
        session.scalars(
            select(CostItem).where(
                CostItem.scope_level == "city",
                CostItem.scope_id == city_id,
            )
        )
    )


def country_items(session: Session, country_id: int, cost_type: str | None = None) -> list[CostItem]:
    stmt = select(CostItem).where(
        CostItem.scope_level == "country",
        CostItem.scope_id == country_id,
    )
    if cost_type:
        stmt = stmt.where(CostItem.cost_type == cost_type)
    return list(session.scalars(stmt))


def scholarships_for_candidate(
    session: Session, *, program_id: int, university_id: int, country_id: int
) -> list[Scholarship]:
    """All awards applicable to one candidate: global, or scoped to its
    country / university / program (mirrors the polymorphic CostItem lookup)."""
    scoped = tuple_(Scholarship.scope_level, Scholarship.scope_id).in_(
        [("country", country_id), ("university", university_id), ("program", program_id)]
    )
    stmt = select(Scholarship).where(
        or_(Scholarship.scope_level == "global", scoped)
    )
    return list(session.scalars(stmt))
