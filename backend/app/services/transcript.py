"""Transcript analysis: vision extraction of GPA/degree from an uploaded file.

Security posture mirrors the PDF exporter's data-only stance: uploads stay in
memory, are size-capped while reading (the router enforces that), and must pass
both a MIME whitelist and a magic-byte check before any byte reaches the model.
The extracted values are treated as untrusted model output — range-validated,
never re-interpolated into another prompt, and never written to the profile by
the server (the user confirms in the UI, which then calls PUT /auth/me/profile).
"""
from __future__ import annotations

import base64

from fastapi import HTTPException

from app.core.llm_client import llm
from app.core.schemas import TranscriptAnalysisResponse, TranscriptExtraction

# MIME -> magic-byte predicate. Both must agree with the uploaded bytes.
def _is_png(b: bytes) -> bool:
    return b.startswith(b"\x89PNG\r\n\x1a\n")


def _is_jpeg(b: bytes) -> bool:
    return b.startswith(b"\xff\xd8\xff")


def _is_webp(b: bytes) -> bool:
    return b.startswith(b"RIFF") and b[8:12] == b"WEBP"


def _is_pdf(b: bytes) -> bool:
    return b.startswith(b"%PDF-")


ALLOWED_TYPES: dict[str, tuple] = {
    "image/png": (_is_png, "png"),
    "image/jpeg": (_is_jpeg, "jpg"),
    "image/webp": (_is_webp, "webp"),
    "application/pdf": (_is_pdf, "pdf"),
}

_SYSTEM = (
    "You read a university/school transcript (image or PDF) and extract facts. Return "
    'ONLY JSON: {"gpa": number|null, "gpa_scale": number|null, "gpa_on_4_scale": '
    'number|null, "degree_level": "high_school"|"bachelor"|"master"|"phd"|null, '
    '"institution": string|null, "confidence": "high"|"medium"|"low"}. '
    "gpa is the overall average exactly as printed; gpa_scale is the scale it uses "
    "(4, 5, 10, 100…); gpa_on_4_scale is your linear conversion to a 4.0 scale. "
    "If the document is not a transcript or values are unreadable, use nulls and "
    'confidence "low". Never guess.'
)


def validate_upload(content_type: str | None, data: bytes) -> str:
    """Return the canonical extension, or raise 415 when type/bytes disagree."""
    entry = ALLOWED_TYPES.get((content_type or "").lower())
    if entry is None:
        raise HTTPException(status_code=415, detail="Upload a PNG, JPEG, WEBP or PDF transcript")
    check, ext = entry
    if not check(data):
        raise HTTPException(status_code=415, detail="File content does not match its declared type")
    return ext


def analyze_transcript(data: bytes, content_type: str, filename: str) -> TranscriptAnalysisResponse:
    if not llm.enabled:
        raise HTTPException(status_code=503, detail="Transcript analysis is unavailable (LLM disabled)")

    ext = validate_upload(content_type, data)
    b64 = base64.b64encode(data).decode("ascii")
    if ext == "pdf":
        part = {
            "type": "file",
            "file": {"filename": "transcript.pdf", "file_data": f"data:application/pdf;base64,{b64}"},
        }
    else:
        part = {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{b64}"}}

    content = [{"type": "text", "text": "Extract the transcript facts as specified."}, part]
    raw = llm.complete_json_content(_SYSTEM, content, max_tokens=300)
    if raw is None:
        if ext == "pdf":
            raise HTTPException(
                status_code=415,
                detail="Could not read this PDF — try uploading a screenshot of the grades page instead",
            )
        raise HTTPException(status_code=503, detail="Transcript analysis failed — try again shortly")

    extraction = _validated(raw)
    note = None
    if extraction.gpa_on_4_scale is None:
        note = "No usable GPA found — you can still enter it manually."
    return TranscriptAnalysisResponse(extraction=extraction, note=note)


def _num(value, lo: float, hi: float) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if lo <= f <= hi else None


def _validated(raw: dict) -> TranscriptExtraction:
    degree = raw.get("degree_level")
    if degree not in ("high_school", "bachelor", "master", "phd"):
        degree = None
    confidence = raw.get("confidence")
    if confidence not in ("high", "medium", "low"):
        confidence = "low"
    institution = raw.get("institution")
    institution = str(institution)[:160] if institution else None
    return TranscriptExtraction(
        gpa=_num(raw.get("gpa"), 0, 1000),
        gpa_scale=_num(raw.get("gpa_scale"), 1, 1000),
        gpa_on_4_scale=_num(raw.get("gpa_on_4_scale"), 0, 4),
        degree_level=degree,
        institution=institution,
        confidence=confidence,
    )
