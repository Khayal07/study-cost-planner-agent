"""Candidate retrieval: turn a PlanningRequest into matching programs.

Phase 2 uses structured SQL filtering (country / field / degree). Phase 4 adds a
pgvector rerank for free-form chat queries; the structured path stays the backbone
so results are always grounded in real rows.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.schemas import PlanningRequest
from app.data.models import City, Country, Program, University


@dataclass
class CandidateRefs:
    program: Program
    university: University
    city: City
    country: Country


def find_candidates(session: Session, request: PlanningRequest, limit: int = 50) -> list[CandidateRefs]:
    stmt = (
        select(Program, University, City, Country)
        .join(University, Program.university_id == University.id)
        .join(City, University.city_id == City.id)
        .join(Country, University.country_id == Country.id)
    )
    # Explicit program filter (chat detail/compare mode) short-circuits the others.
    if request.program_ids:
        stmt = stmt.where(Program.id.in_(request.program_ids)).limit(limit)
        rows = session.execute(stmt).all()
        return [CandidateRefs(program=p, university=u, city=c, country=co) for p, u, c, co in rows]
    if request.field:
        stmt = stmt.where(Program.field.ilike(f"%{request.field}%"))
    if request.degree_level:
        stmt = stmt.where(Program.degree_level.ilike(request.degree_level))
    if request.country:
        stmt = stmt.where(Country.name.ilike(f"%{request.country}%"))

    stmt = stmt.limit(limit)
    rows = session.execute(stmt).all()
    return [CandidateRefs(program=p, university=u, city=c, country=co) for p, u, c, co in rows]
