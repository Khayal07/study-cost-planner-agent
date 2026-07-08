"""Lightweight in-memory per-IP rate limiting (no external dependency).

Two layers, both per client IP and in-memory (single-instance; for multi-instance
deploys swap in a shared store, e.g. Redis):

- A token bucket that blunts short bursts on the expensive public endpoints
  (/plan, /chat, /export/pdf, ...).
- A daily counter that caps how many *paid* requests one IP can make per day
  (chat/plan/export/scholarships/interview/transcribe). The bucket refills and so
  can't bound daily spend on its own; this hard ceiling does.
"""
from __future__ import annotations

import time
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

_SECONDS_PER_DAY = 86_400


class _Bucket:
    __slots__ = ("tokens", "updated")

    def __init__(self, tokens: float, updated: float) -> None:
        self.tokens = tokens
        self.updated = updated


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token-bucket + daily-cap limiter for a fixed set of path prefixes."""

    def __init__(
        self,
        app,
        *,
        capacity: int = 30,
        refill_per_second: float = 0.5,
        protected_prefixes: tuple[str, ...] = ("/plan", "/chat", "/export"),
        paid_prefixes: tuple[str, ...] = (),
        paid_daily_limit: int = 0,
        trust_proxy_header: bool = False,
    ) -> None:
        super().__init__(app)
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self.protected_prefixes = protected_prefixes
        self.paid_prefixes = paid_prefixes
        self.paid_daily_limit = paid_daily_limit
        self.trust_proxy_header = trust_proxy_header
        self._buckets: dict[str, _Bucket] = {}
        # key -> [day_index, count] for the current UTC day.
        self._daily: dict[str, list[int]] = {}
        self._lock = Lock()

    def _client_ip(self, request: Request) -> str:
        # X-Forwarded-For is client-controlled unless a trusted proxy sets it, so a
        # spoofed value would hand out a fresh bucket per request. Only trust it when
        # explicitly configured to sit behind a proxy; otherwise use the peer address.
        if self.trust_proxy_header:
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

    def _allow_daily(self, key: str) -> bool:
        """True if the IP is under its paid-request ceiling for the current day."""
        if self.paid_daily_limit <= 0:
            return True
        day = int(time.time()) // _SECONDS_PER_DAY
        with self._lock:
            entry = self._daily.get(key)
            if entry is None or entry[0] != day:
                self._daily[key] = [day, 1]
                return True
            if entry[1] >= self.paid_daily_limit:
                return False
            entry[1] += 1
            return True

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if request.method != "OPTIONS":
            ip = None
            if any(path.startswith(p) for p in self.protected_prefixes):
                ip = self._client_ip(request)
                if not self._allow(ip):
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Too many requests — please slow down and try again shortly."},
                        headers={"Retry-After": "2"},
                    )
            if any(path.startswith(p) for p in self.paid_prefixes):
                if ip is None:
                    ip = self._client_ip(request)
                if not self._allow_daily(ip):
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Daily limit reached for this feature — please try again tomorrow."},
                        headers={"Retry-After": "3600"},
                    )
        return await call_next(request)
