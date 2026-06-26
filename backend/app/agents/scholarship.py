"""Scholarship Agent — gathers awards applicable to each candidate.

Pure retrieval, mirroring how Tuition/Living agents gather CostItems: for every
candidate it pulls global awards plus those scoped to the candidate's country,
university or program. Eligibility scoring and net-cost math happen downstream.
"""
from __future__ import annotations

from app.agents.context import PlanningContext
from app.data.repository import scholarships_for_candidate


class ScholarshipAgent:
    name = "scholarship"

    def run(self, ctx: PlanningContext) -> None:
        for build in ctx.builds:
            refs = build.refs
            build.scholarships_raw = scholarships_for_candidate(
                ctx.session,
                program_id=refs.program.id,
                university_id=refs.university.id,
                country_id=refs.country.id,
            )
