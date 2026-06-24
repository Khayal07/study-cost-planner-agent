"""Structured budget-form endpoint: POST /plan."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.orchestrator import Orchestrator
from app.core.schemas import PlanningRequest, PlanResult
from app.data.db import get_session

router = APIRouter(prefix="/plan", tags=["plan"])


@router.post("", response_model=PlanResult)
def create_plan(request: PlanningRequest, session: Session = Depends(get_session)) -> PlanResult:
    return Orchestrator().run(session, request)
