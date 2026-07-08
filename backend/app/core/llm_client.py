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
        self.use_openai = settings.use_openai
        self._client = None
        if self.enabled:
            from openai import OpenAI

            # Fail fast: a slow model can hang or rate-limit. A short timeout with no
            # SDK-internal retries means it degrades to our deterministic path instead
            # of blocking the chat request. When an OpenAI key is set we point at
            # OpenAI directly (cheap gpt-4o-mini); otherwise fall back to OpenRouter.
            if self.use_openai:
                self._client = OpenAI(
                    api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url,
                    timeout=settings.llm_timeout_seconds,
                    max_retries=0,
                )
            else:
                self._client = OpenAI(
                    api_key=settings.openrouter_api_key,
                    base_url=settings.openrouter_base_url,
                    timeout=settings.llm_timeout_seconds,
                    max_retries=0,
                )

    @property
    def _headers(self) -> dict:
        # OpenRouter analytics headers; harmless (ignored) when talking to OpenAI.
        return {
            "HTTP-Referer": settings.openrouter_app_url,
            "X-Title": settings.openrouter_app_title,
        }

    @property
    def _models(self) -> tuple[str, ...]:
        if self.use_openai:
            return (settings.openai_model,)
        return (settings.openrouter_model, settings.openrouter_fallback_model)

    def _chat(self, system: str, user: str, max_tokens: int) -> str | None:
        if not self.enabled:
            return None
        for model in self._models:
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

    def complete_messages(self, messages: list[dict], max_tokens: int = 400) -> str | None:
        """Multi-message completion (system + alternating turns) for conversational
        features like the interview simulator. Same timeout/fallback behaviour as
        ``_chat``; returns None when disabled or every model fails."""
        if not self.enabled:
            return None
        for model in self._models:
            try:
                resp = self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=0.4,
                    extra_headers=self._headers,
                )
                content = resp.choices[0].message.content
                if content:
                    return content.strip()
            except Exception as exc:
                logger.warning("LLM call failed for model %s: %s", model, exc)
                continue
        return None

    def complete_json_content(self, system: str, content: list[dict], max_tokens: int = 400) -> dict | None:
        """JSON completion where the user message is a multimodal content list
        (text + image_url/file parts). Used by the transcript analyzer. Returns
        None when disabled, on failure, or on unparseable output."""
        if not self.enabled:
            return None
        raw = None
        for model in self._models:
            try:
                resp = self._client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system + " Respond with ONLY a valid JSON object."},
                        {"role": "user", "content": content},
                    ],
                    max_tokens=max_tokens,
                    temperature=0.1,
                    extra_headers=self._headers,
                )
                raw = resp.choices[0].message.content
                if raw:
                    break
            except Exception as exc:
                logger.warning("LLM vision call failed for model %s: %s", model, exc)
                continue
        if not raw:
            return None
        match = _JSON_RE.search(raw)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    def transcribe(self, data: bytes, filename: str, language: str | None = None) -> str | None:
        """Speech-to-text via whisper-1. Only available on the direct OpenAI path
        (OpenRouter has no audio endpoint). Returns None when unavailable/failed."""
        if not self.enabled or not self.use_openai:
            return None
        try:
            resp = self._client.audio.transcriptions.create(
                model=settings.openai_transcribe_model,
                file=(filename, data),
                language=language or None,
            )
            text = getattr(resp, "text", None)
            return text.strip() if text else None
        except Exception as exc:
            logger.warning("Transcription failed: %s", exc)
            return None

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
