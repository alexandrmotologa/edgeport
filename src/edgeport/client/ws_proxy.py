"""Forwarder for bidirectional WebSocket connections to local development servers."""

import asyncio
import base64
import logging

import websockets
from websockets.exceptions import ConnectionClosed

from edgeport.protocol.frames import Frame, FrameType
from edgeport.protocol.multiplexer import MultiplexedStream, StreamMultiplexer

logger = logging.getLogger("edgeport.ws_proxy")


class LocalWebSocketForwarder:
    """Bridges tunneled WebSocket streams to a local WebSocket server (e.g. Vite HMR)."""

    def __init__(self, target_base_url: str = "http://127.0.0.1:8080") -> None:
        # Convert http/https to ws/wss
        if target_base_url.startswith("https://"):
            self.target_ws_base = "wss://" + target_base_url[len("https://") :]
        elif target_base_url.startswith("http://"):
            self.target_ws_base = "ws://" + target_base_url[len("http://") :]
        else:
            self.target_ws_base = f"ws://{target_base_url.lstrip('/')}"
        self.target_ws_base = self.target_ws_base.rstrip("/")

    async def bridge_stream(
        self,
        stream: MultiplexedStream,
        open_frame: Frame,
        multiplexer: StreamMultiplexer,
    ) -> None:
        """Pipes WebSocket messages bidirectionally between tunnel and local service."""
        stream_id = stream.stream_id
        path = open_frame.payload.get("path", "/")
        query = open_frame.payload.get("query_string", "")
        target_ws_url = f"{self.target_ws_base}{path}"
        if query:
            target_ws_url = f"{target_ws_url}?{query}"

        try:
            async with websockets.connect(target_ws_url) as local_ws:
                # 1. Forward from local WebSocket -> tunnel multiplexer
                async def from_local_to_tunnel() -> None:
                    try:
                        async for message in local_ws:
                            if isinstance(message, str):
                                f = Frame(
                                    type=FrameType.WS_FRAME,
                                    stream_id=stream_id,
                                    payload={"data": message, "is_binary": False},
                                )
                                await multiplexer.send_frame(f)
                            else:
                                b64 = base64.b64encode(message).decode("ascii")
                                f = Frame(
                                    type=FrameType.WS_FRAME,
                                    stream_id=stream_id,
                                    payload={"data": b64, "is_binary": True},
                                )
                                await multiplexer.send_frame(f)
                    except (ConnectionClosed, asyncio.CancelledError):
                        pass
                    finally:
                        close_f = Frame(type=FrameType.WS_CLOSE, stream_id=stream_id)
                        try:
                            await multiplexer.send_frame(close_f)
                        except Exception:
                            pass

                # 2. Forward from tunnel multiplexer -> local WebSocket
                async def from_tunnel_to_local() -> None:
                    try:
                        while True:
                            f = await stream.get_inbound()
                            if f.type == FrameType.WS_FRAME:
                                is_binary = f.payload.get("is_binary", False)
                                raw_data = f.payload.get("data", "")
                                if is_binary:
                                    await local_ws.send(base64.b64decode(raw_data))
                                else:
                                    await local_ws.send(raw_data)
                            elif f.type in (FrameType.WS_CLOSE, FrameType.STREAM_RESET):
                                await local_ws.close()
                                break
                    except (ConnectionClosed, asyncio.CancelledError):
                        pass

                tasks = [
                    asyncio.create_task(from_local_to_tunnel()),
                    asyncio.create_task(from_tunnel_to_local()),
                ]
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for t in tasks:
                    t.cancel()

        except Exception as exc:
            logger.warning("Local WebSocket bridge error on %s: %s", target_ws_url, exc)
            close_f = Frame(type=FrameType.WS_CLOSE, stream_id=stream_id)
            try:
                await multiplexer.send_frame(close_f)
            except Exception:
                pass
        finally:
            await multiplexer.close_stream(stream_id)
