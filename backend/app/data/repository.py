"""Read helpers over the cost database, plus the Source -> Citation mapper."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.schemas import Citation
from app.data.models import CostItem, Source


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
