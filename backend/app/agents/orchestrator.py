"""Deterministic orchestrator: runs the agent DAG over a shared PlanningContext.

Phase 2 wires retrieval -> tuition -> living -> currency and applies a basic budget
gap + ranking inline. Phase 3 inserts the Scenario, Budget Matching and Verifier
agents; Phase 4 adds the chat intent path in front of this.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.agents.budget_matching import BudgetMatchingAgent
from app.agents.context import CandidateBuild, PlanningContext
from app.agents.currency import CurrencyAgent
from app.agents.eligibility import EligibilityAgent
from app.agents.living_cost import LivingCostAgent
from app.agents.net_value import NetValueAgent
from app.agents.scenario import ScenarioAgent
from app.agents.scholarship import ScholarshipAgent
from app.agents.tuition import TuitionAgent
from app.agents.verifier import VerifierAgent
from app.core.config import settings
from app.core.schemas import PlanningRequest, PlanResult
from app.data.retrieval import find_candidates

DISCLAIMER = (
    "Figures are curated approximations grounded in cited sources; tuition/living costs "
    "change over time and vary by individual. Verify each figure at its cited source "
    "before making decisions."
)


class Orchestrator:
    def __init__(self) -> None:
        # Fixed pipeline order over the shared PlanningContext.
        self.agents = [
            TuitionAgent(),
            LivingCostAgent(),
            CurrencyAgent(),
            ScenarioAgent(),
            BudgetMatchingAgent(),
            # Scholarship layer: gather awards -> score eligibility -> net cost / value rank.
            ScholarshipAgent(),
            EligibilityAgent(),
            NetValueAgent(),
            VerifierAgent(),
        ]

    def run(self, session: Session, request: PlanningRequest) -> PlanResult:
        report_currency = (request.report_currency or settings.default_report_currency).upper()
        ctx = PlanningContext(request=request, session=session, report_currency=report_currency)
        ctx.builds = [CandidateBuild(refs=r) for r in find_candidates(session, request)]

        for agent in self.agents:
            agent.run(ctx)

        top = ctx.candidates[: request.max_results]
        return PlanResult(
            request=request,
            report_currency=report_currency,
            candidates=top,
            verification=ctx.verification,
            recommendations=ctx.recommendations,
            generated_at=datetime.utcnow(),
            disclaimer=DISCLAIMER,
        )
