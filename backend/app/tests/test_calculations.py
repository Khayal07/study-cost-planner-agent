"""Unit tests for the deterministic math — the core correctness guarantee.

No database or network: we build synthetic CandidatePlan/PlanningContext objects and
exercise annualization, scenarios and the verifier rules directly.
"""
from __future__ import annotations

from app.agents.context import PlanningContext
from app.agents.currency import _annualize
from app.agents.scenario import ScenarioAgent
from app.agents.verifier import VerifierAgent
from app.core.schemas import CandidatePlan, Citation, CostLine, PlanningRequest


def _citation(url: str | None = "https://example.org") -> Citation:
    return Citation(publisher="Test", url=url, accessed_date=None, source_type="official_university")


def _line(label: str, cost_type: str, amount: float, confidence: str = "estimate") -> CostLine:
    return CostLine(
        label=label, cost_type=cost_type, amount=amount, currency="EUR",
        original_amount=amount, original_currency="EUR", original_period="annual",
        confidence=confidence, citation=_citation(),
    )


def _plan() -> CandidatePlan:
    # tuition 3000 + living(rent 6000 + food 3000 + insurance 1200) + visa 75
    lines = [
        _line("Tuition", "tuition", 3000.0),
        _line("Rent", "rent", 6000.0),
        _line("Food", "food", 3000.0),
        _line("Insurance", "insurance", 1200.0),
        _line("Visa", "visa", 75.0),
    ]
    living = 6000 + 3000 + 1200
    return CandidatePlan(
        program_id=1, program_name="MSc CS", field="Computer Science", degree_level="master",
        language="English", duration_years=2.0, university_name="Test U", city_name="Testville",
        country_name="Testland", country_iso="TT", report_currency="EUR", lines=lines,
        annual_tuition=3000.0, annual_living=living, annual_one_time=75.0, annual_hidden=0.0,
        total_annual=3000.0 + living + 75.0, monthly_living=living / 12,
    )


def test_annualize_monthly_and_one_time():
    assert _annualize(100.0, "monthly") == 1200.0
    assert _annualize(500.0, "annual") == 500.0
    assert _annualize(75.0, "one_time") == 75.0


def test_total_equals_sum_of_lines():
    plan = _plan()
    assert round(sum(ln.amount for ln in plan.lines), 2) == plan.total_annual


def test_scenarios_order_and_multipliers():
    ctx = PlanningContext(request=PlanningRequest(budget_amount=20000), session=None,
                          report_currency="EUR", candidates=[_plan()])
    ScenarioAgent().run(ctx)
    s = {x.name: x for x in ctx.candidates[0].scenarios}
    assert set(s) == {"frugal", "moderate", "comfortable"}
    # Discretionary (rent+food) scales; fixed (tuition+insurance+visa) does not.
    assert s["frugal"].annual_total < s["moderate"].annual_total < s["comfortable"].annual_total
    # Moderate equals the plan's own total (multiplier 1.0).
    assert abs(s["moderate"].annual_total - _plan().total_annual) < 1.0


def test_verifier_passes_clean_plan():
    plan = _plan()
    plan.budget_gap = 20000 - plan.total_annual
    ctx = PlanningContext(request=PlanningRequest(budget_amount=20000), session=None,
                          report_currency="EUR", candidates=[plan], budget_in_report=20000.0)
    VerifierAgent().run(ctx)
    assert ctx.verification.overall == "pass"


def test_verifier_flags_missing_source():
    plan = _plan()
    plan.lines[0] = _line("Tuition", "tuition", 3000.0, confidence="sourced")
    plan.lines[0].citation = _citation(url=None)  # sourced but no URL -> fail
    plan.budget_gap = 20000 - plan.total_annual
    ctx = PlanningContext(request=PlanningRequest(budget_amount=20000), session=None,
                          report_currency="EUR", candidates=[plan], budget_in_report=20000.0)
    VerifierAgent().run(ctx)
    integrity = next(c for c in ctx.verification.checks if c.name == "source_integrity")
    assert integrity.status == "fail"
    assert ctx.verification.overall == "fail"


def test_verifier_flags_wrong_budget_gap():
    plan = _plan()
    plan.budget_gap = 999999.0  # deliberately wrong
    ctx = PlanningContext(request=PlanningRequest(budget_amount=20000), session=None,
                          report_currency="EUR", candidates=[plan], budget_in_report=20000.0)
    VerifierAgent().run(ctx)
    gap = next(c for c in ctx.verification.checks if c.name == "budget_gap")
    assert gap.status == "fail"
