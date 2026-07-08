"""Transcript analysis endpoint: POST /profile/transcript (auth required).

Auth-gated paid vision call. The size cap is enforced while reading the stream
(Content-Length is not trusted); type checks happen in the service. Rate-limited
via the /profile prefix in main.py.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.core.config import settings
from app.core.schemas import TranscriptAnalysisResponse
from app.core.security import get_current_user
from app.data.models import User
from app.services.transcript import analyze_transcript

router = APIRouter(prefix="/profile", tags=["profile"])


async def read_capped(file: UploadFile, cap: int) -> bytes:
    """Read an upload without trusting Content-Length; 413 as soon as cap is passed."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(64 * 1024):
        total += len(chunk)
        if total > cap:
            raise HTTPException(status_code=413, detail=f"File too large (max {cap // (1024 * 1024)} MB)")
        chunks.append(chunk)
    if total == 0:
        raise HTTPException(status_code=422, detail="Empty file")
    return b"".join(chunks)


@router.post("/transcript", response_model=TranscriptAnalysisResponse)
async def transcript(
    file: UploadFile,
    user: User = Depends(get_current_user),
) -> TranscriptAnalysisResponse:
    data = await read_capped(file, settings.transcript_max_bytes)
    return analyze_transcript(data, file.content_type or "", file.filename or "transcript")
