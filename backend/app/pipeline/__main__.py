"""CLI for the data-collection pipeline.

    docker compose exec backend python -m app.pipeline collect --field "Medicine" [--country EE] [--degree master] [--limit 2] [--plan-only]
    docker compose exec backend python -m app.pipeline apply --file db/seed/staging/medicine.json

Deliberately NOT part of app/cli.py: that module runs on every container boot,
and paid-API code stays out of the boot path.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.data.db import SessionLocal
from app.data.seed import SEED_DIR


def _money(program: dict | None) -> str:
    if not program:
        return "—"
    t = program["tuition"]
    return f"{t['amount']:,.0f} {t['currency']}/{t['period']}"


def _print_entries(entries: list[dict]) -> None:
    if not entries:
        return
    print(f"\n{'University':38} {'Program':32} {'Tuition':>18} {'Conf':8} {'Status':18}")
    print("-" * 118)
    for e in entries:
        program = e.get("program")
        conf = program["tuition"]["confidence"] if program else "—"
        name = (program or {}).get("name", "—")
        print(
            f"{e['university'][:37]:38} {name[:31]:32} {_money(program):>18} {conf:8} {e['status']:18}"
        )
        if program and program["tuition"]["source"]["url"]:
            print(f"{'':38} source: {program['tuition']['source']['url'][:90]}")
        for err in e.get("validation", {}).get("errors", []):
            print(f"{'':38} ! {err}")
        for warn in e.get("validation", {}).get("warnings", []):
            print(f"{'':38} ~ {warn}")
    print()


def cmd_collect(args: argparse.Namespace) -> int:
    from app.pipeline.collector import collect

    session = SessionLocal()
    try:
        result = collect(
            session,
            field=args.field,
            degree=args.degree,
            country_iso=args.country,
            limit=args.limit,
            plan_only=args.plan_only,
        )
    except RuntimeError as exc:
        print(f"error: {exc}")
        return 1
    finally:
        session.close()

    if args.plan_only:
        if not result["targets"]:
            print("Nothing to do — every in-scope university is already covered.")
            return 2
        print(f"Would search {len(result['targets'])} universities (0 API calls made):")
        for t in result["targets"]:
            print(f"  {t['university']} — {t['city']}, {t['country']}")
        return 0

    if not result["targets"]:
        print("Nothing to do — every in-scope university is already covered.")
        return 2

    if result["truncated"]:
        print(f"NOTE: target list truncated to the per-run cap of {len(result['targets'])} calls.")
    _print_entries(result["entries"])
    pending = sum(1 for e in result["entries"] if e["status"] == "pending")
    print(f"{result['calls_made']} API calls · {pending} pending for review")
    print(f"Staging file: {result['staging_file']}")
    rel = Path(result["staging_file"])
    try:
        rel = rel.relative_to(SEED_DIR.parent.parent)
    except ValueError:
        pass
    print(f"Review it, then apply with:\n  python -m app.pipeline apply --file {rel}")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    from app.pipeline.merge import apply_staging

    path = Path(args.file)
    if not path.is_absolute():
        # Accept both repo-root-relative (db/seed/staging/x.json) and bare names.
        candidates = [Path.cwd() / path, SEED_DIR / "staging" / path.name]
        path = next((c for c in candidates if c.exists()), candidates[0])
    if not path.exists():
        print(f"Staging file not found: {path}")
        return 1

    session = SessionLocal()
    try:
        summary = apply_staging(session, path)
    finally:
        session.close()

    print(
        f"applied: {summary['applied']} · duplicates skipped: {summary['skipped_duplicate']} · "
        f"rejected: {summary['rejected']} · not offered: {summary['not_offered']} · "
        f"untouched: {summary['untouched']}"
    )
    if summary["applied"]:
        print("data.real.json updated; new rows live in the DB — /meta/options reflects them immediately.")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.pipeline", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_collect = sub.add_parser("collect", help="web-search programs+tuition for a field")
    p_collect.add_argument("--field", required=True, help='e.g. "Medicine"')
    p_collect.add_argument("--country", default=None, help="ISO code filter, e.g. EE")
    p_collect.add_argument("--degree", default=None, choices=["bachelor", "master"])
    p_collect.add_argument("--limit", type=int, default=None, help="max universities this run")
    p_collect.add_argument("--plan-only", action="store_true", help="show targets, no API calls")
    p_collect.set_defaults(func=cmd_collect)

    p_apply = sub.add_parser("apply", help="merge a reviewed staging file into dataset + DB")
    p_apply.add_argument("--file", required=True, help="staging JSON path")
    p_apply.set_defaults(func=cmd_apply)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
