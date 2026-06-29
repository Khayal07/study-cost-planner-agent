"""Lightweight in-memory per-IP rate limiting (no external dependency).

A token-bucket per client IP, applied only to the expensive public endpoints
(/plan, /chat, /export/pdf). This protects a single instance from accidental or
abusive bursts; for multi-instance deploys swap in a shared store (e.g. Redis).
"""
from __future__ import annotations

import time
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class _Bucket:
    __slots__ = ("tokens", "updated")

    def __init__(self, tokens: float, updated: float) -> None:
        self.tokens = tokens
        self.updated = updated


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token-bucket limiter for a fixed set of path prefixes."""

    def __init__(
        self,
        app,
        *,
        capacity: int = 30,
        refill_per_second: float = 0.5,
        protected_prefixes: tuple[str, ...] = ("/plan", "/chat", "/export"),
    ) -> None:
        super().__init__(app)
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self.protected_prefixes = protected_prefixes
        self._buckets: dict[str, _Bucket] = {}
        self._lock = Lock()

    def _client_ip(self, request: Request) -> str:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                self._buckets[key] = _Bucket(self.capacity - 1, now)
                return True
            elapsed = now - bucket.updated
            bucket.tokens = min(self.capacity, bucket.tokens + elapsed * self.refill_per_second)
            bucket.updated = now
            if bucket.tokens >= 1:
                bucket.tokens -= 1
                return True
            return False

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if request.method != "OPTIONS" and any(path.startswith(p) for p in self.protected_prefixes):
            if not self._allow(self._client_ip(request)):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests — please slow down and try again shortly."},
                    headers={"Retry-After": "2"},
                )
        return await call_next(request)
