<div align="center">

# 🎓 Study Abroad Planning Platform

**An AI-powered, multi-agent system that plans the _whole_ study-abroad decision —
not just "how much does it cost?" but "can I get a scholarship, which university is
cheapest _after_ aid, and what do I apply to first?"**

Every number is **grounded in a cited source**. No invented figures.

![Backend](https://img.shields.io/badge/backend-FastAPI-009688)
![Frontend](https://img.shields.io/badge/frontend-Next.js%2015-black)
![DB](https://img.shields.io/badge/db-PostgreSQL%2016%20%2B%20pgvector-336791)
![Tests](https://img.shields.io/badge/tests-93%20passing-brightgreen)
![License](https://img.shields.io/badge/license-educational-blue)

</div>

---

## Table of contents

- [What it does](#what-it-does)
- [Three ways in](#three-ways-in)
- [Screenshots](#screenshots)
- [Quick start](#quick-start-docker)
- [The design principle](#the-design-principle)
- [Documentation](#-documentation) ← deep dives live in [`docs/`](docs/)
- [Project layout](#project-layout)
- [Tech stack](#tech-stack)
- [Testing](#testing)
- [License](#license)

---

## What it does

| Capability | What you get |
|------------|--------------|
| 💰 **Total real cost** | Tuition **plus** living, insurance, visa, transport and hidden costs — not just the headline fee. |
| 🎓 **Scholarship discovery + eligibility** | Real, cited awards matched to your profile, with an explainable `eligible / likely / unknown / ineligible` verdict. Optional **live web search** for fresh awards. |
| 📊 **Net cost & value ranking** | Re-orders universities by cost **after** the best award you may qualify for. |
| 🗂️ **Application planner & tracker** | A prioritized, deadline-aware action plan, plus a personal tracker (accounts) with per-document checklists. |
| 📈 **Visual insights** | Cost radar, cash-flow Sankey, inflation forecast, shareable summary cards. |
| ✍️ **AI writing & practice** | Motivation-letter drafting, interview practice mode. |
| 🖼️ **Smart intake** | Transcript auto-fill from a photo/PDF (vision), voice input (Whisper). |
| 📄 **PDF report** | A downloadable, cited report — optionally focused on a single university. |

Every cost figure traces to a `Source` URL and is labelled `sourced` or `estimate`.

## Three ways in

1. **Structured budget form** — budget, country/field, lifestyle, and optional eligibility
   (nationality / GPA / language test).
2. **Chat** — natural language: _"I want to study CS in Germany, my budget is €8000/year"_,
   _"show me the best value after scholarships"_, _"scholarships at TUM"_.
3. **Accounts** — sign in to save scholarships and track deadlines & documents.

The form and chat run the **same grounded agent pipeline** and produce the same cited results.

## Screenshots

Sample renders live in the repo root and phase captures: `plan-results.png`,
`phase1-radar.png`, `phase1-sankey-cashflow.png`, `phase2-forecast.png`,
`phase2-sharecard.png`, `phase3-interview.png`.

## Quick start (Docker)

```bash
cp .env.example .env
# edit .env → set OPENAI_API_KEY (preferred) or a free OPENROUTER_API_KEY
docker compose up --build
```

- **Frontend:** http://localhost:3000
- **Backend API + interactive docs:** http://localhost:8000/docs
- The backend runs migrations and seeds curated, cited data (incl. scholarships) on boot — idempotent.
- **The LLM is optional.** Without any key the system still works end-to-end (deterministic
  fallbacks); a key makes chat and summaries more fluent and unlocks the AI-only features.

> **Production checklist:** set `ENVIRONMENT=production`, a strong `JWT_SECRET`, a strong
> `POSTGRES_PASSWORD`, and `TRUST_PROXY_HEADER=true` if behind a reverse proxy. See
> [`docs/SECURITY.md`](docs/SECURITY.md) and [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md).

## The design principle

> **LLM for language, Python for math.**
> All cost / currency / budget / eligibility calculations are **deterministic Python**.
> The LLM only handles intent extraction, scenario narration, verification summaries and
> the optional writing features. This keeps every number reproducible and auditable.

```
Form / Chat → Intake → Candidate Retrieval (SQL + pgvector)
   → Tuition + Living Cost (DB, cited)
   → Currency (normalize + FX risk)
   → Scenario (frugal / moderate / comfortable)
   → Budget Matching (rank, gross gap)
   → Scholarship (gather applicable awards)
   → Eligibility (deterministic, explainable verdict)
   → Net Value (best award → net cost, value rank)
   → Verifier (source + calculation + scholarship checks)
   → Output (UI JSON + PDF)
```

Nine agents coordinate through a deterministic orchestrator over a typed shared
`PlanningContext`. Full walkthrough in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## 📚 Documentation

Everything is documented. The deep dives live in [`docs/`](docs/):

| Doc | What's inside |
|-----|---------------|
| [**Architecture**](docs/ARCHITECTURE.md) | The nine agents, the orchestrator, the request lifecycle, retrieval, the currency/FX layer. |
| [**Features**](docs/FEATURES.md) | Every feature end to end — cost engine, scholarships, forecast, charts, letters, interview, transcript vision, voice, PDF, share cards. |
| [**API reference**](docs/API.md) | All 25 endpoints: method, auth, request/response shape, examples. |
| [**Data model**](docs/DATA_MODEL.md) | The 14 tables, relationships, the citation contract, seed datasets. |
| [**AI data pipeline**](docs/DATA_PIPELINE.md) | `collect → staging → apply` for adding new fields of study with human review. |
| [**Configuration**](docs/CONFIGURATION.md) | Every environment variable, defaults, and what each one changes. |
| [**Security**](docs/SECURITY.md) | Threat model, the two hardening passes, the cost guard, and the production checklist. |
| [**Development**](docs/DEVELOPMENT.md) | Local + Docker workflows, the baked-image gotcha, running tests, adding data. |

## Project layout

```
study-cost-plannerr/
├── backend/                    FastAPI service (Python 3.11)
│   └── app/
│       ├── api/                14 routers — the HTTP surface
│       ├── agents/             9 planning agents + orchestrator + shared context
│       ├── services/           chat, planner, forecast, letters, interview, pdf, ...
│       ├── core/               config, security, rate-limit, headers, llm client, schemas
│       ├── data/               ORM models, db session, repository, retrieval, seed
│       ├── pipeline/           AI data-collection pipeline (collect/validate/merge)
│       └── tests/              12 test modules (93 tests)
├── frontend/                   Next.js 15 App Router (React 19 + TS + Tailwind)
│   └── src/
│       ├── app/                layout, home page, shared-plan page p/[id]
│       ├── components/         27 UI components (forms, charts, panels, modals)
│       └── lib/                api client, auth context, i18n, theme, ics export
├── docs/                       ← full documentation set
├── docker-compose.yml          db + backend + frontend
└── .env.example                configuration template
```

## Tech stack

| Layer | Choice |
|-------|--------|
| Frontend | Next.js 15 (App Router) · React 19 · TypeScript · Tailwind · Recharts · Framer Motion |
| Backend | FastAPI · Pydantic v2 · Uvicorn |
| Database | PostgreSQL 16 · pgvector |
| Auth | JWT (PyJWT) · bcrypt password hashing |
| LLM | OpenAI (preferred) or OpenRouter (OpenAI-compatible, free models) |
| Embeddings | fastembed (ONNX, local — no torch) |
| Currency | frankfurter.app (ECB) + er-api fallback, cached |
| PDF & charts | WeasyPrint · Matplotlib |
| Runtime | Docker Compose |

## Testing

```bash
# Full suite (93 tests) — runs in the backend container:
docker compose exec backend python -m pytest app/tests -q
```

Covers deterministic cost math, intent extraction, auth gates, rate limiting + the
per-IP daily cost cap, upload validation, the scholarship/eligibility logic, forecast,
letters/interview, and the data pipeline. More in [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).

## License

Course project (AI Engineering capstone) — for educational use.

---

<div align="center">
<sub>Built with the principle that a number you can't trace is a number you can't trust.</sub>
</div>
