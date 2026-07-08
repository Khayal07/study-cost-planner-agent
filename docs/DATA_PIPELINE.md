# AI data pipeline

Adds a **new field of study** (e.g. Medicine) across the universities already in the
dataset — with AI-assisted collection and **mandatory human review**. Nothing is written
to the live data without an explicit `apply`.

**Code:** `backend/app/pipeline/` — `collector.py` (search), `validate.py` (rules),
`merge.py` (apply). Run via `python -m app.pipeline`.

## How it works

```
collect ──▶ staging file (human review) ──▶ apply ──▶ data.real.json + live DB
  │              │                             │
  web-search    edit / delete entries       re-validates everything again
  (paid, capped) you don't trust
```

1. **collect** — an OpenAI web-search model finds each university's program + tuition with a
   **source URL**. Results (including honest `not_offered` records) land in a staging file.
2. **review** — you inspect / edit / delete entries in the staging file. `apply`
   re-validates regardless, so the review is a safety net, not the only gate.
3. **apply** — merges approved, re-validated entries into `data.real.json` **and** the live
   DB. No reseed — existing accounts and data survive.

## Commands

```bash
# 1. (free) See which universities would be searched — no API calls:
docker compose exec backend python -m app.pipeline collect --field "Medicine" --plan-only

# 2. (paid: ~1 web-search call per university, capped by PIPELINE_MAX_CALLS=40)
docker compose exec backend python -m app.pipeline collect --field "Medicine"
#    Optional filters:  --country EE   --degree master   --limit 5

# 3. Review the staging file (statuses: pending / not_offered / rejected):
#    backend/db/seed/staging/medicine.json

# 4. Merge approved entries into data.real.json + the live DB:
docker compose exec backend python -m app.pipeline apply --file db/seed/staging/medicine.json

# 5. Verify — the field appears immediately (DB-driven picker):
curl http://localhost:8000/meta/options
```

## Safety guarantees

- **Idempotent collect.** Re-running is **free** for universities already covered (an
  existing program, or any staging record — including `not_offered`).
- **Validation** (`validate.py`) rejects:
  - implausible tuition (per-country sanity bands),
  - non-whitelisted currencies,
  - broken / non-HTTP(S) URLs.
- Entries **without a valid source URL** are downgraded to `estimate` confidence — they
  never masquerade as `sourced`.
- The model has an **escape hatch**: if a university genuinely doesn't offer the field, it
  records `not_offered` rather than inventing a program. (Verified in the first real run:
  TalTech honestly recorded as `not_offered`; Tartu's Medicine applied.)
- **No code execution.** Model output is parsed as JSON and validated field-by-field — no
  `eval`/`exec`, no path construction from model output.

## Cost control

- Each `collect` run is capped at `PIPELINE_MAX_CALLS` (default 40) paid web-search calls.
- The search model + timeout reuse the live-scholarship-search settings
  (`OPENAI_SEARCH_MODEL`, `SCHOLARSHIP_SEARCH_TIMEOUT_SECONDS`).

## Adding data by hand (no pipeline)

For a one-off, edit `backend/db/seed/data.real.json` directly (keep the citation contract:
every figure needs a source URL + `sourced`/`estimate` label), then reseed or apply. The
`meta` endpoints are DB-driven, so the picker and chat coverage copy update automatically —
no frontend change needed.
