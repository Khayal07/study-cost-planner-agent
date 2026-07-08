"""Motivation letter endpoint: POST /letters/motivation (auth required).

Auth-gated because it is a paid LLM call that uses the user's saved eligibility
profile. Rate-limited via the /letters prefix in main.py.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.schemas import MotivationLetterRequest, MotivationLetterResponse
from app.core.security import get_current_user
from app.data.db import get_session
from app.data.models import User
from app.services.letters import generate_letter

router = APIRouter(prefix="/letters", tags=["letters"])


@router.post("/motivation", response_model=MotivationLetterResponse)
def motivation(
    request: MotivationLetterRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> MotivationLetterResponse:
    return generate_letter(session, user, request)
