"""Unit tests for the application planner and auth primitives (no DB / no network)."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import jwt

from app.core.config import settings
from app.core.schemas import (
    CandidatePlan,
    Citation,
    PlanningRequest,
    PlanResult,
    ScholarshipMatch,
)
from app.core.security import create_access_token, hash_password, verify_password
from app.services.application_planner import build_application_plan


def _cit() -> Citation:
    return Citation(publisher="P", url="https://x.org", source_type="government")


def _match(sid: int, name: str, value: float, days: int | None, elig: str = "eligible",
           docs: list[str] | None = None) -> ScholarshipMatch:
    deadline = date.today() + timedelta(days=days) if days is not None else None
    return ScholarshipMatch(
        scholarship_id=sid, name=name, provider="Prov", coverage_type="stipend",
        currency="EUR", estimated_value=value, eligibility=elig, deadline=deadline,
        days_until_deadline=days, documents_required=docs or ["Transcript", "CV"], citation=_cit(),
    )


def _plan(matches: list[ScholarshipMatch]) -> PlanResult:
    c = CandidatePlan(
        program_id=1, program_name="MSc CS", field="Computer Science", degree_level="master",
        language="English", duration_years=2.0, university_name="Test U", city_name="City",
        country_name="Land", country_iso="LL", report_currency="EUR",
        total_annual=15000, scholarships=matches,
    )
    return PlanResult(
        request=PlanningRequest(budget_amount=15000), report_currency="EUR", candidates=[c],
        recommendations=[], generated_at=datetime.utcnow(), disclaimer="x",
    )


def test_planner_orders_by_deadline_then_value():
    plan = _plan([
        _match(1, "Far big", 12000, days=200),
        _match(2, "Soon small", 3000, days=10),
        _match(3, "No deadline", 9000, days=None),
    ])
    ap = build_application_plan(plan)
    assert [t.scholarship_id for t in ap.tasks] == [2, 1, 3]
    assert ap.tasks[0].priority == 1
    assert "Closest deadline" in ap.tasks[0].priority_reason


def test_planner_this_week_and_documents():
    plan = _plan([
        _match(1, "Urgent", 5000, days=7, docs=["Transcript", "Passport"]),
        _match(2, "Later", 4000, days=120, docs=["CV", "Transcript"]),
    ])
    ap = build_application_plan(plan)
    assert any("Submit Urgent" in s for s in ap.this_week)
    assert ap.all_documents == ["CV", "Passport", "Transcript"]


def test_planner_skips_ineligible():
    plan = _plan([_match(1, "No", 5000, days=10, elig="ineligible")])
    ap = build_application_plan(plan)
    assert ap.tasks == []


def test_password_hash_roundtrip():
    h = hash_password("s3cret!")
    assert h != "s3cret!"
    assert verify_password("s3cret!", h)
    assert not verify_password("wrong", h)


def test_jwt_token_roundtrip():
    token = create_access_token(42)
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    assert payload["sub"] == "42"
