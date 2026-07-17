"""FastAPI application entry point.

Wires CORS, the health probe, and the feature routers. Routers are added as each
phase lands so the app stays runnable at every step.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.rate_limit import RateLimitMiddleware
from app.core.security_headers import SecurityHeadersMiddleware

def _docs_urls(is_production: bool) -> dict:
    """Interactive API docs config for FastAPI.

    Swagger UI (/docs), ReDoc (/redoc) and the raw OpenAPI schema (/openapi.json)
    hand a caller a complete map of every endpoint and its shape. That's handy in
    development but is needless attack-surface disclosure in production, so we turn
    all three off there and keep them on locally.
    """
    if is_production:
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {}


app = FastAPI(
    title="Study Cost Planning Agent",
    description="Multi-agent system that plans the *total* real cost of studying abroad, "
    "grounded in sourced data.",
    version="0.1.0",
    **_docs_urls(settings.is_production),
)

# Baseline hardening headers on every response (nosniff, deny framing, CSP, HSTS in prod).
app.add_middleware(SecurityHeadersMiddleware)

# Restrict to the configured frontend origin(s). Auth uses bearer tokens (not cookies),
# so credentials stay off; the tracker adds PUT/PATCH/DELETE to the served verbs. Only the
# headers the frontend actually sends are allowed.
_cors_origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Throttle the expensive public endpoints (per client IP, in-memory). /scholarships
# covers the paid live web-search endpoint; /auth blunts login brute-force attempts.
app.add_middleware(
    RateLimitMiddleware,
    protected_prefixes=("/plan", "/chat", "/export", "/scholarships", "/auth", "/forecast", "/letters", "/profile"),
    # Paid (LLM/vision/whisper/web-search) endpoints also get a per-IP daily ceiling
    # so the token bucket's refill can't let one client run up open-ended spend.
    paid_prefixes=("/plan", "/chat", "/export", "/scholarships", "/letters", "/profile"),
    paid_daily_limit=settings.paid_daily_limit_per_ip,
    trust_proxy_header=settings.trust_proxy_header,
)


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Liveness probe used by docker-compose and the frontend."""
    return {
        "status": "ok",
        "service": "study-cost-planner-backend",
        "llm_enabled": settings.llm_enabled,
        "report_currency": settings.default_report_currency,
    }


# Feature routers (added per phase)
from app.api.plan import router as plan_router
from app.api.chat import router as chat_router
from app.api.export import router as export_router
from app.api.auth import router as auth_router
from app.api.applications import router as applications_router
from app.api.meta import router as meta_router
from app.api.plans import router as plans_router
from app.api.scholarship_search import router as scholarship_search_router
from app.api.forecast import router as forecast_router
from app.api.letters import router as letters_router
from app.api.interview import router as interview_router
from app.api.transcript import router as transcript_router
from app.api.transcribe import router as transcribe_router

app.include_router(plan_router)
app.include_router(chat_router)
app.include_router(export_router)
app.include_router(auth_router)
app.include_router(applications_router)
app.include_router(meta_router)
app.include_router(plans_router)
app.include_router(scholarship_search_router)
app.include_router(forecast_router)
app.include_router(letters_router)
app.include_router(interview_router)
app.include_router(transcript_router)
app.include_router(transcribe_router)
