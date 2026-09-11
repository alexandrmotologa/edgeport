"""Tunnel registry and subdomain routing table."""

import time
from dataclasses import dataclass
from typing import Any

from edgeport.protocol.multiplexer import StreamMultiplexer

RESERVED_SUBDOMAINS = {
    "api",
    "admin",
    "www",
    "app",
    "_edgeport",
    "relay",
    "gateway",
    "static",
    "ws",
    "dashboard",
}


@dataclass
class ActiveTunnel:
    """Represents an active reverse tunnel registered with the relay."""

    subdomain: str
    websocket: Any  # Starlette WebSocket or websockets connection
    multiplexer: StreamMultiplexer
    registered_at: float
    basic_auth: str | None = None
    token: str | None = None
    client_ip: str = ""


class TunnelRegistry:
    """Thread-safe registry for connected tunnel clients and subdomains."""

    def __init__(self, grace_period_seconds: float = 60.0) -> None:
        self._tunnels: dict[str, ActiveTunnel] = {}
        self._grace_period_seconds = grace_period_seconds
        # Maps subdomain -> (expiry_timestamp, optional_token)
        self._grace_subdomains: dict[str, tuple[float, str | None]] = {}

    def is_available(self, subdomain: str, token: str | None = None) -> bool:
        """Checks if a subdomain is available to be claimed."""
        sub = subdomain.lower().strip()
        if sub in RESERVED_SUBDOMAINS:
            return False

        # Clean expired grace periods
        self._clean_expired_grace()

        if sub in self._tunnels:
            return False

        if sub in self._grace_subdomains:
            expiry, reserved_token = self._grace_subdomains[sub]
            # Can be reclaimed by the same token
            if reserved_token and token and reserved_token == token:
                return True
            return False

        return True

    def register(
        self,
        subdomain: str,
        websocket: Any,
        multiplexer: StreamMultiplexer,
        basic_auth: str | None = None,
        token: str | None = None,
        client_ip: str = "",
    ) -> ActiveTunnel:
        """Registers an active client tunnel."""
        sub = subdomain.lower().strip()
        tunnel = ActiveTunnel(
            subdomain=sub,
            websocket=websocket,
            multiplexer=multiplexer,
            registered_at=time.time(),
            basic_auth=basic_auth,
            token=token,
            client_ip=client_ip,
        )
        self._tunnels[sub] = tunnel
        self._grace_subdomains.pop(sub, None)
        return tunnel

    def unregister(self, subdomain: str) -> None:
        """Unregisters an active client tunnel and starts grace period."""
        sub = subdomain.lower().strip()
        tunnel = self._tunnels.pop(sub, None)
        if tunnel:
            # Grant grace period to allow quick client reconnection
            self._grace_subdomains[sub] = (
                time.time() + self._grace_period_seconds,
                tunnel.token,
            )

    def get(self, subdomain: str) -> ActiveTunnel | None:
        """Retrieves an active tunnel by subdomain."""
        return self._tunnels.get(subdomain.lower().strip())

    def resolve_subdomain(self, host: str, root_domain: str = "localhost") -> str | None:
        """Resolves subdomain from incoming HTTP Host header.

        Examples:
        - "myapp.example.com" with root "example.com" -> "myapp"
        - "test.localhost:8000" with root "localhost" -> "test"
        - "localhost:8000" with root "localhost" -> None
        """
        if not host:
            return None

        # Strip port if present
        host_no_port = host.split(":", 1)[0].lower().strip()
        root_no_port = root_domain.split(":", 1)[0].lower().strip()

        if host_no_port == root_no_port:
            return None

        if host_no_port.endswith(f".{root_no_port}"):
            sub = host_no_port[: -len(f".{root_no_port}")]
            # In case of nested subdomains, take the leftmost part
            return sub.split(".")[-1]

        return None

    def _clean_expired_grace(self) -> None:
        now = time.time()
        expired = [sub for sub, (expiry, _) in self._grace_subdomains.items() if now > expiry]
        for sub in expired:
            self._grace_subdomains.pop(sub, None)

    @property
    def active_tunnel_count(self) -> int:
        return len(self._tunnels)
