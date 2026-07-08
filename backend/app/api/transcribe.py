"""Voice transcription endpoint: POST /chat/transcribe.

Mounted under /chat so the existing rate-limit prefix applies (parity with the
chat it feeds). Public like /chat; the real cost protection is the in-memory
daily cap on paid whisper calls. Audio stays in memory and is validated by
MIME whitelist + magic bytes before any byte reaches the API.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Form, HTTPException, UploadFile

from app.core.config import settings
from app.core.llm_client import llm
from app.core.schemas import TranscribeResponse
from app.api.transcript import read_capped

router = APIRouter(prefix="/chat", tags=["voice"])

_MAX_TEXT = 4000  # ChatRequest.message bound


def _is_webm(b: bytes) -> bool:
    return b.startswith(b"\x1a\x45\xdf\xa3")  # EBML (webm/mkv)


def _is_ogg(b: bytes) -> bool:
    return b.startswith(b"OggS")


def _is_wav(b: bytes) -> bool:
    return b.startswith(b"RIFF") and b[8:12] == b"WAVE"


def _is_mp4(b: bytes) -> bool:
    return len(b) > 11 and b[4:8] == b"ftyp"


AUDIO_TYPES: dict[str, tuple] = {
    "audio/webm": (_is_webm, "audio.webm"),
    "audio/ogg": (_is_ogg, "audio.ogg"),
    "audio/wav": (_is_wav, "audio.wav"),
    "audio/x-wav": (_is_wav, "audio.wav"),
    "audio/mp4": (_is_mp4, "audio.mp4"),
    "video/webm": (_is_webm, "audio.webm"),  # some browsers label MediaRecorder output video/webm
}

# Process-local daily counter for paid whisper calls. Resets at UTC midnight and
# on restart — deliberately simple; the per-IP rate limiter handles burst abuse.
_calls = {"day": date.min, "count": 0}


def _cap_reached() -> bool:
    today = date.today()
    if _calls["day"] != today:
        _calls["day"] = today
        _calls["count"] = 0
    return _calls["count"] >= settings.voice_daily_limit


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(file: UploadFile, language: str = Form(default="")) -> TranscribeResponse:
    if language not in ("", "az", "en"):
        raise HTTPException(status_code=422, detail="language must be az, en or empty")
    if not llm.enabled or not llm.use_openai:
        raise HTTPException(status_code=503, detail="Voice input is unavailable (transcription disabled)")

    data = await read_capped(file, settings.audio_max_bytes)
    base_type = (file.content_type or "").split(";")[0].strip().lower()
    entry = AUDIO_TYPES.get(base_type)
    if entry is None:
        raise HTTPException(status_code=415, detail="Upload webm, ogg, wav or mp4 audio")
    check, filename = entry
    if not check(data):
        raise HTTPException(status_code=415, detail="Audio content does not match its declared type")

    if _cap_reached():
        return TranscribeResponse(text="", language=language or None, limited=True)

    _calls["count"] += 1
    text = llm.transcribe(data, filename, language or None)
    if text is None:
        raise HTTPException(status_code=503, detail="Transcription failed — try again shortly")
    return TranscribeResponse(text=text[:_MAX_TEXT], language=language or None)
