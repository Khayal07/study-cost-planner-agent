"""Cost forecast endpoint: POST /forecast.

Deterministic inflation projection from static per-country assumptions; the
optional AI commentary is the only LLM call and is off by default. Rate-limited
via the /forecast prefix in main.py.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.core.schemas import ForecastRequest, ForecastResponse
from app.services.forecast import build_forecast

router = APIRouter(prefix="/forecast", tags=["forecast"])


@router.post("", response_model=ForecastResponse)
def forecast(request: ForecastRequest) -> ForecastResponse:
    return build_forecast(request)
