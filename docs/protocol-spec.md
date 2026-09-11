# Wire Protocol Specification

This document defines the binary and JSON framing protocol used between the EdgePort Relay Gateway and Tunnel Clients over WebSocket connections.

## Frame Structure

Messages exchanged over the tunnel WebSocket can be text (JSON) or binary payloads depending on the frame type.

All JSON control frames share a common envelope:

```json
{
  "type": "<FRAME_TYPE>",
  "stream_id": 0,
  "payload": {}
}
```

When transmitting large request or response bodies, binary frames are used:
- Byte 0: Frame Type ID (integer)
- Bytes 1-4: 32-bit big-endian unsigned integer representing `stream_id`
- Bytes 5-N: Raw payload bytes

## Frame Types

### 1. Control Frames (`stream_id` = 0)

#### `REGISTER_TUNNEL` (Client -> Server)
Sent immediately after the client connects.

```json
{
  "type": "REGISTER_TUNNEL",
  "stream_id": 0,
  "payload": {
    "subdomain": "myapp",
    "token": "optional-relay-secret",
    "basic_auth": "optional-user:password"
  }
}
```

#### `TUNNEL_READY` (Server -> Client)
Sent by the relay once the subdomain is verified and assigned.

```json
{
  "type": "TUNNEL_READY",
  "stream_id": 0,
  "payload": {
    "subdomain": "myapp",
    "public_url": "http://myapp.example.com",
    "assigned_at": 1773321400
  }
}
```

#### `TUNNEL_ERROR` (Server -> Client)
Sent if registration fails (e.g. subdomain taken, invalid token).

```json
{
  "type": "TUNNEL_ERROR",
  "stream_id": 0,
  "payload": {
    "code": "SUBDOMAIN_IN_USE",
    "message": "Subdomain 'myapp' is currently claimed by another tunnel"
  }
}
```

#### `PING` / `PONG` (Bidirectional)
Keeps the connection active through firewalls and proxies.

```json
{ "type": "PING", "stream_id": 0, "payload": { "timestamp": 1773321415 } }
{ "type": "PONG", "stream_id": 0, "payload": { "timestamp": 1773321415 } }
```

### 2. Stream Multiplexing Frames (`stream_id` > 0)

#### `STREAM_OPEN` (Server -> Client)
Initiates a new HTTP request through the tunnel.

```json
{
  "type": "STREAM_OPEN",
  "stream_id": 1042,
  "payload": {
    "method": "POST",
    "path": "/api/webhooks/stripe",
    "headers": {
      "host": "myapp.example.com",
      "content-type": "application/json",
      "stripe-signature": "t=1773321400,v1=..."
    },
    "remote_ip": "54.187.174.169"
  }
}
```

#### `STREAM_DATA` (Bidirectional)
Transfers body chunks for either request or response. May be sent as JSON (base64) or binary frame.

```json
{
  "type": "STREAM_DATA",
  "stream_id": 1042,
  "payload": {
    "chunk": "eyJldmVudCI6ICJjaGFyZ2Uuc3VjY2VlZGVkIn0="
  }
}
```

#### `STREAM_HEADERS` (Client -> Server)
Transmits the HTTP response status code and headers from the local service.

```json
{
  "type": "STREAM_HEADERS",
  "stream_id": 1042,
  "payload": {
    "status": 200,
    "headers": {
      "content-type": "application/json",
      "cache-control": "no-cache"
    }
  }
}
```

#### `STREAM_END` (Bidirectional)
Indicates that all data chunks for a stream have been transmitted.

```json
{
  "type": "STREAM_END",
  "stream_id": 1042,
  "payload": {}
}
```

#### `STREAM_RESET` (Bidirectional)
Terminates a stream prematurely due to an error or timeout.

```json
{
  "type": "STREAM_RESET",
  "stream_id": 1042,
  "payload": {
    "reason": "GATEWAY_TIMEOUT"
  }
}
```

### 3. WebSocket Proxying Frames (`stream_id` > 0)

EdgePort supports transparent, bidirectional WebSocket proxying (e.g. for Vite HMR or chat apps).

#### `WS_OPEN` (Server -> Client)
Instructs the client to establish a local WebSocket connection to the destination service.

```json
{
  "type": "WS_OPEN",
  "stream_id": 2001,
  "payload": {
    "path": "/ws",
    "headers": {
      "host": "myapp.example.com",
      "sec-websocket-version": "13"
    },
    "subprotocols": []
  }
}
```

#### `WS_FRAME` (Bidirectional)
Transfers an individual WebSocket message frame (text or base64 binary).

```json
{
  "type": "WS_FRAME",
  "stream_id": 2001,
  "payload": {
    "is_binary": false,
    "data": "{\"type\":\"ping\"}"
  }
}
```

#### `WS_CLOSE` (Bidirectional)
Gracefully closes the WebSocket connection with standard RFC 6455 status code and reason.

```json
{
  "type": "WS_CLOSE",
  "stream_id": 2001,
  "payload": {
    "code": 1000,
    "reason": "Normal Closure"
  }
}
```

## Stream Lifecycle

Each stream passes through the following states:

1. **IDLE**: The `stream_id` is unused.
2. **OPEN**: The server emits `STREAM_OPEN` (or `WS_OPEN`). Both sides can transmit data.
3. **HALF_CLOSED_LOCAL**: One side emitted `STREAM_END` and will send no further data chunks.
4. **CLOSED**: Both sides completed data transmission, or either side emitted `STREAM_RESET` or `WS_CLOSE`. The `stream_id` is retired and released from memory.
