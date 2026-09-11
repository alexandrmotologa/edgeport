"""Unit tests for ReplayEngine and response diffs."""

import httpx
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from edgeport.client.forwarder import LocalForwarder
from edgeport.client.replay import ReplayEngine
from edgeport.client.storage import CapturedTransaction, TransactionStore


@pytest.mark.asyncio
async def test_replay_engine_success_and_diff():
    call_count = 0

    # Local service that returns different counter on each call
    async def echo_counter(request: Request):
        nonlocal call_count
        call_count += 1
        return JSONResponse({"count": call_count, "action": "processed"})

    app = Starlette(routes=[Route("/api/test", echo_counter, methods=["POST"])])

    forwarder = LocalForwarder(target_base_url="http://testserver")
    forwarder._client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")

    store = TransactionStore()

    # Initial transaction
    original_txn = CapturedTransaction(
        method="POST",
        path="/api/test",
        request_headers={"content-type": "application/json"},
        request_body=b'{"init": true}',
        response_status=200,
        response_body=b'{"count": 0, "action": "processed"}',
    )
    store.add(original_txn)

    # Replay
    engine = ReplayEngine(forwarder=forwarder, store=store)
    result = await engine.replay(original_txn.id)
    await forwarder.close()

    assert result.original_id == original_txn.id
    assert result.status_match is True
    assert result.original_status == 200
    assert result.new_status == 200
    assert len(store) == 2  # Original + replayed
    assert "count" in result.body_diff
