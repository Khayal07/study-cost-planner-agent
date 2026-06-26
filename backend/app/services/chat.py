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
SCHOLARSHIP_TOKENS = ["scholarship", "scholarships", "grant", "grants", "funding", "funded",
                      "financial aid", "stipend", "bursary", "təqaüd", "teqaud", "bursa", "burs",
                      "daad", "erasmus", "stipendium", "fully funded", "free study"]
VALUE_TOKENS = ["after scholarship", "after scholarships", "after aid", "net cost", "net price",
                "cheapest after", "best value", "value for money", "with scholarship",
                "with scholarships", "with aid"]

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
        nationality=profile.nationality,
        gpa=profile.gpa,
        language_test=profile.language_test,
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

# Words dropped when matching a university by its full name — they're shared by many
# institutions and carry no distinguishing signal.
_NAME_STOPWORDS = {"university", "of", "the", "for", "and", "a", "an", "college", "institute"}
_UNI_TOKEN_INDEX: list[tuple[int, frozenset[str]]] | None = None


def _uni_token_index(session: Session) -> list[tuple[int, frozenset[str]]]:
    """Cache of (program_id, significant name tokens) for every university."""
    global _UNI_TOKEN_INDEX
    if _UNI_TOKEN_INDEX is None:
        rows = session.execute(
            select(Program.id, University.name).join(
                University, Program.university_id == University.id
            )
        ).all()
        index: list[tuple[int, frozenset[str]]] = []
        for pid, name in rows:
            toks = frozenset(
                t for t in re.split(r"[^a-z0-9]+", fold(name))
                if t and t not in _NAME_STOPWORDS
            )
            if toks:
                index.append((pid, toks))
        _UNI_TOKEN_INDEX = index
    return _UNI_TOKEN_INDEX


def _resolve_named_university(session: Session, text: str) -> int | None:
    """Match a full/partial official university name typed by the user.

    A university matches when ALL its significant name tokens appear in the message,
    so "istanbul technical university" -> {istanbul, technical} resolves to ITU, not
    METU. The most specific match (most tokens) wins, which disambiguates e.g. the two
    Warsaw universities.
    """
    words = {t for t in re.split(r"[^a-z0-9]+", text) if t}
    best: tuple[int, int] | None = None  # (token_count, program_id)
    for pid, toks in _uni_token_index(session):
        if toks <= words and (best is None or len(toks) > best[0]):
            best = (len(toks), pid)
    return best[1] if best else None


def _resolve_university_program(session: Session, text: str) -> int | None:
    """Map a free-text university mention to a program_id (CS master).

    1) precise abbreviations / unambiguous city aliases (ITU, METU, TUM, Berlin…);
    2) otherwise the full/partial official name via significant-token matching.
    """
    for alias, substr in UNIVERSITY_ALIASES.items():
        # Word-boundary match for short aliases to avoid accidental hits.
        pattern = rf"\b{re.escape(alias)}\b" if len(alias) <= 4 else re.escape(alias)
        if re.search(pattern, text):
            row = session.execute(
                select(Program.id)
                .join(University, Program.university_id == University.id)
                .where(University.name.ilike(f"%{substr}%"))
                .limit(1)
            ).first()
            if row:
                return row[0]
    return _resolve_named_university(session, text)


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
    # Superlative / pronoun back-references to the previous list. Word-bounded so
    # short words like "it" don't match inside others (e.g. "univers-it-y").
    if re.search(r"\b(cheapest|best|top one|top option|first one|that one|this one)\b", text):
        return profile.last_candidates[0].program_id
    if re.search(r"\b(last one|the last)\b", text):
        return profile.last_candidates[-1].program_id
    for rank, tokens in ORDINAL_TOKENS.items():
        # These tokens ("second", "2nd", "#2", "option 2") are distinctive enough to
        # match as substrings without the "it"-in-"university" class of false hit.
        if _has_any(text, tokens):
            for ref in profile.last_candidates:
                if ref.rank == rank:
                    return ref.program_id
    return None


# --- response builders -----------------------------------------------------------

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

    _store_candidates(session, profile, plan.candidates)
    budget_r = _budget_in_report(session, profile)
    budget_txt = _money(budget_r or 0, report)
    affordable = [c for c in plan.candidates if c.affordable]
    scope = f" in {profile.country}" if profile.country else " across all countries I cover"

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
        f"{headline}\n\nEach option below shows a match score and a source for every "
        f"figure. Which would you like to explore in detail — or shall I compare the "
        f"top 3 side by side?"
    )

    chips: list[ChatSuggestion] = []
    for c in plan.candidates[:3]:
        chips.append(_suggestion(f"Explore {c.university_name}", f"Tell me about {c.university_name}"))
    chips.append(_suggestion("Compare top 3", "Compare the top 3 options"))
    chips.append(_suggestion("🎓 Best value after scholarships", "Show me the best value after scholarships"))
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

    # Scholarships (now grounded in the dataset).
    awards = _eligible_awards(c)
    if awards:
        top = max(awards, key=lambda m: m.estimated_value)
        sch_txt = (
            f"\n\n🎓 **Scholarships:** you may qualify for {len(awards)} award(s) here — e.g. "
            f"{top.name} (~{_money(top.estimated_value, report)}/yr). Applying the best one could "
            f"bring your total down to about **{_money(_net_of(c), report)}/year**. Say "
            f"\"scholarships\" for the full list with deadlines and cited sources."
        )
    else:
        sch_txt = (
            "\n\nA quick note for transparency: I don't yet have a scholarship in my dataset "
            "matching this option, so I won't guess — accuracy first. Share your nationality, GPA "
            "and English test and I'll re-check eligibility."
        )
    nextstep = ("\n\nWould you like the **scholarships**, a full **PDF report**, or shall I "
                "**compare** this with your other options?")

    answer = intro + verdict + scen_txt + sch_txt + nextstep
    mode = "affordability" if affordability else "detail"

    return ChatResponse(
        mode=mode, answer=answer, profile=profile, detail=c, figures=figures,
        candidates=[c], can_export=bool(profile.budget_amount),
        suggestions=[
            _suggestion(f"Scholarships at {c.university_name}", f"Scholarships at {c.university_name}"),
            _suggestion(f"Download {c.university_name} report", "Generate a PDF report"),
            _suggestion("Compare with others", "Compare the top 3 options"),
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
    _store_candidates(session, profile, cands)

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
        "Here's how your top options compare — full breakdowns and a source for every "
        "figure are in the cards below.\n\n" + insight +
        "\n\nWant me to open one in detail, or generate a PDF report with all of them?"
    )

    chips = [_suggestion(f"Explore {c.university_name}", f"Tell me about {c.university_name}")
             for c in cands]
    chips.append(_suggestion("Generate report", "Generate a PDF report"))
    return ChatResponse(
        mode="compare", answer=answer, profile=profile, candidates=cands,
        can_export=bool(profile.budget_amount), suggestions=chips,
    )


def _eligible_awards(c: CandidatePlan) -> list:
    """Awards counted toward net cost (eligible/likely/unknown), best value first."""
    return [m for m in c.scholarships if m.eligibility in ("eligible", "likely", "unknown")]


def _award_txt(m, report: str) -> str:
    tag = {"eligible": "✅", "likely": "🟡", "unknown": "❔"}.get(m.eligibility, "•")
    val = f"~{_money(m.estimated_value, report)}/yr" if m.estimated_value else "amount varies"
    dl = ""
    if m.days_until_deadline is not None and m.days_until_deadline >= 0:
        dl = f", apply by {m.deadline.isoformat()} ({m.days_until_deadline}d left)"
    return f"{tag} **{m.name}** ({m.provider}) — {val}{dl}"


def _net_of(c: CandidatePlan) -> float:
    return c.net_total_annual if c.net_total_annual is not None else c.total_annual


def _scholarships(session: Session, profile: ChatProfile,
                  program_id: int | None = None) -> ChatResponse:
    """List scholarships the student may qualify for — for one university or across options."""
    if program_id:
        plan = _run_pipeline(session, profile, program_ids=[program_id], max_results=1)
    else:
        plan = _run_pipeline(session, profile, max_results=6)
    if not plan.candidates:
        return _no_coverage(profile)
    report = plan.report_currency
    _store_candidates(session, profile, plan.candidates)

    if program_id:
        c = plan.candidates[0]
        profile.focus_program_id = program_id
        awards = _eligible_awards(c)
        if not awards:
            answer = (
                f"For **{c.university_name}** I don't yet have a scholarship in my dataset that "
                f"matches your profile. Its tuition is {_money(c.annual_tuition, report)}/yr and "
                f"the all-in total ~{_money(c.total_annual, report)}/yr. Tell me your nationality, "
                f"GPA and English test and I'll re-check eligibility."
            )
            return ChatResponse(mode="scholarships", answer=answer, profile=profile,
                                detail=c, candidates=[c],
                                suggestions=[_suggestion("Compare options", "Compare the top 3 options")])
        lines = "\n".join(f"• {_award_txt(m, report)}" for m in awards)
        answer = (
            f"🎓 Scholarships you may qualify for at **{c.university_name}**:\n\n{lines}\n\n"
            f"Applying the best of these brings your estimated cost from "
            f"~{_money(c.total_annual, report)} down to **~{_money(_net_of(c), report)}/year**. "
            f"Each award is shown with my eligibility read (✅ eligible · 🟡 likely · ❔ needs a "
            f"detail) and links to its official source. Verify the latest terms before applying."
        )
        chips = [_suggestion("Plan my applications", f"Help me apply to {c.university_name}"),
                 _suggestion(f"Download {c.university_name} report", "Generate a PDF report"),
                 _suggestion("Compare value", "Show me the best value after scholarships")]
        return ChatResponse(mode="scholarships", answer=answer, profile=profile, detail=c,
                            candidates=[c], can_export=bool(profile.budget_amount), suggestions=chips)

    # Across the current option set.
    with_aid = [c for c in plan.candidates if _eligible_awards(c)]
    if not with_aid:
        answer = (
            "I don't yet have scholarships in my dataset matching your profile for these options. "
            "If you share your nationality, GPA and English test, I can re-check — or try Germany "
            "(DAAD), Hungary (Stipendium Hungaricum) or Turkey (Türkiye Bursları), which have "
            "broad programmes."
        )
        return ChatResponse(mode="scholarships", answer=answer, profile=profile,
                            candidates=plan.candidates, suggestions=_country_chips())
    best = min(with_aid, key=_net_of)
    lines = []
    for c in with_aid[:5]:
        top = max(_eligible_awards(c), key=lambda m: m.estimated_value)
        lines.append(f"• **{c.university_name}**: {top.name} → net ~{_money(_net_of(c), report)}/yr")
    answer = (
        f"Good news — several options come with scholarships you may qualify for. 🎓 "
        f"The best value after aid is **{best.university_name}** "
        f"(~{_money(_net_of(best), report)}/yr).\n\n" + "\n".join(lines) +
        "\n\nWant the full award list (with deadlines and sources) for one of them, or shall I "
        "rank everything by value after scholarships?"
    )
    chips = [_suggestion(f"Scholarships at {c.university_name}", f"Scholarships at {c.university_name}")
             for c in with_aid[:2]]
    chips.append(_suggestion("Rank by value", "Show me the best value after scholarships"))
    return ChatResponse(mode="scholarships", answer=answer, profile=profile,
                        candidates=plan.candidates, can_export=bool(profile.budget_amount),
                        suggestions=chips)


def _value(session: Session, profile: ChatProfile) -> ChatResponse:
    """Rank the current options by net cost after scholarships (best value first)."""
    plan = _run_pipeline(session, profile, max_results=6)
    if not plan.candidates:
        return _no_coverage(profile)
    report = plan.report_currency
    cands = sorted(plan.candidates, key=lambda c: c.value_rank or 9_999)
    _store_candidates(session, profile, cands)
    best = cands[0]
    saved = round(best.total_annual - _net_of(best), 2)
    headline = (
        f"Ranked by **value after scholarships**, your best option is "
        f"**{best.university_name}** (~{_money(_net_of(best), report)}/yr after aid"
        + (f", saving ~{_money(saved, report)} vs. its sticker price" if saved > 0 else "")
        + ")."
    )
    lines = []
    for i, c in enumerate(cands):
        suffix = f"  _(gross {_money(c.total_annual, report)})_" if c.total_scholarship_value > 0 else ""
        lines.append(f"{i + 1}. {c.university_name}: ~{_money(_net_of(c), report)}/yr{suffix}")
    answer = (
        headline + "\n\n" + "\n".join(lines) +
        "\n\nNet figures apply the single best award you may qualify for; say \"scholarships at "
        "<university>\" for the breakdown, or generate a PDF report."
    )
    chips = [_suggestion(f"Scholarships at {best.university_name}", f"Scholarships at {best.university_name}"),
             _suggestion("Generate report", "Generate a PDF report")]
    return ChatResponse(mode="value", answer=answer, profile=profile, candidates=cands,
                        can_export=bool(profile.budget_amount), suggestions=chips)


def _pdf_offer(session: Session, profile: ChatProfile) -> ChatResponse:
    focus_name = _focus_university_name(session, profile)
    if not profile.budget_amount:
        target = f" for **{focus_name}**" if focus_name else ""
        return ChatResponse(
            mode="clarify",
            answer=f"I'd love to put together a full report{target} for you! 📄 To build it I "
            "just need your **yearly budget (and currency)**"
            + ("" if (focus_name or profile.country) else " and a **country** (or say "
               "\"any country\")")
            + ". Then I'll generate a PDF with full cost breakdowns, lifestyle scenarios "
            "and a cited source for every figure.",
            profile=profile, suggestions=_country_chips(),
        )
    report = (profile.report_currency or "EUR").upper()
    budget_txt = _money(profile.budget_amount, profile.budget_currency or report)
    if focus_name:
        answer = (
            f"Your report for **{focus_name}** is ready to generate! 📄 It includes the full "
            f"cost breakdown, frugal/moderate/comfortable scenarios, the budget check against "
            f"your {budget_txt}/year, and a cited source for every figure.\n\n"
            f"**Click \"Download report\" below to save the PDF.**"
        )
    else:
        where = profile.country or "all countries I cover"
        answer = (
            f"Your report is ready to generate! 📄 It covers Computer Science master's options "
            f"in {where} for a budget of {budget_txt}/year, with ranked universities, full "
            f"cost breakdowns, frugal/moderate/comfortable scenarios, the verification report "
            f"and a cited source for every figure.\n\n"
            f"**Click \"Download report\" below to save the PDF.**"
        )
    return ChatResponse(
        mode="answer", answer=answer, profile=profile, can_export=True,
        suggestions=[_suggestion("Compare top 3", "Compare the top 3 options")],
    )


def _focus_university_name(session: Session, profile: ChatProfile) -> str | None:
    """Name of the university the user is focused on (for report wording), or None."""
    if not profile.focus_program_id:
        return None
    row = session.execute(
        select(University.name)
        .join(Program, Program.university_id == University.id)
        .where(Program.id == profile.focus_program_id)
        .limit(1)
    ).first()
    return row[0] if row else None


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
    for key in ("country", "field", "degree_level", "lifestyle", "nationality", "language_test"):
        if slots.get(key):
            setattr(profile, key, slots[key])
    if slots.get("gpa") is not None:
        profile.gpa = float(slots["gpa"])
    if slots.get("budget_amount"):
        profile.budget_amount = float(slots["budget_amount"])
        profile.budget_currency = (slots.get("budget_currency")
                                   or profile.budget_currency or profile.report_currency)
    if _has_any(text, ANYWHERE_TOKENS):
        profile.country = None  # explicit cross-country search

    # 2) Resolve any explicit university reference (by name, or "the second one") and
    # remember it as the focus, so a follow-up report/detail targets the right one —
    # e.g. "generate a report for METU" features METU, not the top-ranked option.
    program_id = _resolve_university_program(session, text)
    if program_id is None:
        program_id = _resolve_ordinal_program(text, profile)
    if program_id is not None:
        profile.focus_program_id = program_id

    # 3) Explicit actions on existing context (the focus above is already applied).
    if _has_any(text, PDF_TOKENS):
        return _pdf_offer(session, profile)
    # Value-after-aid ranking (check before plain scholarships: "value after scholarships").
    if _has_any(text, VALUE_TOKENS):
        if profile.country or profile.budget_amount:
            return _value(session, profile)
        return _ask_for_country(profile)
    if _has_any(text, SCHOLARSHIP_TOKENS):
        if program_id is not None:
            return _scholarships(session, profile, program_id)
        if profile.country or profile.budget_amount:
            return _scholarships(session, profile)
        return _ask_for_country(profile)
    if _has_any(text, COMPARE_TOKENS):
        return _compare(session, profile)

    # 4) A specific university (by name or by "the second one") -> detail.
    if program_id is not None:
        wants_afford = _has_any(text, AFFORD_TOKENS)
        return _detail(session, profile, program_id, affordability=wants_afford)

    # 5) A named institution we don't cover (e.g. "Harvard") -> honest no-coverage,
    # but only when the user isn't already steering us to a country we do cover.
    if not profile.country:
        unknown = _unknown_institution(session, message)
        if unknown:
            return _no_coverage(profile, named=unknown)

    # 6) Affordability phrased generally ("can I afford Germany with X") -> discovery.
    if _has_any(text, AFFORD_TOKENS) and (profile.budget_amount and profile.country):
        return _discovery(session, profile)

    # 7) Narrow cost lookup ("visa in Germany") when not actively planning a budget.
    if _detect_cost_type(text) and not slots.get("budget_amount"):
        grounded = _grounded_answer(session, message, text, profile)
        if grounded is not None:
            return grounded

    # 8) Discovery vs. follow-up questions (progressive slot filling).
    if profile.budget_amount and profile.country:
        return _discovery(session, profile)
    if profile.budget_amount and profile.country is None:
        if _has_any(text, ANYWHERE_TOKENS) or "cheapest" in text:
            return _discovery(session, profile)
        return _ask_for_country(profile)
    if profile.country and not profile.budget_amount:
        return _ask_for_budget(session, profile)

    # 9) Nothing actionable yet — warm onboarding.
    return _greeting(profile)
