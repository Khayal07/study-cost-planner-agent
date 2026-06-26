# Progress Log

## 2026-06-27 — Phase E: Scholarship ecosystem foundation (backend)

Evolves the planner from a cost calculator into a value planner. New grounded scholarship
layer, fully non-breaking (all new request/response fields optional with safe defaults).

**Data:** new `Scholarship` model (`app/data/models.py`) — cited like every figure (one
`Source` each), polymorphic scope reusing `scope_level`/`scope_id` (+`"global"`),
`COVERAGE_TYPES` vocab, index `ix_scholarships_scope` (added in `cli.py`). 8 real cited
scholarships seeded (`db/seed/data.real.json`; 4 in mock): Erasmus Mundus, DAAD,
Deutschlandstipendium, Holland Scholarship, TU Delft van Effen, NAWA Banach, Stipendium
Hungaricum, Türkiye Bursları. Loader extended in `seed.py`; repo helper
`scholarships_for_candidate`.

**Agents** (new DAG steps after BudgetMatching, before Verifier):
`ScholarshipAgent` (gather) → `EligibilityAgent` (deterministic, explainable verdict
eligible/likely/unknown/ineligible + reason list; degree/field matched on the program,
nationality/GPA/language from the optional profile) → `NetValueAgent` (per-award annual
saving in report currency, applies the single best realistic award, derives
`net_total_annual` / `net_budget_gap` / `value_rank` = cheapest-after-aid; gross `rank`
preserved). `VerifierAgent` gained a `scholarships` check (award citation integrity, net ≤
gross, passed-deadline warning).

**Schemas:** `ScholarshipMatch`; `CandidatePlan` net fields; optional
`nationality`/`gpa`/`language_test` on `PlanningRequest` + `ChatProfile`.

Verified: `pytest` 27/27 (10 new). Parity intact — Poland·€15k·CS still AGH ~14,960 /
Warsaw ~15,504 / WUT ~19,244 gross, now with populated `scholarships` and net ≤ gross. Blank
profile → likely/unknown (no crash); minimal `{"budget_amount":12000}` still valid. `tsc`
clean (frontend untouched this phase). Deferred to later phases: chat/PDF surfacing,
frontend panel + value toggle, and the application planner + document tracker (DB + accounts).

## 2026-06-26 — Fix: PDF now reports ONLY the selected university

Bug: selecting a university (budget form card or chat) still exported the **full
comparison** of all options, merely "featuring" the chosen one. User wanted a report for
**that university only**.

Fix — centralised in the backend export endpoint (`app/api/export.py`): when
`focus_program_id` is set, the request is restricted to `program_ids=[focus]`,
`max_results=1`, so the plan is built for a single university. Both callers (budget form
`PlanResults` and chat `profileToPlanRequest`) already pass `focus_program_id`, so both are
fixed in one place. The PDF (`app/services/pdf.py`) now renders a **single-university
layout** when there's one candidate — title "Study Cost Report", university in the
subheader, no option-comparison chart/table, just the breakdown chart. The download
filename is per-university (`study-cost-<slug>.pdf`), read from `Content-Disposition` by the
client (`lib/api.ts`).

Verified: `pytest` 17/17; live `/export/pdf` with `focus_program_id` 9/7/8 returns three
distinct valid PDFs named `agh-university-of-krakow` / `university-of-warsaw` /
`warsaw-university-of-technology`; orchestrator with the forced request yields exactly one
candidate (the selected school). `tsc` clean; backend + frontend images rebuilt, all
containers healthy.

---

## 2026-06-26 — Fix: chat resolved the wrong university when named in full

Bug: with a prior Turkey discovery, "Tell me about **Istanbul** Technical University"
returned **Middle East** Technical University. Two causes, both fixed in
`app/services/chat.py`:

1. **Full names weren't matched.** `_resolve_university_program` only knew abbreviations/
   city aliases (ITU, METU, Berlin…), not the real university names — so the full name
   fell through. Added `_resolve_named_university`: a university matches when **all** its
   significant name tokens appear in the message ({istanbul, technical} → ITU), with the
   most-specific match winning. This also correctly disambiguates the two Warsaw
   universities ("University of Warsaw" vs "Warsaw University of Technology").
2. **"it" matched inside "univers-it-y".** `_resolve_ordinal_program` used a substring
   check, so "it" (and "best"/"last") triggered a false back-reference to the first option
   (the cheapest — METU). Pronoun/superlative back-references are now word-bounded; the
   distinctive ordinals ("second", "#2", "option 2") still match.

Verified: `pytest` 17/17 (incl. a regression test that naming a university isn't read as
"it"); a live two-turn run resolves Istanbul Technical → ITU, Middle East Technical → METU,
"the second one" → rank 2, and both Warsaw universities correctly.

---

## 2026-06-26 — Fixes: any-currency reports, selected-university export, chat history

Three user-reported issues, all fixed and verified end-to-end (pytest 16/16, live API +
Playwright in the running stack).

**1 — Report in any currency (e.g. AZN).** Picking AZN as the report/budget currency
returned **HTTP 500**: frankfurter (ECB) has no AZN rate. Added a free, no-key fallback
provider (`open.er-api.com`) in `CurrencyService`, used **only** when frankfurter can't
resolve a pair — so every existing ECB conversion is byte-for-byte unchanged (parity), and
AZN (and other non-ECB currencies) now work. `config.py` gains `fallback_fx_base_url`.
Verified: `/plan` with `report_currency=AZN` → 200, full plan + breakdown + scenarios all
in AZN; EUR plan totals unchanged.

**2 — Export the *selected* university, not the first.** The form's "Export PDF" always
featured the top-ranked option regardless of which card was selected. Added
`focus_program_id` to `PlanningRequest`; the PDF now features that university (detailed
breakdown, breakdown chart, and a "Focused on …" tag), falling back to rank 1 when unset.
`PlanResults` passes the selected card's `program_id` and shows "PDF features <university>"
in the header. Verified: selecting a different card changes the featured university and the
exported PDF bytes.

**3 — Chat history, New chat, and smarter per-university reports.** The chat had no history
or way to start over. `ChatPanel` now keeps a **conversation rail** with a **New chat**
button, multiple saved conversations (titled from the first message), switch + delete, all
persisted in `localStorage` (`scp-chats-v1`) so they survive reloads. The advisor now sets
`focus_program_id` whenever a university is referenced (by name or "the second one"), so
"generate a report for METU" produces a report **for METU** — `_pdf_offer` names the
university, and the chat Download button passes the focus through `profileToPlanRequest`.
Verified: New chat / switch / delete / reload persistence, and the report wording + focus
target the discussed university.

No business logic, routes, schema meaning, or existing flows changed beyond these fixes;
the deterministic pipeline and citation contract are untouched.

---

## 2026-06-25 — Hardening audit, Phase D: container/runtime hardening

**Status: ✅ Done & verified (all 3 containers healthy, non-root, parity + PDF).**

Phase D of the audit (High H4), the final phase of the agreed Critical+High scope. Runtime
wrapper only — identical app behaviour and ports.

- **Non-root containers** (`backend/Dockerfile`, `frontend/Dockerfile`): backend runs as a new
  `appuser` (uid 1000); frontend runs as the base image's `node` user (uid 1000), with the
  build artifacts `chown`ed. `MPLCONFIGDIR=/tmp/matplotlib` lets WeasyPrint/Matplotlib write
  their font cache without a root-owned home.
- **Healthchecks** (Dockerfiles + `docker-compose.yml`): interpreter-based probes (python for
  backend `/health`, node for frontend `/`) — no need to install `curl` into the slim images.
- **Resilience** (`docker-compose.yml`): `restart: unless-stopped` on db/backend/frontend;
  backend/frontend healthchecks with generous `start_period`; uvicorn now runs `--workers 2`.

**Verified:** `docker compose up --build` → **db / backend / frontend all healthy**;
`id -u` = 1000 in both app containers; reference query (Poland · €15,000 · CS) returns the
**same** totals (AGH 14,958 / Warsaw 15,501 / WUT 19,241); `/chat` discovery works; and
`/export/pdf` returns HTTP 200 with a valid 17 KB `%PDF` — confirming PDF generation works under
the non-root user.

This completes the audit's confirmed scope (Critical + High; Phases A–D). Deferred by agreement:
frontend a11y/UX polish, CI, Alembic, rate limiting, image-digest pinning, frontend multistage.

---

## 2026-06-25 — Hardening audit, Phase C: logging + currency resilience

**Status: ✅ Done & verified (16 tests + currency smoke + parity).**

Phase C of the audit (High H3 + Medium M2). Observability and resilience only — no behaviour
change on the happy path.

- **H3 — Logging** (`backend/app/core/llm_client.py`, `services/currency.py`): added module
  loggers. The previously-silent `except Exception: continue` in the LLM client now logs a
  warning per failed model before falling back; the currency fallback logs a warning when it
  serves a stale rate. Same outcomes, now visible in logs.
- **M2 — Currency resilience** (`services/currency.py`): the live frankfurter fetch now retries
  once on transient failure and calls `session.rollback()` on error so a half-applied insert
  can't poison the request session. The broad fallback `except` is **kept on purpose** — a
  parse error should still fall back to the cached rate rather than crash a plan.

**Verified:** `pytest` 16/16; a direct currency smoke shows PLN→EUR converts correctly and the
per-instance memo holds a single `('PLN','EUR')` key after two conversions; reference query
(Poland · €15,000 · CS) returns the **same** totals (AGH 14,958 / Warsaw 15,501 / WUT 19,241).
Backend image rebuilt.

---

## 2026-06-25 — Hardening audit, Phase B: DB indexes + FX memoization

**Status: ✅ Done & verified (16 tests + indexes confirmed on live DB + parity).**

Phase B of the audit (High-tier performance). Read-path only — identical results, fewer
queries / faster plans. No business logic or schema-meaning change.

- **H1 — Indexes** (`backend/app/data/models.py`, `cli.py`): composite indexes
  `ix_cost_items_scope (scope_level, scope_id, cost_type)` and
  `ix_fx_rates_lookup (base, quote, as_of_date)` declared via `__table_args__`. Because
  `create_all()` skips already-existing tables, `migrate()` now also runs idempotent
  `CREATE INDEX IF NOT EXISTS` (matching names) so the **existing `pgdata` volume** gets them
  on the next boot — confirmed both indexes now exist in the running DB.
- **H2 — FX memoization** (`backend/app/services/currency.py`): `CurrencyService` gained a
  per-instance `(base, quote) → Conversion` memo wrapping `get_rate`. The Currency Agent
  converts every cost line per candidate (e.g. a Poland plan = ~15 PLN→EUR conversions all
  hitting the same cached rate); the same pair is now resolved once per request instead of
  re-querying `fx_rates` each line. Identical numbers, fewer SELECTs.

**Verified:** `pytest` 16/16; `migrate` log shows "perf indexes ensured"; `pg_indexes` lists
both indexes; reference query (Poland · €15,000 · CS) returns the **same** totals (AGH 14,958 /
Warsaw 15,501 / WUT 19,241). Backend image rebuilt.

---

## 2026-06-25 — Hardening audit, Phase A: CORS lockdown + input validation

**Status: ✅ Done & verified (16 tests + live parity/validation/CORS checks).**

Part of a senior-level audit (full report in the plan file). Scope confirmed with the user:
local/demo deployment, implement Critical + High only, all changes parity-safe. This is
**Phase A** (the two Critical items); business logic, routes, schema meaning and user flows
are unchanged.

- **C1 — CORS** (`backend/app/main.py`, `core/config.py`): replaced `allow_origins=["*"]` +
  `allow_credentials=True` (an unsafe combo) with an env-driven allowlist
  (`cors_allow_origins`, default `http://localhost:3000`), `allow_credentials=False` (the app
  uses no cookies/auth), and methods limited to `GET, POST`. Verified: requests from
  `localhost:3000` get the ACAO header; `evil.com` does not.
- **C2 — Input validation** (`backend/app/core/schemas.py`): added Pydantic `Field` bounds —
  `ChatRequest.message` (1–4000 chars), `PlanningRequest.budget_amount` (`>0`, `≤1e9`),
  `max_results` (1–20), `country/field/currency` lengths, `program_ids` (≤50), and the
  round-tripped `ChatProfile` (`last_candidates ≤20`, bounded fields). Bounds sit far above
  any real value, so legit requests are unaffected; abuse now returns a clean 422.
  - Deliberate detail: `budget_amount` `le` is `1e9` so the chat's internal "no budget yet"
    discovery sentinel (1e9) still validates — verified the no-budget country path still works.

**Verified:** `pytest` 16/16; reference query (Poland · €15,000 · CS) returns the **same**
ranked options/totals as before (AGH 14,958 / Warsaw 15,501 / WUT 19,241); oversized
`max_results`, negative budget, and a 5,000-char message all return 422; no-budget discovery
and CORS origin rules behave correctly. Backend image rebuilt.

---

## 2026-06-25 — Chat → intelligent Study Abroad Advisor (backend brain)

**Status: ✅ Backend done & verified (16 unit tests + live multi-turn HTTP test).**

Why: the old chat was stateless and lazy — it either dumped a full plan or returned a
single canned clarify line, and forgot everything between turns. Rebuilt it into a
friendly, *stateful* consultant that still obeys the project rule "LLM for language,
Python for math" (every number stays grounded + cited; nothing invented).

**Diagnosis (root causes in the old code):**
- `ChatRequest`/`postChat` carried only the current message → zero memory.
- `handle_chat` was a rigid 3-way branch (full plan / keyword lookup / one-line clarify)
  with no progressive questioning and a dead-end clarify string.
- No university-detail, compare, affordability, or PDF intents; no way to reference a
  result ("the second one"); intent extraction was CS-only, no degree level.

**What changed (backend only this step):**
- **Session memory without server state:** new `ChatProfile` (budget, country, field,
  degree, lifestyle, last results, focus university) is returned with every answer and
  sent back by the client next turn — the system "remembers" while staying stateless.
  `schemas.py`: `ChatProfile`, `ChatCandidateRef`, `ChatSuggestion`; `ChatResponse` now
  carries `profile`, `suggestions`, `candidates`, `detail`, `can_export`.
- **Advisor state machine** (`services/chat.py`, full rewrite): merges newly-mentioned
  slots into memory → classifies intent → responds warmly and *always ends with a
  next-step question* + one-tap suggestion chips. Modes: `greeting`, `clarify`
  (progressive follow-ups), `discovery` (ranked list with a 0–100 budget-fit **match
  score** + affordability), `detail` (single university, full grounded breakdown +
  scenarios), `compare` (side-by-side top 3), `affordability` ("can I afford X with €Y"),
  `answer` (narrow cost lookup like "visa in Germany"). Reuses the existing deterministic
  `Orchestrator` pipeline + citations untouched.
- **Reference resolution:** university names/aliases (TUM, RWTH, METU, UvA, AGH, ELTE…)
  and unambiguous cities (Berlin→Humboldt, Krakow→AGH…) → a program; ordinals ("the
  second one", "the cheapest") → the right option from the remembered list.
- **Honest no-fabrication fallback:** a named school we don't cover (Harvard, Oxford,
  University of Toronto) gets an explicit "I don't have grounded data for X" answer that
  redirects to the 5 covered countries — never invented numbers. Detail responses state
  plainly that scholarships/admission/English/ranking data aren't in the dataset.
- **Intent extraction** (`agents/intent.py`): added degree-level detection and `15k`
  budgets; new reusable `extract_slots`; `extract_intent` kept backward-compatible.
- **Retrieval:** optional `program_ids` filter on `PlanningRequest` for single-university
  detail/compare (backward compatible).
- **Reliability:** the OpenRouter client now has a 12s timeout + no SDK retries, so a slow
  free model degrades to the deterministic path instead of blocking a chat turn.

**Verified:** `pytest` 16/16 pass; live multi-turn HTTP run (greeting → budget → country
→ discovery → detail → compare → PDF) confirms memory round-trips across requests and
every figure carries a citation. Backend image rebuilt; `/chat` healthy on :8000.

**Next:** redesign `ChatPanel` (frontend) to round-trip the profile and render the ranked
cards, detail, comparison, suggestion chips and PDF download.

### Frontend — advisor UX (✅ done & verified live)

Extended the existing "Verified Ledger" design language into chat rather than inventing a
new one (teal = sourced / amber = estimate stays the brand; mono ledger figures; `.card`
/`.chip`/`.btn-primary`). `ChatPanel` now:
- **Round-trips the `ChatProfile`** with every turn → the UI remembers the whole
  conversation (verified: "study in Poland, budget €15,000" in one message ranked 3
  options; later "Explore"/"compare"/"Can I afford METU" all reused the remembered budget).
- Renders **ranked discovery cards** (rank, university, city/country, total, a budget-fit
  **match meter**, an affordability badge on the confidence axis, tuition + living, and an
  **Explore** action) — joined from `candidates` + the per-option `match_score` in the
  profile. Prose stays warm and lean; the cards carry the data (no duplicated text lists).
- **University detail / affordability**: the warm answer plus an **annual source ledger**
  — every cost line with a clickable `CitationChip` (sourced/estimate).
- **Compare** reuses the card grid; **narrow lookups** render cited figures.
- **One-tap suggestion chips** drive follow-ups; a **Download report** button exports the
  PDF straight from the conversation (`profileToPlanRequest` → existing `/export/pdf`).
  Redundant chips (per-option "Explore", "report" when the Download button shows) are
  filtered out.

**Verified:** `tsc` + `next build` clean; Docker images rebuilt; Playwright drove the live
app — discovery → Explore → detail (cited ledger) → compare → affordability, in **dark
mode** and at **390px mobile** (cards stack, names truncate, no overflow). `/chat` and
`/export/pdf` both returned 200; the PDF downloaded from chat.

---

## 2026-06-24 — Frontend redesign: premium "Verified Ledger" UI + dark mode

**Status: ✅ Done & verified (build + Playwright in light/dark/mobile).**

Transformed the plain blue/white UI into a modern, production-grade SaaS interface.
Scope was UI only — no backend, agent, chat, or data logic changed; all functionality
(form → plan, chat, PDF export, citations) still works.

**Design system (new):** token-based theming via CSS variables in `globals.css`
(light + dark), mapped to semantic Tailwind colors in `tailwind.config.ts`
(`background/surface/foreground/muted/border/primary/accent/...`) — **no hardcoded
colors**, so one class works in both themes. Concept: *teal = sourced, amber = estimate*
(the data model's own confidence axis becomes the brand). Fonts: Bricolage Grotesque
(display) + Inter (body) + JetBrains Mono (figures, a "ledger" motif). Radius/shadow
scales, keyframes (fade/scale/shimmer/pulse), reduced-motion support.

**Dark mode:** full system in `src/lib/theme.tsx` — `ThemeProvider` + `useTheme`,
class-based, localStorage persistence (`scp-theme`), system-preference detection +
live OS-change following, and an inline no-flash init script in `layout.tsx`.
`ThemeToggle` sun/moon control in the navbar.

**Components:** new `Navbar` (glass, sticky, status pill, GitHub, toggle), `Hero`
(thesis headline + animated count-up stats reflecting the real dataset 5/15/76),
`Footer`, `Skeletons` (shimmer loading). Redesigned `BudgetForm` (iconed header,
segmented lifestyle control), `PlanResults` (theme-reactive Recharts with gradient
bars + custom tooltip via `useChartColors`, ranked candidate cards with hover-lift,
ledger-mono breakdown table, scenario tiles, verification panel), `CitationChip`
(semantic sourced/estimate), `ChatPanel` (chat bubbles, sample chips, typing dots).
`page.tsx`: segmented tabs, refined empty/error states, loading skeleton.

**Verified:** `next build` clean (fonts fetched, types valid); Playwright screenshots
in light, dark, and 390px mobile (no overflow, navbar collapses gracefully). Docker
`frontend` image rebuilt; live on `localhost:3000`.

---

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
| 5 | 🇹🇷 Turkey | Bogazici, ITU, METU | ✅ seeded + verified |

**All 5 approved countries done** → real dataset: 5 countries, 12 cities, 15 universities,
15 programs, **76 cost items, 40 sources** (18 sourced / 58 labelled estimate). Verifier
5/5 pass per country. Currencies exercised: EUR, PLN, HUF, TRY, USD (all convert to the
report currency consistently). Remaining optional expansion (Czech, Italy, Georgia) was
deferred per the approved scope.

**Reseed workflow note:** the backend image bundles the seed JSON at build time
(`COPY . .`). After editing `data.real.json`, either rebuild the image, or bind-mount
the live file for the reseed run:
`docker compose run --rm -v "${PWD}/db/seed:/code/db/seed" backend python -m app.cli reseed`
(run from the `backend/` dir; WORKDIR in the image is `/code`).

**Batch 5 — Turkey notes:** highest sourcing difficulty — state universities (Bogazici,
ITU, METU) charge credit-based / USD-indexed fees published only in PDFs or fee calculators,
so all three tuitions are flagged `estimate` with reasoning and the official fee page as
source (Bogazici ~USD 3,000/yr, ITU ~USD 3,000/yr, METU ~USD 1,500/yr). Living costs in
**TRY** (volatile — Currency Agent adds an FX-risk note); tuition in **USD**. Residence-permit
card fee and private insurance sourced to Goc Idaresi / SGK. Verifier: 5/5 pass.

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
