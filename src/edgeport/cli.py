"""EdgePort Command Line Interface (CLI) implemented with Typer."""

import asyncio
import logging
import secrets
from typing import Annotated

import typer
import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from edgeport import __version__
from edgeport.client.forwarder import LocalForwarder
from edgeport.client.replay import ReplayEngine
from edgeport.client.storage import TransactionStore
from edgeport.client.tunnel_client import TunnelClient
from edgeport.config import Config
from edgeport.server.gateway import RelayGateway
from edgeport.sink.mock_server import MockSinkServer
from edgeport.tui.app import EdgePortTUI
from edgeport.web.app import create_web_inspector_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("edgeport")
console = Console()
app = typer.Typer(
    name="edgeport",
    help="Zero-config reverse tunneling and webhook replay engine",
    no_args_is_help=True,
)


@app.command()
def expose(
    port: Annotated[int, typer.Argument(help="Local port to expose (e.g. 8080)")],
    subdomain: Annotated[
        str | None,
        typer.Option("--subdomain", "-s", help="Custom subdomain prefix (default: random)"),
    ] = None,
    relay: Annotated[
        str | None,
        typer.Option("--relay", "-r", help="Relay WebSocket URL"),
    ] = None,
    token: Annotated[
        str | None,
        typer.Option("--token", "-t", help="Relay authentication token"),
    ] = None,
    auth: Annotated[
        str | None,
        typer.Option(
            "--auth",
            "-a",
            help="Enforce HTTP Basic Auth on public tunnel (user:password)",
        ),
    ] = None,
    web_port: Annotated[
        int,
        typer.Option("--web-port", "-w", help="Local web inspector port"),
    ] = 4040,
    no_web: Annotated[
        bool,
        typer.Option("--no-web", help="Disable embedded local web dashboard"),
    ] = False,
    no_tui: Annotated[
        bool,
        typer.Option("--no-tui", help="Run without terminal TUI (headless console mode)"),
    ] = False,
) -> None:
    """Exposes a local HTTP port to the public internet through an EdgePort relay."""
    cfg = Config.load()
    relay_url = relay or cfg["relay_url"]
    relay_token = token or cfg["relay_token"]
    sub = subdomain or secrets.token_hex(4)
    target_url = f"http://127.0.0.1:{port}"

    store = TransactionStore()
    forwarder = LocalForwarder(target_base_url=target_url)
    replay_engine = ReplayEngine(forwarder=forwarder, store=store)

    client = TunnelClient(
        relay_url=relay_url,
        subdomain=sub,
        target_url=target_url,
        token=relay_token,
        basic_auth=auth,
        store=store,
        forwarder=forwarder,
    )

    # Start embedded web inspector server if requested
    if not no_web:
        web_app = create_web_inspector_app(client=client, replay_engine=replay_engine)
        config = uvicorn.Config(web_app, host="127.0.0.1", port=web_port, log_level="warning")
        web_server = uvicorn.Server(config)
    else:
        web_server = None

    if no_tui:
        # Headless console mode
        async def run_headless() -> None:
            table = Table(title="EdgePort Reverse Tunnel", show_header=True)
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Subdomain", sub)
            table.add_row("Local Target", target_url)
            table.add_row("Relay Gateway", relay_url)
            if not no_web:
                table.add_row("Web Inspector", f"http://127.0.0.1:{web_port}")
            if auth:
                table.add_row("Basic Auth", "Enabled")

            console.print(table)

            def on_connected(public_url: str) -> None:
                console.print(Panel(
                    f"[bold green]Tunnel Connected![/]\nPublic URL: [bold cyan]{public_url}[/]",
                    title="Active Tunnel",
                ))

            client.on_connected(on_connected)

            tasks = [asyncio.create_task(client.start())]
            if web_server:
                tasks.append(asyncio.create_task(web_server.serve()))

            await asyncio.gather(*tasks)

        try:
            asyncio.run(run_headless())
        except KeyboardInterrupt:
            console.print("\n[yellow]Tunnel stopped.[/]")
    else:
        # Interactive Textual TUI mode
        async def run_with_tui() -> None:
            tasks = [asyncio.create_task(client.start())]
            if web_server:
                tasks.append(asyncio.create_task(web_server.serve()))

            tui_app = EdgePortTUI(client=client, replay_engine=replay_engine, store=store)
            try:
                await tui_app.run_async()
            finally:
                await client.stop()
                if web_server:
                    web_server.should_exit = True
                for t in tasks:
                    t.cancel()

        asyncio.run(run_with_tui())


@app.command()
def serve(
    host: Annotated[str, typer.Option("--host", "-h", help="Bind host address")] = "0.0.0.0",
    port: Annotated[int, typer.Option("--port", "-p", help="Public listening port")] = 8000,
    domain: Annotated[
        str,
        typer.Option("--domain", "-d", help="Base domain name for subdomain routing"),
    ] = "localhost",
    token: Annotated[
        str | None,
        typer.Option("--token", "-t", help="Require secret token from connecting clients"),
    ] = None,
) -> None:
    """Runs the public EdgePort Relay Gateway server."""
    console.print(Panel(
        f"[bold green]Starting EdgePort Relay Gateway[/]\n"
        f"Host: [cyan]{host}:{port}[/]\n"
        f"Base Domain: [cyan]{domain}[/]\n"
        f"Client Token Auth: [yellow]{'Enabled' if token else 'Disabled'}[/]\n"
        f"Tunnel Ingress: [cyan]ws://{domain}:{port}/ws/tunnel[/]",
        title="EdgePort Relay Gateway",
    ))

    gateway = RelayGateway(domain=domain, port=port, relay_secret=token)
    uvicorn.run(gateway.app, host=host, port=port, log_level="info")


@app.command()
def sink(
    port: Annotated[int, typer.Option("--port", "-p", help="Port to listen for webhooks")] = 8080,
    subdomain: Annotated[
        str | None,
        typer.Option("--subdomain", "-s", help="Optional subdomain to expose via reverse tunnel"),
    ] = None,
    relay: Annotated[
        str | None,
        typer.Option("--relay", "-r", help="Relay WebSocket URL"),
    ] = None,
) -> None:
    """Runs a standalone mock webhook sink server that captures and logs payloads."""
    console.print(Panel(
        f"[bold green]Starting Mock Webhook Sink Server[/]\n"
        f"Local Port: [cyan]{port}[/]\n"
        f"All incoming requests will receive 200 OK and be logged.",
        title="EdgePort Mock Sink",
    ))

    if subdomain:
        cfg = Config.load()
        relay_url = relay or cfg["relay_url"]

        async def run_sink_with_tunnel() -> None:
            sink_server = MockSinkServer(port=port)
            sink_cfg = uvicorn.Config(
                sink_server.app,
                host="127.0.0.1",
                port=port,
                log_level="warning",
            )
            sink_task = asyncio.create_task(uvicorn.Server(sink_cfg).serve())

            client = TunnelClient(
                relay_url=relay_url,
                subdomain=subdomain,
                target_url=f"http://127.0.0.1:{port}",
            )
            client.on_connected(
                lambda url: console.print(f"[bold green]Sink tunnel active:[/] [cyan]{url}[/]")
            )
            tunnel_task = asyncio.create_task(client.start())

            await asyncio.gather(sink_task, tunnel_task)

        try:
            asyncio.run(run_sink_with_tunnel())
        except KeyboardInterrupt:
            console.print("\n[yellow]Sink stopped.[/]")
    else:
        server = MockSinkServer(port=port)
        server.run()


@app.command()
def version() -> None:
    """Displays the installed EdgePort version."""
    console.print(f"EdgePort version [bold cyan]{__version__}[/]")


if __name__ == "__main__":
    app()
