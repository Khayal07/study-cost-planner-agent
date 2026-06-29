"""Eligibility Agent — scores each gathered award against the candidate + profile.

Deterministic and explainable: every verdict comes with a reason list (no LLM in the
decision). Hard criteria (degree, field, GPA, excluded/required nationality) can make an
award `ineligible`; missing optional inputs yield `unknown`/`likely` rather than a false
negative, so a blank profile never crashes and never wrongly rules awards out.

Degree and field are matched against the *candidate program* (always known); nationality,
GPA and language come from the student profile (all optional).
"""
from __future__ import annotations

from datetime import date

from app.agents.context import PlanningContext
from app.core.schemas import CandidatePlan, ScholarshipMatch
from app.data.models import Scholarship
from app.data.repository import to_citation


def _split(value: str | None) -> list[str]:
    return [t.strip() for t in value.split(",") if t.strip()] if value else []


class EligibilityAgent:
    name = "eligibility"

    def run(self, ctx: PlanningContext) -> None:
        req = ctx.request
        for build in ctx.builds:
            if build.plan is None:
                continue
            matches = [
                self._evaluate(sch, build.plan, req.nationality, req.gpa, req.language_test)
                for sch in build.scholarships_raw
            ]
            # Eligible first, then likely/unknown, ineligible last; stable otherwise.
            order = {"eligible": 0, "likely": 1, "unknown": 2, "ineligible": 3}
            matches.sort(key=lambda m: order.get(m.eligibility, 4))
            build.plan.scholarships = matches

    def _evaluate(
        self,
        sch: Scholarship,
        plan: CandidatePlan,
        nationality: str | None,
        gpa: float | None,
        language_test: str | None,
    ) -> ScholarshipMatch:
        reasons: list[str] = []
        hard_fail = False
        missing_hard = False   # a hard criterion exists but profile lacks the input
        missing_soft = False   # a soft criterion (language) is unmet only for lack of input

        # --- degree (matched on the candidate program) ---
        allowed_degrees = [d.lower() for d in _split(sch.degree_levels)]
        if allowed_degrees:
            if plan.degree_level.lower() in allowed_degrees:
                reasons.append(f"{plan.degree_level.title()} level eligible ✓")
            else:
                hard_fail = True
                reasons.append(
                    f"Requires {'/'.join(allowed_degrees)}; this is a {plan.degree_level} program ✗"
                )

        # --- field (matched on the candidate program) ---
        allowed_fields = [f.lower() for f in _split(sch.fields)]
        if allowed_fields:
            if any(f in plan.field.lower() or plan.field.lower() in f for f in allowed_fields):
                reasons.append(f"{plan.field} field eligible ✓")
            else:
                hard_fail = True
                reasons.append(f"Restricted to {'/'.join(allowed_fields)} ✗")

        # --- nationality (include list and/or "!"-prefixed excludes) ---
        if sch.nationality_rule:
            tokens = _split(sch.nationality_rule)
            excludes = [t[1:].lower() for t in tokens if t.startswith("!")]
            includes = [t.lower() for t in tokens if not t.startswith("!")]
            if nationality:
                nat = nationality.lower()
                if any(x in nat for x in excludes):
                    hard_fail = True
                    reasons.append(f"Not open to {nationality} ✗")
                elif includes and not any(i in nat for i in includes):
                    hard_fail = True
                    reasons.append(f"Open only to: {'/'.join(includes)} ✗")
                else:
                    reasons.append("Open to your nationality ✓")
            else:
                if includes:
                    missing_hard = True
                    reasons.append(f"Nationality-restricted ({'/'.join(includes)}); add yours to confirm")
                else:
                    reasons.append("Nationality not provided — assumed not excluded")

        # --- GPA ---
        if sch.min_gpa is not None:
            min_gpa = float(sch.min_gpa)
            if gpa is not None:
                if gpa >= min_gpa:
                    reasons.append(f"GPA {gpa:.1f} ≥ {min_gpa:.1f} ✓")
                else:
                    hard_fail = True
                    reasons.append(f"GPA {gpa:.1f} below required {min_gpa:.1f} ✗")
            else:
                missing_hard = True
                reasons.append(f"Requires GPA ≥ {min_gpa:.1f}; not provided")

        # --- language ---
        if sch.language_requirement:
            if language_test:
                reasons.append(f"Language: {sch.language_requirement} (you noted: {language_test})")
            else:
                missing_soft = True
                reasons.append(f"Language proof needed: {sch.language_requirement}")

        # --- deadline ---
        days = None
        if sch.deadline is not None:
            days = (sch.deadline - date.today()).days
            if days >= 0:
                reasons.append(f"Deadline in {days} days ({sch.deadline.isoformat()})")
            else:
                hard_fail = True  # a passed deadline can't be applied to — rule it out
                reasons.append(f"Deadline passed ({sch.deadline.isoformat()}) ✗")

        if hard_fail:
            eligibility = "ineligible"
        elif missing_hard:
            eligibility = "unknown"
        elif missing_soft:
            eligibility = "likely"
        else:
            eligibility = "eligible"

        return ScholarshipMatch(
            scholarship_id=sch.id,
            name=sch.name,
            provider=sch.provider,
            coverage_type=sch.coverage_type,
            amount=float(sch.amount) if sch.amount is not None else None,
            coverage_pct=float(sch.coverage_pct) if sch.coverage_pct is not None else None,
            currency=sch.currency,
            eligibility=eligibility,
            reasons=reasons,
            deadline=sch.deadline,
            days_until_deadline=days,
            renewable=sch.renewable,
            application_url=sch.application_url,
            documents_required=_split(sch.documents_required),
            citation=to_citation(sch.source),
        )
