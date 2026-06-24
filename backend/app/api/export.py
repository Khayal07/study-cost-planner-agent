"""PDF export endpoint: POST /export/pdf — re-runs the plan and returns a PDF."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.agents.orchestrator import Orchestrator
from app.core.schemas import PlanningRequest
from app.data.db import get_session
from app.services.pdf import render_plan_pdf

router = APIRouter(prefix="/export", tags=["export"])


@router.post("/pdf")
def export_pdf(request: PlanningRequest, session: Session = Depends(get_session)) -> Response:
    plan = Orchestrator().run(session, request)
    pdf_bytes = render_plan_pdf(plan)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=study-cost-plan.pdf"},
    )
