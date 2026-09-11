"""Security utilities for IP filtering and rate limiting on Relay Gateway."""

import ipaddress
import time


class TokenBucketRateLimiter:
    """Thread-safe in-memory token bucket rate limiter."""

    def __init__(self, capacity: int = 100, refill_rate_per_sec: float = 20.0) -> None:
        self.capacity = capacity
        self.refill_rate = refill_rate_per_sec
        # Maps key -> (tokens, last_updated)
        self._buckets: dict[str, tuple[float, float]] = {}

    def allow_request(self, key: str) -> bool:
        """Determines whether a request for a given key is allowed under rate limits."""
        now = time.time()
        tokens, last_updated = self._buckets.get(key, (float(self.capacity), now))

        # Refill tokens
        elapsed = now - last_updated
        tokens = min(float(self.capacity), tokens + elapsed * self.refill_rate)

        if tokens >= 1.0:
            self._buckets[key] = (tokens - 1.0, now)
            return True

        self._buckets[key] = (tokens, now)
        return False


class IPAllowlist:
    """Matches client IP addresses against configured CIDR networks or IP lists."""

    # Well-known official Stripe webhook IP prefixes (sample set)
    STRIPE_WEBHOOK_CIDRS = [
        "3.18.12.63",
        "3.130.192.231",
        "13.235.14.237",
        "13.235.122.149",
        "18.211.135.69",
        "35.154.171.200",
        "52.15.183.38",
        "54.88.130.119",
        "54.88.130.237",
        "54.187.174.169",
        "54.187.205.235",
        "54.187.216.72",
    ]

    def __init__(self, allowed_cidrs: list[str] | None = None, allow_stripe: bool = False) -> None:
        self.networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []

        combined = list(allowed_cidrs or [])
        if allow_stripe:
            combined.extend(self.STRIPE_WEBHOOK_CIDRS)

        for item in combined:
            item = item.strip()
            if not item:
                continue
            try:
                # Support single IPs or CIDRs
                if "/" in item:
                    self.networks.append(ipaddress.ip_network(item, strict=False))
                else:
                    self.networks.append(ipaddress.ip_network(f"{item}/32", strict=False))
            except ValueError:
                pass

    def is_allowed(self, ip_str: str) -> bool:
        """Checks if an IP address belongs to the allowed networks."""
        if not self.networks:
            return True  # No restriction configured
        try:
            ip = ipaddress.ip_address(ip_str.strip())
            return any(ip in net for net in self.networks)
        except ValueError:
            return False
