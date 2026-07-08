"""Motivation letter generator (auth-only; a paid LLM call producing a personal draft).

The server pulls the eligibility profile from the signed-in user's row — the
request only carries the award/program context. Every free-text field passes
through sanitize_prompt_field before prompt interpolation. When application_id
is supplied and owned, the draft is persisted on the tracked application and a
matching "motivation letter" checklist document is ticked.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.llm_client import llm
from app.core.schemas import MotivationLetterRequest, MotivationLetterResponse
from app.core.text import sanitize_prompt_field
from app.data.models import Application, User

_SYSTEM = (
    "You draft motivation letters for scholarship applications. Write a complete, "
    "sincere letter (250-400 words) in the first person as the student. Use only the "
    "facts provided — never invent grades, achievements, institutions or personal "
    "history. Where a personal story or specific detail is needed, insert a clearly "
    "marked placeholder like [describe your project]. No heading, greeting line "
    "'Dear Selection Committee,' is fine. Do not mention being an AI."
)
_LANG = {
    "en": "Write in English.",
    "az": "Write in Azerbaijani (Azərbaycan dilində yaz).",
}
_TONE = {
    "formal": "Keep the tone formal and precise.",
    "personal": "Keep the tone warm and personal while staying professional.",
}
_LETTER_DOC_TOKENS = ("motivation letter", "motivation", "motivasiya")


def generate_letter(
    session: Session, user: User, request: MotivationLetterRequest
) -> MotivationLetterResponse:
    if not llm.enabled:
        raise HTTPException(status_code=503, detail="AI letter drafting is unavailable (LLM disabled)")

    parts = [f"Scholarship: {sanitize_prompt_field(request.scholarship_name, max_len=160)}."]
    if request.provider:
        parts.append(f"Provider: {sanitize_prompt_field(request.provider, max_len=160)}.")
    if request.university_name:
        parts.append(f"University: {sanitize_prompt_field(request.university_name, max_len=160)}.")
    if request.program_name:
        parts.append(f"Program: {sanitize_prompt_field(request.program_name, max_len=160)}.")
    if user.nationality:
        parts.append(f"Student nationality: {sanitize_prompt_field(user.nationality, max_len=80)}.")
    if user.gpa is not None:
        parts.append(f"GPA: {float(user.gpa):.2f} on a 4.0 scale.")
    if user.language_test:
        parts.append(f"Language test: {sanitize_prompt_field(user.language_test, max_len=120)}.")
    if request.user_notes:
        parts.append(f"Student's own notes: {sanitize_prompt_field(request.user_notes, max_len=600)}.")
    parts.append(_TONE[request.tone])
    parts.append(_LANG[request.language])

    letter = llm.complete_text(_SYSTEM, "\n".join(parts), max_tokens=800)
    if not letter:
        raise HTTPException(status_code=503, detail="AI letter drafting failed — try again shortly")

    saved = False
    if request.application_id is not None:
        app = session.get(Application, request.application_id)
        if app is not None and app.user_id == user.id:
            app.motivation_letter = letter
            for doc in app.documents:
                if any(tok in doc.name.lower() for tok in _LETTER_DOC_TOKENS):
                    doc.done = True
            session.commit()
            saved = True

    return MotivationLetterResponse(letter=letter, language=request.language, saved=saved)
