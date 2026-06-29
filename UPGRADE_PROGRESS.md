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

## Phase 2 — 10x Frontend Overhaul (bold redesign) — NOT STARTED

Add **framer-motion**. Keep teal/amber tokens + Inter/Bricolage/JetBrains-Mono.
- [ ] Onboarding wizard (multi-step) replacing dense BudgetForm; submits same PlanningRequest
- [ ] Dashboard shell layout in `app/page.tsx`; sticky animated navbar
- [ ] Framer Motion micro-interactions (page/section transitions, staggered cards, number transitions)
- [ ] Results redesign + accessible chart (`role="img"` + data-table fallback, keyboard tooltip)
- [ ] Chat redesign (fluid `dvh` height not fixed 640px, typing indicator, sticky composer)
- [ ] a11y pass (SVG not emoji, focus trap in AuthModal, text+color states)
- [ ] Dark-mode polish on all new surfaces

## Phase 3 — 10 Brainstormed Features — NOT STARTED
1. [ ] Side-by-side comparison (pin 2–3 candidates)
2. [ ] Full-degree projection + inflation slider (`Program.duration_years`)
3. [ ] Interactive what-if sliders (debounced /plan)
4. [ ] Saved plans + shareable links (new `SavedPlan` model + `/plans` CRUD)
5. [ ] Map-based country explorer (**react-simple-maps**, from /meta/options)
6. [ ] Scholarship match score + "improve eligibility" tips (EligibilityAgent reasons)
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
