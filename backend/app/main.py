"""FastAPI application entry point.

Wires CORS, the health probe, and the feature routers. Routers are added as each
phase lands so the app stays runnable at every step.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.rate_limit import RateLimitMiddleware

app = FastAPI(
    title="Study Cost Planning Agent",
    description="Multi-agent system that plans the *total* real cost of studying abroad, "
    "grounded in sourced data.",
    version="0.1.0",
)

# Restrict to the configured frontend origin(s). Auth uses bearer tokens (not cookies),
# so credentials stay off; the tracker adds PUT/PATCH/DELETE to the served verbs.
_cors_origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)

# Throttle the expensive public endpoints (per client IP, in-memory).
# /scholarships covers the paid live web-search endpoint.
app.add_middleware(
    RateLimitMiddleware,
    protected_prefixes=("/plan", "/chat", "/export", "/scholarships"),
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

app.include_router(plan_router)
app.include_router(chat_router)
app.include_router(export_router)
app.include_router(auth_router)
app.include_router(applications_router)
app.include_router(meta_router)
app.include_router(plans_router)
app.include_router(scholarship_search_router)
