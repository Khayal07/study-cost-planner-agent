# Configuration

All configuration is via environment variables, loaded from `.env`
(`backend/app/core/config.py`, Pydantic Settings). Copy the template and edit:

```bash
cp .env.example .env
```

Defaults are chosen so the app **boots locally without a full `.env`**. The only thing you
need for the AI features is one LLM key.

## LLM — OpenAI (preferred)

| Variable | Default | What it does |
|----------|---------|--------------|
| `OPENAI_API_KEY` | _(empty)_ | Enables OpenAI directly for chat + intent. When set, takes precedence over OpenRouter. |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | API base (override for a proxy). |
| `OPENAI_MODEL` | `gpt-4o-mini` | Chat/intent model. |
| `OPENAI_SEARCH_MODEL` | `gpt-4o-mini-search-preview` | Web-search model, used only by live scholarship search. |
| `OPENAI_TRANSCRIBE_MODEL` | `whisper-1` | Voice transcription model. |

## LLM — OpenRouter (fallback, free models)

Used when no `OPENAI_API_KEY` is set. Get a free key at <https://openrouter.ai/keys>.

| Variable | Default |
|----------|---------|
| `OPENROUTER_API_KEY` | _(empty)_ |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` |
| `OPENROUTER_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` |
| `OPENROUTER_FALLBACK_MODEL` | `deepseek/deepseek-chat-v3-0324:free` |
| `OPENROUTER_APP_URL` / `OPENROUTER_APP_TITLE` | attribution headers for OpenRouter analytics |

> **The LLM is optional.** With no key, intent extraction falls back to a deterministic
> parser and narratives use templates — the app still works end to end.

`LLM_TIMEOUT_SECONDS` (default `12.0`) hard-caps each LLM call so a slow free model can't
block a chat turn; on timeout the caller uses its deterministic path.

## Cost guardrails (paid features)

| Variable | Default | What it does |
|----------|---------|--------------|
| `SCHOLARSHIP_CACHE_HOURS` | `24` | Cache window for a live scholarship search per (country, field, degree). |
| `SCHOLARSHIP_SEARCH_DAILY_LIMIT` | `40` | Max paid web-search calls per day. |
| `SCHOLARSHIP_SEARCH_MAX_RESULTS` | `6` | Results per search. |
| `SCHOLARSHIP_SEARCH_TIMEOUT_SECONDS` | `30.0` | Per-search timeout. |
| `VOICE_DAILY_LIMIT` | `200` | Max paid Whisper transcriptions per day. |
| `PIPELINE_MAX_CALLS` | `40` | Hard cap on paid web-search calls per data-pipeline `collect` run. |
| `PAID_DAILY_LIMIT_PER_IP` | `60` | Per-IP daily ceiling across all paid endpoints (see [Security](SECURITY.md)). |

## Uploads

| Variable | Default | What it does |
|----------|---------|--------------|
| `TRANSCRIPT_MAX_BYTES` | `5 MB` | Max transcript image/PDF upload. |
| `AUDIO_MAX_BYTES` | `4 MB` | Max audio upload (~90 s of opus). |

## Database

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_URL` | `postgresql+psycopg://studyplanner:studyplanner@localhost:5432/studyplanner` | Inside Docker, host is `db`. |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` / `POSTGRES_HOST` / `POSTGRES_PORT` | `studyplanner…` | Used by docker-compose. **Change the password for production.** |

## Currency

| Variable | Default |
|----------|---------|
| `FRANKFURTER_BASE_URL` | `https://api.frankfurter.dev/v1` (ECB, no key) |
| `FX_CACHE_HOURS` | `24` |
| `FALLBACK_FX_BASE_URL` | `https://open.er-api.com/v6` (for currencies ECB doesn't cover, e.g. AZN) |

## App behaviour

| Variable | Default | What it does |
|----------|---------|--------------|
| `DEFAULT_REPORT_CURRENCY` | `EUR` | Currency used when the client doesn't specify one. |
| `SOURCE_STALE_MONTHS` | `18` | A source older than this is flagged as stale. |
| `SEED_DATASET` | `real` | `real` (web-sourced) or `mock` (demo). |
| `CORS_ALLOW_ORIGINS` | `http://localhost:3000` | Comma-separated allowed browser origins. |

## Security / deployment

| Variable | Default | What it does |
|----------|---------|--------------|
| `ENVIRONMENT` | `development` | Set to `production` to enforce hardened config at startup (HSTS on; refuses to boot with the default JWT secret). |
| `JWT_SECRET` | `dev-insecure-change-me` | **Must** be a strong value in production. |
| `JWT_EXPIRE_MINUTES` | `10080` (7 days) | Token lifetime. |
| `TRUST_PROXY_HEADER` | `false` | Only honour `X-Forwarded-For` when behind a trusted reverse proxy. Leaving it false prevents rate-limit bypass via a spoofed header. |

## Frontend

| Variable | Default | What it does |
|----------|---------|--------------|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Browser-facing backend URL. **Public** by design (no secrets). |

## Production checklist

```dotenv
ENVIRONMENT=production
JWT_SECRET=<a long random string>
POSTGRES_PASSWORD=<a strong password>
TRUST_PROXY_HEADER=true      # only if behind a reverse proxy
CORS_ALLOW_ORIGINS=https://your-frontend-domain
OPENAI_API_KEY=<your key>    # rotate if ever exposed
```
