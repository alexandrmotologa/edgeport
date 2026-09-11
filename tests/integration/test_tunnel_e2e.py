"""End-to-end integration tests verifying complete tunnel multiplexing and replay."""

import asyncio
import socket

import httpx
import pytest
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from edgeport.client.forwarder import LocalForwarder
from edgeport.client.replay import ReplayEngine
from edgeport.client.storage import TransactionStore
from edgeport.client.tunnel_client import TunnelClient
from edgeport.server.gateway import RelayGateway


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.asyncio
async def test_end_to_end_tunnel_concurrency_and_replay():
    relay_port = get_free_port()
    local_port = get_free_port()

    # 1. Local echo service
    async def local_handler(request: Request) -> JSONResponse:
        body = await request.body()
        return JSONResponse(
            {
                "echo_method": request.method,
                "echo_path": request.url.path,
                "echo_body": body.decode("utf-8") if body else "",
                "custom_header": request.headers.get("x-custom-test", ""),
            },
            status_code=200,
        )

    local_app = Starlette(
        routes=[Route("/{path:path}", local_handler, methods=["GET", "POST", "PUT", "DELETE"])]
    )
    local_config = uvicorn.Config(
        local_app, host="127.0.0.1", port=local_port, log_level="error"
    )
    local_server = uvicorn.Server(local_config)
    local_task = asyncio.create_task(local_server.serve())

    # 2. Relay Gateway server
    relay = RelayGateway(domain="localhost", port=relay_port)
    relay_config = uvicorn.Config(
        relay.app, host="127.0.0.1", port=relay_port, log_level="error"
    )
    relay_server = uvicorn.Server(relay_config)
    relay_task = asyncio.create_task(relay_server.serve())

    # Allow servers to bind
    await asyncio.sleep(0.5)

    # 3. Connect TunnelClient
    subdomain = "test-tunnel"
    store = TransactionStore()
    forwarder = LocalForwarder(target_base_url=f"http://127.0.0.1:{local_port}")
    replay_engine = ReplayEngine(forwarder=forwarder, store=store)

    client = TunnelClient(
        relay_url=f"ws://127.0.0.1:{relay_port}/ws/tunnel",
        subdomain=subdomain,
        target_url=f"http://127.0.0.1:{local_port}",
        store=store,
        forwarder=forwarder,
    )

    connected_event = asyncio.Event()
    client.on_connected(lambda _: connected_event.set())
    client_task = asyncio.create_task(client.start())

    # Wait for tunnel handshake to complete
    await asyncio.wait_for(connected_event.wait(), timeout=5.0)
    assert client.is_connected is True

    # 4. Execute 25 concurrent requests through the public relay
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{relay_port}", timeout=10.0) as http:
        async def send_single_request(idx: int) -> dict:
            headers = {
                "Host": f"{subdomain}.localhost:{relay_port}",
                "X-Custom-Test": f"req-{idx}",
            }
            resp = await http.post(
                f"/api/webhook/{idx}",
                headers=headers,
                json={"transaction_index": idx, "message": f"payload_{idx}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["echo_method"] == "POST"
            assert data["echo_path"] == f"/api/webhook/{idx}"
            assert data["custom_header"] == f"req-{idx}"
            return data

        # Send concurrent requests
        results = await asyncio.gather(*(send_single_request(i) for i in range(25)))
        assert len(results) == 25

    # 5. Verify captured transactions in client store
    assert len(store) == 25
    first_txn = store.all()[0]
    assert first_txn.response_status == 200

    # 6. Verify replay engine
    replay_res = await replay_engine.replay(first_txn.id)
    assert replay_res.original_id == first_txn.id
    assert replay_res.status_match is True
    assert replay_res.new_status == 200
    assert len(store) == 26  # Original 25 + 1 replayed

    # 7. Clean teardown
    await client.stop()
    client_task.cancel()
    relay_server.should_exit = True
    local_server.should_exit = True
    await asyncio.gather(relay_task, local_task, return_exceptions=True)
