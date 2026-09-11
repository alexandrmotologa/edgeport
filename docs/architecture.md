# Architecture

EdgePort connects external internet traffic to local services through a client-relay model. This document details how connections are routed, multiplexed, and inspected.

## System Components

```
+-------------------------------------------------------------+
|                     External Internet                       |
|   (Stripe, GitHub, Mobile Client, Web Browser, Curl)        |
+-------------------------------------------------------------+
                              |
                     Public HTTP/HTTPS
                              |
                              v
+-------------------------------------------------------------+
|                      Relay Gateway                          |
|  - Inbound HTTP Reverse Proxy                               |
|  - Subdomain & Host Header Routing Table                    |
|  - Optional Basic Auth Gate                                 |
|  - WebSocket Tunnel Acceptor (/ws/tunnel)                   |
|  - Stream Multiplexer (Assigns stream_id per request)       |
+-------------------------------------------------------------+
                              ^
                              |
               Encrypted Persistent WebSocket
                  (Multiplexed Stream Wire)
                              |
                              v
+-------------------------------------------------------------+
|                      Tunnel Client                          |
|  - Persistent Outbound WebSocket Connection                 |
|  - Frame Demultiplexer & Stream Router                      |
|  - Local Forwarder (httpx.AsyncClient -> localhost:PORT)    |
|  - Request & Response Ring Buffer Storage                   |
|  - Webhook Replay Engine & Diff Inspector                   |
|  - Textual Terminal TUI & Embedded Web Dashboard            |
+-------------------------------------------------------------+
                              |
                      Local HTTP Request
                              v
+-------------------------------------------------------------+
|                 Target Local Service                        |
|        (Django, FastAPI, Express, Rails, Next.js)           |
+-------------------------------------------------------------+
```

## 1. Connection Establishment

1. The client connects to the relay gateway at `/ws/tunnel`.
2. The client transmits a `REGISTER_TUNNEL` frame containing:
   - Desired subdomain (for example: `checkout`)
   - Client authentication token (if required by relay)
   - Basic Auth credentials (if public protection was requested)
3. The relay verifies the token, checks for subdomain collisions, and registers the client in its routing registry.
4. The relay returns a `TUNNEL_READY` frame with the assigned public URL (such as `https://checkout.example.com`).

## 2. Request Handling and Multiplexing

When an external caller makes an HTTP request to `https://checkout.example.com/api/v1/charge`:

1. The relay inspects the HTTP `Host` header (`checkout.example.com`), extracts the subdomain (`checkout`), and finds the active client connection.
2. If Basic Auth is configured for this subdomain, the relay checks the caller's `Authorization` header. Unauthorized callers receive a 401 response without reaching the client.
3. The relay assigns a unique integer `stream_id` to the request.
4. The relay serializes the request into wire frames:
   - `STREAM_OPEN`: contains `stream_id`, HTTP method (`POST`), path (`/api/v1/charge`), query parameters, and headers.
   - `STREAM_DATA`: contains binary chunks of the request body.
   - `STREAM_END`: signals that the entire request body has been sent.
5. The relay transmits these frames over the existing WebSocket to the client.
6. The client demultiplexes frames by `stream_id`. As frames arrive, the local forwarder constructs an HTTP request and dispatches it to the local service using `httpx.AsyncClient`.

## 3. Response Streaming

1. As the local service responds, the client captures:
   - Response status code
   - Response headers
   - Response body chunks
   - Execution duration in milliseconds
2. The client streams response frames back to the relay:
   - `STREAM_HEADERS`: carries status code and response headers.
   - `STREAM_DATA`: carries response body chunks.
   - `STREAM_END`: marks completion of the response.
3. The relay writes the headers and stream body directly to the external HTTP response socket.
4. The client saves the full transaction to its in-memory storage buffer and emits an event to update the Textual TUI and the web dashboard.

## 4. Reconnection and Fault Tolerance

Network connections between the local machine and the relay can drop. EdgePort uses the following mechanisms to maintain availability:

- **Periodic Heartbeats**: The client transmits `PING` frames every 15 seconds. If the relay does not reply with a `PONG` within 10 seconds, the client marks the connection dead.
- **Subdomain Grace Period**: When a client disconnects unexpectedly, the relay reserves the client's subdomain for 60 seconds. If the client reconnects within that window, it reclaims the same subdomain.
- **Exponential Backoff**: When reconnecting, the client applies an exponential backoff delay starting at 1 second up to a maximum of 30 seconds.
