# Progress Log

## 2026-06-24 — Replace mock data with real, web-sourced data (in progress)

Goal: replace the placeholder seed with internet-sourced figures, each cost entry
storing its source URL. Scope approved: existing 5 countries first
(Germany, Netherlands, Poland, Hungary, Turkey), web-verified JSON + reproducible loader.

**Infrastructure (done):**
- `data.json` → renamed `db/seed/data.mock.json` (kept as dev/fallback dataset).
- New default dataset `db/seed/data.real.json` (web-sourced), selected by
  `SEED_DATASET` env (`real` default | `mock` fallback); loader falls back to mock
  if `data.real.json` is absent. See `app/data/seed.py`, `app/core/config.py`.
- Loader enhancement (backward compatible): each city living item may carry its **own**
  source (e.g. a semester fee cited to the university, not the city's Numbeo source).
- New CLI `reseed` (reset + migrate + seed) for re-running during the incremental build.
- New reusable verification harness `scripts/verify_seed.py` (DB-wide source/currency/range
  audit + runs the real Verifier Agent per country). Run: `python -m scripts.verify_seed`.
- No app UI / agent logic / chat flow changed. OpenRouter key untouched.

**Coverage so far:**

| Batch | Country | Universities | Status |
|-------|---------|--------------|--------|
| 1 | 🇩🇪 Germany | TUM, Humboldt Berlin, RWTH Aachen | ✅ seeded + verified |
| 2 | 🇳🇱 Netherlands | UvA, TU Delft, TU Eindhoven | ✅ seeded + verified |
| 3 | 🇵🇱 Poland | Univ. of Warsaw, Warsaw Tech (MiNI), AGH Krakow | ✅ seeded + verified |
| 4 | 🇭🇺 Hungary | ELTE, BME, Univ. of Szeged | ✅ seeded + verified |
| 5 | 🇹🇷 Turkey | — | ⏳ pending |

**Reseed workflow note:** the backend image bundles the seed JSON at build time
(`COPY . .`). After editing `data.real.json`, either rebuild the image, or bind-mount
the live file for the reseed run:
`docker compose run --rm -v "${PWD}/db/seed:/code/db/seed" backend python -m app.cli reseed`
(run from the `backend/` dir; WORKDIR in the image is `/code`).

**Batch 4 — Hungary notes:** living costs and insurance in **HUF** (second FX currency,
HUF→EUR conversion verified). Tuition all official and `sourced`: ELTE M.Sc. Computer
Science EUR 6,400/yr (EUR 3,200/sem), BME Computer Science Engineering EUR 7,000/yr
(EUR 3,500/sem), Szeged M.Sc. Computer Science EUR 8,200/yr (EUR 4,100/sem). Residence
permit EUR 110 (OIF, sourced). Verifier: 5/5 pass for all four countries.

**Batch 3 — Poland notes:** first non-EUR country — living costs stored in **PLN**,
which exercises the Currency Agent (PLN→EUR via Frankfurter); `totals_consistency` passes
after conversion. Tuition: Warsaw Tech M.Sc. Data Science EUR 6,540/yr and AGH EUR 3,600/yr
(EUR 1,800/sem) are official (`sourced`); University of Warsaw publishes English-programme
fees only as a non-machine-readable PDF, so its tuition is flagged `estimate` (~EUR 2,800/yr,
with reasoning) rather than guessed silently. Visa EUR 135 (raised June 2024, sourced).
Verifier: 5/5 pass for all three countries.

**Batch 2 — Netherlands notes:** all three are non-EEA institutional master fees,
sourced from official pages — UvA M.Sc. Computer Science EUR 23,490/yr (2025-26, joint
with VU), TU Delft EUR 22,290/yr (2025-26), TU Eindhoven EUR 21,700/yr (2026-27, uniform
master rate). Residence permit EUR 243 (IND, sourced). Living from Numbeo (estimate+URL);
rents shown as student room/shared-flat values with the Numbeo 1-bed figure noted.
Verifier: 5/5 pass per country.

**Batch 1 — Germany notes:** key correction vs mock — TUM now charges non-EU tuition
(EUR 6,000/semester STEM master, from WS2024/25 = EUR 12,000/yr; old data said EUR 0).
Berlin (Humboldt) and NRW (RWTH) remain tuition-free; their real cost is the semester
contribution (EUR 355 / EUR 329 per semester), encoded as city-scoped `hidden_misc` with
the university as source (one university per German city in this dataset). Living costs
from Numbeo (flagged `estimate` with URLs); visa EUR 75 (Federal Foreign Office, sourced);
public student health insurance ~EUR 136/mo (estimate, varies by age). Verifier: 5/5 pass.

---

## 2026-06-24 — Local Postgres access for external tooling (VS Code DB client)

**Status: ✅ Done & verified from host.**

Goal: connect to the Dockerized Postgres directly from a VS Code database client
(SQLTools / PostgreSQL extension), separate from the app.

What changed:
- **Host port remapped to `5433`.** Host port `5432` is already occupied by a native
  PostgreSQL install on this machine (PID confirmed as `postgres`). To avoid connecting
  to the wrong server, `docker-compose.yml` now exposes the container as `5433:5432`.
  Inside the compose network the backend is unchanged (`db:5432`) — the app was not touched.
- Credentials reused from `.env` (not invented); OpenRouter key untouched.
- `db` container recreated; data preserved in the `pgdata` volume.

Verified from the host terminal (native `psql`/`pg_isready`, not from inside the container):
- `pg_isready -h localhost -p 5433` → *accepting connections*.
- Query returned 5 countries / 15 universities / 74 cost_items (our seeded data).
- `server_version` = 16.14 (Docker pgvector:pg16) — confirms the Docker DB, not the
  native PostgreSQL 18 on 5432.

### Connection details for the VS Code DB client
| Field | Value |
|-------|-------|
| Host | `localhost` |
| Port | `5433` |
| Database | `studyplanner` |
| Username | `studyplanner` |
| Password | `studyplanner` |
| SSL | disabled |

> Note: the app/backend keeps using the internal `db:5432` over the compose network;
> only the host-facing port changed. `.env` `DATABASE_URL` is intentionally left as
> `@db:5432` (internal) and must not be pointed at `localhost:5433`.
