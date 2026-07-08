# Security

This project has been through **two security passes** (a hardening audit and a
pentester-style re-audit). This document is the honest, current picture.

## Summary

**No secret leak.** `.env` is gitignored and has **never** been committed (verified against
git history). No API keys are hardcoded anywhere; the frontend only ever sees the public
`NEXT_PUBLIC_API_BASE_URL`.

**Solid baseline.** ORM-only queries (no SQL injection), bcrypt password hashing, ownership
checks on all account routes, strict security headers, locked CORS, an SSRF-locked PDF
renderer, and validated file uploads.

## Threat model & posture

| Area | Status | How |
|------|:------:|-----|
| Secret leakage | ✅ | `.env` gitignored + never committed; no keys in source or frontend. |
| SQL injection | ✅ | 100% SQLAlchemy ORM; no string-built SQL. |
| Command injection | ✅ | No `subprocess` / `os.system` / `shell=True`. |
| Unsafe deserialization | ✅ | No `pickle` / `yaml.load` / `eval` / `exec`. |
| Prompt injection | ✅ | `core/text.py::sanitize_prompt_field()` strips control chars/newlines before any user text reaches an LLM prompt (scholarship search, collector, interview). |
| SSRF (PDF) | ✅ | WeasyPrint URL fetcher locked to `data:` URIs; all images base64, all CSS inline. |
| SSRF (web search) | ✅ | The model chooses URLs from a sanitized prompt; the app never fetches user-supplied URLs. |
| File uploads | ✅ | Size caps enforced mid-stream (not trusting `Content-Length`), MIME allowlist **and** magic-byte checks, kept in memory (never written to disk). |
| CORS | ✅ | Locked to configured origins; credentials off (bearer tokens); explicit method/header allowlist. |
| Security headers | ✅ | `nosniff`, `X-Frame-Options: DENY`, strict CSP (`default-src 'none'`), `Referrer-Policy`, HSTS in production. |
| Passwords | ✅ | bcrypt with per-password salt; registration requires ≥ 8 chars. |
| Auth secrets in prod | ✅ | App refuses to boot in production with the default `JWT_SECRET`. |
| Cost abuse on paid endpoints | ⚠️→✅ | Per-IP token bucket **plus** a per-IP daily cap on paid endpoints (see below). |
| Multi-instance rate limits | ⚠️ | In-memory, single-instance today; use Redis for a distributed deploy. |
| Token revocation | ⚠️ | No logout/blacklist; JWTs are short-lived (7 days). Acceptable, not ideal. |

## Hardening pass 1 — audit (merged to `main`)

- `/auth` rate-limited (login brute-force); `X-Forwarded-For` only honoured when
  `TRUST_PROXY_HEADER=true` (prevents rate-limit bypass via spoofed XFF).
- `core/security_headers.py` — the header middleware above.
- CORS `allow_headers` narrowed to `Authorization, Content-Type`.
- `core/text.py::sanitize_prompt_field()` — prompt-injection guard.
- `services/pdf.py` — WeasyPrint locked to `data:` URIs.
- Postgres host port bound to `127.0.0.1`.

## Hardening pass 2 — pentester re-audit + cost guard

The re-audit confirmed no leak and found one real gap: the paid endpoints
(`/chat`, `/plan`, `/export`, `/scholarships`, `/letters`, `/profile`, and their children
`/chat/interview`, `/chat/transcribe`, `/profile/transcript`) were only **burst**-throttled —
the token bucket refills, so a patient attacker could still run up open-ended LLM/vision/
Whisper/web-search spend.

**Decision:** keep the public UX (no forced login), add a **cost guard** instead of auth.

- `core/rate_limit.py` — new `_allow_daily()`: a per-IP **daily ceiling** on the paid
  prefixes, alongside the existing token bucket. On limit: `429` + `Retry-After`.
- `core/config.py` — `PAID_DAILY_LIMIT_PER_IP` (default `60`).
- `core/schemas.py` — registration password minimum raised `6 → 8`.
- Tests added; **93/93 pass**. Live smoke: weak password → `422`, strong → `200`,
  `/health` → ok.

The per-feature caps (`SCHOLARSHIP_SEARCH_DAILY_LIMIT`, `VOICE_DAILY_LIMIT`,
`PIPELINE_MAX_CALLS`) provide a second, feature-specific line of defense.

## Known limitations (by design, for a course project)

- **In-memory limiter.** Rate limits and daily caps reset on restart and are per-process.
  A multi-instance deployment needs a shared store (Redis).
- **No token revocation.** Mitigated by a 7-day expiry; add a blacklist if you need instant logout.
- **Weak default DB credentials** are for local dev only (`studyplanner`), and the DB port is
  bound to loopback. Set a strong `POSTGRES_PASSWORD` for production.

## Production checklist

1. `ENVIRONMENT=production` (enforces HSTS + rejects the default JWT secret).
2. Strong `JWT_SECRET` and `POSTGRES_PASSWORD`.
3. `TRUST_PROXY_HEADER=true` **only** if behind a trusted reverse proxy.
4. Restrict `CORS_ALLOW_ORIGINS` to your real frontend domain.
5. **Rotate any API key that was ever printed or shared.** Keys live only in `.env`
   (gitignored), but rotate on any suspicion of exposure.
6. Consider Redis-backed rate limiting if running more than one instance.
