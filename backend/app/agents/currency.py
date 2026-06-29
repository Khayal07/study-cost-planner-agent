"""Currency Agent — normalizes every figure to the report currency and annualizes it.

This is where the deterministic math happens: conversion (via CurrencyService),
annualization (monthly x12, one_time counted in year one), per-component CostLines
with citations, category subtotals and the first-year total. It also raises FX risk
notes for volatile or stale rates.
"""
from __future__ import annotations

from app.agents.context import CandidateBuild, PlanningContext
from app.core.schemas import CandidatePlan, CostLine
from app.data.models import CostItem
from app.data.repository import to_citation
from app.services.currency import CurrencyService

LABELS = {
    "tuition": "Tuition",
    "rent": "Rent",
    "food": "Food & groceries",
    "transport": "Transport",
    "utilities": "Utilities & internet",
    "insurance": "Health insurance",
    "visa": "Visa / residence permit",
    "hidden_misc": "Other fees",
}

LIVING_TYPES = {"rent", "food", "transport", "utilities", "insurance"}

# Conservative working-weeks assumption for the part-time earnings estimate (Phase 3 #7):
# the term-time weekly cap applied across a typical academic working year.
WORK_WEEKS_PER_YEAR = 40


def _annualize(amount: float, period: str) -> float:
    if period == "monthly":
        return amount * 12
    return amount  # annual or one_time counted as-is for the first year


class CurrencyAgent:
    name = "currency"

    def run(self, ctx: PlanningContext) -> None:
        fx = CurrencyService(ctx.session)
        report = ctx.report_currency
        for build in ctx.builds:
            build.plan = self._build_plan(build, fx, report)
            ctx.candidates.append(build.plan)

    def _build_plan(self, build: CandidateBuild, fx: CurrencyService, report: str) -> CandidatePlan:
        refs = build.refs
        lines: list[CostLine] = []
        fx_notes: set[str] = set()
        totals = {"tuition": 0.0, "living": 0.0, "one_time": 0.0, "hidden": 0.0}

        all_items: list[CostItem] = [*build.tuition_raw, *build.living_raw, *build.country_raw]
        for item in all_items:
            line, annual = self._line(item, fx, report, fx_notes)
            lines.append(line)
            if item.cost_type == "tuition":
                totals["tuition"] += annual
            elif item.cost_type in LIVING_TYPES:
                totals["living"] += annual
            elif item.cost_type == "visa":
                totals["one_time"] += annual
            elif item.cost_type == "hidden_misc":
                totals["hidden"] += annual

        total_annual = round(sum(totals.values()), 2)
        annual_living = round(totals["living"], 2)

        work = self._work_offset(refs.country, fx, report)

        return CandidatePlan(
            program_id=refs.program.id,
            program_name=refs.program.name,
            field=refs.program.field,
            degree_level=refs.program.degree_level,
            language=refs.program.language,
            duration_years=float(refs.program.duration_years),
            university_name=refs.university.name,
            university_url=refs.university.official_url,
            city_name=refs.city.name,
            country_name=refs.country.name,
            country_iso=refs.country.iso_code,
            report_currency=report,
            lines=sorted(lines, key=lambda ln: (-ln.amount)),
            annual_tuition=round(totals["tuition"], 2),
            annual_living=annual_living,
            annual_one_time=round(totals["one_time"], 2),
            annual_hidden=round(totals["hidden"], 2),
            total_annual=total_annual,
            monthly_living=round(annual_living / 12, 2),
            fx_notes=sorted(fx_notes),
            work_hours_cap=work["hours_cap"],
            work_annual_earnings=work["annual_earnings"],
            work_note=work["note"],
            work_citation=work["citation"],
        )

    def _work_offset(self, country, fx: CurrencyService, report: str) -> dict:
        """Estimated annual gross from term-time part-time work, in the report currency.

        Sourced cap + wage; the working-weeks figure is a deliberate estimate, so the
        result is shown as a *potential* offset (never auto-subtracted from the cost)."""
        if country.work_hours_cap is None or country.work_hourly_wage is None:
            return {"hours_cap": None, "annual_earnings": None, "note": None, "citation": None}
        cap = int(country.work_hours_cap)
        wage = float(country.work_hourly_wage)
        wage_ccy = country.work_wage_currency or report
        local = cap * wage * WORK_WEEKS_PER_YEAR
        earnings_report, _ = fx.convert(local, wage_ccy, report)
        return {
            "hours_cap": cap,
            "annual_earnings": round(earnings_report, 2),
            "note": country.work_note,
            "citation": to_citation(country.work_source) if country.work_source else None,
        }

    def _line(
        self, item: CostItem, fx: CurrencyService, report: str, fx_notes: set[str]
    ) -> tuple[CostLine, float]:
        orig_amount = float(item.amount)
        converted_amount, conv = fx.convert(orig_amount, item.currency, report)
        annual = round(_annualize(converted_amount, item.period), 2)
        did_convert = item.currency.upper() != report.upper()

        if did_convert:
            fx_notes.add(
                f"{item.currency}->{report} at {conv.rate:.4f} "
                f"({'ECB ' + conv.as_of.isoformat() if conv.as_of else 'cached'})"
            )
            if conv.status == "stale":
                fx_notes.add(f"{item.currency} rate is stale (FX API unavailable); verify before relying on it")
            if CurrencyService.is_volatile(item.currency):
                fx_notes.add(f"{item.currency} is volatile; keep an extra budget buffer")

        line = CostLine(
            label=LABELS.get(item.cost_type, item.cost_type),
            cost_type=item.cost_type,
            amount=annual,
            currency=report,
            original_amount=orig_amount,
            original_currency=item.currency,
            original_period=item.period,
            confidence=item.confidence,
            note=item.note,
            converted=did_convert,
            citation=to_citation(item.source),
        )
        return line, annual
