"""Saved plans + shareable links (Phase 3 #4).

- POST /plans, GET /plans, DELETE /plans/{id}: manage the signed-in user's saved
  plans (the small, stable PlanningRequest is what we persist).
- GET /plans/shared/{public_id}: public, no auth. Re-runs the planner so a shared
  link always reflects current sourced data.
"""
from __future__ import annotations

import json
import secrets

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.orchestrator import Orchestrator
from app.core.schemas import (
    PlanningRequest,
    SavedPlanCreate,
    SavedPlanDetail,
    SavedPlanOut,
)
from app.core.security import get_current_user
from app.data.db import get_session
from app.data.models import SavedPlan, User

router = APIRouter(prefix="/plans", tags=["plans"])


def _request_of(sp: SavedPlan) -> PlanningRequest:
    return PlanningRequest(**json.loads(sp.request_json))


def _to_out(sp: SavedPlan) -> SavedPlanOut:
    return SavedPlanOut(
        id=sp.id, public_id=sp.public_id, title=sp.title,
        created_at=sp.created_at, request=_request_of(sp),
    )


@router.post("", response_model=SavedPlanOut, status_code=status.HTTP_201_CREATED)
def create_saved_plan(
    req: SavedPlanCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> SavedPlanOut:
    sp = SavedPlan(
        public_id=secrets.token_urlsafe(8),
        user_id=user.id,
        title=req.title.strip(),
        request_json=json.dumps(req.request.model_dump(mode="json")),
    )
    session.add(sp)
    session.commit()
    session.refresh(sp)
    return _to_out(sp)


@router.get("", response_model=list[SavedPlanOut])
def list_saved_plans(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
) -> list[SavedPlanOut]:
    rows = session.scalars(
        select(SavedPlan).where(SavedPlan.user_id == user.id).order_by(SavedPlan.created_at.desc())
    ).all()
    return [_to_out(sp) for sp in rows]


@router.get("/shared/{public_id}", response_model=SavedPlanDetail)
def get_shared_plan(public_id: str, session: Session = Depends(get_session)) -> SavedPlanDetail:
    sp = session.scalar(select(SavedPlan).where(SavedPlan.public_id == public_id))
    if sp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    request = _request_of(sp)
    plan = Orchestrator().run(session, request)
    return SavedPlanDetail(
        public_id=sp.public_id, title=sp.title, created_at=sp.created_at,
        request=request, plan=plan,
    )


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_saved_plan(
    plan_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    sp = session.get(SavedPlan, plan_id)
    if sp is None or sp.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    session.delete(sp)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
