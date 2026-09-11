"""Unit tests for LocalForwarder."""

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from edgeport.client.forwarder import LocalForwarder


@pytest.mark.asyncio
async def test_forwarder_refused_connection():
    # Attempting to forward to a port with no listener
    forwarder = LocalForwarder(target_base_url="http://127.0.0.1:59999", timeout=1.0)
    status, _, body, duration = await forwarder.forward("GET", "/test")
    await forwarder.close()

    assert status in (502, 504)
    assert duration > 0


@pytest.mark.asyncio
async def test_forwarder_success_with_transport():
    # Build test ASGI app
    async def handler(request: Request):
        data = await request.json()
        return JSONResponse({"echo": data, "query": request.query_params.get("q")}, status_code=201)

    app = Starlette(routes=[Route("/api/echo", handler, methods=["POST"])])

    # Test LocalForwarder by injecting ASGI transport into httpx client
    forwarder = LocalForwarder(target_base_url="http://testserver")
    import httpx
    forwarder._client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")

    status, headers, body, duration = await forwarder.forward(
        method="POST",
        path="/api/echo",
        query_string="q=test",
        headers={"content-type": "application/json"},
        body=b'{"hello": "world"}',
    )
    await forwarder.close()

    assert status == 201
    assert b'"hello":"world"' in body
    assert b'"query":"test"' in body
    assert duration >= 0
