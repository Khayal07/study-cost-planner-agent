"""Application planner (public) + the personal application tracker (auth required).

- POST /applications/plan: deterministic, prioritized list of scholarships to apply
  to for a given plan request. No account needed.
- The rest (create/list/update/delete + document toggles) operate on the signed-in
  user's tracked applications, persisted in the database.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.orchestrator import Orchestrator
from app.core.schemas import (
    ApplicationCreate,
    ApplicationOut,
    ApplicationPlan,
    ApplicationUpdate,
    DocumentOut,
    PlanningRequest,
)
from app.core.security import get_current_user
from app.data.db import get_session
from app.data.models import APPLICATION_STATUSES, Application, ApplicationDocument, User
from app.services.application_planner import build_application_plan

router = APIRouter(prefix="/applications", tags=["applications"])


def _days_until(d: date | None) -> int | None:
    return (d - date.today()).days if d is not None else None


def _to_out(app: Application) -> ApplicationOut:
    return ApplicationOut(
        id=app.id, scholarship_id=app.scholarship_id, program_id=app.program_id,
        scholarship_name=app.scholarship_name, provider=app.provider,
        university_name=app.university_name, coverage_type=app.coverage_type,
        estimated_value=float(app.estimated_value) if app.estimated_value is not None else None,
        currency=app.currency, deadline=app.deadline,
        days_until_deadline=_days_until(app.deadline),
        application_url=app.application_url, status=app.status, notes=app.notes,
        documents=[
            DocumentOut(id=d.id, name=d.name, done=d.done)
            for d in sorted(app.documents, key=lambda x: x.id)
        ],
    )


def _owned(app_id: int, user: User, session: Session) -> Application:
    app = session.get(Application, app_id)
    if app is None or app.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return app


# --- planner (public) ---

@router.post("/plan", response_model=ApplicationPlan)
def plan_applications(
    request: PlanningRequest, session: Session = Depends(get_session)
) -> ApplicationPlan:
    if request.focus_program_id is not None:
        request = request.model_copy(
            update={"program_ids": [request.focus_program_id], "max_results": 1}
        )
    plan = Orchestrator().run(session, request)
    return build_application_plan(plan)


# --- tracker (auth) ---

@router.get("", response_model=list[ApplicationOut])
def list_applications(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
) -> list[ApplicationOut]:
    apps = session.scalars(
        select(Application).where(Application.user_id == user.id).order_by(Application.created_at.desc())
    ).all()
    return [_to_out(a) for a in apps]


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def create_application(
    req: ApplicationCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApplicationOut:
    app = Application(
        user_id=user.id, scholarship_id=req.scholarship_id, program_id=req.program_id,
        scholarship_name=req.scholarship_name, provider=req.provider,
        university_name=req.university_name, coverage_type=req.coverage_type,
        estimated_value=req.estimated_value, currency=req.currency,
        deadline=req.deadline, application_url=req.application_url, status="planned",
    )
    app.documents = [ApplicationDocument(name=n, done=False) for n in req.documents]
    session.add(app)
    session.commit()
    session.refresh(app)
    return _to_out(app)


@router.patch("/{app_id}", response_model=ApplicationOut)
def update_application(
    app_id: int,
    req: ApplicationUpdate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApplicationOut:
    app = _owned(app_id, user, session)
    if req.status is not None:
        if req.status not in APPLICATION_STATUSES:
            raise HTTPException(status_code=422, detail=f"Invalid status: {req.status}")
        app.status = req.status
    if req.notes is not None:
        app.notes = req.notes
    session.commit()
    session.refresh(app)
    return _to_out(app)


@router.patch("/{app_id}/documents/{doc_id}", response_model=ApplicationOut)
def toggle_document(
    app_id: int,
    doc_id: int,
    done: bool,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApplicationOut:
    app = _owned(app_id, user, session)
    doc = next((d for d in app.documents if d.id == doc_id), None)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    doc.done = done
    session.commit()
    session.refresh(app)
    return _to_out(app)


@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_application(
    app_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    app = _owned(app_id, user, session)
    session.delete(app)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
