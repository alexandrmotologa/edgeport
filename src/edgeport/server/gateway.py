"""Public Relay Gateway handling HTTP reverse proxying and WebSocket tunnels."""

import asyncio
import base64
import logging
import time
from collections.abc import AsyncGenerator

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    Response,
    StreamingResponse,
)
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from edgeport.protocol.frames import (
    Frame,
    FrameType,
    RegisterTunnelPayload,
    TunnelErrorPayload,
    TunnelReadyPayload,
)
from edgeport.protocol.multiplexer import StreamMultiplexer
from edgeport.protocol.serializer import decode_frame, encode_frame

from .admin import render_admin_html
from .auth import verify_basic_auth, verify_relay_token
from .registry import TunnelRegistry
from .security import IPAllowlist, TokenBucketRateLimiter

logger = logging.getLogger("edgeport.relay")


class RelayGateway:
    """Public reverse proxy server and WebSocket tunnel manager."""

    def __init__(
        self,
        domain: str = "localhost",
        port: int = 8000,
        relay_secret: str | None = None,
        request_timeout: float = 30.0,
        ip_allowlist: IPAllowlist | None = None,
        rate_limiter: TokenBucketRateLimiter | None = None,
    ) -> None:
        self.domain = domain
        self.port = port
        self.relay_secret = relay_secret
        self.request_timeout = request_timeout
        self.registry = TunnelRegistry()
        self.ip_allowlist = ip_allowlist
        self.rate_limiter = rate_limiter

        # Build Starlette application
        self.app = Starlette(
            routes=[
                WebSocketRoute("/ws/tunnel", self._handle_tunnel_websocket),
                Route("/_edgeport/health", self._handle_health, methods=["GET"]),
                Route("/_edgeport/stats", self._handle_stats, methods=["GET"]),
                Route("/_edgeport/admin", self._handle_admin_dashboard, methods=["GET"]),
                Route("/api/admin/tunnels", self._handle_admin_list_tunnels, methods=["GET"]),
                Route(
                    "/api/admin/tunnels/{subdomain}/disconnect",
                    self._handle_admin_disconnect,
                    methods=["POST"],
                ),
                Route(
                    "/{path:path}",
                    self._handle_http_proxy,
                    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
                ),
                WebSocketRoute("/{path:path}", self._handle_ws_proxy),
            ]
        )

    async def _handle_health(self, request: Request) -> Response:
        return JSONResponse(
            {
                "status": "healthy",
                "version": "0.1.0",
                "active_tunnels": self.registry.active_tunnel_count,
            }
        )

    async def _handle_stats(self, request: Request) -> Response:
        return JSONResponse(
            {
                "domain": self.domain,
                "port": self.port,
                "active_tunnels": self.registry.active_tunnel_count,
            }
        )

    async def _handle_admin_dashboard(self, request: Request) -> Response:
        return HTMLResponse(render_admin_html())

    async def _handle_admin_list_tunnels(self, request: Request) -> Response:
        tunnels_data = []
        for sub, t in self.registry._tunnels.items():
            tunnels_data.append(
                {
                    "subdomain": sub,
                    "client_ip": t.client_ip,
                    "registered_at": t.registered_at,
                    "has_basic_auth": bool(t.basic_auth),
                }
            )
        return JSONResponse({"domain": self.domain, "tunnels": tunnels_data})

    async def _handle_admin_disconnect(self, request: Request) -> Response:
        subdomain = request.path_params.get("subdomain", "")
        tunnel = self.registry.get(subdomain)
        if tunnel:
            try:
                await tunnel.websocket.close(code=1000)
            except Exception:
                pass
            self.registry.unregister(subdomain)
            return JSONResponse({"status": "disconnected", "subdomain": subdomain})
        return JSONResponse({"error": "Tunnel not found"}, status_code=404)

    async def _handle_tunnel_websocket(self, websocket: WebSocket) -> None:
        await websocket.accept()
        tunnel_subdomain: str | None = None

        async def send_raw(payload: str | bytes) -> None:
            if isinstance(payload, bytes):
                await websocket.send_bytes(payload)
            else:
                await websocket.send_text(payload)

        multiplexer = StreamMultiplexer(send_raw_callback=send_raw, is_server=True)

        try:
            # First message must be REGISTER_TUNNEL
            first_msg = await websocket.receive_text()
            frame = decode_frame(first_msg)

            if frame.type != FrameType.REGISTER_TUNNEL:
                err = Frame(
                    type=FrameType.TUNNEL_ERROR,
                    payload=TunnelErrorPayload(
                        code="INVALID_HANDSHAKE",
                        message="First message must be REGISTER_TUNNEL",
                    ).model_dump(),
                )
                await websocket.send_text(encode_frame(err))
                await websocket.close()
                return

            reg_data = RegisterTunnelPayload(**frame.payload)

            # Check token authentication
            if not verify_relay_token(reg_data.token, self.relay_secret):
                err = Frame(
                    type=FrameType.TUNNEL_ERROR,
                    payload=TunnelErrorPayload(
                        code="UNAUTHORIZED",
                        message="Invalid or missing relay authentication token",
                    ).model_dump(),
                )
                await websocket.send_text(encode_frame(err))
                await websocket.close()
                return

            sub = reg_data.subdomain.lower().strip()
            if not self.registry.is_available(sub, reg_data.token):
                err = Frame(
                    type=FrameType.TUNNEL_ERROR,
                    payload=TunnelErrorPayload(
                        code="SUBDOMAIN_UNAVAILABLE",
                        message=f"Subdomain '{sub}' is already in use or reserved",
                    ).model_dump(),
                )
                await websocket.send_text(encode_frame(err))
                await websocket.close()
                return

            # Register tunnel
            client_ip = websocket.client.host if websocket.client else "unknown"
            self.registry.register(
                subdomain=sub,
                websocket=websocket,
                multiplexer=multiplexer,
                basic_auth=reg_data.basic_auth,
                token=reg_data.token,
                client_ip=client_ip,
            )
            tunnel_subdomain = sub

            public_url = (
                f"http://{sub}.{self.domain}:{self.port}"
                if self.port not in (80, 443)
                else f"http://{sub}.{self.domain}"
            )

            ready_frame = Frame(
                type=FrameType.TUNNEL_READY,
                payload=TunnelReadyPayload(
                    subdomain=sub,
                    public_url=public_url,
                    assigned_at=time.time(),
                ).model_dump(),
            )
            await websocket.send_text(encode_frame(ready_frame))

            # Main receive loop
            while True:
                msg = await websocket.receive()
                if "text" in msg and msg["text"]:
                    f = decode_frame(msg["text"])
                    await multiplexer.handle_inbound_frame(f)
                elif "bytes" in msg and msg["bytes"]:
                    f = decode_frame(msg["bytes"])
                    await multiplexer.handle_inbound_frame(f)

        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except Exception as exc:
            logger.warning("Tunnel connection error: %s", exc)
        finally:
            if tunnel_subdomain:
                self.registry.unregister(tunnel_subdomain)

    async def _handle_http_proxy(self, request: Request) -> Response:
        subdomain = request.query_params.get("subdomain")
        if not subdomain:
            subdomain = request.headers.get("x-edgeport-subdomain")
        if not subdomain:
            host = request.headers.get("host", "")
            subdomain = self.registry.resolve_subdomain(host, self.domain)

        if not subdomain:
            msg = (
                f"EdgePort Relay Gateway\nStatus: Healthy\n"
                f"Active Tunnels: {self.registry.active_tunnel_count}\n"
            )
            return PlainTextResponse(msg)

        # 1. IP Allowlist check
        client_ip = request.client.host if request.client else ""
        if self.ip_allowlist and not self.ip_allowlist.is_allowed(client_ip):
            return PlainTextResponse("403 Forbidden: IP address not allowed", status_code=403)

        # 2. Rate Limiting check
        if self.rate_limiter and not self.rate_limiter.allow_request(subdomain):
            return PlainTextResponse("429 Too Many Requests: Rate limit exceeded", status_code=429)

        tunnel = self.registry.get(subdomain)
        if not tunnel:
            return PlainTextResponse(
                f"EdgePort: Subdomain '{subdomain}' is not connected or offline.",
                status_code=502,
            )

        # Enforce basic auth if configured
        auth_header = request.headers.get("authorization")
        if tunnel.basic_auth and not verify_basic_auth(auth_header, tunnel.basic_auth):
            return Response(
                "Authentication Required",
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="EdgePort Protected Tunnel"'},
            )

        # Create multiplexed stream
        multiplexer = tunnel.multiplexer
        stream_id = multiplexer.next_stream_id()
        stream = await multiplexer.create_stream(stream_id)

        try:
            body_bytes = await request.body()

            hop_by_hop = {"connection", "upgrade", "keep-alive", "transfer-encoding"}
            proxy_headers = {
                k.lower(): v
                for k, v in request.headers.items()
                if k.lower() not in hop_by_hop
            }

            open_frame = Frame(
                type=FrameType.STREAM_OPEN,
                stream_id=stream_id,
                payload={
                    "method": request.method,
                    "path": request.url.path,
                    "headers": proxy_headers,
                    "query_string": request.url.query,
                    "remote_ip": client_ip,
                },
            )
            await multiplexer.send_frame(open_frame)

            if body_bytes:
                await multiplexer.send_binary_data(stream_id, body_bytes)

            await multiplexer.send_binary_end(stream_id)

            first_frame = await stream.get_inbound(timeout=self.request_timeout)

            if first_frame.type != FrameType.STREAM_HEADERS:
                return PlainTextResponse("Invalid response from tunnel client", status_code=502)

            status_code = first_frame.payload.get("status", 200)
            raw_resp_headers = first_frame.payload.get("headers", {})

            resp_headers = {
                k: v for k, v in raw_resp_headers.items() if k.lower() not in hop_by_hop
            }

            async def body_generator() -> AsyncGenerator[bytes, None]:
                try:
                    while True:
                        frame = await stream.get_inbound(timeout=self.request_timeout)
                        if frame.type == FrameType.STREAM_DATA:
                            chunk_b64 = frame.payload.get("chunk", "")
                            yield base64.b64decode(chunk_b64)
                        elif frame.type in (FrameType.STREAM_END, FrameType.STREAM_RESET):
                            break
                finally:
                    await multiplexer.close_stream(stream_id)

            return StreamingResponse(
                body_generator(),
                status_code=status_code,
                headers=resp_headers,
            )

        except asyncio.TimeoutError:
            await multiplexer.close_stream(stream_id)
            return PlainTextResponse("504 Gateway Timeout: Tunnel did not respond", status_code=504)
        except Exception as exc:
            logger.error("Error proxying request on stream %d: %s", stream_id, exc)
            await multiplexer.close_stream(stream_id)
            return PlainTextResponse(f"502 Bad Gateway: {exc}", status_code=502)

    async def _handle_ws_proxy(self, websocket: WebSocket) -> None:
        subdomain = websocket.query_params.get("subdomain")
        if not subdomain:
            subdomain = websocket.headers.get("x-edgeport-subdomain")
        if not subdomain:
            host = websocket.headers.get("host", "")
            subdomain = self.registry.resolve_subdomain(host, self.domain)

        if not subdomain:
            await websocket.close(code=1008)
            return

        tunnel = self.registry.get(subdomain)
        if not tunnel:
            await websocket.close(code=1011)
            return

        await websocket.accept()

        multiplexer = tunnel.multiplexer
        stream_id = multiplexer.next_stream_id()
        stream = await multiplexer.create_stream(stream_id)

        try:
            # Send WS_OPEN frame
            open_frame = Frame(
                type=FrameType.WS_OPEN,
                stream_id=stream_id,
                payload={
                    "path": websocket.url.path,
                    "query_string": websocket.url.query,
                    "headers": dict(websocket.headers),
                },
            )
            await multiplexer.send_frame(open_frame)

            async def from_external_to_tunnel() -> None:
                try:
                    while True:
                        msg = await websocket.receive()
                        if "text" in msg and msg["text"]:
                            f = Frame(
                                type=FrameType.WS_FRAME,
                                stream_id=stream_id,
                                payload={"data": msg["text"], "is_binary": False},
                            )
                            await multiplexer.send_frame(f)
                        elif "bytes" in msg and msg["bytes"]:
                            b64_data = base64.b64encode(msg["bytes"]).decode("ascii")
                            f = Frame(
                                type=FrameType.WS_FRAME,
                                stream_id=stream_id,
                                payload={"data": b64_data, "is_binary": True},
                            )
                            await multiplexer.send_frame(f)
                except WebSocketDisconnect:
                    pass
                finally:
                    close_frame = Frame(type=FrameType.WS_CLOSE, stream_id=stream_id)
                    try:
                        await multiplexer.send_frame(close_frame)
                    except Exception:
                        pass

            async def from_tunnel_to_external() -> None:
                try:
                    while True:
                        frame = await stream.get_inbound()
                        if frame.type == FrameType.WS_FRAME:
                            is_binary = frame.payload.get("is_binary", False)
                            raw_data = frame.payload.get("data", "")
                            if is_binary:
                                await websocket.send_bytes(base64.b64decode(raw_data))
                            else:
                                await websocket.send_text(raw_data)
                        elif frame.type in (FrameType.WS_CLOSE, FrameType.STREAM_RESET):
                            await websocket.close()
                            break
                except Exception:
                    pass

            tasks = [
                asyncio.create_task(from_external_to_tunnel()),
                asyncio.create_task(from_tunnel_to_external()),
            ]
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in tasks:
                t.cancel()

        finally:
            await multiplexer.close_stream(stream_id)
