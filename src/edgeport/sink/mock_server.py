"""Standalone mock webhook sink server for local testing."""

import json
import logging
import time

import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

logger = logging.getLogger("edgeport.sink")
console = Console()


class MockSinkServer:
    """Listens on a local port and responds with 200 OK to any webhook request."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        response_status: int = 200,
    ) -> None:
        self.host = host
        self.port = port
        self.response_status = response_status

        self.app = Starlette(
            routes=[
                Route(
                    "/{path:path}",
                    self._handle_catch_all,
                    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
                )
            ]
        )

    async def _handle_catch_all(self, request: Request) -> JSONResponse:
        body_bytes = await request.body()
        raw_headers = dict(request.headers)

        body_str = ""
        is_json = False
        if body_bytes:
            try:
                parsed = json.loads(body_bytes)
                body_str = json.dumps(parsed, indent=2)
                is_json = True
            except Exception:
                body_str = body_bytes.decode("utf-8", errors="replace")

        # Visual log of received webhook
        header_text = f"[bold green]{request.method}[/] [bold cyan]{request.url.path}[/]"
        if is_json:
            renderable = Syntax(body_str, "json", theme="monokai", word_wrap=True)
        else:
            renderable = body_str or "[dim]<empty body>[/]"

        console.print(Panel(renderable, title=header_text, subtitle=f"{time.strftime('%H:%M:%S')}"))

        return JSONResponse(
            {
                "status": "received",
                "method": request.method,
                "path": request.url.path,
                "query": str(request.url.query),
                "headers_count": len(raw_headers),
                "timestamp": time.time(),
            },
            status_code=self.response_status,
        )

    def run(self) -> None:
        """Runs the mock sink server synchronously."""
        uvicorn.run(self.app, host=self.host, port=self.port, log_level="warning")
