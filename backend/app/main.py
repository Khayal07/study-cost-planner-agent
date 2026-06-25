"""FastAPI application entry point.

Wires CORS, the health probe, and the feature routers. Routers are added as each
phase lands so the app stays runnable at every step.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

app = FastAPI(
    title="Study Cost Planning Agent",
    description="Multi-agent system that plans the *total* real cost of studying abroad, "
    "grounded in sourced data.",
    version="0.1.0",
)

# Restrict to the configured frontend origin(s). The app uses no cookies/auth, so
# credentials are off; only the two verbs the API actually serves are allowed.
_cors_origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
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

app.include_router(plan_router)
app.include_router(chat_router)
app.include_router(export_router)
