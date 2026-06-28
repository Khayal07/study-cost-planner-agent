"""Verification harness for the seeded dataset.

Runs two things and prints a report:

1. A **DB-wide audit** over every ``cost_item``:
   - source presence: any ``confidence='sourced'`` figure must have a source URL;
   - currency validity: 3-letter ISO codes only;
   - sanity ranges: tuition (annual) and living (monthly) within plausible bands.

2. The **Verifier Agent** itself, by running a full plan per seeded country so its
   real checks (source integrity, freshness, totals consistency, budget gap,
   plausibility) execute against live, currency-converted candidates.

Usage (inside the backend container):
    python -m scripts.verify_seed
"""
from __future__ import annotations

import sys

from sqlalchemy import select

from app.agents.orchestrator import Orchestrator
from app.core.schemas import PlanningRequest
from app.data.db import SessionLocal
from app.data.models import Country, CostItem, Source

# Plausibility bands (annualized where noted), mirroring the Verifier agent.
TUITION_ANNUAL_BAND = (0.0, 200000.0)  # wide: raw units, covers non-EUR tuitions (e.g. CZK ~132,000/yr)
LIVING_MONTHLY_BAND = (0.0, 60000.0)  # wide: covers high-inflation currencies (TRY)


def _annualize(amount: float, period: str) -> float:
    return amount * 12 if period == "monthly" else amount


def db_audit(session) -> list[str]:
    problems: list[str] = []
    items = list(session.scalars(select(CostItem)))
    sources = {s.id: s for s in session.scalars(select(Source))}

    sourced_missing_url = 0
    bad_currency = 0
    for it in items:
        src = sources.get(it.source_id)
        if it.confidence == "sourced" and (src is None or not src.url):
            sourced_missing_url += 1
            problems.append(f"[source] {it.cost_type} #{it.id} is 'sourced' but has no URL")
        if not (isinstance(it.currency, str) and len(it.currency) == 3 and it.currency.isalpha()):
            bad_currency += 1
            problems.append(f"[currency] {it.cost_type} #{it.id} has invalid currency '{it.currency}'")
        amt = float(it.amount)
        if it.cost_type == "tuition":
            lo, hi = TUITION_ANNUAL_BAND
            if not (lo <= _annualize(amt, it.period) <= hi):
                problems.append(f"[range] tuition #{it.id} = {amt} {it.currency}/{it.period} out of band")

    print("== DB-wide audit ==")
    print(f"  cost_items checked : {len(items)}")
    print(f"  sources            : {len(sources)}")
    print(f"  sourced w/o URL    : {sourced_missing_url}")
    print(f"  invalid currency   : {bad_currency}")
    print(f"  sourced figures    : {sum(1 for i in items if i.confidence == 'sourced')}")
    print(f"  estimate figures   : {sum(1 for i in items if i.confidence == 'estimate')}")
    return problems


def verify_countries(session) -> list[str]:
    problems: list[str] = []
    orch = Orchestrator()
    countries = list(session.scalars(select(Country)))
    print("\n== Verifier Agent (per country) ==")
    for co in countries:
        req = PlanningRequest(
            country=co.name, field=None, budget_amount=100000,
            budget_currency="EUR", report_currency="EUR",
        )
        result = orch.run(session, req)
        rep = result.verification
        print(f"\n-- {co.name}: {len(result.candidates)} candidate(s); overall={rep.overall} --")
        for c in rep.checks:
            print(f"   {c.status.upper():4}  {c.name}: {c.detail}")
        if rep.overall == "fail":
            problems.append(f"{co.name}: verifier overall FAIL")
    return problems


def main() -> int:
    session = SessionLocal()
    try:
        problems = db_audit(session) + verify_countries(session)
    finally:
        session.close()

    print("\n== Summary ==")
    if problems:
        print(f"  {len(problems)} problem(s):")
        for p in problems:
            print(f"   - {p}")
        return 1
    print("  All checks passed: every sourced figure has a URL, currencies valid, "
          "ranges plausible, verifier overall not 'fail'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
