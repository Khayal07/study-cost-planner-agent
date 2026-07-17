"""Application configuration, loaded from environment variables.

A single ``settings`` instance is imported across the app. Defaults are chosen so
the API can boot locally even before a full ``.env`` is provided.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_JWT_SECRET = "dev-insecure-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- LLM (OpenRouter) ---
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    openrouter_fallback_model: str = "deepseek/deepseek-chat-v3-0324:free"
    openrouter_app_url: str = "http://localhost:3000"
    openrouter_app_title: str = "Study Cost Planning Agent"
    # Hard cap per LLM call so a slow/free model can't block a chat turn; on timeout
    # callers fall back to their deterministic path.
    llm_timeout_seconds: float = 12.0

    # --- LLM (OpenAI, preferred when a key is set) ---
    # When openai_api_key is provided the chat/intent LLM uses OpenAI directly
    # (base_url below) instead of OpenRouter. Keeps calls small and cheap.
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    # Model with built-in web search, used only by the live scholarship search.
    openai_search_model: str = "gpt-4o-mini-search-preview"

    # --- Live scholarship search (web) ---
    # Guardrails so a $5 credit lasts: cache results per (country, field, degree),
    # cap searches per day, and keep result count / tokens small.
    scholarship_cache_hours: int = 24
    scholarship_search_daily_limit: int = 40
    scholarship_search_max_results: int = 6
    scholarship_search_timeout_seconds: float = 30.0

    # --- Data-collection pipeline (python -m app.pipeline) ---
    # Hard cap on paid web-search calls per collect run; the search model and
    # timeout reuse the live-scholarship-search settings above.
    pipeline_max_calls: int = 40

    # --- Uploads (transcript analysis + voice transcription) ---
    transcript_max_bytes: int = 5 * 1024 * 1024   # 5 MB image/PDF cap
    audio_max_bytes: int = 4 * 1024 * 1024        # ~90s of opus at 48kbps
    voice_daily_limit: int = 200                  # paid whisper calls per day
    openai_transcribe_model: str = "whisper-1"

    # --- Database ---
    database_url: str = "postgresql+psycopg://studyplanner:studyplanner@localhost:5432/studyplanner"

    # --- Currency ---
    frankfurter_base_url: str = "https://api.frankfurter.dev/v1"
    fx_cache_hours: int = 24
    # Fallback FX provider (free, no key) for currencies the ECB/frankfurter feed
    # doesn't cover — e.g. AZN. Used only when frankfurter can't resolve a pair.
    fallback_fx_base_url: str = "https://open.er-api.com/v6"

    # --- App behaviour ---
    default_report_currency: str = "EUR"
    source_stale_months: int = 18

    # Comma-separated browser origins allowed to call the API (CORS). The app uses no
    # cookies/auth, so credentials are disabled; override for other frontends/deploys.
    cors_allow_origins: str = "http://localhost:3000"

    # Which seed dataset to load: "real" (web-sourced, the default) or "mock"
    # (the original curated demo dataset, kept as a dev/fallback). See app/data/seed.py.
    seed_dataset: str = "real"

    # Deployment environment. Set ENVIRONMENT=production to enforce hardened
    # config (e.g. a real JWT secret) at startup.
    environment: str = "development"

    # Only honour the client-supplied X-Forwarded-For header for rate-limiting when
    # the API actually sits behind a trusted reverse proxy. Left False, any client
    # could spoof XFF to get a fresh rate-limit bucket and bypass throttling.
    trust_proxy_header: bool = False

    # Per-IP daily ceiling on the paid endpoints (chat/plan/export/scholarships/
    # interview/transcribe). The token bucket above only blunts bursts and refills;
    # this hard cap bounds a single client's daily spend. In-memory, single-instance
    # (resets on restart) — swap in a shared store for multi-instance deploys.
    paid_daily_limit_per_ip: int = 60

    # --- Auth (accounts + application tracker) ---
    # Override in production via JWT_SECRET. The default is for local dev only.
    jwt_secret: str = _INSECURE_JWT_SECRET
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    @property
    def is_production(self) -> bool:
        """True when running with ENVIRONMENT=production (enables prod hardening)."""
        return self.environment.lower() == "production"

    @property
    def use_openai(self) -> bool:
        """Prefer OpenAI directly when a real key is configured."""
        return bool(self.openai_api_key and not self.openai_api_key.startswith("sk-xxx"))

    @property
    def llm_enabled(self) -> bool:
        """LLM features are active when either OpenAI or OpenRouter has a real key."""
        if self.use_openai:
            return True
        return bool(self.openrouter_api_key and not self.openrouter_api_key.startswith("sk-or-v1-xxx"))

    @model_validator(mode="after")
    def _enforce_production_secrets(self) -> "Settings":
        """Refuse to boot in production with the insecure default JWT secret."""
        if self.environment.lower() == "production" and self.jwt_secret == _INSECURE_JWT_SECRET:
            raise ValueError(
                "JWT_SECRET must be set to a strong value when ENVIRONMENT=production"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
