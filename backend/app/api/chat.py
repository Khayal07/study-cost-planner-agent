"""Chat endpoint: POST /chat — natural-language, grounded, cited."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.schemas import ChatRequest, ChatResponse
from app.data.db import get_session
from app.services.chat import handle_chat

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest, session: Session = Depends(get_session)) -> ChatResponse:
    return handle_chat(session, request.message, request.report_currency, request.profile)
