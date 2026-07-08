# API reference

Base URL: `http://localhost:8000` · Interactive docs (OpenAPI/Swagger): `/docs`

**Auth:** protected routes require an `Authorization: Bearer <token>` header. Get a token
from `/auth/register` or `/auth/login`.

**Rate limiting:** the expensive prefixes (`/plan`, `/chat`, `/export`, `/scholarships`,
`/auth`, `/forecast`, `/letters`, `/profile`) are throttled per IP (token bucket), and the
paid ones additionally carry a per-IP **daily cap** (`PAID_DAILY_LIMIT_PER_IP`, default 60).
On limit: `429` with `Retry-After`. See [SECURITY.md](SECURITY.md).

---

## Endpoint index

| Method | Path | Auth | Purpose |
|--------|------|:----:|---------|
| GET | `/health` | — | Liveness + whether the LLM is configured |
| POST | `/plan` | — | Structured budget form → ranked, cited plan (incl. scholarships + net cost) |
| POST | `/chat` | — | Natural-language → grounded answer / discovery / scholarships / value |
| POST | `/export/pdf` | — | Re-run the plan and download a PDF report |
| POST | `/forecast` | — | Multi-year inflation projection (deterministic; optional LLM note) |
| POST | `/scholarships/search` | — | Live web-search for fresh scholarships (paid, cached, capped) |
| POST | `/chat/interview` | — | Interview practice simulator (multi-turn) |
| POST | `/chat/transcribe` | — | Transcribe an audio clip (Whisper) |
| POST | `/applications/plan` | — | Prioritized scholarship action plan (deadline → value) |
| POST | `/auth/register` | — | Create account → JWT |
| POST | `/auth/login` | — | Sign in → JWT |
| GET | `/auth/me` | ✔ | Current user profile |
| PUT | `/auth/me/profile` | ✔ | Save eligibility profile (nationality, GPA, language) |
| POST | `/letters/motivation` | ✔ | Draft a motivation letter (LLM) |
| POST | `/profile/transcript` | ✔ | Upload & analyze a transcript (vision) |
| GET | `/applications` | ✔ | List the user's tracked applications |
| POST | `/applications` | ✔ | Create a tracked application |
| PATCH | `/applications/{id}` | ✔ | Update status / notes |
| DELETE | `/applications/{id}` | ✔ | Remove a tracked application |
| PATCH | `/applications/{id}/documents/{doc_id}` | ✔ | Toggle a document checklist item |
| GET | `/meta/options` | — | Countries, fields, currencies (DB-driven) |
| GET | `/meta/stats` | — | Dataset counts (universities, programs, …) |
| POST | `/plans` | ✔ | Save a plan → shareable link |
| GET | `/plans` | ✔ | List the user's saved plans |
| GET | `/plans/shared/{public_id}` | — | Fetch a shared plan (public, unguessable token) |
| DELETE | `/plans/{id}` | ✔ | Delete a saved plan |

---

## Selected examples

### `GET /health`

```json
{ "status": "ok", "service": "study-cost-planner-backend",
  "llm_enabled": true, "report_currency": "EUR" }
```

### `POST /plan`

```jsonc
// request
{ "country": "Germany", "field": "Computer Science", "degree_level": "master",
  "budget_amount": 12000, "budget_currency": "EUR", "lifestyle": "moderate",
  "report_currency": "EUR",
  "nationality": "AZ", "gpa": 3.6, "language_test": "IELTS 7.0" }  // eligibility optional
```

Returns a ranked list of candidate programs, each with cited tuition + living costs,
scenarios, applicable scholarships, an eligibility verdict, gross/net totals, and a
`value_rank`.

### `POST /chat`

```jsonc
// request
{ "message": "I want to study CS in Germany, my budget is €12000/year",
  "report_currency": "EUR", "profile": null }   // profile is round-tripped each turn
```

Returns `{ mode, answer, profile, suggestions, candidates, plan, can_export, ... }`.
The `profile` must be sent back on the next turn (stateless server; treated as untrusted).

### `POST /scholarships/search`

```jsonc
// request
{ "country": "Germany", "field": "Computer Science",
  "degree_level": "master", "report_currency": "EUR" }
// response
{ "results": [ { "name": "...", "provider": "DAAD", "amount": "...",
  "official_url": "...", "annual_value": 11208.0 } ],
  "cached": false, "limited": false, "note": null }
```

### `POST /auth/register`

```jsonc
// request  (password: min 8 chars)
{ "email": "you@example.com", "password": "at-least-8-chars" }
// response
{ "token": "<jwt>", "user": { "id": 1, "email": "you@example.com", ... } }
```

### File uploads

- `POST /profile/transcript` — multipart, field `file`; PNG/JPEG/WEBP or PDF, ≤ 5 MB.
- `POST /chat/transcribe` — multipart, field `file`; WebM/Ogg/Wav/MP4 audio, ≤ 4 MB.

Both validate MIME **and** magic bytes; oversize uploads are rejected mid-stream (`413`),
the file is never trusted by `Content-Length` and never written to disk.

---

## Status codes

| Code | Meaning |
|------|---------|
| `200` | OK |
| `401` | Missing/invalid token, or bad credentials on login |
| `409` | Email already registered |
| `413` | Upload exceeds the size cap |
| `415` | Unsupported / mismatched file type |
| `422` | Request body failed validation (e.g. password < 8 chars) |
| `429` | Rate limit or daily cost cap reached (see `Retry-After`) |
