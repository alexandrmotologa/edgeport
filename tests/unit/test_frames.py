"""Unit tests for Frame models and payloads."""

from edgeport.protocol.frames import (
    Frame,
    FrameType,
    RegisterTunnelPayload,
    StreamHeadersPayload,
    StreamOpenPayload,
    TunnelReadyPayload,
)


def test_frame_initialization():
    frame = Frame(
        type=FrameType.REGISTER_TUNNEL,
        stream_id=0,
        payload={"subdomain": "test-sub", "token": "sec123"},
    )
    assert frame.type == FrameType.REGISTER_TUNNEL
    assert frame.stream_id == 0
    assert frame.payload["subdomain"] == "test-sub"


def test_register_payload_validation():
    payload = RegisterTunnelPayload(subdomain="myapp", token="tok123", basic_auth="u:p")
    assert payload.subdomain == "myapp"
    assert payload.token == "tok123"
    assert payload.basic_auth == "u:p"


def test_stream_open_payload():
    payload = StreamOpenPayload(
        method="POST",
        path="/api/test",
        headers={"host": "myapp.example.com"},
        query_string="foo=bar",
        remote_ip="127.0.0.1",
    )
    assert payload.method == "POST"
    assert payload.headers["host"] == "myapp.example.com"
    assert payload.query_string == "foo=bar"


def test_tunnel_ready_payload():
    payload = TunnelReadyPayload(
        subdomain="demo",
        public_url="https://demo.example.com",
        assigned_at=1773321400.0,
    )
    assert payload.subdomain == "demo"
    assert payload.public_url == "https://demo.example.com"


def test_stream_headers_payload():
    payload = StreamHeadersPayload(status=201, headers={"location": "/resource/1"})
    assert payload.status == 201
    assert payload.headers["location"] == "/resource/1"
