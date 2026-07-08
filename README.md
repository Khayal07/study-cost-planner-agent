# Study Abroad Planning Platform

An AI-powered, multi-agent platform that helps students plan the **whole** study-abroad
decision — not just *"how much does it cost?"* but *"can I get a scholarship, which university
is cheapest **after** aid, and what do I apply to first?"*

It combines, in one grounded system:

- **Total real cost** — tuition **plus** living, insurance, visa, transport and hidden costs.
- **Scholarship discovery + eligibility** — real, cited awards matched to your profile, with an
  explainable eligible / likely / unknown / ineligible verdict.
- **Net cost & value ranking** — re-orders universities by cost **after** the best award you
  may qualify for.
- **Application planner & tracker** — a prioritized, deadline-aware action plan, plus a
  personal tracker (accounts) with per-document checklists.

Every figure is **grounded in a cited source** (no invented numbers).

Three ways in:
1. **Structured budget form** — budget, country/field, lifestyle, and optional eligibility
   (nationality / GPA / language test).
2. **Chat** — natural language ("I want to study CS in Germany, my budget is €8000/year";
   "show me the best value after scholarships"; "scholarships at TUM").
3. **Applications** — sign in to save scholarships and track deadlines & documents.

Form and chat run the **same grounded agent pipeline** and produce the same cited results.

> AI Engineering course capstone. Design principle: **LLM for language, Python for math.**
> All cost/currency/budget calculations are deterministic Python; the LLM only handles
> intent extraction, scenario narration and verification summaries.

## Architecture

```
Form / Chat → Intake → Candidate Retrieval (SQL + pgvector)
   → Tuition + Living Cost (DB, cited)
   → Currency (normalize + FX risk)
   → Scenario (frugal / moderate / comfortable)
   → Budget Matching (rank, compute gross gap)
   → Scholarship (gather applicable awards)
   → Eligibility (deterministic, explainable verdict + reasons)
   → Net Value (apply best award → net cost, value rank)
   → Verifier (source + calculation + scholarship checks)
   → Output (UI JSON + PDF)
```

Nine agents coordinate through a deterministic orchestrator over a typed shared
`PlanningContext`. The scholarship layer (`Scholarship` → `Eligibility` → `NetValue`) is fully
non-breaking: an unchanged `/plan` call returns the same plan with empty scholarship fields.
A separate **application planner** turns the eligible awards into a deadline-then-value
prioritized action plan. See `app/agents/`, `app/services/application_planner.py`, and the
plans in `.claude/plans/`.

## Tech stack

| Layer | Choice |
|-------|--------|
| Frontend | Next.js (App Router) + TypeScript + Tailwind + Recharts |
| Backend | FastAPI + Pydantic v2 |
| Database | PostgreSQL 16 + pgvector |
| Auth | JWT (PyJWT) + bcrypt password hashing |
| LLM | OpenRouter (OpenAI-compatible), free models |
| Embeddings | fastembed (ONNX, local) |
| Currency | frankfurter.app (ECB), cached |
| PDF | WeasyPrint + Matplotlib |

## Quick start (Docker)

```bash
cp .env.example .env
# edit .env → set OPENROUTER_API_KEY (free key from https://openrouter.ai/keys)
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API + docs: http://localhost:8000/docs
- The backend runs migrations and seeds curated data (incl. scholarships) on boot (idempotent).
- For production, set `JWT_SECRET` in `.env` (the default is for local dev only).

## Local development (without Docker)

Backend:
```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# point DATABASE_URL at a local Postgres with the vector extension, then:
python -m app.cli migrate && python -m app.cli seed
uvicorn app.main:app --reload
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

## Run the tests

Deterministic-math and intent unit tests (no DB/network needed):

```bash
docker compose exec backend python -m pytest app/tests -q
```

## Data pipeline (AI-assisted field coverage)

Adds a **new field of study** (e.g. Medicine) across the universities already in the
dataset: an OpenAI web-search model finds each university's program + tuition with a
source URL, results land in a **staging file for human review**, and only an explicit
`apply` merges them into `data.real.json` + the live DB. Nothing is written without
review; every figure keeps a source URL + accessed date.

```bash
# 1. (free) See which universities would be searched — no API calls:
docker compose exec backend python -m app.pipeline collect --field "Medicine" --plan-only

# 2. (paid: ~1 web-search call per university, capped by PIPELINE_MAX_CALLS=40)
docker compose exec backend python -m app.pipeline collect --field "Medicine"
#    Optional filters: --country EE   --degree master   --limit 5

# 3. Review the staging file (statuses: pending / not_offered / rejected):
#    backend/db/seed/staging/medicine.json
#    Edit or delete entries you don't trust — apply re-validates everything anyway.

# 4. Merge approved entries into data.real.json + the live DB (no reseed, accounts survive):
docker compose exec backend python -m app.pipeline apply --file db/seed/staging/medicine.json

# 5. Check: the field appears immediately (DB-driven picker):
curl http://localhost:8000/meta/options
```

Re-running `collect` is free for universities already covered (existing program,
or any staging record — including `not_offered`). Validation rejects implausible
tuition (per-country bands), non-whitelisted currencies and broken URLs; entries
without a valid source URL are downgraded to `estimate` confidence.

## API endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/health` | — | Liveness + whether the LLM is configured |
| POST | `/plan` | — | Structured budget form → ranked, cited plan (incl. scholarships + net cost) |
| POST | `/chat` | — | Natural-language → grounded answer, discovery, scholarships or value ranking |
| POST | `/export/pdf` | — | Re-run the plan and download a PDF report (incl. scholarship section) |
| POST | `/applications/plan` | — | Prioritized scholarship action plan (deadline → value) + "this week" |
| POST | `/auth/register` · `/auth/login` | — | Create account / sign in → JWT |
| GET / PUT | `/auth/me` · `/auth/me/profile` | ✔ | Current user / save eligibility profile |
| GET / POST | `/applications` | ✔ | List / create tracked applications |
| PATCH / DELETE | `/applications/{id}` | ✔ | Update status/notes · remove |
| PATCH | `/applications/{id}/documents/{doc_id}` | ✔ | Tick a document on/off |

Authenticated routes take a `Authorization: Bearer <token>` header. Interactive docs at
http://localhost:8000/docs.

## Scholarship ecosystem & accounts

- **Real, cited scholarships** are seeded alongside the cost data (DAAD, Erasmus Mundus,
  Deutschlandstipendium, Holland Scholarship, TU Delft van Effen, NAWA Banach, Stipendium
  Hungaricum, Türkiye Bursları), each with a `Source` URL — same citation contract as every cost
  figure. Scopes are polymorphic: `global` / `country` / `university` / `program`.
- **Explainable eligibility.** A deterministic agent scores each award against the candidate
  program (degree, field) and your optional profile (nationality, GPA, language), returning
  `eligible` / `likely` / `unknown` / `ineligible` plus a human-readable reason list. The LLM is
  never used for the verdict.
- **Net cost & value ranking.** The best realistic award is applied to compute `net_total_annual`
  and a `value_rank`; the UI offers a **Cost ↔ Value-after-aid** toggle while preserving the gross
  ranking.
- **Application planner & tracker.** `/applications/plan` returns a deadline-then-value priority
  list with a "this week" action list and the union of required documents. Signed-in users save
  awards from any university, then track status and tick off documents — persisted to their
  account (DB), surviving reloads.

## Roadmap (status)

- [x] **0. Scaffold** — docker-compose, FastAPI + Next skeleton, `/health`.
- [x] **1. Data layer** — schema, pgvector, curated seed (5 countries) with source URLs.
- [x] **2. Core agents + orchestrator** — tuition, living, currency; form path.
- [x] **3. Scenario + budget matching + verifier**.
- [x] **4. Chat** — intent extraction (LLM + fallback) + grounded answers.
- [x] **5. Outputs** — comparison charts + PDF export.
- [x] **6. Polish** — unit tests, docs, Docker.
- [x] **E. Scholarship foundation** — data model + `Scholarship`/`Eligibility`/`NetValue` agents.
- [x] **F. Chat & PDF** — scholarship/value chat modes; net-cost section in the PDF.
- [x] **G. Frontend** — scholarship panel, net-cost badges, Cost/Value toggle, eligibility inputs.
- [x] **H. Accounts** — JWT auth, application planner, and the persistent application tracker.

### Notes & known simplifications
- **LLM is optional.** Without `OPENROUTER_API_KEY` the system still works end-to-end:
  intent extraction falls back to a deterministic parser, and narratives/summaries use
  templates. A key makes chat answers and summaries more fluent.
- **Grounded retrieval** for chat currently uses **structured SQL lookups** (more accurate
  for this small, structured dataset). The `knowledge_chunks` pgvector column is in place
  and reserved for semantic retrieval as a future enhancement.
- **Seed data** is curated and approximate; each figure cites a source URL and is labelled
  `sourced` or `estimate`. Verify at the source before relying on a number.

## License

Course project — for educational use.
