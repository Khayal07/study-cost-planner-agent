"""Study Abroad Advisor — a stateful, conversational brain over the grounded pipeline.

Design goals (why this exists):
- The old chat was stateless and lazy: it either dumped a full plan or returned a
  one-line clarify. This module turns it into a friendly consultant that *remembers*
  the conversation (via a round-tripped ``ChatProfile``), asks warm follow-up
  questions, discovers universities by budget, explains a single university in
  detail, compares options, and answers affordability questions.
- It keeps the project's core rule — **LLM for language, Python for math**. Every
  number still comes from the same deterministic agent pipeline and carries a
  citation. Nothing is invented; when data is missing (e.g. scholarships) we say so.

Memory model: no server-side sessions. The ``ChatProfile`` (budget, country, field,
degree, lifestyle, last results) is returned with each answer and sent back by the
client on the next turn, so the system 'remembers' without statefulness.
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.intent import COUNTRY_SYNONYMS, extract_slots
from app.agents.orchestrator import Orchestrator
from app.core.config import settings
from app.core.schemas import (
    CandidatePlan,
    ChatCandidateRef,
    ChatProfile,
    ChatResponse,
    ChatSuggestion,
    CitedFigure,
    PlanningRequest,
)
from app.core.text import fold
from app.data.models import City, CostItem, Country, Program, University
from app.data.repository import to_citation
from app.services.currency import CurrencyService

# Large stand-in budget so the pipeline computes totals even before the user gives a
# budget (we then simply don't show affordability until they do).
_NO_BUDGET = 1_000_000_000.0

CURRENCY_SYMBOL = {"EUR": "€", "USD": "$", "GBP": "£", "TRY": "₺", "PLN": "zł",
                   "HUF": "Ft", "AZN": "₼"}

# --- intent keyword sets (folded, diacritic-insensitive) -------------------------

GREETING_TOKENS = ["hello", "hi ", "hi!", "hey", "salam", "good morning",
                   "good evening", "good afternoon"]
THANKS_TOKENS = ["thank", "thanks", "tesekkur", "sag ol", "sagol", "cheers", "appreciate"]
COMPARE_TOKENS = ["compare", "comparison", "vs", "versus", "muqayise", "difference between",
                  "side by side", "side-by-side"]
PDF_TOKENS = ["pdf", "report", "hesabat", "download", "export", "document"]
AFFORD_TOKENS = ["afford", "enough", "kifayet", "can i study", "do i need", "need for",
                 "how much do i need", "is it enough", "cover", "within my budget"]
ANYWHERE_TOKENS = ["anywhere", "any country", "doesn't matter", "doesnt matter",
                   "no preference", "cheapest country", "wherever", "any where"]
DETAIL_TOKENS = ["tell me about", "explore", "details", "detail", "more about",
                 "info on", "information about", "look at", "show me"]

COST_KEYWORDS = {
    "visa": ["visa", "viza"],
    "insurance": ["insurance", "sigorta", "health insurance"],
    "tuition": ["tuition", "tehsil haqqi", "fee", "fees"],
    "rent": ["rent", "kiraye", "accommodation", "housing", "apartment"],
    "food": ["food", "qida", "yemek", "groceries"],
    "transport": ["transport", "neqliyyat"],
    "utilities": ["utilities", "kommunal", "bills"],
}
COUNTRY_SCOPE = {"visa", "insurance"}
LIVING_SCOPE = {"rent", "food", "transport", "utilities"}

# Short names students actually type -> a substring of the official DB name (folded).
UNIVERSITY_ALIASES = {
    "tum": "technical university of munich",
    "technical university of munich": "technical university of munich",
    "munich": "technical university of munich",
    "rwth": "rwth aachen",
    "aachen": "rwth aachen",
    "humboldt": "humboldt",
    "berlin": "humboldt",
    "uva": "university of amsterdam",
    "amsterdam": "university of amsterdam",
    "tu delft": "delft university of technology",
    "delft": "delft university of technology",
    "tu eindhoven": "eindhoven university of technology",
    "tue": "eindhoven university of technology",
    "eindhoven": "eindhoven university of technology",
    "agh": "agh university",
    "krakow": "agh university",
    "cracow": "agh university",
    "warsaw university of technology": "warsaw university of technology",
    "wut": "warsaw university of technology",
    "university of warsaw": "university of warsaw",
    "uw": "university of warsaw",
    "elte": "eotvos lorand",
    "eotvos": "eotvos lorand",
    "bme": "budapest university of technology",
    "budapest": "budapest university of technology",
    "szeged": "szeged",
    "metu": "middle east technical",
    "ankara": "middle east technical",
    "itu": "istanbul technical",
    "bogazici": "bogazici",
    "bosphorus": "bogazici",
}

ORDINAL_TOKENS = {
    1: ["first", "1st", "#1", "number one", "option 1", "option one", "top one", "top option"],
    2: ["second", "2nd", "#2", "number two", "option 2", "option two"],
    3: ["third", "3rd", "#3", "number three", "option 3", "option three"],
    4: ["fourth", "4th", "#4", "option 4"],
    5: ["fifth", "5th", "#5", "option 5"],
}


# --- small helpers ---------------------------------------------------------------

def _sym(currency: str) -> str:
    return CURRENCY_SYMBOL.get(currency.upper(), currency.upper() + " ")


def _money(amount: float, currency: str) -> str:
    return f"{_sym(currency)}{amount:,.0f}"


def _has_any(text: str, tokens: list[str]) -> bool:
    return any(t in text for t in tokens)


def _detect_cost_type(text: str) -> str | None:
    for cost_type, tokens in COST_KEYWORDS.items():
        if any(fold(t) in text for t in tokens):
            return cost_type
    return None


def _suggestion(label: str, message: str) -> ChatSuggestion:
    return ChatSuggestion(label=label, message=message)


def _country_chips() -> list[ChatSuggestion]:
    return [
        _suggestion("🇩🇪 Germany", "I want to study in Germany"),
        _suggestion("🇳🇱 Netherlands", "I want to study in the Netherlands"),
        _suggestion("🇵🇱 Poland", "I want to study in Poland"),
        _suggestion("🇹🇷 Turkey", "I want to study in Turkey"),
    ]


# --- pipeline access -------------------------------------------------------------

def _run_pipeline(session: Session, profile: ChatProfile, *,
                  program_ids: list[int] | None = None, max_results: int = 6):
    """Run the deterministic agent pipeline for the current profile."""
    report = (profile.report_currency or settings.default_report_currency).upper()
    budget = profile.budget_amount if profile.budget_amount else _NO_BUDGET
    request = PlanningRequest(
        country=profile.country,
        field=profile.field or "Computer Science",
        degree_level=profile.degree_level,
        budget_amount=budget,
        budget_currency=(profile.budget_currency or report).upper(),
        report_currency=report,
        lifestyle=profile.lifestyle or "moderate",
        max_results=max_results,
        program_ids=program_ids,
    )
    return Orchestrator().run(session, request)


def _match_score(budget_in_report: float | None, total: float) -> int | None:
    """0-100 budget-fit score. More affordable = safer = higher; over-budget tapers."""
    if not budget_in_report or total <= 0:
        return None
    ratio = budget_in_report / total
    if ratio >= 1:
        return min(100, 85 + round((ratio - 1) * 30))
    return max(1, round(ratio * 70))


def _budget_in_report(session: Session, profile: ChatProfile) -> float | None:
    if not profile.budget_amount:
        return None
    report = (profile.report_currency or settings.default_report_currency).upper()
    amount, _ = CurrencyService(session).convert(
        profile.budget_amount, (profile.budget_currency or report).upper(), report
    )
    return round(amount, 2)


def _store_candidates(session: Session, profile: ChatProfile,
                      candidates: list[CandidatePlan]) -> list[ChatCandidateRef]:
    budget_r = _budget_in_report(session, profile)
    refs: list[ChatCandidateRef] = []
    for c in candidates:
        refs.append(ChatCandidateRef(
            rank=c.rank or 0, program_id=c.program_id, program_name=c.program_name,
            university_name=c.university_name, city_name=c.city_name,
            country_name=c.country_name, total_annual=c.total_annual,
            affordable=c.affordable, match_score=_match_score(budget_r, c.total_annual),
        ))
    profile.last_candidates = refs
    return refs


# --- reference resolution --------------------------------------------------------

def _resolve_university_program(session: Session, text: str) -> int | None:
    """Map a free-text university mention to a program_id (CS master) via aliases."""
    matched_substr: str | None = None
    for alias, substr in UNIVERSITY_ALIASES.items():
        # Word-boundary match for short aliases to avoid accidental hits.
        pattern = rf"\b{re.escape(alias)}\b" if len(alias) <= 4 else re.escape(alias)
        if re.search(pattern, text):
            matched_substr = substr
            break
    if not matched_substr:
        return None
    row = session.execute(
        select(Program.id)
        .join(University, Program.university_id == University.id)
        .where(University.name.ilike(f"%{matched_substr}%"))
        .limit(1)
    ).first()
    return row[0] if row else None


_KNOWN_PLACES: set[str] | None = None
# Capitalized phrase following a targeting preposition, e.g. "for Harvard",
# "at University of Toronto", "about Oxford".
_NAMED_TARGET_RE = re.compile(
    r"\b(?:for|at|about|into|to|in)\s+"
    r"([A-Z][A-Za-z.&'-]+(?:\s+(?:of|the)?\s*[A-Z][A-Za-z.&'-]+){0,4})"
)


def _known_places(session: Session) -> set[str]:
    """Folded country + city names we cover, to avoid flagging them as 'unknown'."""
    global _KNOWN_PLACES
    if _KNOWN_PLACES is None:
        places = {fold(v) for v in COUNTRY_SYNONYMS.values()}
        places |= {fold(k) for k in COUNTRY_SYNONYMS}
        for (name,) in session.execute(select(City.name)).all():
            places.add(fold(name))
        _KNOWN_PLACES = places
    return _KNOWN_PLACES


def _unknown_institution(session: Session, message: str) -> str | None:
    """Return a named institution the user asked about that we don't cover, else None.

    Lets us answer 'How much for Harvard?' honestly instead of guessing or deflecting.
    """
    known = _known_places(session)
    for phrase in _NAMED_TARGET_RE.findall(message):
        phrase = phrase.strip()
        folded = fold(phrase)
        if folded in known or any(p in folded for p in known):
            continue
        if _resolve_university_program(session, folded):
            continue
        return phrase
    return None


def _resolve_ordinal_program(text: str, profile: ChatProfile) -> int | None:
    if not profile.last_candidates:
        return None
    if _has_any(text, ["cheapest", "best", "top option", "first option", "that one", "it"]):
        return profile.last_candidates[0].program_id
    if "last" in text:
        return profile.last_candidates[-1].program_id
    for rank, tokens in ORDINAL_TOKENS.items():
        if _has_any(text, tokens):
            for ref in profile.last_candidates:
                if ref.rank == rank:
                    return ref.program_id
    return None


# --- response builders -----------------------------------------------------------

def _candidate_summary_line(c: CandidatePlan, report: str,
                            score: int | None = None) -> str:
    fit = ""
    if c.affordable is True:
        fit = " — fits your budget ✅"
    elif c.affordable is False:
        gap = abs(c.budget_gap or 0)
        fit = f" — over by ~{_money(gap, report)} ⚠️"
    score_txt = f" · match {score}/100" if score is not None else ""
    return (f"{c.rank}. {c.university_name} ({c.city_name}, {c.country_name}) — "
            f"~{_money(c.total_annual, report)}/yr{fit}{score_txt}")


def _greeting(profile: ChatProfile) -> ChatResponse:
    answer = (
        "Hi! 👋 I'm your study-abroad cost advisor. I can help you find universities "
        "that fit your budget, break down the real cost of studying in each country "
        "(tuition, rent, food, insurance, visa — everything), compare your options and "
        "even put it all into a downloadable report.\n\n"
        "To point you in the right direction, tell me a little about your plan:\n"
        "1. Which country are you interested in?\n"
        "2. What's your yearly budget (and currency)?\n\n"
        "I currently have grounded, source-cited data for Computer Science master's "
        "programmes in Germany, the Netherlands, Poland, Hungary and Turkey."
    )
    return ChatResponse(
        mode="greeting", answer=answer, profile=profile,
        suggestions=[
            _suggestion("Study in Germany on €12k", "I want to study in Germany, my budget is €12000 per year"),
            _suggestion("Cheapest options anywhere", "Show me the cheapest options, budget €8000, any country"),
            _suggestion("🇩🇪 Germany", "I want to study in Germany"),
            _suggestion("🇵🇱 Poland", "I want to study in Poland"),
        ],
    )


def _thanks(profile: ChatProfile) -> ChatResponse:
    return ChatResponse(
        mode="answer",
        answer="You're very welcome! 😊 If you'd like, I can compare more universities, "
        "dig into the costs for a specific one, or generate a full PDF report. What would "
        "help most next?",
        profile=profile,
        suggestions=[
            _suggestion("Compare top 3", "Compare the top 3 options"),
            _suggestion("Generate report", "Generate a PDF report"),
        ],
    )


def _ask_for_budget(session: Session, profile: ChatProfile) -> ChatResponse:
    """Country known, budget missing — show what we cover there, then ask budget."""
    plan = _run_pipeline(session, profile, max_results=6)
    report = plan.report_currency
    if not plan.candidates:
        return _no_coverage(profile)
    _store_candidates(session, profile, plan.candidates)
    lines = "\n".join(
        f"• {c.university_name} ({c.city_name}) — ~{_money(c.total_annual, report)}/yr total"
        for c in plan.candidates
    )
    where = profile.country or "the countries I cover"
    answer = (
        f"Great choice! Here are the Computer Science master's programmes I have "
        f"source-cited cost data for in {where}:\n\n{lines}\n\n"
        f"These yearly totals include tuition, rent, food, transport, utilities, "
        f"insurance and visa — all grounded in cited sources.\n\n"
        f"**What's your yearly budget (and currency)?** Once I know that, I'll show you "
        f"exactly which ones fit and rank them by value for money."
    )
    return ChatResponse(
        mode="discovery", answer=answer, profile=profile, candidates=plan.candidates,
        suggestions=[
            _suggestion("Budget €10,000/yr", f"My budget is 10000 EUR for {where}"),
            _suggestion("Budget €15,000/yr", f"My budget is 15000 EUR for {where}"),
            _suggestion("Compare these", "Compare the top 3 options"),
        ],
    )


def _ask_for_country(profile: ChatProfile) -> ChatResponse:
    """Budget known, country missing — warm follow-up with country chips."""
    report = (profile.report_currency or "EUR").upper()
    budget_txt = _money(profile.budget_amount or 0, profile.budget_currency or report)
    answer = (
        f"Perfect — a budget of about {budget_txt} per year gives you real options. 🎯\n\n"
        f"To recommend the best-fitting universities, which country are you leaning "
        f"toward? I have grounded cost data for:\n"
        f"• 🇩🇪 Germany  • 🇳🇱 Netherlands  • 🇵🇱 Poland  • 🇭🇺 Hungary  • 🇹🇷 Turkey\n\n"
        f"If you're open to anywhere, just say \"any country\" and I'll show you the "
        f"best value across all of them."
    )
    chips = _country_chips()
    chips.append(_suggestion("Any country — cheapest", "Show me the cheapest options in any country"))
    return ChatResponse(mode="clarify", answer=answer, profile=profile, suggestions=chips)


def _discovery(session: Session, profile: ChatProfile) -> ChatResponse:
    """Budget known (country optional) — rank options and invite a next step."""
    plan = _run_pipeline(session, profile, max_results=6)
    report = plan.report_currency
    if not plan.candidates:
        return _no_coverage(profile)

    refs = _store_candidates(session, profile, plan.candidates)
    budget_r = _budget_in_report(session, profile)
    budget_txt = _money(budget_r or 0, report)
    affordable = [c for c in plan.candidates if c.affordable]
    scope = f" in {profile.country}" if profile.country else " across all countries I cover"

    score_by_id = {r.program_id: r.match_score for r in refs}
    lines = "\n".join(
        _candidate_summary_line(c, report, score_by_id.get(c.program_id))
        for c in plan.candidates
    )

    if affordable:
        best = affordable[0]
        headline = (
            f"Based on your budget of {budget_txt}/year, I found "
            f"**{len(affordable)} of {len(plan.candidates)}** programmes{scope} that fit. 🎉 "
            f"Your strongest match is **{best.university_name}** in {best.city_name} "
            f"(~{_money(best.total_annual, report)}/yr)."
        )
    else:
        closest = plan.candidates[0]
        short = abs(closest.budget_gap or 0)
        headline = (
            f"With a budget of {budget_txt}/year, none of the options{scope} fully fit yet — "
            f"but the closest is **{closest.university_name}** "
            f"(~{_money(closest.total_annual, report)}/yr, short by ~{_money(short, report)}). "
            f"Switching to a frugal lifestyle or a cheaper city can close that gap."
        )

    answer = (
        f"{headline}\n\nHere's the full ranked list (every figure is source-cited):\n\n"
        f"{lines}\n\n"
        f"Which one would you like to explore in detail — or shall I compare the top 3 "
        f"side by side?"
    )

    chips: list[ChatSuggestion] = []
    for c in plan.candidates[:3]:
        chips.append(_suggestion(f"Explore {c.university_name}", f"Tell me about {c.university_name}"))
    chips.append(_suggestion("Compare top 3", "Compare the top 3 options"))
    if profile.budget_amount:
        chips.append(_suggestion("Generate report", "Generate a PDF report"))

    return ChatResponse(
        mode="discovery", answer=answer, profile=profile, candidates=plan.candidates,
        can_export=bool(profile.budget_amount), suggestions=chips,
    )


def _detail(session: Session, profile: ChatProfile, program_id: int,
            *, affordability: bool = False) -> ChatResponse:
    plan = _run_pipeline(session, profile, program_ids=[program_id], max_results=1)
    if not plan.candidates:
        return _no_coverage(profile)
    c = plan.candidates[0]
    report = plan.report_currency
    profile.focus_program_id = program_id

    # Key figures with citations.
    figures: list[CitedFigure] = []
    for line in c.lines:
        figures.append(CitedFigure(
            label=line.label, amount=round(line.amount, 0), currency=report,
            confidence=line.confidence, citation=line.citation,
        ))

    tuition_txt = (f"{_money(c.annual_tuition, report)}/yr"
                   if c.annual_tuition > 0 else "no tuition fee 🎉")
    intro = (
        f"Here's the full picture for **{c.university_name}** in {c.city_name}, "
        f"{c.country_name}. 📍\n\n"
        f"It offers the {c.program_name} ({c.degree_level}, taught in {c.language}, "
        f"{c.duration_years:g} years). Annual costs, all grounded in cited sources:\n"
        f"• Tuition: {tuition_txt}\n"
        f"• Living: ~{_money(c.monthly_living, report)}/month "
        f"(rent, food, transport, utilities, insurance)\n"
        f"• **Estimated total: ~{_money(c.total_annual, report)}/year** "
        f"— including visa, one-off and local fees"
    )

    # Affordability verdict.
    verdict = ""
    budget_r = _budget_in_report(session, profile)
    if budget_r is not None:
        gap = budget_r - c.total_annual
        if gap >= 0:
            verdict = (
                f"\n\n✅ **Yes — this fits your budget.** At {_money(budget_r, report)}/year "
                f"you'd have about {_money(gap, report)} to spare for travel, books or savings."
            )
        else:
            verdict = (
                f"\n\n⚠️ **This is above your budget** of {_money(budget_r, report)}/year by "
                f"~{_money(abs(gap), report)}. A frugal lifestyle could help — see the scenarios below."
            )

    # Scenario range.
    scen_txt = ""
    scen = {s.name: s for s in c.scenarios}
    if "frugal" in scen and "comfortable" in scen:
        scen_txt = (
            f"\n\nDepending on lifestyle, your yearly total ranges from about "
            f"{_money(scen['frugal'].annual_total, report)} (frugal) to "
            f"{_money(scen['comfortable'].annual_total, report)} (comfortable)."
        )

    honesty = (
        "\n\nA quick note for transparency: my dataset covers verified **costs** only. I "
        "don't yet hold scholarship, admission-requirement, English-test or ranking data, "
        "so I won't guess at those — I'd rather be accurate than make something up."
    )
    nextstep = ("\n\nWould you like a full **PDF report** for this university, or shall I "
                "**compare** it with your other options?")

    answer = intro + verdict + scen_txt + honesty + nextstep
    mode = "affordability" if affordability else "detail"

    return ChatResponse(
        mode=mode, answer=answer, profile=profile, detail=c, figures=figures,
        candidates=[c], can_export=bool(profile.budget_amount),
        suggestions=[
            _suggestion(f"Download {c.university_name} report", "Generate a PDF report"),
            _suggestion("Compare with others", "Compare the top 3 options"),
            _suggestion("Show cheaper options", "Show me cheaper options"),
        ],
    )


def _compare(session: Session, profile: ChatProfile) -> ChatResponse:
    refs = profile.last_candidates[:3]
    if not refs:
        # Nothing to compare yet — run discovery instead.
        if profile.budget_amount or profile.country:
            return _discovery(session, profile)
        return _ask_for_country(profile)

    ids = [r.program_id for r in refs]
    plan = _run_pipeline(session, profile, program_ids=ids, max_results=len(ids))
    report = plan.report_currency
    cands = sorted(plan.candidates, key=lambda c: c.total_annual)

    blocks = []
    for c in cands:
        tuition = (_money(c.annual_tuition, report) + "/yr") if c.annual_tuition > 0 else "free"
        afford = ""
        if c.affordable is True:
            afford = " · fits budget ✅"
        elif c.affordable is False:
            afford = f" · over by {_money(abs(c.budget_gap or 0), report)} ⚠️"
        blocks.append(
            f"**{c.university_name}** ({c.city_name}, {c.country_name})\n"
            f"   Total: ~{_money(c.total_annual, report)}/yr{afford}\n"
            f"   Tuition: {tuition} · Living: ~{_money(c.monthly_living, report)}/mo"
        )

    cheapest = cands[0]
    lowest_living = min(cands, key=lambda c: c.monthly_living)
    insight = (
        f"💡 **{cheapest.university_name}** is the cheapest overall at "
        f"~{_money(cheapest.total_annual, report)}/yr"
    )
    if lowest_living.university_name != cheapest.university_name:
        insight += (f", while **{lowest_living.university_name}** has the lowest monthly "
                    f"living cost (~{_money(lowest_living.monthly_living, report)}/mo)")
    insight += "."

    answer = (
        "Here's a side-by-side comparison of your top options — every figure is "
        "source-cited:\n\n" + "\n\n".join(blocks) + "\n\n" + insight +
        "\n\nWant me to open one in detail, or generate a PDF report with all of them?"
    )

    chips = [_suggestion(f"Explore {c.university_name}", f"Tell me about {c.university_name}")
             for c in cands]
    chips.append(_suggestion("Generate report", "Generate a PDF report"))
    return ChatResponse(
        mode="compare", answer=answer, profile=profile, candidates=cands,
        can_export=bool(profile.budget_amount), suggestions=chips,
    )


def _pdf_offer(session: Session, profile: ChatProfile) -> ChatResponse:
    if not profile.budget_amount:
        return ChatResponse(
            mode="clarify",
            answer="I'd love to put together a full report for you! 📄 To build it I just "
            "need your **yearly budget (and currency)** and a **country** (or say \"any "
            "country\"). Then I'll generate a PDF with ranked options, full cost "
            "breakdowns, lifestyle scenarios and a source for every figure.",
            profile=profile, suggestions=_country_chips(),
        )
    report = (profile.report_currency or "EUR").upper()
    where = profile.country or "all countries I cover"
    answer = (
        f"Your report is ready to generate! 📄 It covers Computer Science master's options "
        f"in {where} for a budget of {_money(profile.budget_amount, profile.budget_currency or report)}/year, "
        f"with ranked universities, full cost breakdowns, frugal/moderate/comfortable "
        f"scenarios, the verification report and a cited source for every figure.\n\n"
        f"**Click \"Download report\" below to save the PDF.**"
    )
    return ChatResponse(
        mode="answer", answer=answer, profile=profile, can_export=True,
        suggestions=[_suggestion("Compare top 3", "Compare the top 3 options")],
    )


def _no_coverage(profile: ChatProfile, named: str | None = None) -> ChatResponse:
    if named:
        lead = (f"I don't have grounded, source-cited data for **{named}** in my dataset "
                f"yet, so I won't guess at its costs — being accurate matters more than "
                f"sounding helpful. 🙏\n\n")
    else:
        where = f" for {profile.country}" if profile.country else ""
        lead = (f"I'm sorry — I don't have grounded, source-cited data{where} in my dataset "
                f"yet, so I won't guess at the numbers (accuracy matters more). 🙏\n\n")
    answer = (
        lead +
        "Right now I cover Computer Science master's programmes in **Germany, the "
        "Netherlands, Poland, Hungary and Turkey** — 15 universities, each figure cited. "
        "Would you like to explore one of those?"
    )
    return ChatResponse(mode="clarify", answer=answer, profile=profile,
                        suggestions=_country_chips())


def _grounded_answer(session: Session, message: str, text: str,
                     profile: ChatProfile) -> ChatResponse | None:
    """Narrow lookup like 'visa cost in Germany' — grounded figures + a follow-up."""
    cost_type = _detect_cost_type(text)
    if not cost_type:
        return None
    report = (profile.report_currency or settings.default_report_currency).upper()
    country = profile.country
    fx = CurrencyService(session)

    def fig(item: CostItem, label: str) -> CitedFigure:
        amount, _ = fx.convert(float(item.amount), item.currency, report)
        return CitedFigure(label=label, amount=round(amount, 2), currency=report,
                           confidence=item.confidence, citation=to_citation(item.source))

    figs: list[CitedFigure] = []
    if cost_type in COUNTRY_SCOPE:
        stmt = select(CostItem, Country).join(Country, CostItem.scope_id == Country.id).where(
            CostItem.scope_level == "country", CostItem.cost_type == cost_type)
        if country:
            stmt = stmt.where(Country.name.ilike(f"%{country}%"))
        for item, co in session.execute(stmt).all():
            figs.append(fig(item, f"{cost_type.capitalize()} — {co.name}"))
    elif cost_type == "tuition":
        stmt = (select(CostItem, University, Country)
                .join(Program, CostItem.scope_id == Program.id)
                .join(University, Program.university_id == University.id)
                .join(Country, University.country_id == Country.id)
                .where(CostItem.scope_level == "program", CostItem.cost_type == "tuition"))
        if country:
            stmt = stmt.where(Country.name.ilike(f"%{country}%"))
        for item, uni, co in session.execute(stmt).all():
            figs.append(fig(item, f"Tuition/yr — {uni.name}"))
    elif cost_type in LIVING_SCOPE:
        stmt = (select(CostItem, City, Country)
                .join(City, CostItem.scope_id == City.id)
                .join(Country, City.country_id == Country.id)
                .where(CostItem.scope_level == "city", CostItem.cost_type == cost_type))
        if country:
            stmt = stmt.where(Country.name.ilike(f"%{country}%"))
        for item, city, co in session.execute(stmt).all():
            figs.append(fig(item, f"{cost_type.capitalize()}/mo — {city.name}"))

    if not figs:
        return None
    shown = figs[:8]
    lines = "\n".join(f"• {f.label}: {_money(f.amount, f.currency)} ({f.confidence})" for f in shown)
    scope = f" in {country}" if country else ""
    answer = (
        f"Here's what I found for **{cost_type}**{scope}, straight from cited sources:\n\n"
        f"{lines}\n\n"
        f"Would you like me to fold this into a full cost plan? If you tell me your yearly "
        f"budget, I'll show which universities fit."
    )
    chips = [_suggestion("Plan my full costs", "My budget is 12000 EUR")]
    if not country:
        chips = _country_chips()
    return ChatResponse(mode="answer", answer=answer, profile=profile,
                        figures=shown, suggestions=chips)


# --- entry point -----------------------------------------------------------------

def handle_chat(session: Session, message: str, report_currency: str,
                profile_in: ChatProfile | None = None) -> ChatResponse:
    profile = profile_in.model_copy(deep=True) if profile_in else ChatProfile()
    profile.report_currency = (
        report_currency or profile.report_currency or settings.default_report_currency
    ).upper()
    profile.turn += 1
    text = fold(message)

    # 0) Pure social turns (short greetings/thanks with no planning content).
    if _has_any(text, THANKS_TOKENS) and len(text) < 40:
        return _thanks(profile)
    if _has_any(text, GREETING_TOKENS) and len(text) < 25:
        return _greeting(profile)

    # 1) Merge any newly-mentioned slots into memory (so users never repeat themselves).
    slots = extract_slots(message, profile.report_currency)
    for key in ("country", "field", "degree_level", "lifestyle"):
        if slots.get(key):
            setattr(profile, key, slots[key])
    if slots.get("budget_amount"):
        profile.budget_amount = float(slots["budget_amount"])
        profile.budget_currency = (slots.get("budget_currency")
                                   or profile.budget_currency or profile.report_currency)
    if _has_any(text, ANYWHERE_TOKENS):
        profile.country = None  # explicit cross-country search

    # 2) Explicit actions on existing context.
    if _has_any(text, PDF_TOKENS):
        return _pdf_offer(session, profile)
    if _has_any(text, COMPARE_TOKENS):
        return _compare(session, profile)

    # 3) A specific university (by name or by "the second one").
    program_id = _resolve_university_program(session, text)
    if program_id is None:
        program_id = _resolve_ordinal_program(text, profile)
    if program_id is not None:
        wants_afford = _has_any(text, AFFORD_TOKENS)
        return _detail(session, profile, program_id, affordability=wants_afford)

    # 3b) A named institution we don't cover (e.g. "Harvard") -> honest no-coverage,
    # but only when the user isn't already steering us to a country we do cover.
    if not profile.country:
        unknown = _unknown_institution(session, message)
        if unknown:
            return _no_coverage(profile, named=unknown)

    # 4) Affordability phrased generally ("can I afford Germany with X") -> discovery.
    if _has_any(text, AFFORD_TOKENS) and (profile.budget_amount and profile.country):
        return _discovery(session, profile)

    # 5) Narrow cost lookup ("visa in Germany") when not actively planning a budget.
    if _detect_cost_type(text) and not slots.get("budget_amount"):
        grounded = _grounded_answer(session, message, text, profile)
        if grounded is not None:
            return grounded

    # 6) Discovery vs. follow-up questions (progressive slot filling).
    if profile.budget_amount and profile.country:
        return _discovery(session, profile)
    if profile.budget_amount and profile.country is None:
        if _has_any(text, ANYWHERE_TOKENS) or "cheapest" in text:
            return _discovery(session, profile)
        return _ask_for_country(profile)
    if profile.country and not profile.budget_amount:
        return _ask_for_budget(session, profile)

    # 7) Nothing actionable yet — warm onboarding.
    return _greeting(profile)
