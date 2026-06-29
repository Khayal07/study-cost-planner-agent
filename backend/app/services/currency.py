"""Currency conversion via frankfurter.app (ECB data), with a DB cache.

Conversion is deterministic and auditable: rates are cached in `fx_rates` with the
date they apply to, so the Verifier can re-derive any conversion. On API failure we
fall back to the most recent cached rate and flag it as stale.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.data.models import FxRate

logger = logging.getLogger(__name__)

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
        # Per-request memo: rates don't change within a single plan, so each
        # (base, quote) pair is resolved once instead of re-querying the cache table
        # for every cost line (the Currency Agent converts many lines per candidate).
        self._memo: dict[tuple[str, str], Conversion] = {}

    def get_rate(self, base: str, quote: str) -> Conversion:
        base, quote = base.upper(), quote.upper()
        cached = self._memo.get((base, quote))
        if cached is not None:
            return cached
        conv = self._resolve_rate(base, quote)
        self._memo[(base, quote)] = conv
        return conv

    def _resolve_rate(self, base: str, quote: str) -> Conversion:
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

        # 2) Fetch live from frankfurter, with one retry for transient failures.
        last_exc: Exception | None = None
        for attempt in (1, 2):
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
            except Exception as exc:  # network, HTTP, or payload-parse error
                # Clear any half-applied insert so the session stays usable.
                self.session.rollback()
                last_exc = exc
                logger.warning(
                    "FX fetch %s->%s failed (attempt %d/2): %s", base, quote, attempt, exc
                )

        # 2b) Secondary provider for currencies frankfurter/ECB doesn't cover (e.g. AZN).
        # ECB pairs always succeed above, so this never changes their rates (parity).
        try:
            secondary = self._fetch_fallback(base, quote)
            if secondary is not None:
                return secondary
        except Exception as exc:
            self.session.rollback()
            logger.warning("Secondary FX %s->%s failed: %s", base, quote, exc)

        # 3) Fall back to the most recent cached rate, flagged stale.
        if cached:
            logger.warning(
                "FX %s->%s falling back to stale cache from %s: %s",
                base, quote, cached.as_of_date, last_exc,
            )
            return Conversion(float(cached.rate), cached.as_of_date, "stale")
        raise last_exc or RuntimeError(
            f"FX conversion {base}->{quote} failed: all providers unavailable and no cached rate"
        )

    def _fetch_fallback(self, base: str, quote: str) -> Conversion | None:
        """Resolve a pair via the secondary provider (covers non-ECB currencies).

        open.er-api.com returns every quote for a given base and needs no API key.
        Returns None if the provider can't supply this pair (caller then falls back
        to a stale cached rate or raises).
        """
        resp = httpx.get(
            f"{settings.fallback_fx_base_url}/latest/{base}",
            timeout=10.0,
            follow_redirects=True,
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("result") != "success":
            return None
        raw = payload.get("rates", {}).get(quote)
        if raw is None:
            return None
        rate = float(raw)

        as_of = date.today()
        ts = payload.get("time_last_update_unix")
        if isinstance(ts, (int, float)):
            try:
                as_of = datetime.fromtimestamp(ts, tz=timezone.utc).date()
            except (OverflowError, OSError, ValueError):
                pass

        self.session.add(FxRate(base=base, quote=quote, rate=rate, as_of_date=as_of))
        self.session.commit()
        logger.info("FX %s->%s resolved via fallback provider (%.4f)", base, quote, rate)
        return Conversion(rate, as_of, "live")

    def convert(self, amount: float, base: str, quote: str) -> tuple[float, Conversion]:
        conv = self.get_rate(base, quote)
        return round(amount * conv.rate, 2), conv

    @staticmethod
    def is_volatile(currency: str) -> bool:
        return currency.upper() in VOLATILE_CURRENCIES
