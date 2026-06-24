"""Living Cost Agent — gathers city living costs plus country-level visa/insurance/hidden."""
from __future__ import annotations

from app.agents.context import PlanningContext
from app.data.repository import country_items, living_items


class LivingCostAgent:
    name = "living_cost"

    def run(self, ctx: PlanningContext) -> None:
        for build in ctx.builds:
            build.living_raw = living_items(ctx.session, build.refs.city.id)
            build.country_raw = country_items(ctx.session, build.refs.country.id)
            if not build.living_raw:
                ctx.warnings.append(
                    f"No living-cost records for city '{build.refs.city.name}'"
                )
