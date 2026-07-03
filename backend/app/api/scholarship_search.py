"""Live scholarship search endpoint: POST /scholarships/search.

Triggered explicitly from the UI (a button), never automatically, so a paid
web-search call only happens on demand. Guardrails (cache + daily cap) live in
the service. See app/services/scholarship_search.py.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.schemas import LiveScholarshipSearchRequest, LiveScholarshipSearchResponse
from app.data.db import get_session
from app.services.scholarship_search import search_live_scholarships

router = APIRouter(prefix="/scholarships", tags=["scholarships"])


@router.post("/search", response_model=LiveScholarshipSearchResponse)
def search(
    request: LiveScholarshipSearchRequest,
    session: Session = Depends(get_session),
) -> LiveScholarshipSearchResponse:
    return search_live_scholarships(
        session,
        country=request.country,
        field=request.field,
        degree_level=request.degree_level,
        report_currency=request.report_currency,
    )
