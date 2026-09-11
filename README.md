# EdgePort

EdgePort is a self-hosted reverse tunneling and webhook replay tool written in Python. It exposes your local HTTP services to the internet through an encrypted WebSocket connection to a public relay server. Every incoming request is captured locally, displayed in a terminal user interface or an embedded web inspector, and can be replayed against your local service with a single keypress.

## Features

- Single persistent WebSocket tunnel multiplexing concurrent HTTP streams
- Subdomain routing by Host header on the public relay
- Interactive terminal inspector (TUI) powered by Textual
- Embedded web dashboard at http://localhost:4040 with live Server-Sent Events
- One-click request replay with diff comparisons
- Copy captured requests directly as executable curl commands
- Standalone mock sink mode to capture webhooks before building a backend
- Optional relay access tokens and HTTP basic auth protection
- Automatic heartbeat ping/pong and reconnection with exponential backoff

## Installation

Requirements: Python 3.12 or newer.

```bash
git clone https://github.com/alexandrmotologa/edgeport.git
cd edgeport
pip install -e .
```

To install with development dependencies:

```bash
pip install -e ".[dev]"
```

## Quick Start

### 1. Expose a local port

To expose a web application running on port 8080:

```bash
edgeport expose 8080 --subdomain myapp
```

EdgePort connects to the default relay server, registers `myapp`, and forwards incoming traffic to `http://localhost:8080`.

### 2. Run your own relay gateway

You can run the public relay gateway on any VPS:

```bash
edgeport serve --host 0.0.0.0 --port 8000 --domain yourdomain.com
```

Then point the client to your relay:

```bash
edgeport expose 8080 --subdomain myapp --relay ws://yourdomain.com:8000
```

### 3. Webhook mock sink

When testing third-party webhooks before your application logic is written, start a mock sink:

```bash
edgeport sink --port 8080 --subdomain stripe-test
```

The sink responds with 200 OK to all incoming HTTP methods and logs the complete payload and headers.

## Terminal Inspector

When running `edgeport expose`, a live Textual dashboard displays incoming traffic:

- Press `j` or `k` to navigate through captured requests.
- Press `r` to replay the selected request against localhost.
- Press `c` to copy the selected request as a curl command.
- Press `/` to filter requests by URL path or status code.
- Press `q` to disconnect and exit.

If you prefer a plain console output or want to run EdgePort in scripts:

```bash
edgeport expose 8080 --no-tui
```

## Web Inspector

EdgePort runs an embedded local web dashboard at `http://localhost:4040` by default. You can inspect request headers, format JSON bodies, and trigger replays from a browser.

To disable the web inspector or change the port:

```bash
edgeport expose 8080 --web-port 4041
edgeport expose 8080 --no-web
```

## Security

Protect public endpoints by requiring HTTP Basic Authentication before traffic reaches your machine:

```bash
edgeport expose 8080 --subdomain demo --auth developer:secretpass
```

To restrict who can establish tunnels on your public relay, set an authentication token on the server and client:

```bash
# On the relay server
edgeport serve --token YOUR_SECRET_TOKEN

# On the client
edgeport expose 8080 --relay ws://yourdomain.com:8000 --token YOUR_SECRET_TOKEN
```

## Architecture

EdgePort consists of three primary components:

1. **Relay Gateway**: A public server that listens for inbound HTTP requests, routes them by Host header to the correct client, and manages tunnel registrations over WebSockets.
2. **Tunnel Client**: A client daemon on the developer machine that establishes an outbound WebSocket connection to the relay and forwards payloads to localhost via `httpx`.
3. **Wire Protocol**: A binary and JSON multiplexed framing protocol that handles concurrent streams (`STREAM_OPEN`, `STREAM_DATA`, `STREAM_END`, `STREAM_RESET`) over a single socket connection.

Read [docs/architecture.md](docs/architecture.md) for full design details.

## Documentation

- [Getting Started](docs/quickstart.md)
- [System Architecture](docs/architecture.md)
- [Protocol Specification](docs/protocol-spec.md)
- [Self-Hosting Guide](docs/self-hosting.md)
- [Webhook Inspection and Replay](docs/webhooks.md)

## License

MIT License. See [LICENSE](LICENSE) for details.
