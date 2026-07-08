"""Interview simulator: the LLM plays a scholarship/admissions interviewer.

Stateless like /chat — the client sends the whole (bounded) history each turn.
The interviewer asks one question at a time; after MAX_QUESTIONS (or an explicit
"finish") it returns structured feedback parsed defensively from JSON.
"""
from __future__ import annotations

import json
import re

from app.core.llm_client import llm
from app.core.schemas import (
    InterviewFeedback,
    InterviewRequest,
    InterviewResponse,
)
from app.core.text import sanitize_prompt_field

MAX_QUESTIONS = 6

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

_LANG = {
    "en": "Conduct the interview in English.",
    "az": "Conduct the interview in Azerbaijani (Azərbaycan dilində apar).",
}

_SYSTEM = (
    "You are a friendly but rigorous interviewer for a scholarship/university admission. "
    "Ask exactly ONE question per turn — short and specific (motivation, academic "
    "background, goals, funding need, resilience). React briefly (one sentence) to the "
    "student's previous answer before the next question. Never answer for the student, "
    "never invent facts about them. {lang}"
)

_FEEDBACK_SYSTEM = (
    "You are an interview coach. Based on the transcript, return ONLY a JSON object: "
    '{{"strengths": ["..."], "improvements": ["..."], "overall": "..."}} — 2-3 concise '
    "items per list and a 1-2 sentence overall verdict. {lang} Respond with ONLY valid JSON."
)

_UNAVAILABLE = {
    "en": "Interview practice is unavailable right now (AI is disabled).",
    "az": "Müsahibə məşqi hazırda mümkün deyil (AI deaktivdir).",
}


def _context_line(request: InterviewRequest) -> str:
    ctx = request.context
    bits = []
    if ctx.scholarship_name:
        bits.append(f"scholarship: {sanitize_prompt_field(ctx.scholarship_name, max_len=160)}")
    if ctx.university_name:
        bits.append(f"university: {sanitize_prompt_field(ctx.university_name, max_len=160)}")
    if ctx.program_name:
        bits.append(f"program: {sanitize_prompt_field(ctx.program_name, max_len=160)}")
    if ctx.field:
        bits.append(f"field: {sanitize_prompt_field(ctx.field, max_len=120)}")
    return f"Interview context — {'; '.join(bits)}." if bits else "General admission interview."


def _to_messages(request: InterviewRequest, system: str) -> list[dict]:
    messages = [{"role": "system", "content": system + " " + _context_line(request)}]
    for turn in request.history:
        role = "assistant" if turn.role == "interviewer" else "user"
        messages.append({"role": role, "content": sanitize_prompt_field(turn.content, max_len=1200)})
    return messages


def _question_count(request: InterviewRequest) -> int:
    return sum(1 for t in request.history if t.role == "interviewer")


def run_interview(request: InterviewRequest) -> InterviewResponse:
    lang = _LANG[request.language]
    asked = _question_count(request)

    if not llm.enabled:
        return InterviewResponse(message=_UNAVAILABLE[request.language], done=True, question_count=asked)

    if request.action == "finish" or (request.action == "reply" and asked >= MAX_QUESTIONS):
        return _feedback(request, lang, asked)

    system = _SYSTEM.format(lang=lang)
    if request.action == "start":
        messages = _to_messages(request, system)
        messages.append({"role": "user", "content": "Please start the interview with a short welcome and your first question."})
    else:
        messages = _to_messages(request, system)

    reply = llm.complete_messages(messages, max_tokens=400)
    if not reply:
        return _feedback(request, lang, asked) if asked > 0 else InterviewResponse(
            message=_UNAVAILABLE[request.language], done=True, question_count=asked
        )
    return InterviewResponse(message=reply, done=False, question_count=asked + 1)


def _feedback(request: InterviewRequest, lang: str, asked: int) -> InterviewResponse:
    transcript = "\n".join(
        f"{t.role}: {sanitize_prompt_field(t.content, max_len=1200)}" for t in request.history
    )
    raw = llm.complete_messages(
        [
            {"role": "system", "content": _FEEDBACK_SYSTEM.format(lang=lang)},
            {"role": "user", "content": transcript or "No answers were given."},
        ],
        max_tokens=500,
    )
    feedback = _parse_feedback(raw)
    message = feedback.overall or _UNAVAILABLE[request.language]
    return InterviewResponse(message=message, done=True, feedback=feedback, question_count=asked)


def _parse_feedback(raw: str | None) -> InterviewFeedback:
    if not raw:
        return InterviewFeedback(overall="")
    match = _JSON_RE.search(raw)
    if not match:
        # Model ignored the JSON instruction — salvage the text as the verdict.
        return InterviewFeedback(overall=raw[:400])
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return InterviewFeedback(overall=raw[:400])
    return InterviewFeedback(
        strengths=[str(s)[:300] for s in data.get("strengths", [])][:5],
        improvements=[str(s)[:300] for s in data.get("improvements", [])][:5],
        overall=str(data.get("overall", ""))[:600],
    )
