"""Unit tests for frame serialization and binary encoding."""

import base64

from edgeport.protocol.frames import Frame, FrameType
from edgeport.protocol.serializer import (
    decode_frame,
    encode_binary_data_frame,
    encode_binary_end_frame,
    encode_frame,
)


def test_encode_and_decode_json_frame():
    frame = Frame(
        type=FrameType.STREAM_OPEN,
        stream_id=42,
        payload={"method": "GET", "path": "/hello"},
    )
    encoded = encode_frame(frame)
    assert isinstance(encoded, str)
    decoded = decode_frame(encoded)

    assert decoded.type == FrameType.STREAM_OPEN
    assert decoded.stream_id == 42
    assert decoded.payload["method"] == "GET"
    assert decoded.payload["path"] == "/hello"


def test_encode_and_decode_binary_data_frame():
    raw_chunk = b'{"status": "ok", "bytes": 1234}'
    stream_id = 99
    bin_frame = encode_binary_data_frame(stream_id, raw_chunk)

    assert isinstance(bin_frame, bytes)
    assert len(bin_frame) == 5 + len(raw_chunk)

    decoded = decode_frame(bin_frame)
    assert decoded.type == FrameType.STREAM_DATA
    assert decoded.stream_id == 99

    # Check decoded payload
    recovered_bytes = base64.b64decode(decoded.payload["chunk"])
    assert recovered_bytes == raw_chunk


def test_encode_and_decode_binary_end_frame():
    stream_id = 101
    bin_frame = encode_binary_end_frame(stream_id)

    assert len(bin_frame) == 5
    decoded = decode_frame(bin_frame)
    assert decoded.type == FrameType.STREAM_END
    assert decoded.stream_id == 101


def test_decode_from_bytes_json():
    json_bytes = b'{"type":"PING","stream_id":0,"payload":{"t":123}}'
    decoded = decode_frame(json_bytes)
    assert decoded.type == FrameType.PING
    assert decoded.stream_id == 0
    assert decoded.payload["t"] == 123
