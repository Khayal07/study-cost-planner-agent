"""Application planner — turns a plan's eligible scholarships into an action plan.

Deterministic: prioritizes the awards the student may qualify for by deadline urgency
then award value, derives a "this week" task list and the union of required documents.
No LLM, no invented data — it only reorganizes what the eligibility agent produced.
"""
from __future__ import annotations

from datetime import datetime

from app.core.schemas import ApplicationPlan, ApplicationTask, PlanResult

_APPLICABLE = {"eligible", "likely", "unknown"}
_FAR = 10_000  # sort key for "no deadline" so dated tasks come first


def build_application_plan(plan: PlanResult) -> ApplicationPlan:
    tasks: list[ApplicationTask] = []
    seen: set[tuple[int, int]] = set()

    for c in plan.candidates:
        for m in c.scholarships:
            if m.eligibility not in _APPLICABLE or m.estimated_value <= 0:
                continue
            key = (m.scholarship_id, c.program_id)
            if key in seen:
                continue
            seen.add(key)
            tasks.append(
                ApplicationTask(
                    scholarship_id=m.scholarship_id, name=m.name, provider=m.provider,
                    university_name=c.university_name, program_id=c.program_id,
                    coverage_type=m.coverage_type, estimated_value=m.estimated_value,
                    currency=c.report_currency, eligibility=m.eligibility,
                    deadline=m.deadline, days_until_deadline=m.days_until_deadline,
                    priority=0, priority_reason="", application_url=m.application_url,
                    documents=list(m.documents_required),
                )
            )

    # Prioritize: soonest deadline first, then highest value.
    tasks.sort(key=lambda t: (
        t.days_until_deadline if t.days_until_deadline is not None else _FAR,
        -t.estimated_value,
    ))

    soonest = min(
        (t.days_until_deadline for t in tasks if t.days_until_deadline is not None),
        default=None,
    )
    most_valuable = max((t.estimated_value for t in tasks), default=0.0)
    for i, t in enumerate(tasks):
        t.priority = i + 1
        if t.days_until_deadline is not None and t.days_until_deadline == soonest:
            t.priority_reason = f"Closest deadline — {t.days_until_deadline} days left"
        elif t.estimated_value == most_valuable:
            t.priority_reason = "Highest award value"
        else:
            t.priority_reason = "Strong fit for your profile"

    this_week = _this_week(tasks)
    all_documents = sorted({d for t in tasks for d in t.documents})
    return ApplicationPlan(
        tasks=tasks, this_week=this_week, all_documents=all_documents,
        generated_at=datetime.utcnow(),
    )


def _this_week(tasks: list[ApplicationTask]) -> list[str]:
    if not tasks:
        return ["No matching scholarships yet — add your nationality, GPA and language test to surface more."]
    actions: list[str] = []
    urgent = [t for t in tasks if t.days_until_deadline is not None and 0 <= t.days_until_deadline <= 14]
    for t in urgent:
        actions.append(
            f"Submit {t.name} for {t.university_name} by {t.deadline.isoformat()} "
            f"({t.days_until_deadline} days left)."
        )
    top = tasks[0]
    docs = ", ".join(top.documents[:3]) if top.documents else "the required documents"
    actions.append(f"Start your #1 priority — {top.name}: gather {docs}.")
    return actions
