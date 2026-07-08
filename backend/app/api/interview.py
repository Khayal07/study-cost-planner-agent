"""Interview simulator endpoint: POST /chat/interview.

Mounted under /chat so the existing rate-limit prefix covers it. Public and
stateless (parity with /chat) — the bounded history travels with each request.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.core.schemas import InterviewRequest, InterviewResponse
from app.services.interview import run_interview

router = APIRouter(prefix="/chat", tags=["interview"])


@router.post("/interview", response_model=InterviewResponse)
def interview(request: InterviewRequest) -> InterviewResponse:
    return run_interview(request)
