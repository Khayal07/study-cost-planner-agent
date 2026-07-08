# Architecture

## Big picture

```
┌─────────────┐        ┌──────────────────────────────────────────┐
│  Next.js UI │  HTTP  │            FastAPI backend               │
│ (form/chat) │ ─────▶ │  middleware → routers → services/agents  │
└─────────────┘        │              → PostgreSQL + pgvector      │
                       └──────────────────────────────────────────┘
                                    │            │
                              OpenAI / OpenRouter │  frankfurter.app (FX)
```

Three containers (see `docker-compose.yml`): **db** (Postgres 16 + pgvector),
**backend** (FastAPI/Uvicorn), **frontend** (Next.js). The backend migrates and seeds
on boot, idempotently.

## The design principle

**LLM for language, Python for math.** Deterministic Python owns every number; the LLM
only handles intent extraction, narration, verification summaries, and the optional
writing/vision/voice features. Without any API key the app still works end to end via
deterministic fallbacks.

## The middleware stack

Every request passes through, in order (`backend/app/main.py`):

1. **SecurityHeadersMiddleware** — `nosniff`, `X-Frame-Options: DENY`, strict CSP,
   `Referrer-Policy`, and HSTS in production (`core/security_headers.py`).
2. **CORSMiddleware** — locked to the configured origins; credentials off (bearer tokens,
   not cookies); explicit method/header allowlist.
3. **RateLimitMiddleware** — per-IP token bucket (burst control) **plus** a per-IP daily
   cost cap on paid endpoints (`core/rate_limit.py`). See [Security](SECURITY.md).

## The planning pipeline

The heart of the app. A request (from the form or chat) becomes a typed
`PlanningContext` (`agents/context.py`) that flows through nine agents, coordinated by
`agents/orchestrator.py`. Each agent reads and enriches the shared context.

```
Intake ─▶ Candidate Retrieval ─▶ Tuition ─▶ Living Cost ─▶ Currency
   ─▶ Scenario ─▶ Budget Matching ─▶ Scholarship ─▶ Eligibility
   ─▶ Net Value ─▶ Verifier ─▶ Output (UI JSON / PDF)
```

| # | Agent (`backend/app/agents/`) | Responsibility |
|---|-------------------------------|----------------|
| 1 | `intent.py` | Extract structured intent from natural language (LLM + deterministic fallback). |
| 2 | `tuition.py` | Look up program tuition from the DB, with source citations. |
| 3 | `living_cost.py` | Assemble living-cost items (rent, food, insurance, visa, transport, hidden). |
| 4 | `currency.py` | Normalize every figure to the report currency; flag FX risk. |
| 5 | `scenario.py` | Produce frugal / moderate / comfortable spending scenarios. |
| 6 | `budget_matching.py` | Rank candidates against the budget; compute the gross gap. |
| 7 | `scholarship.py` | Gather awards applicable to each candidate (scope-aware). |
| 8 | `eligibility.py` | Deterministic, explainable verdict: `eligible / likely / unknown / ineligible` + reasons. |
| 9 | `net_value.py` | Apply the best realistic award → `net_total_annual`, `value_rank`. |
| — | `verifier.py` | Cross-check sources, calculations and scholarship claims before output. |

The scholarship layer (`Scholarship → Eligibility → NetValue`) is **non-breaking**: an
unchanged `/plan` call returns the same plan with empty scholarship fields.

## Request lifecycles

**Structured form** — `POST /plan` → `orchestrator.run()` → cited, ranked plan JSON.

**Chat** — `POST /chat` → `services/chat.py` folds a stateless `ChatProfile`, extracts
intent, routes to a *mode* (greeting / discovery / plan / scholarships / value / detail),
then reuses the same pipeline. The profile is round-tripped to the client (stateless
server) and treated as untrusted input (sanitized, validated).

**PDF** — `POST /export/pdf` → re-runs the plan → `services/pdf.py` renders HTML →
WeasyPrint. WeasyPrint's URL fetcher is locked to `data:` URIs (no external fetches;
all images are base64, all CSS inline) — an SSRF guard.

## Retrieval

Candidate retrieval (`data/retrieval.py`, `data/repository.py`) currently uses
**structured SQL lookups** — more accurate for this small, curated dataset. A
`knowledge_chunks` pgvector column exists and is reserved for semantic retrieval as a
future enhancement; `fastembed` (ONNX, local) provides embeddings without a torch dep.

## Currency & FX

`services/currency.py` + `agents/currency.py` convert figures to the report currency
using **frankfurter.app** (ECB data, no key), cached for `FX_CACHE_HOURS`. Currencies the
ECB feed doesn't cover (e.g. AZN) fall back to **open.er-api.com**. Rates are cached in the
`fx_rates` table.

## Determinism & grounding contract

- Every cost figure references a `Source` row (URL + accessed date) and is labelled
  `sourced` or `estimate`.
- The `verifier` agent refuses to emit a plan whose numbers don't reconcile with their
  sources.
- Eligibility verdicts are **never** produced by the LLM — they're pure Python rules over
  the program and the user's optional profile.

## Where to look

| Concern | File(s) |
|---------|---------|
| App wiring / middleware | `backend/app/main.py` |
| Orchestration | `backend/app/agents/orchestrator.py`, `agents/context.py` |
| Chat routing | `backend/app/services/chat.py` |
| Config | `backend/app/core/config.py` |
| LLM client | `backend/app/core/llm_client.py` |
| DB models | `backend/app/data/models.py` |
