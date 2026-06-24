"""Budget Matching Agent — converts the budget, computes gaps, ranks, advises.

Ranking: affordable options first, then cheapest total. Gaps are computed for the
moderate baseline and for each scenario. Recommendations are grounded in the
computed numbers (no invented advice).
"""
from __future__ import annotations

from app.agents.context import PlanningContext
from app.services.currency import CurrencyService


class BudgetMatchingAgent:
    name = "budget_matching"

    def run(self, ctx: PlanningContext) -> None:
        fx = CurrencyService(ctx.session)
        budget, _ = fx.convert(
            ctx.request.budget_amount, ctx.request.budget_currency, ctx.report_currency
        )
        ctx.budget_in_report = round(budget, 2)

        for plan in ctx.candidates:
            plan.budget_gap = round(budget - plan.total_annual, 2)
            plan.affordable = plan.budget_gap >= 0
            for scen in plan.scenarios:
                scen.budget_gap = round(budget - scen.annual_total, 2)

        # Rank: affordable first, then cheapest total.
        ctx.candidates.sort(key=lambda p: (not p.affordable, p.total_annual))
        for i, plan in enumerate(ctx.candidates):
            plan.rank = i + 1

        ctx.recommendations = self._recommendations(ctx, budget)

    def _recommendations(self, ctx: PlanningContext, budget: float) -> list[str]:
        cur = ctx.report_currency
        recs: list[str] = []
        if not ctx.candidates:
            return ["No matching programs found for these filters."]

        affordable = [p for p in ctx.candidates if p.affordable]
        cheapest = ctx.candidates[0]

        if affordable:
            best = affordable[0]
            recs.append(
                f"{len(affordable)} of {len(ctx.candidates)} options fit your "
                f"{budget:,.0f} {cur}/year budget. Most affordable: {best.program_name} "
                f"at {best.university_name} (~{best.total_annual:,.0f} {cur}/year)."
            )
        else:
            short = abs(cheapest.budget_gap or 0)
            recs.append(
                f"No option fits your {budget:,.0f} {cur}/year budget. Closest: "
                f"{cheapest.university_name} (~{cheapest.total_annual:,.0f} {cur}/year, "
                f"short by ~{short:,.0f} {cur})."
            )

        # Lifestyle saving tip from the cheapest candidate's scenarios.
        scen = {s.name: s for s in cheapest.scenarios}
        if "frugal" in scen and "moderate" in scen:
            saving = round(scen["moderate"].annual_total - scen["frugal"].annual_total, 2)
            if saving > 0:
                recs.append(
                    f"Switching to a frugal lifestyle saves about {saving:,.0f} {cur}/year "
                    f"versus moderate."
                )

        # Tuition-free insight if any candidate has zero tuition.
        free = [p for p in ctx.candidates if p.annual_tuition == 0]
        if free:
            recs.append(
                f"{len(free)} option(s) have no tuition (e.g. {free[0].university_name}); "
                f"living cost is then the main expense."
            )

        # Cheaper-city insight.
        if len(ctx.candidates) > 1:
            by_living = sorted(ctx.candidates, key=lambda p: p.monthly_living)
            low = by_living[0]
            recs.append(
                f"Lowest living cost: {low.city_name} (~{low.monthly_living:,.0f} {cur}/month)."
            )
        return recs
