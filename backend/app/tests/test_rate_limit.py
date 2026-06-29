"""Unit test for the token-bucket rate limiter's allow/deny logic."""
from __future__ import annotations

from app.core.rate_limit import RateLimitMiddleware


def test_token_bucket_allows_capacity_then_denies():
    # capacity=3, no refill within the test window.
    mw = RateLimitMiddleware(app=None, capacity=3, refill_per_second=0.0)
    allowed = [mw._allow("1.2.3.4") for _ in range(5)]
    assert allowed == [True, True, True, False, False]


def test_buckets_are_per_key():
    mw = RateLimitMiddleware(app=None, capacity=1, refill_per_second=0.0)
    assert mw._allow("a") is True
    assert mw._allow("a") is False
    # A different IP has its own bucket.
    assert mw._allow("b") is True
