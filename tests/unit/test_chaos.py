"""Unit tests for chaos fault and latency injection."""

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from edgeport.client.forwarder import LocalForwarder


@pytest.mark.asyncio
async def test_chaos_delay_injection():
    app = Starlette(routes=[Route("/test", lambda r: PlainTextResponse("ok"))])
    forwarder = LocalForwarder(target_base_url="http://testserver", chaos_delay_ms=100.0)
    import httpx
    forwarder._client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")

    status, _, _, duration = await forwarder.forward("GET", "/test")
    await forwarder.close()

    assert status == 200
    assert duration >= 90.0  # Injected delay of at least ~100ms


@pytest.mark.asyncio
async def test_chaos_mock_status_injection():
    forwarder = LocalForwarder(target_base_url="http://testserver", chaos_mock_status=429)
    status, _, body, _ = await forwarder.forward("GET", "/test")
    await forwarder.close()

    assert status == 429
    assert b"Simulated status 429" in body


@pytest.mark.asyncio
async def test_chaos_fail_rate_injection():
    forwarder = LocalForwarder(target_base_url="http://testserver", chaos_fail_rate=1.0)
    status, _, body, _ = await forwarder.forward("GET", "/test")
    await forwarder.close()

    assert status == 500
    assert b"Chaos Failure" in body
