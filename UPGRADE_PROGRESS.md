# World-Class Upgrade — Progress Tracker

Branch: `feat/world-class-upgrade`
Full plan: `C:\Users\sadig\.claude\plans\you-are-an-expert-cosmic-castle.md`

Decisions: phased execution · bold redesign (keep teal=sourced / amber=estimate
tokens) · new frontend deps allowed: framer-motion + react-simple-maps · backend
hardening with minimal/zero new deps. Each phase ends with a commit + approval
checkpoint before the next.

---

## Phase 1 — Stabilize & De-hardcode ✅ DONE (commit `0a78314`)

Backend
- [x] `GET /meta/stats` — live counters (countries/universities/programs/cited_figures/sourced_figures/scholarships)
- [x] `/meta/options` now also returns `report_currencies` + `default_report_currency`
- [x] FX fallback: `raise last_exc or RuntimeError(...)` (no bare `raise None`) — `services/currency.py`
- [x] PDF export guarded with try/except → HTTP 500, worker no longer crashes — `api/export.py`
- [x] Eligibility: passed scholarship deadline → `ineligible` (was warn-only) — `agents/eligibility.py`
- [x] JWT fail-fast when `ENVIRONMENT=production` + default secret — `core/config.py`
- [x] In-memory per-IP token-bucket rate limit on /plan, /chat, /export — `core/rate_limit.py` + `main.py`
- [x] Tests: `tests/conftest.py` (SQLite + TestClient), `tests/test_api_routes.py`, `tests/test_rate_limit.py` — **44 pass**
- NOTE: did NOT remove cli.py manual index creation (intentional for pre-existing DBs); test_advisor.py is NOT empty — both audit "cleanup" items were wrong.
- NOTE: `net_value.py:40` was NOT a real bug — line 38 `> 0` filter already excludes negatives.

Frontend
- [x] Hero counters from `/meta/stats` (was hardcoded 8/25/130; label now "cited figures" = 130 total) — `components/Hero.tsx`
- [x] Currencies + countries from backend; removed hardcoded `CURRENCIES` — `components/BudgetForm.tsx`
- [x] Budget/GPA validation with inline errors; emoji 🎓 → SVG icon — `components/BudgetForm.tsx`
- [x] Global `ErrorBoundary` wired in `app/layout.tsx` — `components/ErrorBoundary.tsx`
- [x] Chat localStorage schema validation (`isValidConversation`) — `components/ChatPanel.tsx`
- [x] Tracker loading skeleton (`ApplicationsSkeleton`) — `components/Skeletons.tsx` + `ApplicationsTracker.tsx`
- [x] Typed Recharts tooltip (dropped `any`) — `components/PlanResults.tsx`
- [x] `npm run build` clean; live `/meta/stats` verified = `{countries:8, universities:25, cited_figures:130, sourced_figures:33, scholarships:8}`

---

## Phase 2 — 10x Frontend Overhaul (bold redesign) — IN PROGRESS

Added **framer-motion@^11**. Keep teal/amber tokens + Inter/Bricolage/JetBrains-Mono.
- [x] Onboarding wizard (multi-step, 4 steps) replacing dense BudgetForm; submits same PlanningRequest — `components/OnboardingWizard.tsx` (BudgetForm.tsx now unused, kept)
- [x] Sticky animated navbar (entrance + scroll-elevation shadow) — `components/Navbar.tsx`
- [x] Framer Motion micro-interactions: tab transitions (AnimatePresence in `app/page.tsx`), staggered result cards (`components/PlanResults.tsx`)
- [x] Accessible chart (`role="img"` + aria-label summary + `sr-only` data-table fallback) — `components/PlanResults.tsx`
- [x] Chat: fluid `dvh` height (was fixed 640px) — `components/ChatPanel.tsx` (typing indicator + sticky composer already present)
- [x] a11y: SVG not emoji (🎓 removed in PlanResults + ChatPanel), focus trap + Escape + focus restore in AuthModal — `components/AuthModal.tsx`
- [x] Dark-mode: all new surfaces use existing theme tokens → dark-compatible by construction
- NOTE: `npm run build` clean after every step. Number-transition count-up already exists in Hero.tsx.

## Phase 3 — 10 Brainstormed Features — IN PROGRESS (5/10 done, #2 deferred)
1. [x] Side-by-side comparison (pin 2–3 candidates) — `ComparisonView.tsx` + pin button in `PlanResults.tsx` (commit `4c90ee9`). Verified: teal=cheapest, amber=most aid, ties unmarked.
2. [DEFERRED] Full-degree projection + inflation slider — built then REMOVED at user request: a manual inflation slider is meaningless guesswork. Redo later with a SOURCED per-country inflation figure (new data field), not an LLM/manual estimate, to honour the "every figure cited" principle.
3. [x] Interactive what-if sliders (debounced /plan) — `WhatIfPanel` in `PlanResults.tsx` + `refreshing`/`onWhatIf` in `app/page.tsx` (commit `985b9f7`). Re-plans in place, no skeleton swap.
4. [x] Saved plans + shareable links — `SavedPlan` model + `/plans` CRUD + public `/plans/shared/{public_id}` (re-runs planner so links stay current); frontend "Save & share" on results, Saved tab (`SavedPlans.tsx`), public view `app/p/[id]/page.tsx` (commit `976f6e9`). Verified end-to-end incl. auth gating + friendly 404.
5. [x] Map-based country explorer (**react-simple-maps**) — `CountryMap.tsx` in the form-tab empty state; covered countries from /meta/options (aliases: Czechia→czech republic, Turkey→türkiye), click pre-fills wizard via `initialCountry` prop (commit `976f6e9`). Topojson bundled at `frontend/public/countries-110m.json`; `.npmrc` legacy-peer-deps for React 19; Dockerfile copies `.npmrc`.
6. [x] Scholarship match score + "improve eligibility" tips — EligibilityAgent now emits `match_score` (0–100, deterministic deductions) + actionable `tips` (only for fixable missing inputs; cleared for hard fails). Frontend: score meter per row + per-row "Improve your odds" + panel-level deduped "Improve your eligibility" summary; 🎓 header → SVG (`ScholarshipPanel.tsx`). 44 tests pass. Verified: 100 eligible / 90 missing-language.
7. [ ] Part-time work earnings offset (new `Country.work_hours_cap` field)
8. [ ] FX stress scenario ("currency drops X%") for volatile currencies
9. [ ] Deadline calendar + ICS export (hand-built .ics, no dep)
10. [ ] i18n EN/AZ (chat already understands AZ)

---

## How to verify / run
- Backend tests: `docker compose run --rm --no-deps -e DATABASE_URL="sqlite://" backend python -m pytest app/tests -q`
- Full stack: `docker compose up -d` (if backend can't resolve `db`, run `docker compose down` then `up` to recreate the network — hit this once)
- Frontend build: `cd frontend && npm run build`
- Images are baked (no bind mount) — rebuild after backend edits: `docker compose build backend && docker compose up -d backend`
