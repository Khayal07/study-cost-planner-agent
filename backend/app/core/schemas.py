"""Pydantic schemas shared across agents, the API and the PDF report.

These are the *contracts* between layers. The most important is `Citation`: every
numeric figure surfaced to a user travels with one, so chat and PDF can always cite
the source and say whether it is `sourced` or an `estimate`.
"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class Citation(BaseModel):
    publisher: str
    url: str | None = None
    accessed_date: date | None = None
    source_type: str


class CostLine(BaseModel):
    """A single cost component, annualized and converted to the report currency."""

    label: str                      # "Tuition", "Rent", "Health insurance", ...
    cost_type: str
    amount: float                   # annualized, in report currency
    currency: str                   # report currency
    original_amount: float
    original_currency: str
    original_period: str            # annual | monthly | one_time
    confidence: str                 # sourced | estimate
    note: str | None = None
    converted: bool = False         # True if a currency conversion was applied
    citation: Citation


class ScenarioBreakdown(BaseModel):
    """One lifestyle scenario for a candidate (frugal / moderate / comfortable)."""

    name: str
    multiplier: float               # applied to discretionary living costs
    annual_total: float
    monthly_living: float
    budget_gap: float               # budget - annual_total (negative = shortfall)
    narrative: str | None = None


class CandidatePlan(BaseModel):
    program_id: int
    program_name: str
    field: str
    degree_level: str
    language: str
    duration_years: float

    university_name: str
    university_url: str | None = None
    city_name: str
    country_name: str
    country_iso: str

    report_currency: str
    lines: list[CostLine] = Field(default_factory=list)

    annual_tuition: float = 0.0
    annual_living: float = 0.0       # rent+food+transport+utilities+insurance (annualized)
    annual_one_time: float = 0.0     # visa etc. (counted in year one)
    annual_hidden: float = 0.0
    total_annual: float = 0.0        # moderate baseline
    monthly_living: float = 0.0

    fx_notes: list[str] = Field(default_factory=list)
    scenarios: list[ScenarioBreakdown] = Field(default_factory=list)

    # Budget matching (filled by Budget Matching Agent)
    budget_gap: float | None = None  # budget - total_annual (moderate)
    affordable: bool | None = None
    rank: int | None = None


class VerificationCheck(BaseModel):
    name: str
    status: str                      # pass | warn | fail
    detail: str


class VerificationReport(BaseModel):
    overall: str                     # pass | warn | fail
    checks: list[VerificationCheck] = Field(default_factory=list)
    summary: str | None = None       # human-readable (LLM) summary


class PlanningRequest(BaseModel):
    country: str | None = Field(default=None, max_length=120)
    field: str | None = Field(default="Computer Science", max_length=120)
    degree_level: str | None = Field(default=None, max_length=40)
    # le is generous: it must also admit the chat's internal "no budget yet" sentinel
    # (1e9) used by discovery before the student gives a budget.
    budget_amount: float = Field(gt=0, le=1_000_000_000)
    budget_currency: str = Field(default="EUR", max_length=3)
    report_currency: str = Field(default="EUR", max_length=3)
    lifestyle: str = "moderate"      # frugal | moderate | comfortable
    max_results: int = Field(default=5, ge=1, le=20)
    # Optional explicit program filter (used by chat "tell me about X" detail mode);
    # when set, retrieval restricts to exactly these programs.
    program_ids: list[int] | None = Field(default=None, max_length=50)
    # Which university the report should feature (the one the user selected/asked about).
    # Ignored by planning; used by the PDF to pick the detailed breakdown. Falls back to
    # the top-ranked option when unset or not among the candidates.
    focus_program_id: int | None = None


class PlanResult(BaseModel):
    request: PlanningRequest
    report_currency: str
    candidates: list[CandidatePlan]
    verification: VerificationReport | None = None
    recommendations: list[str] = Field(default_factory=list)
    generated_at: datetime
    disclaimer: str


class ChatCandidateRef(BaseModel):
    """A compact pointer to one option from the last discovery list.

    Round-tripped in the profile so the advisor can resolve references like
    "the second one" / "compare the top 3" without re-running anything.
    """

    rank: int
    program_id: int
    program_name: str
    university_name: str
    city_name: str
    country_name: str
    total_annual: float
    affordable: bool | None = None
    match_score: int | None = None


class ChatProfile(BaseModel):
    """The advisor's memory of the conversation, round-tripped each turn.

    The frontend stores this opaque object and sends it back with every message,
    so the system has no server-side session state but still 'remembers'.
    """

    country: str | None = Field(default=None, max_length=120)
    field: str | None = Field(default=None, max_length=120)
    degree_level: str | None = Field(default=None, max_length=40)
    budget_amount: float | None = Field(default=None, gt=0, le=1_000_000_000)
    budget_currency: str | None = Field(default=None, max_length=3)
    lifestyle: str | None = Field(default=None, max_length=20)
    report_currency: str = Field(default="EUR", max_length=3)

    # Conversation working set (bounded — this object is round-tripped from the client)
    last_candidates: list[ChatCandidateRef] = Field(default_factory=list, max_length=20)
    focus_program_id: int | None = None   # university most recently discussed
    turn: int = Field(default=0, ge=0, le=100_000)


class ChatSuggestion(BaseModel):
    """A one-tap follow-up the user can send next (rendered as a chip)."""

    label: str
    message: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    report_currency: str = Field(default="EUR", max_length=3)
    profile: ChatProfile | None = None


class CitedFigure(BaseModel):
    """A single grounded figure used in a chat answer."""

    label: str
    amount: float
    currency: str
    confidence: str
    citation: Citation


class ChatResponse(BaseModel):
    # greeting | discovery | detail | compare | affordability | answer | clarify
    mode: str
    answer: str
    profile: ChatProfile = Field(default_factory=ChatProfile)
    suggestions: list[ChatSuggestion] = Field(default_factory=list)
    extracted: dict = Field(default_factory=dict)
    figures: list[CitedFigure] = Field(default_factory=list)
    candidates: list[CandidatePlan] = Field(default_factory=list)  # discovery / compare
    detail: CandidatePlan | None = None                            # single-university detail
    plan: PlanResult | None = None                                 # full plan (when built)
    can_export: bool = False        # frontend may offer a PDF download from the profile
