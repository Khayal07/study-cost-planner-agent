"""Unit tests for the scholarship layer — eligibility, net cost and value ranking.

No database or network: synthetic Scholarship/CandidatePlan objects exercise the
deterministic rules directly. Awards are kept in EUR so CurrencyService takes the
identity path (no session needed).
"""
from __future__ import annotations

from datetime import date, timedelta

from app.agents.context import CandidateBuild, PlanningContext
from app.agents.eligibility import EligibilityAgent
from app.agents.net_value import NetValueAgent
from app.agents.verifier import VerifierAgent
from app.core.schemas import CandidatePlan, Citation, CostLine, PlanningRequest
from app.data.models import Scholarship, Source


def _source(url: str | None = "https://example.org/scholarship") -> Source:
    return Source(url=url, title="Award", publisher="Provider", source_type="government")


def _sch(sid: int = 1, *, url: str | None = "https://example.org/scholarship", **kw) -> Scholarship:
    base = dict(
        name=f"Award {sid}", provider="Provider", scope_level="country", scope_id=1,
        coverage_type="stipend", amount=None, coverage_pct=None, currency="EUR",
        period="annual", degree_levels=None, fields=None, nationality_rule=None,
        min_gpa=None, language_requirement=None, renewable=False, deadline=None,
        application_url="https://apply.example.org", documents_required="Transcript,CV",
        confidence="sourced",
    )
    base.update(kw)
    s = Scholarship(**base)
    s.id = sid
    s.source = _source(url)
    return s


def _line(cost_type: str, amount: float) -> CostLine:
    return CostLine(
        label=cost_type, cost_type=cost_type, amount=amount, currency="EUR",
        original_amount=amount, original_currency="EUR", original_period="annual",
        confidence="estimate",
        citation=Citation(publisher="T", url="https://t.org", source_type="estimate"),
    )


def _plan(program_id: int = 1, tuition: float = 3000.0) -> CandidatePlan:
    lines = [_line("tuition", tuition), _line("rent", 6000.0), _line("food", 3000.0),
             _line("insurance", 1200.0), _line("visa", 75.0)]
    living = 6000 + 3000 + 1200
    return CandidatePlan(
        program_id=program_id, program_name="MSc CS", field="Computer Science",
        degree_level="master", language="English", duration_years=2.0,
        university_name=f"Uni {program_id}", city_name="City", country_name="Land",
        country_iso="LL", report_currency="EUR", lines=lines,
        annual_tuition=tuition, annual_living=living, annual_one_time=75.0, annual_hidden=0.0,
        total_annual=tuition + living + 75.0, monthly_living=living / 12,
    )


def _evaluate(sch: Scholarship, plan: CandidatePlan, **profile):
    return EligibilityAgent()._evaluate(
        sch, plan, profile.get("nationality"), profile.get("gpa"), profile.get("language_test")
    )


# --- eligibility verdicts ---

def test_degree_match_and_mismatch():
    plan = _plan()
    assert _evaluate(_sch(degree_levels="master,phd"), plan).eligibility == "eligible"
    assert _evaluate(_sch(degree_levels="bachelor"), plan).eligibility == "ineligible"


def test_gpa_threshold():
    plan = _plan()
    assert _evaluate(_sch(min_gpa=3.5), plan, gpa=3.8).eligibility == "eligible"
    assert _evaluate(_sch(min_gpa=3.5), plan, gpa=3.2).eligibility == "ineligible"
    # GPA required but not provided -> unknown (counted optimistically, flagged).
    assert _evaluate(_sch(min_gpa=3.5), plan).eligibility == "unknown"


def test_nationality_exclude_rule():
    plan = _plan()
    assert _evaluate(_sch(nationality_rule="!Turkey"), plan, nationality="Turkey").eligibility == "ineligible"
    assert _evaluate(_sch(nationality_rule="!Turkey"), plan, nationality="Azerbaijan").eligibility == "eligible"
    # Only an exclusion rule + no nationality given -> assumed not excluded.
    assert _evaluate(_sch(nationality_rule="!Turkey"), plan).eligibility == "eligible"


def test_language_missing_is_likely():
    plan = _plan()
    m = _evaluate(_sch(language_requirement="IELTS 6.5"), plan)
    assert m.eligibility == "likely"


def test_deadline_days_until():
    plan = _plan()
    d = date.today() + timedelta(days=30)
    m = _evaluate(_sch(deadline=d), plan)
    assert m.days_until_deadline == 30


# --- net cost & value ranking ---

def _run_net(plans_and_awards, budget=20000.0):
    """plans_and_awards: list of (plan, [scholarships]); runs eligibility + net value."""
    builds = []
    candidates = []
    for plan, awards in plans_and_awards:
        b = CandidateBuild(refs=None, plan=plan, scholarships_raw=awards)
        builds.append(b)
        candidates.append(plan)
    ctx = PlanningContext(request=PlanningRequest(budget_amount=budget), session=None,
                          report_currency="EUR", builds=builds, candidates=candidates,
                          budget_in_report=budget)
    EligibilityAgent().run(ctx)
    NetValueAgent().run(ctx)
    return ctx


def test_full_tuition_zeroes_tuition_in_net():
    plan = _plan(tuition=3000.0)
    ctx = _run_net([(plan, [_sch(coverage_type="full_tuition", degree_levels="master")])])
    assert plan.total_scholarship_value == 3000.0
    assert plan.net_total_annual == round(plan.total_annual - 3000.0, 2)


def test_monthly_stipend_annualized_and_capped():
    plan = _plan(tuition=3000.0)  # total 13275
    ctx = _run_net([(plan, [_sch(coverage_type="stipend", amount=1000, period="monthly",
                                 degree_levels="master")])])
    # 1000/mo -> 12000/yr, below total so applied in full.
    assert plan.total_scholarship_value == 12000.0
    assert plan.net_total_annual == round(13275.0 - 12000.0, 2)
    assert plan.net_total_annual >= 0


def test_value_rank_orders_by_net_cost():
    a = _plan(program_id=1, tuition=3000.0)   # stipend -> net ~1275
    b = _plan(program_id=2, tuition=3000.0)   # full tuition -> net ~10275
    ctx = _run_net([
        (b, [_sch(2, coverage_type="full_tuition", degree_levels="master")]),
        (a, [_sch(1, coverage_type="stipend", amount=1000, period="monthly", degree_levels="master")]),
    ])
    assert a.value_rank == 1 and b.value_rank == 2


def test_ineligible_award_not_applied():
    plan = _plan(tuition=3000.0)
    ctx = _run_net([(plan, [_sch(coverage_type="full_tuition", degree_levels="bachelor")])])
    assert plan.total_scholarship_value == 0.0
    assert plan.net_total_annual == plan.total_annual


# --- verifier scholarship check ---

def test_verifier_scholarship_pass_and_uncited_fail():
    plan = _plan()
    ctx = _run_net([(plan, [_sch(coverage_type="full_tuition", degree_levels="master")])])
    plan.budget_gap = 20000 - plan.total_annual
    VerifierAgent().run(ctx)
    check = next(c for c in ctx.verification.checks if c.name == "scholarships")
    assert check.status == "pass"

    # Uncited award -> fail.
    plan2 = _plan()
    ctx2 = _run_net([(plan2, [_sch(coverage_type="full_tuition", degree_levels="master", url=None)])])
    plan2.budget_gap = 20000 - plan2.total_annual
    VerifierAgent().run(ctx2)
    check2 = next(c for c in ctx2.verification.checks if c.name == "scholarships")
    assert check2.status == "fail"
