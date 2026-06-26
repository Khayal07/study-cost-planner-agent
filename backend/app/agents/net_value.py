"""Net-Value Agent — the cost picture *after* scholarships.

Converts each award to an annual saving in the report currency, applies the single best
realistic award per candidate (a student rarely stacks two full rides), and derives the
net total, net budget gap and a `value_rank` (cheapest-after-aid). Gross `rank` from the
Budget Matching agent is preserved — both rankings coexist. Adds grounded, net-aware
recommendations without touching the existing ones.
"""
from __future__ import annotations

from app.agents.context import PlanningContext
from app.core.schemas import CandidatePlan, ScholarshipMatch
from app.data.models import Scholarship
from app.services.currency import CurrencyService

# Awards we count toward net cost (optimistic for missing-input cases, per the plan).
APPLICABLE = {"eligible", "likely", "unknown"}


class NetValueAgent:
    name = "net_value"

    def run(self, ctx: PlanningContext) -> None:
        fx = CurrencyService(ctx.session)
        report = ctx.report_currency
        budget = ctx.budget_in_report
        any_award = False

        for build in ctx.builds:
            plan = build.plan
            if plan is None:
                continue
            raw_by_id = {s.id: s for s in build.scholarships_raw}

            for m in plan.scholarships:
                m.estimated_value = self._value(m, raw_by_id.get(m.scholarship_id), plan, fx, report)

            applicable = [m for m in plan.scholarships if m.eligibility in APPLICABLE and m.estimated_value > 0]
            best = max(applicable, key=lambda m: m.estimated_value, default=None)
            applied = round(min(best.estimated_value, plan.total_annual), 2) if best else 0.0

            plan.total_scholarship_value = applied
            plan.net_total_annual = round(plan.total_annual - applied, 2)
            if budget is not None:
                plan.net_budget_gap = round(budget - plan.net_total_annual, 2)
                plan.net_affordable = plan.net_budget_gap >= 0
            if applied > 0:
                any_award = True

        # Value ranking by net cost (falls back to gross when no award applies).
        ranked = sorted(ctx.candidates, key=lambda p: (p.net_total_annual if p.net_total_annual is not None else p.total_annual))
        for i, plan in enumerate(ranked):
            plan.value_rank = i + 1

        if any_award:
            ctx.recommendations.extend(self._recommendations(ctx, ranked, budget))

    def _value(
        self,
        m: ScholarshipMatch,
        raw: Scholarship | None,
        plan: CandidatePlan,
        fx: CurrencyService,
        report: str,
    ) -> float:
        ct = m.coverage_type
        if ct in ("full_tuition", "tuition_waiver"):
            return round(plan.annual_tuition, 2)
        if ct == "partial_tuition":
            return round(plan.annual_tuition * (m.coverage_pct or 0) / 100, 2)
        # Cash awards (stipend / living_grant / fixed_amount): convert + annualize.
        if m.amount is None:
            return 0.0
        converted, _ = fx.convert(m.amount, m.currency, report)
        period = raw.period if raw else "annual"
        annual = converted * 12 if period == "monthly" else converted
        return round(annual, 2)

    def _recommendations(
        self, ctx: PlanningContext, ranked: list[CandidatePlan], budget: float | None
    ) -> list[str]:
        cur = ctx.report_currency
        recs: list[str] = []

        # Cheapest after scholarships (only meaningful if it actually received an award).
        with_award = [p for p in ranked if p.total_scholarship_value > 0]
        if with_award:
            best = min(
                with_award,
                key=lambda p: p.net_total_annual if p.net_total_annual is not None else p.total_annual,
            )
            note = ""
            if best.rank and best.value_rank and best.rank != best.value_rank:
                note = f" (was #{best.rank} on gross cost)"
            recs.append(
                f"After scholarships, best value is {best.university_name}: "
                f"~{best.net_total_annual:,.0f} {cur}/year{note}, down from "
                f"~{best.total_annual:,.0f} {cur}."
            )

        # Eligible-award summary + nearest deadline.
        eligible = [
            m for p in ctx.candidates for m in p.scholarships
            if m.eligibility in ("eligible", "likely")
        ]
        if eligible:
            top_value = max(m.estimated_value for m in eligible)
            with_deadline = [m for m in eligible if m.days_until_deadline is not None and m.days_until_deadline >= 0]
            nearest = min(with_deadline, key=lambda m: m.days_until_deadline, default=None)
            tail = ""
            if nearest:
                tail = f" Nearest deadline: {nearest.name} in {nearest.days_until_deadline} days ({nearest.deadline.isoformat()})."
            names = ", ".join(sorted({m.name for m in eligible})[:3])
            recs.append(
                f"You look eligible for awards worth up to ~{top_value:,.0f} {cur}/year "
                f"(e.g. {names}).{tail}"
            )
        return recs
