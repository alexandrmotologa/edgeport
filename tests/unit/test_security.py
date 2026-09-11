"""Unit tests for rate limiting and IP allowlisting."""

import time

from edgeport.server.security import IPAllowlist, TokenBucketRateLimiter


def test_token_bucket_rate_limiter():
    limiter = TokenBucketRateLimiter(capacity=3, refill_rate_per_sec=10.0)

    # First 3 allowed
    assert limiter.allow_request("sub1") is True
    assert limiter.allow_request("sub1") is True
    assert limiter.allow_request("sub1") is True
    # 4th rejected immediately
    assert limiter.allow_request("sub1") is False

    # Different key allowed
    assert limiter.allow_request("sub2") is True

    # After small wait, refilled
    time.sleep(0.15)
    assert limiter.allow_request("sub1") is True


def test_ip_allowlist_matching():
    # Empty allowlist allows all
    open_list = IPAllowlist()
    assert open_list.is_allowed("1.2.3.4") is True

    # Configured CIDRs
    allowlist = IPAllowlist(allowed_cidrs=["192.168.1.0/24", "10.0.0.5"], allow_stripe=True)

    assert allowlist.is_allowed("192.168.1.50") is True
    assert allowlist.is_allowed("10.0.0.5") is True
    assert allowlist.is_allowed("10.0.0.6") is False
    assert allowlist.is_allowed("8.8.8.8") is False

    # Stripe webhook IP
    assert allowlist.is_allowed("54.187.174.169") is True
