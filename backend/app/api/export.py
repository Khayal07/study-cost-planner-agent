"""PDF export endpoint: POST /export/pdf — re-runs the plan and returns a PDF."""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.agents.orchestrator import Orchestrator
from app.core.schemas import PlanningRequest
from app.data.db import get_session
from app.services.pdf import render_plan_pdf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["export"])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "report"


@router.post("/pdf")
def export_pdf(request: PlanningRequest, session: Session = Depends(get_session)) -> Response:
    # A selected university → a report for THAT university only, not the whole comparison.
    if request.focus_program_id is not None:
        request = request.model_copy(
            update={"program_ids": [request.focus_program_id], "max_results": 1}
        )

    plan = Orchestrator().run(session, request)
    try:
        pdf_bytes = render_plan_pdf(plan)
    except Exception:  # WeasyPrint render/layout failure — don't crash the worker
        logger.exception("PDF rendering failed for export request")
        raise HTTPException(status_code=500, detail="Could not generate the PDF report. Please try again.")

    filename = "study-cost-plan.pdf"
    if request.focus_program_id is not None and plan.candidates:
        filename = f"study-cost-{_slugify(plan.candidates[0].university_name)}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
