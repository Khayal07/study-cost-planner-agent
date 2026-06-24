"""Tuition Agent — gathers program tuition figures (no LLM, no math beyond lookup)."""
from __future__ import annotations

from app.agents.context import PlanningContext
from app.data.repository import tuition_items


class TuitionAgent:
    name = "tuition"

    def run(self, ctx: PlanningContext) -> None:
        for build in ctx.builds:
            build.tuition_raw = tuition_items(ctx.session, build.refs.program.id)
            if not build.tuition_raw:
                ctx.warnings.append(
                    f"No tuition record for program '{build.refs.program.name}'"
                )
