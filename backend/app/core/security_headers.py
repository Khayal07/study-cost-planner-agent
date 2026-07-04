"""Baseline HTTP security headers for every API response.

The API only ever returns JSON or a PDF attachment — it never serves HTML that a
browser renders as a document — so the policy can be strict: deny framing, forbid
MIME sniffing, and lock the (unused) content sources down. HSTS is emitted only in
production, where the API is expected to be served over HTTPS.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import settings

_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # API responses are never rendered as a document; forbid all sources + framing.
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach a fixed set of hardening headers to each response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for name, value in _HEADERS.items():
            response.headers.setdefault(name, value)
        if settings.environment.lower() == "production":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        return response
