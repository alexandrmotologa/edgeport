<p align="center">
  <img src="docs/images/logo.png?raw=true" alt="EdgePort Logo" width="130" style="border-radius: 28px;" />
</p>

<h1 align="center">EdgePort</h1>

<p align="center">
  <b>Self-hosted reverse tunneling and webhook replay engine</b><br>
  Expose localhost to the public internet with real-time traffic inspection, HMAC re-signing, and zero configuration.
</p>

<p align="center">
  <a href="https://github.com/alexandrmotologa/edgeport/actions"><img src="https://github.com/alexandrmotologa/edgeport/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/edgeport/"><img src="https://img.shields.io/badge/python-3.12%2B-blue.svg" alt="Python 3.12+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
</p>

---

EdgePort is a self-hosted reverse tunneling and webhook replay tool written in Python. It exposes your local HTTP and WebSocket services to the internet through an encrypted connection to a public relay server. Every incoming request is captured locally, displayed in a terminal user interface or an embedded web inspector, and can be replayed against your local service with a single keypress.

## Features

- **Bidirectional WebSocket Tunneling**: Multiplex concurrent HTTP streams and WebSocket connections (Vite HMR, live chat) over a single persistent tunnel.
- **Subdomain Routing**: Clean hostname-based routing (`subdomain.yourdomain.com`) with header and query parameter fallbacks.
- **Interactive Terminal Inspector (TUI)**: Fast keyboard-driven interface powered by Textual with instant replay, cURL copy, and HAR export.
- **Embedded Web Inspector**: Dark-mode dashboard at `http://localhost:4040` with live Server-Sent Events, Edit & Replay modal, and mobile QR codes.
- **HMAC Webhook Re-signing**: Recomputes authentic signatures for Stripe, GitHub, and Shopify when modifying request bodies before replay.
- **Mock Webhook Generator**: Dispatch realistic pre-configured webhooks (`edgeport mock`) directly to your local endpoints.
- **HAR 1.2 & Postman Export**: One-click export of captured traffic to industry-standard formats.
- **Chaos Testing Engine**: Inject configurable artificial latency (`--delay-ms`) and failure rates (`--fail-rate`).
- **Relay Security Controls**: Token-bucket rate limiting, CIDR IP allowlists, client tokens, and HTTP basic auth.
- **Relay Administration Console**: Web dashboard at `/_edgeport/admin` to monitor active tunnels and disconnect clients.
- **Cross-Platform Notifications**: Non-blocking desktop alerts on incoming requests and 5xx errors.
- **Standalone Mock Sink**: Capture and inspect webhooks before building any application logic.

## The Mascot: The Harbor Osprey

<p align="center">
  <img src="docs/images/logo.png?raw=true" alt="The Harbor Osprey Mascot" width="180" style="border-radius: 36px; margin: 12px 0;" />
</p>

EdgePort uses the **Harbor Osprey** ("The Edge Guardian"). In nature, the osprey commands coastal edges and harbors, vigilantly surveying the boundary between the wild open sea and the protected harbor. With razor-sharp vision and aerodynamic dives, it pierces through the surface barrier to retrieve payloads with zero hesitation. 

In EdgePort, the Osprey embodies the reverse tunnel gateway: standing guard at the public network edge, intercepting incoming webhook streams, and tunneling them securely into your protected localhost port.

---

## Web Inspector

EdgePort runs an embedded local web dashboard at `http://localhost:4040` by default. It allows inspecting headers, viewing formatted JSON payloads, editing bodies before replay, and downloading traffic archives.

<p align="center">
  <img src="docs/images/web-inspector.png?raw=true" alt="EdgePort Web Inspector" width="920" style="border-radius: 8px; box-shadow: 0 8px 30px rgba(0,0,0,0.4);" />
</p>

### Mobile Testing with QR Codes

Click **📱 QR Code** in the inspector header to display a scannable QR code for your public tunnel URL. This enables instant mobile browser testing and camera webhook triggering without manually typing subdomains.

<p align="center">
  <img src="docs/images/qr-modal.png?raw=true" alt="EdgePort Mobile QR Code Modal" width="760" style="border-radius: 8px; box-shadow: 0 8px 30px rgba(0,0,0,0.4);" />
</p>

---

## Relay Administration Console

When self-hosting the EdgePort Relay Gateway, navigate to `http://yourdomain.com:8000/_edgeport/admin` to view connected tunnels, client IP addresses, uptime, and disconnect unauthorized connections.

<p align="center">
  <img src="docs/images/relay-admin.png?raw=true" alt="EdgePort Relay Administration Dashboard" width="860" style="border-radius: 8px; box-shadow: 0 8px 30px rgba(0,0,0,0.4);" />
</p>

---

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

EdgePort connects to the relay server, registers `myapp`, and forwards incoming traffic to `http://localhost:8080`.

To display a terminal QR code for scanning with your phone:

```bash
edgeport expose 8080 --subdomain myapp --qr --no-tui
```

To enable desktop notifications for incoming requests:

```bash
edgeport expose 8080 --notify
```

### 2. Run your own relay gateway

You can run the public relay gateway on any VPS or local server:

```bash
edgeport serve --host 0.0.0.0 --port 8000 --domain yourdomain.com --token SECRET_TOKEN
```

Access the relay admin console in your browser at:
`http://yourdomain.com:8000/_edgeport/admin`

### 3. Generate mock webhooks

Send a mock Stripe payment succeeded webhook to your local application:

```bash
# Print payload and signature to console
edgeport mock stripe payment_intent.succeeded --print-only

# Send directly to local webhook endpoint with signed HMAC
edgeport mock stripe payment_intent.succeeded --target http://localhost:8080/webhooks --secret whsec_test_secret

# List all available mock templates
edgeport mock --list
```

### 4. Export captured traffic

Export captured transactions from the running inspector:

```bash
# Export as HAR 1.2
edgeport export --format har --output traffic.har

# Export as Postman v2.1 Collection
edgeport export --format postman --output collection.json
```

You can also click the **Export HAR** and **Export Postman** buttons in the web dashboard at `http://localhost:4040`.

### 5. Chaos testing and fault injection

Test how your system handles slow networks or intermittent failures:

```bash
# Add 350ms artificial latency to forwarded requests
edgeport expose 8080 --delay-ms 350

# Inject 15% random failure rate returning 503 Service Unavailable
edgeport expose 8080 --fail-rate 0.15 --mock-status 503
```

### 6. Webhook mock sink

When testing third-party webhooks before your application logic is written:

```bash
edgeport sink --port 8080 --subdomain stripe-test
```

The sink responds with 200 OK to all incoming HTTP methods and logs the complete payload and headers.

## Terminal Inspector

When running `edgeport expose`, an interactive Textual dashboard displays incoming traffic:

- Press `j` or `k` to navigate through captured requests.
- Press `r` to replay the selected request against localhost.
- Press `c` to copy the selected request as an executable curl command.
- Press `e` to export captured transactions as a HAR file.
- Press `q` to disconnect and exit.

To run without the terminal TUI in headless mode:

```bash
edgeport expose 8080 --no-tui
```

## Security

Protect public endpoints by requiring HTTP Basic Authentication before traffic reaches your machine:

```bash
edgeport expose 8080 --subdomain demo --auth developer:secretpass
```

To restrict who can establish tunnels on your public relay, configure an authentication token:

```bash
# On the relay server
edgeport serve --token YOUR_SECRET_TOKEN

# On the client
edgeport expose 8080 --relay ws://yourdomain.com:8000 --token YOUR_SECRET_TOKEN
```

The relay server also includes a built-in token-bucket rate limiter and CIDR IP allowlists to protect internal networks.

## Architecture

EdgePort consists of three primary components:

1. **Relay Gateway**: An ASGI server that accepts inbound HTTP and WebSocket requests, routes them by Host header or query parameter to the correct tunnel client, and serves an admin console.
2. **Tunnel Client**: A client daemon on the developer machine that establishes an outbound WebSocket connection to the relay, forwards HTTP requests to localhost via `httpx`, proxies WebSocket streams, and powers the TUI/web inspectors.
3. **Wire Protocol**: A binary and JSON multiplexed framing protocol that handles concurrent streams (`STREAM_OPEN`, `STREAM_DATA`, `STREAM_END`, `WS_OPEN`, `WS_FRAME`, `WS_CLOSE`) over a single socket connection.

Read [docs/architecture.md](docs/architecture.md) for full design details.

## Documentation

- [Getting Started](docs/quickstart.md)
- [System Architecture](docs/architecture.md)
- [Protocol Specification](docs/protocol-spec.md)
- [Self-Hosting Guide](docs/self-hosting.md)
- [Webhook Inspection and Replay](docs/webhooks.md)

## License

MIT License. See [LICENSE](LICENSE) for details.
