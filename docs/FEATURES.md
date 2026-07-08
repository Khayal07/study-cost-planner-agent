# Features

Every user-facing capability, with the code path behind it.

---

## 1. Total real cost engine

The core value proposition: the **whole** cost of studying abroad, not just tuition.

- **Cost items:** tuition, rent, food, insurance, visa, transport, and hidden costs —
  each a `CostItem` row citing a `Source`.
- **Scenarios:** frugal / moderate / comfortable spending profiles (`agents/scenario.py`).
- **Currency-normalized:** everything converted to your report currency with FX-risk flags.
- **Grounded:** each figure is `sourced` or `estimate` and carries a source URL + date.

**Code:** `agents/tuition.py`, `agents/living_cost.py`, `agents/currency.py`,
`agents/scenario.py`. **UI:** `BudgetForm.tsx`, `PlanResults.tsx`, `ComparisonView.tsx`.

## 2. Scholarship discovery & explainable eligibility

- **Seeded, cited awards:** DAAD, Erasmus Mundus, Deutschlandstipendium, Holland
  Scholarship, TU Delft van Effen, NAWA Banach, Stipendium Hungaricum, Türkiye Bursları —
  each with a `Source` URL. Scopes are polymorphic: `global / country / university / program`.
- **Explainable verdict:** a deterministic agent scores each award against the program
  (degree, field) and your optional profile (nationality, GPA, language) →
  `eligible / likely / unknown / ineligible` + a human-readable reason list. **The LLM is
  never used for the verdict.**

**Code:** `agents/scholarship.py`, `agents/eligibility.py`. **UI:** `ScholarshipPanel.tsx`.

## 3. Live scholarship web search (optional, paid)

On demand, an OpenAI web-search model finds **fresh** awards for a country/field/degree.

- Cached per `(country, field, degree)` for `SCHOLARSHIP_CACHE_HOURS`.
- Capped at `SCHOLARSHIP_SEARCH_DAILY_LIMIT` calls/day and `SCHOLARSHIP_SEARCH_MAX_RESULTS`.
- Selected awards fold into the net-cost total and the PDF.

**Code:** `services/scholarship_search.py`, `api/scholarship_search.py`.

## 4. Net cost & value ranking

The best realistic award is applied to compute `net_total_annual` and a `value_rank`.
The UI offers a **Cost ↔ Value-after-aid** toggle while preserving the gross ranking.

**Code:** `agents/net_value.py`. **UI:** net-cost badges + toggle in `PlanResults.tsx`.

## 5. Application planner & tracker (accounts)

- **Planner:** `/applications/plan` returns a deadline-then-value priority list with a
  "this week" action list and the union of required documents.
- **Tracker:** signed-in users save awards, track status, and tick documents off —
  persisted to their account and surviving reloads.
- **Calendar export:** deadlines export to `.ics` (`lib/ics.ts`).

**Code:** `services/application_planner.py`, `api/applications.py`.
**UI:** `ApplicationsTracker.tsx`, `DeadlineCalendar.tsx`.

## 6. Visual insights

| Chart | What it shows | Component |
|-------|---------------|-----------|
| Cost radar | Cost dimensions across candidates | `CostRadar.tsx` |
| Cash-flow Sankey | Where the money flows (income → cost buckets) | `CostSankey.tsx`, `CashFlowChart.tsx` |
| Inflation forecast | Projected multi-year cost with inflation | `CostForecast.tsx` |
| Country map | Geographic overview of options | `CountryMap.tsx` |
| Share card | A shareable summary image (`html-to-image`) | `ShareCard.tsx` |

**Forecast backend:** `services/forecast.py`, `api/forecast.py`, `data/inflation.py` —
deterministic projection with optional LLM commentary.

## 7. AI writing & practice

- **Motivation letters:** draft a tailored letter from your profile + target program
  (`services/letters.py`, `api/letters.py`, `LetterModal.tsx`). Auth required.
- **Interview practice:** a multi-turn LLM interview simulator with context
  (`services/interview.py`, `api/interview.py`, `InterviewPanel.tsx`).

## 8. Smart intake

- **Transcript auto-fill (vision):** upload a photo/PDF of your transcript; an OpenAI
  vision model extracts GPA/courses to prefill your profile. Auth required.
  **Guards:** 5 MB cap, MIME allowlist + magic-byte check, in-memory (never written to disk).
  **Code:** `services/transcript.py`, `api/transcript.py`, `TranscriptUpload.tsx`.
- **Voice input (Whisper):** speak your query; OpenAI Whisper transcribes it.
  **Guards:** 4 MB cap, audio MIME + magic-byte check, `VOICE_DAILY_LIMIT`/day.
  **Code:** `api/transcribe.py`, `MicButton.tsx`.

## 9. PDF report

A downloadable, cited report — tuition, living costs, scenarios, scholarships and net
cost. Can be **focused on a single university** via `focus_program_id`.

**Code:** `services/pdf.py`, `api/export.py`. Rendered with WeasyPrint (SSRF-locked to
`data:` URIs) + Matplotlib charts embedded as base64.

## 10. Accounts & saved plans

- JWT auth (register/login), bcrypt-hashed passwords (`core/security.py`, `api/auth.py`).
- Save a plan → get a shareable public link (`/plans/shared/{public_id}`, unguessable token).
- **UI:** `AuthModal.tsx`, `SavedPlans.tsx`, shared-plan page `app/p/[id]/page.tsx`.

## 11. UX polish

Onboarding wizard, dark/light theme, internationalization (incl. Azerbaijani translation
of chat/apps/saved tabs), skeleton loaders, error boundaries.

**UI:** `OnboardingWizard.tsx`, `ThemeToggle.tsx`, `lib/i18n.tsx`, `lib/theme.tsx`,
`Skeletons.tsx`, `ErrorBoundary.tsx`.

## 12. AI data pipeline

Add a **new field of study** across the existing universities with AI-assisted collection
and mandatory human review. Full guide: [DATA_PIPELINE.md](DATA_PIPELINE.md).
