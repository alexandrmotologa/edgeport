# Getting Started with EdgePort

This guide covers installing EdgePort, running your first reverse tunnel, and inspecting incoming requests.

## Prerequisites

- Python 3.12 or higher
- Git
- Access to a terminal

## Installation

Install EdgePort in a Python virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install git+https://github.com/alexandrmotologa/edgeport.git
```

For local development:

```bash
git clone https://github.com/alexandrmotologa/edgeport.git
cd edgeport
pip install -e ".[dev]"
```

## First Tunnel

Start a simple local web server on port 8000:

```bash
python -m http.server 8000
```

In a second terminal window, run:

```bash
edgeport expose 8000 --subdomain test-site
```

The output indicates the assigned public URL:

```text
Tunnel established!
Public URL: http://test-site.localhost:8000
Forwarding to: http://127.0.0.1:8000
Web Inspector: http://127.0.0.1:4040
```

Open the public URL in your browser or make a request with curl:

```bash
curl http://test-site.localhost:8000
```

The request appears in real time both in your terminal inspector and on the web dashboard at `http://127.0.0.1:4040`.

## Replaying a Request

When you test webhooks or APIs, you often need to repeat the same request after modifying local code.

In the Textual terminal interface:
1. Use arrow keys or `j`/`k` to highlight the request.
2. Press `r` to resend the exact HTTP payload to your local server.
3. The response time and status code appear immediately.

In the web interface:
1. Navigate to `http://localhost:4040`.
2. Click on the captured request.
3. Click the Replay button in the top-right corner.

## Command Reference

| Command | Description |
| :--- | :--- |
| `edgeport expose <port>` | Exposes a local port through a tunnel |
| `edgeport serve` | Runs the public relay gateway daemon |
| `edgeport sink` | Starts a mock server that accepts and logs all incoming webhooks |
| `edgeport replay <id>` | Replays a captured request from the command line |
| `edgeport version` | Displays the current installed version |

Common flags for `edgeport expose`:

- `--subdomain <name>`: Requests a specific subdomain prefix.
- `--relay <url>`: Target relay WebSocket address (default: `ws://localhost:8000` or configured default).
- `--token <token>`: Relay client authentication token.
- `--auth <user:pass>`: Protects public endpoint with HTTP Basic Authentication.
- `--no-tui`: Disables the interactive terminal UI.
- `--web-port <port>`: Custom port for the local web inspector (default: 4040).
- `--no-web`: Disables the local web inspector server.
