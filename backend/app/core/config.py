"""Application configuration, loaded from environment variables.

A single ``settings`` instance is imported across the app. Defaults are chosen so
the API can boot locally even before a full ``.env`` is provided.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- LLM (OpenRouter) ---
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    openrouter_fallback_model: str = "deepseek/deepseek-chat-v3-0324:free"
    openrouter_app_url: str = "http://localhost:3000"
    openrouter_app_title: str = "Study Cost Planning Agent"

    # --- Database ---
    database_url: str = "postgresql+psycopg://studyplanner:studyplanner@localhost:5432/studyplanner"

    # --- Currency ---
    frankfurter_base_url: str = "https://api.frankfurter.app"
    fx_cache_hours: int = 24

    # --- App behaviour ---
    default_report_currency: str = "EUR"
    source_stale_months: int = 18

    @property
    def llm_enabled(self) -> bool:
        """LLM features are only active when an API key is configured."""
        return bool(self.openrouter_api_key and not self.openrouter_api_key.startswith("sk-or-v1-xxx"))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
