"""Small management CLI used by docker-compose on boot.

    python -m app.cli migrate   # create pgvector extension + schema (idempotent)
    python -m app.cli seed      # load curated seed data (idempotent)
    python -m app.cli reset     # drop all tables (dev convenience)
"""
from __future__ import annotations

import sys

from sqlalchemy import text

from app.data.db import Base, engine

# Importing models registers them on Base.metadata.
from app.data import models  # noqa: F401


def migrate() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    # create_all() skips already-existing tables (and therefore their newly-declared
    # indexes), so ensure the performance indexes exist on a pre-existing database too.
    # Idempotent; names match the __table_args__ declarations in models.py.
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_cost_items_scope "
            "ON cost_items (scope_level, scope_id, cost_type)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_fx_rates_lookup "
            "ON fx_rates (base, quote, as_of_date)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_scholarships_scope "
            "ON scholarships (scope_level, scope_id)"
        ))
        # Phase 3 #7: student work-rights columns on an existing countries table.
        # Idempotent — create_all() won't ALTER a table that already exists.
        for ddl in (
            "ALTER TABLE countries ADD COLUMN IF NOT EXISTS work_hours_cap INTEGER",
            "ALTER TABLE countries ADD COLUMN IF NOT EXISTS work_hourly_wage NUMERIC(12,2)",
            "ALTER TABLE countries ADD COLUMN IF NOT EXISTS work_wage_currency VARCHAR(3)",
            "ALTER TABLE countries ADD COLUMN IF NOT EXISTS work_note TEXT",
            "ALTER TABLE countries ADD COLUMN IF NOT EXISTS work_source_id INTEGER REFERENCES sources(id)",
        ):
            conn.execute(text(ddl))
    print("[cli] migrate: schema ready (pgvector enabled, perf indexes ensured)")


def seed() -> None:
    from app.data.seed import load_seed

    result = load_seed()
    print(f"[cli] seed: {result}")


def reset() -> None:
    Base.metadata.drop_all(bind=engine)
    print("[cli] reset: all tables dropped")


def reseed() -> None:
    """Dev convenience: wipe and reload the active seed dataset from scratch.

    Useful while building the real dataset incrementally (the plain ``seed`` is
    idempotent and skips when data is already present).
    """
    reset()
    migrate()
    seed()


COMMANDS = {"migrate": migrate, "seed": seed, "reset": reset, "reseed": reseed}


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in COMMANDS:
        print(f"usage: python -m app.cli [{'|'.join(COMMANDS)}]")
        return 1
    COMMANDS[argv[0]]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
