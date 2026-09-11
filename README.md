# EdgePort

EdgePort is a self-hosted reverse tunneling and webhook replay tool written in Python. It exposes your local HTTP and WebSocket services to the internet through an encrypted connection to a public relay server. Every incoming request is captured locally, displayed in a terminal user interface or an embedded web inspector, and can be replayed against your local service with a single keypress.

## Features

- Single persistent WebSocket tunnel multiplexing concurrent HTTP streams and WebSocket connections (Vite HMR, chat).
- Subdomain routing by Host header or query parameter on the public relay.
- Interactive terminal inspector (TUI) powered by Textual with replay, cURL copy, and HAR export.
- Embedded web dashboard at http://localhost:4040 with live Server-Sent Events, Edit & Replay modal, and mobile QR code view.
- Automatic HMAC webhook resigning for Stripe, GitHub, and Shopify when modifying payloads during replay.
- Built-in mock webhook generator (`edgeport mock`) for testing Stripe, GitHub, and Shopify webhooks.
- Traffic export to standard HAR 1.2 and Postman Collection v2.1 formats.
- Chaos testing engine with artificial latency injection and failure rates.
- Relay security controls: Token Bucket rate limiter and CIDR/IP allowlists.
- Relay administrative web console at `/_edgeport/admin`.
- Cross-platform desktop notifications on incoming webhooks or 5xx errors.
- Standalone mock sink mode to capture webhooks before building a backend.
- Optional relay access tokens and HTTP basic auth protection.

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

## Web Inspector

EdgePort runs an embedded local web dashboard at `http://localhost:4040` by default. It features:

- Live request stream via Server-Sent Events.
- Request and response body inspection with JSON syntax formatting.
- Header tables with quick copying.
- **Edit & Replay**: modify headers or body payload, re-sign HMAC with your secret, and re-run against localhost.
- **Mobile QR Code**: view the tunnel QR code modal to test camera webviews on physical phones.
- **HAR & Postman Export**: download your captured traffic with one click.

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
