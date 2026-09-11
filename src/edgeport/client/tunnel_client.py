"""Persistent WebSocket tunnel client connecting developer machine to relay."""

import asyncio
import base64
import logging
import time
from collections.abc import Callable

import websockets
from websockets.exceptions import ConnectionClosed

from edgeport.protocol.frames import (
    Frame,
    FrameType,
    RegisterTunnelPayload,
    StreamHeadersPayload,
)
from edgeport.protocol.multiplexer import StreamMultiplexer
from edgeport.protocol.serializer import decode_frame, encode_frame

from .forwarder import LocalForwarder
from .storage import CapturedTransaction, TransactionStore

logger = logging.getLogger("edgeport.client")


class TunnelClient:
    """Manages outbound reverse tunnel connection to a public EdgePort relay."""

    def __init__(
        self,
        relay_url: str = "ws://localhost:8000/ws/tunnel",
        subdomain: str = "demo",
        target_url: str = "http://127.0.0.1:8080",
        token: str | None = None,
        basic_auth: str | None = None,
        store: TransactionStore | None = None,
        forwarder: LocalForwarder | None = None,
    ) -> None:
        self.relay_url = relay_url
        self.subdomain = subdomain
        self.target_url = target_url
        self.token = token
        self.basic_auth = basic_auth
        self.store = store if store is not None else TransactionStore()
        self.forwarder = (
            forwarder
            if forwarder is not None
            else LocalForwarder(target_base_url=target_url)
        )

        self.public_url: str | None = None
        self.is_connected = False
        self._running = False
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._multiplexer: StreamMultiplexer | None = None

        self._connected_callbacks: list[Callable[[str], None]] = []
        self._disconnected_callbacks: list[Callable[[], None]] = []
        self._error_callbacks: list[Callable[[str], None]] = []

    def on_connected(self, callback: Callable[[str], None]) -> None:
        self._connected_callbacks.append(callback)

    def on_disconnected(self, callback: Callable[[], None]) -> None:
        self._disconnected_callbacks.append(callback)

    def on_error(self, callback: Callable[[str], None]) -> None:
        self._error_callbacks.append(callback)

    async def start(self) -> None:
        """Starts the persistent tunnel connection loop with automatic reconnect."""
        self._running = True
        backoff = 1.0
        max_backoff = 30.0

        while self._running:
            try:
                await self._connect_and_run()
                backoff = 1.0  # Reset backoff on successful session
            except (ConnectionClosed, OSError) as exc:
                self.is_connected = False
                for cb in self._disconnected_callbacks:
                    cb()
                if not self._running:
                    break
                logger.warning(
                    "Tunnel connection lost (%s). Reconnecting in %.1fs...",
                    exc,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
            except Exception as exc:
                logger.error("Unexpected tunnel error: %s", exc)
                for cb in self._error_callbacks:
                    cb(str(exc))
                if not self._running:
                    break
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

    async def stop(self) -> None:
        """Stops the client and closes connections."""
        self._running = False
        if self._ws:
            await self._ws.close()
        await self.forwarder.close()

    async def _connect_and_run(self) -> None:
        async with websockets.connect(self.relay_url) as ws:
            self._ws = ws

            async def send_raw(payload: str | bytes) -> None:
                if isinstance(payload, bytes):
                    await ws.send(payload)
                else:
                    await ws.send(payload)

            self._multiplexer = StreamMultiplexer(send_raw_callback=send_raw, is_server=False)

            # Send registration handshake
            reg_frame = Frame(
                type=FrameType.REGISTER_TUNNEL,
                payload=RegisterTunnelPayload(
                    subdomain=self.subdomain,
                    token=self.token,
                    basic_auth=self.basic_auth,
                ).model_dump(),
            )
            await ws.send(encode_frame(reg_frame))

            # Await handshake response
            first_msg = await ws.recv()
            resp_frame = decode_frame(first_msg)

            if resp_frame.type == FrameType.TUNNEL_ERROR:
                err_msg = resp_frame.payload.get("message", "Registration rejected")
                logger.error("Relay registration failed: %s", err_msg)
                for cb in self._error_callbacks:
                    cb(err_msg)
                raise ConnectionError(f"Tunnel registration failed: {err_msg}")

            if resp_frame.type != FrameType.TUNNEL_READY:
                raise ConnectionError(f"Unexpected handshake response: {resp_frame.type}")

            self.public_url = resp_frame.payload.get("public_url")
            self.is_connected = True

            for cb in self._connected_callbacks:
                cb(self.public_url or "")

            # Run reader and heartbeat concurrently
            tasks = [
                asyncio.create_task(self._reader_loop(ws)),
                asyncio.create_task(self._heartbeat_loop(ws)),
            ]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
            for t in done:
                t.result()

    async def _heartbeat_loop(self, ws: websockets.WebSocketClientProtocol) -> None:
        while self._running:
            await asyncio.sleep(15)
            ping_frame = Frame(type=FrameType.PING, payload={"timestamp": time.time()})
            await ws.send(encode_frame(ping_frame))

    async def _reader_loop(self, ws: websockets.WebSocketClientProtocol) -> None:
        assert self._multiplexer is not None
        while self._running:
            raw_msg = await ws.recv()
            frame = decode_frame(raw_msg)

            if frame.stream_id == 0:
                await self._multiplexer.handle_inbound_frame(frame)
                continue

            stream = self._multiplexer.get_stream(frame.stream_id)

            if frame.type == FrameType.STREAM_OPEN:
                stream = await self._multiplexer.create_stream(frame.stream_id)
                # Spawn worker to handle this stream
                asyncio.create_task(self._handle_incoming_stream(stream, frame))
            elif stream:
                stream.push_inbound(frame)

    async def _handle_incoming_stream(self, stream, open_frame: Frame) -> None:
        assert self._multiplexer is not None
        stream_id = stream.stream_id
        method = open_frame.payload.get("method", "GET")
        path = open_frame.payload.get("path", "/")
        headers = open_frame.payload.get("headers", {})
        query_string = open_frame.payload.get("query_string", "")

        # Collect body chunks until STREAM_END
        body_chunks = []
        try:
            while True:
                f = await stream.get_inbound(timeout=30.0)
                if f.type == FrameType.STREAM_DATA:
                    chunk_b64 = f.payload.get("chunk", "")
                    body_chunks.append(base64.b64decode(chunk_b64))
                elif f.type in (FrameType.STREAM_END, FrameType.STREAM_RESET):
                    break

            req_body = b"".join(body_chunks)

            # Forward to local service
            status, resp_headers, resp_body, duration_ms = await self.forwarder.forward(
                method=method,
                path=path,
                query_string=query_string,
                headers=headers,
                body=req_body,
            )

            # Send response headers back to relay
            hdr_frame = Frame(
                type=FrameType.STREAM_HEADERS,
                stream_id=stream_id,
                payload=StreamHeadersPayload(
                    status=status,
                    headers=resp_headers,
                ).model_dump(),
            )
            await self._multiplexer.send_frame(hdr_frame)

            # Send response body chunks back to relay
            if resp_body:
                await self._multiplexer.send_binary_data(stream_id, resp_body)

            # Send end frame
            await self._multiplexer.send_binary_end(stream_id)

            # Store captured transaction
            txn = CapturedTransaction(
                method=method,
                path=path,
                query_string=query_string,
                request_headers=headers,
                request_body=req_body,
                response_status=status,
                response_headers=resp_headers,
                response_body=resp_body,
                duration_ms=duration_ms,
            )
            self.store.add(txn)

        except Exception as exc:
            logger.error("Stream handling error on stream %d: %s", stream_id, exc)
            reset_frame = Frame(
                type=FrameType.STREAM_RESET,
                stream_id=stream_id,
                payload={"reason": str(exc)},
            )
            try:
                await self._multiplexer.send_frame(reset_frame)
            except Exception:
                pass
        finally:
            await self._multiplexer.close_stream(stream_id)
