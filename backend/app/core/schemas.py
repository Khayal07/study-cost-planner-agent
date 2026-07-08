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


class ScholarshipMatch(BaseModel):
    """A scholarship evaluated against one candidate + the student profile.

    Computed at request time (never stored). `estimated_value` is the annual saving in
    the report currency; `eligibility` and `reasons` make the verdict explainable.
    """

    scholarship_id: int
    name: str
    provider: str
    coverage_type: str
    amount: float | None = None
    coverage_pct: float | None = None
    currency: str
    estimated_value: float = 0.0          # annual saving in report currency
    eligibility: str = "unknown"          # eligible | likely | ineligible | unknown
    match_score: int = 100                # 0–100 fit score (deterministic, explainable)
    reasons: list[str] = Field(default_factory=list)
    tips: list[str] = Field(default_factory=list)  # actionable "improve eligibility" hints
    deadline: date | None = None
    days_until_deadline: int | None = None
    renewable: bool = False
    application_url: str | None = None
    documents_required: list[str] = Field(default_factory=list)
    citation: Citation


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

    # Scholarship layer (filled by Scholarship / Eligibility / NetValue agents).
    # All defaulted so an unchanged /plan call still returns a valid plan.
    scholarships: list[ScholarshipMatch] = Field(default_factory=list)
    total_scholarship_value: float = 0.0          # best realistic combination, annual
    net_total_annual: float | None = None         # total_annual - total_scholarship_value
    net_budget_gap: float | None = None           # budget - net_total_annual
    net_affordable: bool | None = None
    value_rank: int | None = None                 # rank by net cost (cheapest-after-aid)

    # Part-time work offset (Phase 3 #7) — sourced potential earnings, not guaranteed.
    work_hours_cap: int | None = None             # term-time hours/week the visa allows
    work_annual_earnings: float | None = None     # estimated annual gross, report currency
    work_note: str | None = None                  # the assumption / legal note
    work_citation: Citation | None = None


class VerificationCheck(BaseModel):
    name: str
    status: str                      # pass | warn | fail
    detail: str


class VerificationReport(BaseModel):
    overall: str                     # pass | warn | fail
    checks: list[VerificationCheck] = Field(default_factory=list)
    summary: str | None = None       # human-readable (LLM) summary


class LiveScholarship(BaseModel):
    """A scholarship found by the live web search (AI-fetched, source-cited).

    Fields are free text (values vary in phrasing across sources) except
    ``annual_value``: the AI's best numeric estimate of the yearly cash value in
    the report currency, used to fold a user-selected award into the net total.
    """

    name: str
    provider: str | None = None
    amount: str | None = None            # display text (e.g. "€1,200/month" or "Full tuition")
    coverage_type: str | None = None     # free text summary
    deadline: str | None = None          # free text (dates vary in phrasing)
    eligibility: str | None = None       # short eligibility summary
    official_url: str | None = None
    annual_value: float | None = None    # yearly value in report currency (for totals)


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
    # Optional eligibility inputs for scholarship matching. All optional: when blank the
    # eligibility agent returns 'likely'/'unknown' verdicts and existing flows are unchanged.
    nationality: str | None = Field(default=None, max_length=80)
    gpa: float | None = Field(default=None, ge=0, le=4.0)
    language_test: str | None = Field(default=None, max_length=120)
    # User-selected live (web-found) scholarships to fold into the featured university's
    # net cost and list in the PDF. Empty for a normal plan; only the PDF export uses these.
    extra_scholarships: list[LiveScholarship] = Field(default_factory=list, max_length=20)


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

    # Optional eligibility inputs (round-tripped like the other slots)
    nationality: str | None = Field(default=None, max_length=80)
    gpa: float | None = Field(default=None, ge=0, le=4.0)
    language_test: str | None = Field(default=None, max_length=120)

    # Conversation working set (bounded — this object is round-tripped from the client)
    last_candidates: list[ChatCandidateRef] = Field(default_factory=list, max_length=20)
    focus_program_id: int | None = None   # university most recently discussed
    # An action the user asked for but that we had to pause to collect a missing slot
    # (e.g. "pdf" while we ask for their budget). Resumed next turn once the slot lands,
    # so the user doesn't lose their intent. One of: "pdf" | "value" | "scholarships".
    pending_action: str | None = Field(default=None, max_length=20)
    turn: int = Field(default=0, ge=0, le=100_000)


class ChatSuggestion(BaseModel):
    """A one-tap follow-up the user can send next (rendered as a chip)."""

    label: str
    message: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    report_currency: str = Field(default="EUR", max_length=3)
    profile: ChatProfile | None = None


# --- Live scholarship search (web-sourced, AI-fetched) ---

class LiveScholarshipSearchRequest(BaseModel):
    country: str = Field(min_length=2, max_length=120)
    field: str = Field(min_length=2, max_length=120)
    degree_level: str | None = Field(default=None, max_length=40)
    report_currency: str = Field(default="EUR", max_length=3)


class LiveScholarshipSearchResponse(BaseModel):
    results: list[LiveScholarship] = []
    cached: bool = False        # served from the 24h cache (no API call)
    limited: bool = False       # daily cap hit — results may be empty/stale
    note: str | None = None     # human-readable status (e.g. LLM disabled)


# --- Cost forecast (deterministic projection + optional AI commentary) ---

class ForecastRequest(BaseModel):
    country_iso: str | None = Field(default=None, max_length=3)
    country_name: str = Field(min_length=2, max_length=120)
    annual_tuition: float = Field(ge=0, le=1_000_000)
    annual_living: float = Field(ge=0, le=1_000_000)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    years: int = Field(default=4, ge=1, le=6)
    with_commentary: bool = False
    language: str = Field(default="en", pattern="^(en|az)$")


class ForecastYear(BaseModel):
    year_offset: int
    year_label: str
    tuition: float
    living: float
    total: float


class ForecastAssumptions(BaseModel):
    tuition_inflation_pct: float
    living_inflation_pct: float
    note: str


class ForecastResponse(BaseModel):
    series: list[ForecastYear]
    assumptions: ForecastAssumptions
    commentary: str | None = None


# --- Motivation letter generator (auth; ties into the application tracker) ---

class MotivationLetterRequest(BaseModel):
    application_id: int | None = None  # when set (and owned), the draft is persisted
    scholarship_name: str = Field(min_length=2, max_length=160)
    provider: str | None = Field(default=None, max_length=160)
    university_name: str | None = Field(default=None, max_length=160)
    program_name: str | None = Field(default=None, max_length=160)
    language: str = Field(default="en", pattern="^(en|az)$")
    tone: str = Field(default="formal", pattern="^(formal|personal)$")
    user_notes: str | None = Field(default=None, max_length=600)


class MotivationLetterResponse(BaseModel):
    letter: str
    language: str
    saved: bool = False  # persisted onto the tracked application


# --- Interview simulator (stateless, /chat prefix) ---

class InterviewContext(BaseModel):
    scholarship_name: str | None = Field(default=None, max_length=160)
    university_name: str | None = Field(default=None, max_length=160)
    program_name: str | None = Field(default=None, max_length=160)
    field: str | None = Field(default=None, max_length=120)


class InterviewTurn(BaseModel):
    role: str = Field(pattern="^(interviewer|student)$")
    content: str = Field(min_length=1, max_length=1200)


class InterviewRequest(BaseModel):
    context: InterviewContext = Field(default_factory=InterviewContext)
    history: list[InterviewTurn] = Field(default_factory=list, max_length=16)
    action: str = Field(default="start", pattern="^(start|reply|finish)$")
    language: str = Field(default="en", pattern="^(en|az)$")


class InterviewFeedback(BaseModel):
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    overall: str = ""


class InterviewResponse(BaseModel):
    message: str
    done: bool = False
    feedback: InterviewFeedback | None = None
    question_count: int = 0


# --- Transcript analysis (auth; vision extraction, user confirms before saving) ---

class TranscriptExtraction(BaseModel):
    gpa: float | None = None            # as printed on the transcript
    gpa_scale: float | None = None      # the scale it is printed on (4, 5, 10, 100…)
    gpa_on_4_scale: float | None = Field(default=None, ge=0, le=4)
    degree_level: str | None = None     # bachelor | master | phd | high_school
    institution: str | None = None
    confidence: str = "low"             # high | medium | low


class TranscriptAnalysisResponse(BaseModel):
    extraction: TranscriptExtraction
    note: str | None = None


# --- Voice transcription (whisper; feeds the chat input) ---

class TranscribeResponse(BaseModel):
    text: str
    language: str | None = None
    limited: bool = False  # daily cap hit


# --- Accounts + application tracker (Phase H) ---

class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=200)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    id: int
    email: str
    nationality: str | None = None
    gpa: float | None = None
    language_test: str | None = None


class AuthResponse(BaseModel):
    token: str
    user: UserOut


class ProfileUpdate(BaseModel):
    nationality: str | None = Field(default=None, max_length=80)
    gpa: float | None = Field(default=None, ge=0, le=4.0)
    language_test: str | None = Field(default=None, max_length=120)


class ApplicationTask(BaseModel):
    """One prioritized scholarship to apply to (output of the application planner)."""

    scholarship_id: int
    name: str
    provider: str
    university_name: str
    program_id: int
    coverage_type: str
    estimated_value: float
    currency: str
    eligibility: str
    deadline: date | None = None
    days_until_deadline: int | None = None
    priority: int
    priority_reason: str
    application_url: str | None = None
    documents: list[str] = Field(default_factory=list)


class ApplicationPlan(BaseModel):
    tasks: list[ApplicationTask] = Field(default_factory=list)
    this_week: list[str] = Field(default_factory=list)
    all_documents: list[str] = Field(default_factory=list)
    generated_at: datetime


class ApplicationCreate(BaseModel):
    scholarship_id: int | None = None
    program_id: int | None = None
    scholarship_name: str = Field(min_length=1, max_length=200)
    provider: str | None = Field(default=None, max_length=200)
    university_name: str | None = Field(default=None, max_length=200)
    coverage_type: str | None = Field(default=None, max_length=20)
    estimated_value: float | None = None
    currency: str | None = Field(default=None, max_length=3)
    deadline: date | None = None
    application_url: str | None = None
    documents: list[str] = Field(default_factory=list, max_length=40)


class ApplicationUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=16)
    notes: str | None = Field(default=None, max_length=2000)
    motivation_letter: str | None = Field(default=None, max_length=20000)


class DocumentOut(BaseModel):
    id: int
    name: str
    done: bool


class ApplicationOut(BaseModel):
    id: int
    scholarship_id: int | None = None
    program_id: int | None = None
    scholarship_name: str
    provider: str | None = None
    university_name: str | None = None
    coverage_type: str | None = None
    estimated_value: float | None = None
    currency: str | None = None
    deadline: date | None = None
    days_until_deadline: int | None = None
    application_url: str | None = None
    status: str
    notes: str | None = None
    motivation_letter: str | None = None
    documents: list[DocumentOut] = Field(default_factory=list)


# --- Saved plans + shareable links (Phase 3 #4) ---

class SavedPlanCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    request: PlanningRequest


class SavedPlanOut(BaseModel):
    """Summary row for the saved-plans list."""

    id: int
    public_id: str
    title: str
    created_at: datetime
    request: PlanningRequest


class SavedPlanDetail(BaseModel):
    """A saved plan resolved to a freshly-computed result (used by the share view)."""

    public_id: str
    title: str
    created_at: datetime
    request: PlanningRequest
    plan: PlanResult


class CitedFigure(BaseModel):
    """A single grounded figure used in a chat answer."""

    label: str
    amount: float
    currency: str
    confidence: str
    citation: Citation


class ChatResponse(BaseModel):
    # greeting | discovery | detail | compare | affordability | scholarships | value
    # | answer | clarify
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
