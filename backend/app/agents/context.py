"""Shared, typed state passed through the agent pipeline.

The orchestrator runs agents in a fixed order; each agent reads and enriches this
single `PlanningContext`. This is the "typed shared state" design from the plan —
multi-agent coordination without fragile LLM routing.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.schemas import CandidatePlan, PlanningRequest, VerificationReport
from app.data.models import CostItem, Scholarship
from app.data.retrieval import CandidateRefs


@dataclass
class CandidateBuild:
    """Per-candidate working accumulator filled across agents."""

    refs: CandidateRefs
    tuition_raw: list[CostItem] = field(default_factory=list)
    living_raw: list[CostItem] = field(default_factory=list)   # city-scoped
    country_raw: list[CostItem] = field(default_factory=list)  # visa / insurance / hidden
    scholarships_raw: list[Scholarship] = field(default_factory=list)  # gathered by Scholarship agent
    plan: CandidatePlan | None = None                          # built by Currency agent


@dataclass
class PlanningContext:
    request: PlanningRequest
    session: Session
    report_currency: str
    budget_in_report: float | None = None  # student budget converted to report currency
    builds: list[CandidateBuild] = field(default_factory=list)
    candidates: list[CandidatePlan] = field(default_factory=list)
    verification: VerificationReport | None = None
    recommendations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
