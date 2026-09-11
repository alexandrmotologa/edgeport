"""Integration test verifying end-to-end WebSocket proxy tunneling."""

import asyncio
import socket

import pytest
import uvicorn
import websockets
from starlette.applications import Starlette
from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocket

from edgeport.client.tunnel_client import TunnelClient
from edgeport.server.gateway import RelayGateway


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.asyncio
async def test_end_to_end_websocket_tunneling():
    relay_port = get_free_port()
    local_port = get_free_port()

    # 1. Local WebSocket Echo server (simulates Vite HMR or chat)
    async def echo_ws(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                msg = await websocket.receive()
                if "text" in msg and msg["text"]:
                    await websocket.send_text(f"echo:{msg['text']}")
                elif "bytes" in msg and msg["bytes"]:
                    await websocket.send_bytes(b"echo:" + msg["bytes"])
        except Exception:
            pass

    local_app = Starlette(routes=[WebSocketRoute("/ws-echo", echo_ws)])
    local_config = uvicorn.Config(
        local_app, host="127.0.0.1", port=local_port, log_level="error"
    )
    local_server = uvicorn.Server(local_config)
    local_task = asyncio.create_task(local_server.serve())

    # 2. Relay Gateway
    relay = RelayGateway(domain="localhost", port=relay_port)
    relay_config = uvicorn.Config(
        relay.app, host="127.0.0.1", port=relay_port, log_level="error"
    )
    relay_server = uvicorn.Server(relay_config)
    relay_task = asyncio.create_task(relay_server.serve())

    await asyncio.sleep(0.5)

    # 3. Tunnel Client
    subdomain = "ws-test"
    client = TunnelClient(
        relay_url=f"ws://127.0.0.1:{relay_port}/ws/tunnel",
        subdomain=subdomain,
        target_url=f"http://127.0.0.1:{local_port}",
    )
    connected_event = asyncio.Event()
    client.on_connected(lambda _: connected_event.set())
    client_task = asyncio.create_task(client.start())

    await asyncio.wait_for(connected_event.wait(), timeout=5.0)

    # 4. Connect external caller to public relay using subdomain query or header
    external_ws_url = f"ws://127.0.0.1:{relay_port}/ws-echo?subdomain={subdomain}"
    async with websockets.connect(external_ws_url) as ws:
        # Send text message
        await ws.send("hello_vite_hmr")
        resp = await asyncio.wait_for(ws.recv(), timeout=5.0)
        assert resp == "echo:hello_vite_hmr"

        # Send binary message
        await ws.send(b"binary_payload")
        resp_bytes = await asyncio.wait_for(ws.recv(), timeout=5.0)
        assert resp_bytes == b"echo:binary_payload"

    # Clean teardown
    await client.stop()
    client_task.cancel()
    relay_server.should_exit = True
    local_server.should_exit = True
    await asyncio.gather(relay_task, local_task, return_exceptions=True)
