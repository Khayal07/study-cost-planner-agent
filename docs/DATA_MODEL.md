# Data model

Defined in `backend/app/data/models.py` (SQLAlchemy 2.0 ORM, PostgreSQL 16 + pgvector).

## The core idea: the citation contract

> **Every cost figure is a `CostItem` that references exactly one `Source`.**

Any output — a chat answer or a PDF — can therefore trace
`CostItem → Source → url`. There are no invented numbers; a figure is either
`sourced` (has a real URL) or `estimate` (labelled as such).

## The polymorphic scope pattern

Both `CostItem` and `Scholarship` use `(scope_level, scope_id)` to attach to a
`program`, `university`, `city`, `country`, or (scholarships only) `global` — without
separate tables per level. A composite index on those columns backs every plan/chat query.

```
scope_level = "program"     → scope_id = programs.id      (e.g. tuition)
scope_level = "city"        → scope_id = cities.id        (e.g. rent, food)
scope_level = "country"     → scope_id = countries.id     (e.g. visa)
scope_level = "global"      → scope_id = NULL             (scholarships only)
```

## Tables

### Reference / catalog

| Table | Purpose | Key columns |
|-------|---------|-------------|
| `sources` | Provenance for every figure | `url` (NULL for pure estimates), `title`, `publisher`, `source_type`, `accessed_date` |
| `countries` | Country + default currency + optional student work rights | `iso_code`, `default_currency`, `work_hours_cap`, `work_hourly_wage` |
| `cities` | City → country | `country_id`, `name` |
| `universities` | University → country + city | `official_url`, `source_id` |
| `programs` | A field of study at a university | `field`, `degree_level`, `language`, `duration_years` |

### Grounded facts

| Table | Purpose | Notes |
|-------|---------|-------|
| `cost_items` | Every cost figure | `cost_type` ∈ {tuition, rent, food, transport, insurance, visa, utilities, hidden_misc}; `period` ∈ {annual, monthly, one_time}; `confidence` ∈ {sourced, estimate}; FK → `sources`. Indexed on `(scope_level, scope_id, cost_type)`. |
| `scholarships` | Grounded awards | Polymorphic scope; `coverage_type` (waiver / partial / stipend / …); eligibility columns (`degree_levels`, `fields`, `nationality_rule`, `min_gpa`, `language_requirement`) where **NULL = no restriction = pass**; FK → `sources`. |
| `knowledge_chunks` | Embedded text for semantic chat retrieval | `embedding Vector(384)` (BAAI/bge-small via fastembed). Reserved for future semantic retrieval. |
| `fx_rates` | Cached currency rates | `(base, quote, as_of_date)`; optional `source_id`. |
| `scholarship_search_cache` | Cache of live web-search results | Unique key `(country, field, degree_level)`; `fetched_at` also drives the daily call cap. |

### Accounts

| Table | Purpose | Notes |
|-------|---------|-------|
| `users` | Registered student | `email` (unique), `password_hash` (bcrypt), optional profile (`nationality`, `gpa`, `language_test`). Cascades to applications + saved plans. |
| `applications` | A tracked scholarship | Award fields **denormalized** so the tracker survives a dataset reseed; `status` ∈ {planned, in_progress, submitted, accepted, rejected}; optional `motivation_letter`. |
| `application_documents` | Per-application checklist item | `name`, `done`. |
| `saved_plans` | A saved plan | Stores the **request** (`request_json`) and re-runs the planner on read, so shared links always reflect current data; `public_id` is an unguessable share token. |

## Relationships (at a glance)

```
Country ─┬─ City ──── University ──── Program
         └─ (universities)                │
                                          ▼
Source ◀── CostItem / Scholarship  (via scope_level + scope_id)

User ─┬─ Application ─── ApplicationDocument
      └─ SavedPlan
```

## Controlled vocabularies

Kept as plain strings, validated in Python (see the `*_TYPES` / `*_LEVELS` sets at the top
of `models.py`): `COST_TYPES`, `PERIODS`, `SCOPE_LEVELS`, `CONFIDENCE`, `SOURCE_TYPES`,
`COVERAGE_TYPES`, `APPLICATION_STATUSES`.

## Seed data

Two datasets, selected by `SEED_DATASET` (`data/seed.py`):

- **`real`** (default) — web-sourced, cited data. **12 countries, 33 universities, 34
  programs** (Computer Science across all, plus Medicine at Tartu added via the
  [AI data pipeline](DATA_PIPELINE.md)). Scholarships seeded alongside (DAAD, Erasmus
  Mundus, Deutschlandstipendium, Holland Scholarship, TU Delft van Effen, NAWA Banach,
  Stipendium Hungaricum, Türkiye Bursları).
- **`mock`** — the original curated demo dataset, kept as a dev/fallback.

Seeding runs on boot and is **idempotent**. Migrations + seeding also available via the CLI:
`python -m app.cli migrate` and `python -m app.cli seed`.
