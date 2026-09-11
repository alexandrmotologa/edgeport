# Self-Hosting EdgePort Relay

This guide explains how to deploy your own EdgePort relay server on a Linux VPS using Docker and Caddy for automatic TLS certificates.

## Architecture on VPS

When you host your own relay:
- Inbound traffic on ports 80 and 443 hits Caddy.
- Caddy obtains a wildcard certificate (`*.yourdomain.com`) or terminates TLS.
- Caddy forwards HTTP requests and WebSocket connections to the EdgePort relay daemon on port 8000.

## DNS Setup

Point your domain and a wildcard subdomain to your VPS IP address:

```text
A   yourdomain.com       -> 203.0.113.10
A   *.yourdomain.com     -> 203.0.113.10
```

## Running with Docker Compose

Create a `docker-compose.yml` file:

```yaml
version: "3.9"

services:
  edgeport-relay:
    image: python:3.12-slim
    restart: unless-stopped
    working_dir: /app
    volumes:
      - .:/app
    command: >
      sh -c "pip install . && edgeport serve --host 0.0.0.0 --port 8000 --domain yourdomain.com --token SECRET_RELAY_TOKEN"
    environment:
      - PYTHONUNBUFFERED=1
    ports:
      - "127.0.0.1:8000:8000"

  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config

volumes:
  caddy_data:
  caddy_config:
```

### Caddy Configuration (`Caddyfile`)

```text
yourdomain.com, *.yourdomain.com {
    reverse_proxy 127.0.0.1:8000
}
```

Start the services:

```bash
docker compose up -d
```

## Running Directly with Python

If you prefer running without Docker:

1. Install Python 3.12 and create a virtual environment:
   ```bash
   python3 -m venv /opt/edgeport-env
   /opt/edgeport-env/bin/pip install git+https://github.com/alexandrmotologa/edgeport.git
   ```

2. Create a systemd unit file at `/etc/systemd/system/edgeport.service`:
   ```ini
   [Unit]
   Description=EdgePort Relay Service
   After=network.target

   [Service]
   Type=simple
   User=www-data
   ExecStart=/opt/edgeport-env/bin/edgeport serve --host 0.0.0.0 --port 8000 --domain yourdomain.com --token SECRET_RELAY_TOKEN
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

3. Enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now edgeport
   ```

## Verifying the Deployment

Test the relay health endpoint:

```bash
curl http://yourdomain.com:8000/_edgeport/health
```

Expected output:

```json
{"status":"healthy","version":"0.1.0","active_tunnels":0}
```
