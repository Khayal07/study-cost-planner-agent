"""Currency conversion via frankfurter.app (ECB data), with a DB cache.

Conversion is deterministic and auditable: rates are cached in `fx_rates` with the
date they apply to, so the Verifier can re-derive any conversion. On API failure we
fall back to the most recent cached rate and flag it as stale.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.data.models import FxRate

# Currencies with high short-term volatility — surfaced as FX risk notes.
VOLATILE_CURRENCIES = {"TRY", "ARS", "EGP", "NGN", "RUB", "VES"}


@dataclass
class Conversion:
    rate: float
    as_of: date | None
    status: str  # "identity" | "live" | "cache" | "stale"


class CurrencyService:
    def __init__(self, session: Session):
        self.session = session

    def get_rate(self, base: str, quote: str) -> Conversion:
        base, quote = base.upper(), quote.upper()
        if base == quote:
            return Conversion(1.0, date.today(), "identity")

        # 1) Fresh cache hit? ECB publishes once per business day, so a rate dated
        # within the last day is considered fresh.
        cached = self.session.scalar(
            select(FxRate)
            .where(FxRate.base == base, FxRate.quote == quote)
            .order_by(FxRate.as_of_date.desc())
        )
        if cached and cached.as_of_date >= date.today() - timedelta(days=1):
            return Conversion(float(cached.rate), cached.as_of_date, "cache")

        # 2) Fetch live from frankfurter
        try:
            resp = httpx.get(
                f"{settings.frankfurter_base_url}/latest",
                params={"from": base, "to": quote},
                timeout=10.0,
                follow_redirects=True,
            )
            resp.raise_for_status()
            payload = resp.json()
            rate = float(payload["rates"][quote])
            as_of = date.fromisoformat(payload["date"])
            self.session.add(FxRate(base=base, quote=quote, rate=rate, as_of_date=as_of))
            self.session.commit()
            return Conversion(rate, as_of, "live")
        except Exception:
            # 3) Fall back to the most recent cached rate, flagged stale
            if cached:
                return Conversion(float(cached.rate), cached.as_of_date, "stale")
            raise

    def convert(self, amount: float, base: str, quote: str) -> tuple[float, Conversion]:
        conv = self.get_rate(base, quote)
        return round(amount * conv.rate, 2), conv

    @staticmethod
    def is_volatile(currency: str) -> bool:
        return currency.upper() in VOLATILE_CURRENCIES
