"""PDF export endpoint: POST /export/pdf — re-runs the plan and returns a PDF."""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.agents.orchestrator import Orchestrator
from app.core.schemas import Citation, LiveScholarship, PlanResult, PlanningRequest, ScholarshipMatch
from app.data.db import get_session
from app.services.pdf import render_plan_pdf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["export"])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "report"


def _apply_extra_scholarships(plan: PlanResult, extras: list[LiveScholarship]) -> None:
    """Fold user-selected live (web-found) scholarships into the featured university:
    list them alongside the dataset awards and lower its net total by their combined
    yearly value (floored at zero). Export always features one university → candidate[0]."""
    if not extras or not plan.candidates:
        return
    top = plan.candidates[0]
    cur = top.report_currency
    added = 0.0
    for i, s in enumerate(extras):
        val = float(s.annual_value or 0)
        added += val
        top.scholarships.append(ScholarshipMatch(
            scholarship_id=-(i + 1),  # negative → distinguishes web awards from dataset rows
            name=s.name,
            provider=s.provider or "Web source",
            coverage_type=s.coverage_type or "external award",
            estimated_value=round(val, 2),
            currency=cur,
            eligibility="likely",
            match_score=100,
            reasons=[s.eligibility] if s.eligibility else [],
            application_url=s.official_url,
            citation=Citation(
                publisher=s.provider or "Web source",
                url=s.official_url,
                source_type="official_university",
            ),
        ))
    if added <= 0:
        return
    base = top.total_annual
    combined = min((top.total_scholarship_value or 0.0) + added, base)
    top.total_scholarship_value = round(combined, 2)
    top.net_total_annual = round(base - combined, 2)
    if top.budget_gap is not None:
        budget_report = top.total_annual + top.budget_gap
        top.net_budget_gap = round(budget_report - top.net_total_annual, 2)
        top.net_affordable = top.net_budget_gap >= 0


@router.post("/pdf")
def export_pdf(request: PlanningRequest, session: Session = Depends(get_session)) -> Response:
    # A selected university → a report for THAT university only, not the whole comparison.
    if request.focus_program_id is not None:
        request = request.model_copy(
            update={"program_ids": [request.focus_program_id], "max_results": 1}
        )

    plan = Orchestrator().run(session, request)
    _apply_extra_scholarships(plan, request.extra_scholarships)
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
