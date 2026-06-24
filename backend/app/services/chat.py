"""Chat orchestration: same grounded pipeline as the form, two modes.

- **plan**: the message contains enough to plan (a budget) -> run the full agent
  pipeline and summarize, with citations.
- **answer**: a narrow question (e.g. "visa cost in Germany") -> structured lookup
  of real cost rows, converted and cited. No invented numbers.
- **clarify**: not enough info -> ask for what's missing.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.intent import extract_intent
from app.agents.orchestrator import Orchestrator
from app.core.config import settings
from app.core.llm_client import llm
from app.core.schemas import ChatResponse, CitedFigure
from app.core.text import fold
from app.data.models import City, CostItem, Country, Program, University
from app.data.repository import to_citation
from app.services.currency import CurrencyService

COST_KEYWORDS = {
    "visa": ["visa", "viza"],
    "insurance": ["insurance", "sığorta", "sigorta", "health"],
    "tuition": ["tuition", "təhsil haqqı", "təhsil haqqi", "fee", "fees"],
    "rent": ["rent", "kirayə", "kira", "accommodation", "housing"],
    "food": ["food", "qida", "yemək", "groceries"],
    "transport": ["transport", "nəqliyyat"],
    "utilities": ["utilities", "kommunal"],
}
COUNTRY_SCOPE = {"visa", "insurance"}
LIVING_SCOPE = {"rent", "food", "transport", "utilities"}


def _detect_cost_type(message: str) -> str | None:
    text = fold(message)
    for cost_type, tokens in COST_KEYWORDS.items():
        if any(fold(t) in text for t in tokens):
            return cost_type
    return None


def _figure(session: Session, item: CostItem, report: str, label: str) -> CitedFigure:
    fx = CurrencyService(session)
    amount, _ = fx.convert(float(item.amount), item.currency, report)
    return CitedFigure(
        label=label, amount=round(amount, 2), currency=report,
        confidence=item.confidence, citation=to_citation(item.source),
    )


def _grounded_answer(session: Session, message: str, extracted: dict, report: str) -> ChatResponse | None:
    cost_type = _detect_cost_type(message)
    country_name = extracted.get("country")
    if not cost_type:
        return None

    figs: list[CitedFigure] = []

    if cost_type in COUNTRY_SCOPE:
        stmt = select(CostItem, Country).join(Country, CostItem.scope_id == Country.id).where(
            CostItem.scope_level == "country", CostItem.cost_type == cost_type
        )
        if country_name:
            stmt = stmt.where(Country.name.ilike(f"%{country_name}%"))
        for item, country in session.execute(stmt).all():
            figs.append(_figure(session, item, report, f"{cost_type.capitalize()} — {country.name}"))

    elif cost_type == "tuition":
        stmt = (
            select(CostItem, Program, University, Country)
            .join(Program, CostItem.scope_id == Program.id)
            .join(University, Program.university_id == University.id)
            .join(Country, University.country_id == Country.id)
            .where(CostItem.scope_level == "program", CostItem.cost_type == "tuition")
        )
        if country_name:
            stmt = stmt.where(Country.name.ilike(f"%{country_name}%"))
        for item, prog, uni, country in session.execute(stmt).all():
            figs.append(_figure(session, item, report, f"Tuition/yr — {uni.name}"))

    elif cost_type in LIVING_SCOPE:
        stmt = (
            select(CostItem, City, Country)
            .join(City, CostItem.scope_id == City.id)
            .join(Country, City.country_id == Country.id)
            .where(CostItem.scope_level == "city", CostItem.cost_type == cost_type)
        )
        if country_name:
            stmt = stmt.where(Country.name.ilike(f"%{country_name}%"))
        for item, city, country in session.execute(stmt).all():
            figs.append(_figure(session, item, report, f"{cost_type.capitalize()}/mo — {city.name}"))

    if not figs:
        return None

    # Keep the answer compact (top few), but report how many were found.
    shown = figs[:8]
    lines = [f"- {f.label}: {f.amount:,.0f} {f.currency} ({f.confidence})" for f in shown]
    scope = f" in {country_name}" if country_name else ""
    header = f"Here is what I found for {cost_type}{scope} (grounded in cited sources):"
    text = header + "\n" + "\n".join(lines)
    if llm.enabled:
        better = llm.complete_text(
            system="Answer the student's question in 1-2 sentences using ONLY the figures "
            "provided. Do not invent numbers. Mention they are sourced/estimates.",
            user=f"Question: {message}\nFigures:\n" + "\n".join(lines),
        )
        if better:
            text = better
    return ChatResponse(mode="answer", answer=text, extracted=extracted, figures=shown)


def _plan_answer(plan, report: str) -> str:
    if not plan.candidates:
        return "I couldn't find matching programs for that request."
    top = plan.candidates[0]
    base = (
        f"Top match: {top.program_name} at {top.university_name} ({top.city_name}, "
        f"{top.country_name}) — about {top.total_annual:,.0f} {report}/year "
        f"({'within' if top.affordable else 'over'} budget). "
        + (plan.recommendations[0] if plan.recommendations else "")
    )
    if llm.enabled:
        ctx = "\n".join(
            f"{c.rank}. {c.university_name} ({c.city_name}): {c.total_annual:,.0f} {report}/yr, "
            f"gap {c.budget_gap:,.0f}" for c in plan.candidates[:5]
        )
        better = llm.complete_text(
            system="Summarize study-abroad cost options for the student in 2-3 sentences. "
            "Use ONLY the provided totals; do not invent numbers.",
            user=f"Report currency {report}. Options:\n{ctx}\nRecommendations: {plan.recommendations}",
        )
        if better:
            return better
    return base


def handle_chat(session: Session, message: str, report_currency: str) -> ChatResponse:
    report_currency = (report_currency or settings.default_report_currency).upper()
    request, extracted = extract_intent(message, report_currency)

    if request is not None:
        plan = Orchestrator().run(session, request)
        return ChatResponse(
            mode="plan", answer=_plan_answer(plan, report_currency),
            extracted=extracted, plan=plan,
        )

    answer = _grounded_answer(session, message, extracted, report_currency)
    if answer is not None:
        return answer

    # Not enough info and not a narrow lookup -> clarify.
    missing = "your yearly budget (with currency)"
    if not extracted.get("country"):
        missing += " and a target country"
    return ChatResponse(
        mode="clarify",
        answer=f"Tell me {missing} and I'll build a full grounded cost plan. "
        "You can also ask narrow questions like 'visa cost in Germany' or "
        "'tuition in Poland'.",
        extracted=extracted,
    )
