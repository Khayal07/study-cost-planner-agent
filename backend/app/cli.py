"""Small management CLI used by docker-compose on boot.

    python -m app.cli migrate   # create schema + pgvector extension (idempotent)
    python -m app.cli seed      # load curated seed data (idempotent)

Phase 0 ships safe stubs so `docker compose up` succeeds; Phase 1 fills these in.
"""
from __future__ import annotations

import sys


def migrate() -> None:
    print("[cli] migrate: no-op stub (schema lands in Phase 1)")


def seed() -> None:
    print("[cli] seed: no-op stub (seed data lands in Phase 1)")


COMMANDS = {"migrate": migrate, "seed": seed}


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in COMMANDS:
        print(f"usage: python -m app.cli [{'|'.join(COMMANDS)}]")
        return 1
    COMMANDS[argv[0]]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
