"""Embedded Starlette web application serving the EdgePort Web Inspector."""

import asyncio
import json
from collections.abc import AsyncGenerator
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Route
from starlette.staticfiles import StaticFiles

from edgeport.client.exporter import export_to_har, export_to_postman
from edgeport.client.replay import ReplayEngine
from edgeport.client.storage import CapturedTransaction
from edgeport.client.tunnel_client import TunnelClient
from edgeport.utils.qrcode_gen import generate_svg_qr

STATIC_DIR = Path(__file__).parent / "static"


def create_web_inspector_app(client: TunnelClient, replay_engine: ReplayEngine) -> Starlette:
    """Constructs the web inspector ASGI app."""
    store = client.store
    event_queues: list[asyncio.Queue] = []

    def on_transaction(txn: CapturedTransaction) -> None:
        payload = {
            "id": txn.id,
            "method": txn.method,
            "path": txn.path,
            "status": txn.response_status,
            "duration_ms": round(txn.duration_ms, 1),
            "provider": txn.provider_hint,
            "timestamp": txn.timestamp,
        }
        for q in list(event_queues):
            try:
                q.put_nowait(payload)
            except Exception:
                pass

    store.subscribe(on_transaction)

    async def handle_index(request: Request) -> Response:
        return FileResponse(STATIC_DIR / "index.html")

    async def handle_get_transactions(request: Request) -> Response:
        txns = [
            {
                "id": t.id,
                "method": t.method,
                "path": t.path,
                "status": t.response_status,
                "duration_ms": round(t.duration_ms, 1),
                "provider": t.provider_hint,
                "timestamp": t.timestamp,
            }
            for t in store.all()
        ]
        return JSONResponse({"transactions": txns})

    async def handle_get_transaction_detail(request: Request) -> Response:
        txn_id = request.path_params["id"]
        txn = store.get(txn_id)
        if not txn:
            return JSONResponse({"error": "Transaction not found"}, status_code=404)

        return JSONResponse(
            {
                "id": txn.id,
                "timestamp": txn.timestamp,
                "method": txn.method,
                "path": txn.path,
                "full_url": txn.full_url,
                "request_headers": txn.request_headers,
                "request_body": txn.formatted_request_body,
                "response_status": txn.response_status,
                "response_headers": txn.response_headers,
                "response_body": txn.formatted_response_body,
                "duration_ms": round(txn.duration_ms, 1),
                "provider": txn.provider_hint,
                "curl_command": txn.to_curl(client.target_url),
            }
        )

    async def handle_replay(request: Request) -> Response:
        txn_id = request.path_params["id"]
        override_body = None
        override_headers = None
        secret = None

        if request.method == "POST":
            try:
                body_bytes = await request.body()
                if body_bytes:
                    data = json.loads(body_bytes)
                    if "override_body" in data and data["override_body"] is not None:
                        val = data["override_body"]
                        override_body = val.encode("utf-8") if isinstance(val, str) else val
                    override_headers = data.get("override_headers")
                    secret = data.get("webhook_secret")
            except Exception:
                pass

        try:
            result = await replay_engine.replay(
                txn_id,
                override_body=override_body,
                override_headers=override_headers,
                webhook_secret=secret,
            )
            return JSONResponse(
                {
                    "original_id": result.original_id,
                    "replayed_id": result.replayed_id,
                    "original_status": result.original_status,
                    "new_status": result.new_status,
                    "status_match": result.status_match,
                    "body_diff": result.body_diff,
                    "duration_ms": round(result.duration_ms, 1),
                }
            )
        except KeyError:
            return JSONResponse({"error": "Transaction not found"}, status_code=404)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    async def handle_export_har(request: Request) -> Response:
        base_url = client.public_url or client.target_url
        data = export_to_har(store.all(), base_url=base_url)
        return JSONResponse(
            data,
            headers={"Content-Disposition": 'attachment; filename="edgeport-traffic.har"'},
        )

    async def handle_export_postman(request: Request) -> Response:
        base_url = client.public_url or client.target_url
        data = export_to_postman(store.all(), base_url=base_url)
        return JSONResponse(
            data,
            headers={
                "Content-Disposition": (
                    'attachment; filename="edgeport-collection.postman_collection.json"'
                )
            },
        )

    async def handle_qrcode(request: Request) -> Response:
        target = client.public_url or client.target_url
        svg_content = generate_svg_qr(target)
        return Response(content=svg_content, media_type="image/svg+xml")

    async def handle_info(request: Request) -> Response:
        return JSONResponse(
            {
                "public_url": client.public_url,
                "target_url": client.target_url,
                "subdomain": client.subdomain,
                "is_connected": client.is_connected,
            }
        )

    async def handle_events(request: Request) -> Response:
        queue: asyncio.Queue = asyncio.Queue()
        event_queues.append(queue)

        async def sse_generator() -> AsyncGenerator[str, None]:
            try:
                # Send initial ping
                yield "event: ping\ndata: {}\n\n"
                while True:
                    data = await queue.get()
                    yield f"event: transaction\ndata: {json.dumps(data)}\n\n"
            finally:
                if queue in event_queues:
                    event_queues.remove(queue)

        return StreamingResponse(
            sse_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    app = Starlette(
        routes=[
            Route("/", handle_index, methods=["GET"]),
            Route("/events", handle_events, methods=["GET"]),
            Route("/api/info", handle_info, methods=["GET"]),
            Route("/api/qrcode", handle_qrcode, methods=["GET"]),
            Route("/api/export/har", handle_export_har, methods=["GET"]),
            Route("/api/export/postman", handle_export_postman, methods=["GET"]),
            Route("/api/transactions", handle_get_transactions, methods=["GET"]),
            Route("/api/transactions/{id}", handle_get_transaction_detail, methods=["GET"]),
            Route("/api/transactions/{id}/replay", handle_replay, methods=["POST"]),
        ]
    )

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
