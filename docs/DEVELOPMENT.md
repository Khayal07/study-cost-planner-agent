# Development

## Run it (Docker — recommended)

```bash
cp .env.example .env      # set OPENAI_API_KEY or OPENROUTER_API_KEY (optional)
docker compose up --build
```

- Frontend: <http://localhost:3000>
- Backend + Swagger: <http://localhost:8000/docs>
- The backend migrates + seeds on boot (idempotent).

Three services (`docker-compose.yml`): `db` (Postgres 16 + pgvector), `backend`
(FastAPI/Uvicorn), `frontend` (Next.js).

## ⚠️ The baked-image gotcha

**Backend code is baked into the image — there is no bind mount.** After editing backend
files you **must rebuild** for the container to pick them up:

```bash
docker compose build backend && docker compose up -d backend
```

Running tests or hitting the API against a stale container is the #1 source of "my change
didn't work" confusion. Rebuild first.

## Run it (local, without Docker)

**Backend** — needs a local Postgres with the `vector` extension:

```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# point DATABASE_URL at your Postgres, then:
python -m app.cli migrate && python -m app.cli seed
uvicorn app.main:app --reload
```

> Note: `pgvector`, `weasyprint` and `matplotlib` need system libraries; if a local venv is
> awkward on your OS, just use Docker — that's how tests are run here.

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

## Tests

The full suite runs in the backend container:

```bash
docker compose exec backend python -m pytest app/tests -q
# a single module:
docker compose exec backend python -m pytest app/tests/test_rate_limit.py -q
```

**93 tests** across 12 modules:

| Module | Covers |
|--------|--------|
| `test_calculations.py` | Deterministic cost/currency/budget math |
| `test_intent.py` | Intent extraction + deterministic fallback |
| `test_advisor.py` | Chat routing / grounded answers |
| `test_scholarships.py` | Scholarship gathering + eligibility verdicts |
| `test_forecast.py` | Inflation projection |
| `test_letters_interview.py` | Motivation letters + interview mode |
| `test_applications.py` | Auth primitives, JWT, planner logic |
| `test_api_routes.py` | Route contracts + auth gates (401/409) |
| `test_rate_limit.py` | Token bucket + per-IP daily cost cap |
| `test_uploads.py` | Upload size/type/magic-byte validation |
| `test_pipeline.py` | Data pipeline collect/validate/merge |

> One test is flaky when the Numbeo/live-data path 429s — it depends on an external rate
> limit, not on our code.

## Common tasks

**Add a new field of study** → see [DATA_PIPELINE.md](DATA_PIPELINE.md).

**Add data by hand** → edit `backend/db/seed/data.real.json` (keep the citation contract),
then reseed. The `meta` endpoints are DB-driven, so the UI picker updates automatically.

**Change the seed dataset** → `SEED_DATASET=mock` for the demo dataset.

**Reseed from scratch** (⚠️ drops seeded data):

```bash
docker compose exec backend python -m app.cli seed
```

## Project layout

See the [root README](../README.md#project-layout). Backend entrypoints:

| Concern | File |
|---------|------|
| App + middleware wiring | `backend/app/main.py` |
| Config (all env vars) | `backend/app/core/config.py` |
| Orchestrator | `backend/app/agents/orchestrator.py` |
| Chat routing | `backend/app/services/chat.py` |
| ORM models | `backend/app/data/models.py` |
| CLI (migrate/seed) | `backend/app/cli.py` |

## Coding conventions

- **Deterministic Python for every number**; the LLM only touches language. Keep it that way.
- **Every cost/award figure cites a `Source`.** Don't add a figure without a URL (or an
  explicit `estimate` label).
- New user text that reaches an LLM prompt must go through
  `core/text.py::sanitize_prompt_field()`.
- Add a test alongside any behavioural change; run the suite in Docker before you commit.
