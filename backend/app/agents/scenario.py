"""Scenario Agent — builds frugal / moderate / comfortable lifestyle scenarios.

Lifestyle multipliers apply only to *discretionary* living costs (rent, food,
transport, utilities). Tuition, insurance, visa and hidden fees are fixed. Narratives
are deterministic templates to keep LLM usage minimal and rate-limit friendly.
"""
from __future__ import annotations

from app.agents.context import PlanningContext
from app.core.schemas import ScenarioBreakdown

SCENARIOS = [("frugal", 0.80), ("moderate", 1.00), ("comfortable", 1.35)]
DISCRETIONARY = {"rent", "food", "transport", "utilities"}


class ScenarioAgent:
    name = "scenario"

    def run(self, ctx: PlanningContext) -> None:
        cur = ctx.report_currency
        for plan in ctx.candidates:
            discretionary = sum(ln.amount for ln in plan.lines if ln.cost_type in DISCRETIONARY)
            insurance = sum(ln.amount for ln in plan.lines if ln.cost_type == "insurance")
            fixed_other = plan.annual_tuition + plan.annual_one_time + plan.annual_hidden

            plan.scenarios = []
            for label, mult in SCENARIOS:
                disc = discretionary * mult
                annual_total = round(fixed_other + insurance + disc, 2)
                monthly_living = round((insurance + disc) / 12, 2)
                plan.scenarios.append(
                    ScenarioBreakdown(
                        name=label,
                        multiplier=mult,
                        annual_total=annual_total,
                        monthly_living=monthly_living,
                        budget_gap=0.0,  # filled by Budget Matching Agent
                        narrative=(
                            f"{label.capitalize()} lifestyle: about "
                            f"{monthly_living:,.0f} {cur}/month on living, "
                            f"~{annual_total:,.0f} {cur}/year in total."
                        ),
                    )
                )
