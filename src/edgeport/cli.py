"""EdgePort Command Line Interface (CLI) implemented with Typer."""

import asyncio
import logging
import secrets
from typing import Annotated

import httpx
import typer
import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from edgeport import __version__
from edgeport.client.forwarder import LocalForwarder
from edgeport.client.notify import NotificationManager
from edgeport.client.replay import ReplayEngine
from edgeport.client.storage import TransactionStore
from edgeport.client.tunnel_client import TunnelClient
from edgeport.config import Config
from edgeport.mock.templates import generate_mock_webhook, list_mock_templates
from edgeport.server.gateway import RelayGateway
from edgeport.sink.mock_server import MockSinkServer
from edgeport.tui.app import EdgePortTUI
from edgeport.utils.qrcode_gen import generate_terminal_qr
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
    qr: Annotated[
        bool,
        typer.Option("--qr", help="Display terminal QR code upon connection"),
    ] = False,
    notify: Annotated[
        bool,
        typer.Option("--notify", help="Enable desktop notifications on incoming requests"),
    ] = False,
    delay_ms: Annotated[
        int,
        typer.Option("--delay-ms", help="Inject artificial latency in ms (chaos testing)"),
    ] = 0,
    fail_rate: Annotated[
        float,
        typer.Option("--fail-rate", help="Inject artificial failure rate 0.0-1.0 (chaos testing)"),
    ] = 0.0,
    mock_status: Annotated[
        int | None,
        typer.Option("--mock-status", help="Force response status on chaos failure"),
    ] = None,
) -> None:
    """Exposes a local HTTP port to the public internet through an EdgePort relay."""
    cfg = Config.load()
    relay_url = relay or cfg["relay_url"]
    relay_token = token or cfg["relay_token"]
    sub = subdomain or secrets.token_hex(4)
    target_url = f"http://127.0.0.1:{port}"

    store = TransactionStore()
    forwarder = LocalForwarder(
        target_base_url=target_url,
        chaos_delay_ms=delay_ms,
        chaos_fail_rate=fail_rate,
        chaos_mock_status=mock_status,
    )
    replay_engine = ReplayEngine(forwarder=forwarder, store=store)

    if notify:
        notifier = NotificationManager(enabled=True)
        store.subscribe(
            lambda t: notifier.on_transaction(t.method, t.path, t.response_status, t.provider_hint)
        )

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
            if delay_ms > 0:
                table.add_row("Chaos Delay", f"{delay_ms}ms")
            if fail_rate > 0.0:
                table.add_row("Chaos Fail Rate", f"{fail_rate * 100:.0f}%")

            console.print(table)

            def on_connected(public_url: str) -> None:
                console.print(Panel(
                    f"[bold green]Tunnel Connected![/]\nPublic URL: [bold cyan]{public_url}[/]",
                    title="Active Tunnel",
                ))
                if qr:
                    console.print(generate_terminal_qr(public_url))

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
def mock(
    provider: Annotated[
        str | None,
        typer.Argument(help="Webhook provider (e.g. stripe, github, shopify, generic)"),
    ] = None,
    event: Annotated[
        str | None,
        typer.Argument(help="Event name (e.g. payment_intent.succeeded, push, orders/create)"),
    ] = None,
    target: Annotated[
        str | None,
        typer.Option("--target", "-t", help="Target webhook endpoint URL to send the payload to"),
    ] = None,
    secret: Annotated[
        str | None,
        typer.Option("--secret", "-s", help="Webhook signing secret to compute HMAC signature"),
    ] = None,
    list_all: Annotated[
        bool,
        typer.Option("--list", "-l", help="List all available mock webhook templates"),
    ] = False,
    print_only: Annotated[
        bool,
        typer.Option("--print-only", help="Print headers and payload without sending HTTP request"),
    ] = False,
) -> None:
    """Generates and dispatches realistic, signed mock webhooks for Stripe, GitHub, Shopify."""
    if list_all or not provider:
        templates = list_mock_templates()
        table = Table(title="Available Mock Webhook Templates", show_header=True)
        table.add_column("Provider", style="cyan")
        table.add_column("Event Name", style="green")

        for item in templates:
            table.add_row(item["provider"], item["event"])

        console.print(table)
        console.print("\n[dim]Usage: edgeport mock <provider> <event> --target <url>[/]")
        return

    if not event:
        console.print(
            f"[red]Error:[/] Specify event for '{provider}'. Run with --list to see all options."
        )
        raise typer.Exit(1)

    try:
        headers, payload_str = generate_mock_webhook(provider, event, secret=secret)
    except ValueError as exc:
        console.print(f"[red]Error:[/] {exc}")
        raise typer.Exit(1)

    if print_only or not target:
        console.print(Panel(
            f"[bold green]Mock Webhook Generated:[/] [cyan]{provider} / {event}[/]\n"
            f"Signed: [yellow]{'Yes (HMAC)' if secret else 'No (unsigned mock)'}[/]",
            title="EdgePort Mock Webhook",
        ))
        console.print("\n[bold]Headers:[/]")
        for k, v in headers.items():
            console.print(f"  [cyan]{k}[/]: {v}")
        console.print("\n[bold]Payload:[/]")
        console.print(Syntax(payload_str, "json", theme="monokai", line_numbers=True))
        if not target and not print_only:
            console.print("\n[dim]Tip: Pass --target <url> to dispatch payload immediately.[/]")
        return

    # Send payload to target URL
    console.print(f"[dim]Dispatching mock webhook to {target}...[/]")
    try:
        resp = httpx.post(target, headers=headers, content=payload_str, timeout=10.0)
        status_color = "green" if resp.status_code < 400 else "red"
        console.print(Panel(
            f"Status Code: [bold {status_color}]{resp.status_code}[/]\n"
            f"Response Body: {resp.text[:300] if resp.text else '<empty response>'}",
            title=f"Mock Webhook Dispatched: {provider} / {event}",
        ))
    except Exception as exc:
        console.print(f"[bold red]Failed to deliver mock webhook:[/] {exc}")
        raise typer.Exit(1)


@app.command()
def export(
    format: Annotated[
        str,
        typer.Option("--format", "-f", help="Export format: har or postman"),
    ] = "har",
    output: Annotated[
        str | None,
        typer.Option("--output", "-o", help="Output file path"),
    ] = None,
    server: Annotated[
        str,
        typer.Option("--server", help="Local web inspector server URL"),
    ] = "http://127.0.0.1:4040",
) -> None:
    """Exports captured HTTP traffic from the running web inspector to HAR 1.2 or Postman."""
    fmt = format.lower().strip()
    if fmt not in ("har", "postman"):
        console.print("[red]Error:[/] Supported formats are 'har' and 'postman'.")
        raise typer.Exit(1)

    url = f"{server.rstrip('/')}/api/export/{fmt}"
    try:
        resp = httpx.get(url, timeout=5.0)
        if resp.status_code != 200:
            console.print(f"[red]Export failed with status {resp.status_code}:[/] {resp.text}")
            raise typer.Exit(1)

        default_filename = (
            "edgeport-traffic.har" if fmt == "har"
            else "edgeport-collection.postman_collection.json"
        )
        out_path = output or default_filename

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(resp.text)

        console.print(f"[bold green]Successfully exported traffic to[/] [cyan]{out_path}[/]")
    except Exception as exc:
        console.print(f"[red]Failed to connect to inspector at {server}:[/] {exc}")
        raise typer.Exit(1)


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

