"""Thin OpenRouter client (OpenAI-compatible) used only for *language* tasks.

Design notes for free models:
- We do NOT rely on native tool/function calling (inconsistent on free tiers).
  Instead we ask for plain JSON and parse defensively.
- We keep calls few and short, and fall back to a secondary model on error.
- When no API key is configured the client is disabled and callers use their own
  deterministic fallback text, so the system still works end-to-end without an LLM.
"""
from __future__ import annotations

import json
import logging
import re

from app.core.config import settings

logger = logging.getLogger(__name__)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


class LLMClient:
    def __init__(self) -> None:
        self.enabled = settings.llm_enabled
        self._client = None
        if self.enabled:
            from openai import OpenAI

            # Fail fast: free models can hang or rate-limit. A short timeout with no
            # SDK-internal retries means a slow model degrades to our deterministic
            # path instead of blocking the chat request.
            self._client = OpenAI(
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
                timeout=settings.llm_timeout_seconds,
                max_retries=0,
            )

    @property
    def _headers(self) -> dict:
        return {
            "HTTP-Referer": settings.openrouter_app_url,
            "X-Title": settings.openrouter_app_title,
        }

    def _chat(self, system: str, user: str, max_tokens: int) -> str | None:
        if not self.enabled:
            return None
        for model in (settings.openrouter_model, settings.openrouter_fallback_model):
            try:
                resp = self._client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    max_tokens=max_tokens,
                    temperature=0.3,
                    extra_headers=self._headers,
                )
                content = resp.choices[0].message.content
                if content:
                    return content.strip()
            except Exception as exc:
                # Free models can rate-limit or hang; log and try the fallback model.
                logger.warning("LLM call failed for model %s: %s", model, exc)
                continue
        return None

    def complete_text(self, system: str, user: str, max_tokens: int = 220) -> str | None:
        return self._chat(system, user, max_tokens)

    def complete_json(self, system: str, user: str, max_tokens: int = 400) -> dict | None:
        raw = self._chat(system + " Respond with ONLY a valid JSON object.", user, max_tokens)
        if not raw:
            return None
        match = _JSON_RE.search(raw)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


# Module-level singleton (client construction is cheap; reused across requests).
llm = LLMClient()
