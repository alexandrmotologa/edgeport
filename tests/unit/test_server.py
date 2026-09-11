"""Unit tests for Server authentication and registry components."""

import base64

from edgeport.protocol.multiplexer import StreamMultiplexer
from edgeport.server.auth import verify_basic_auth, verify_relay_token
from edgeport.server.registry import TunnelRegistry


def test_verify_relay_token():
    # No secret required
    assert verify_relay_token(None, None) is True
    assert verify_relay_token("anything", None) is True

    # Secret required
    secret = "my-secret-key-123"
    assert verify_relay_token(secret, secret) is True
    assert verify_relay_token("wrong", secret) is False
    assert verify_relay_token(None, secret) is False


def test_verify_basic_auth():
    # No auth required
    assert verify_basic_auth(None, None) is True

    # Auth required
    creds = "admin:secretpass"
    encoded = base64.b64encode(creds.encode("utf-8")).decode("ascii")
    header = f"Basic {encoded}"

    assert verify_basic_auth(header, creds) is True
    assert verify_basic_auth("Basic invalid", creds) is False
    assert verify_basic_auth(None, creds) is False


def test_registry_subdomain_resolution():
    registry = TunnelRegistry()

    # Resolution with domain localhost
    assert registry.resolve_subdomain("demo.localhost:8000", "localhost") == "demo"
    assert registry.resolve_subdomain("localhost:8000", "localhost") is None

    # Resolution with custom domain
    assert registry.resolve_subdomain("api.myapp.example.com", "example.com") == "myapp"
    assert registry.resolve_subdomain("checkout.example.com:443", "example.com") == "checkout"
    assert registry.resolve_subdomain("example.com", "example.com") is None


def test_registry_registration_and_grace_period():
    registry = TunnelRegistry(grace_period_seconds=10.0)
    mux = StreamMultiplexer()

    # Reserved subdomains
    assert registry.is_available("api") is False
    assert registry.is_available("admin") is False

    # Available subdomain
    assert registry.is_available("coolapp") is True

    # Register
    tunnel = registry.register(
        subdomain="coolapp",
        websocket=None,
        multiplexer=mux,
        token="tok1",
    )
    assert tunnel.subdomain == "coolapp"
    assert registry.is_available("coolapp") is False
    assert registry.get("coolapp") is not None

    # Unregister triggers grace period
    registry.unregister("coolapp")
    assert registry.get("coolapp") is None

    # Reconnect with same token within grace period is allowed
    assert registry.is_available("coolapp", token="tok1") is True
    # Reconnect with different token is rejected
    assert registry.is_available("coolapp", token="tok2") is False
