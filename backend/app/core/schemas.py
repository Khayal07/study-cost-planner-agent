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
    country: str | None = None
    field: str | None = "Computer Science"
    degree_level: str | None = None
    budget_amount: float
    budget_currency: str = "EUR"
    report_currency: str = "EUR"
    lifestyle: str = "moderate"      # frugal | moderate | comfortable
    max_results: int = 5


class PlanResult(BaseModel):
    request: PlanningRequest
    report_currency: str
    candidates: list[CandidatePlan]
    verification: VerificationReport | None = None
    recommendations: list[str] = Field(default_factory=list)
    generated_at: datetime
    disclaimer: str
