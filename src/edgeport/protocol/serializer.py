"""Frame serialization and deserialization for wire transmission."""

import base64
import json
import struct
from typing import Any

from .frames import Frame, FrameType

# Binary frame type identifiers for high-speed streaming
BIN_FRAME_STREAM_DATA = 0x01
BIN_FRAME_STREAM_END = 0x02
BIN_FRAME_PING = 0x03
BIN_FRAME_PONG = 0x04

BIN_TO_FRAME_TYPE = {
    BIN_FRAME_STREAM_DATA: FrameType.STREAM_DATA,
    BIN_FRAME_STREAM_END: FrameType.STREAM_END,
    BIN_FRAME_PING: FrameType.PING,
    BIN_FRAME_PONG: FrameType.PONG,
}

FRAME_TYPE_TO_BIN = {
    FrameType.STREAM_DATA: BIN_FRAME_STREAM_DATA,
    FrameType.STREAM_END: BIN_FRAME_STREAM_END,
    FrameType.PING: BIN_FRAME_PING,
    FrameType.PONG: BIN_FRAME_PONG,
}


def encode_frame(frame: Frame) -> str:
    """Serializes a Frame object into a JSON string."""
    return json.dumps(
        {
            "type": frame.type.value,
            "stream_id": frame.stream_id,
            "payload": frame.payload,
        },
        separators=(",", ":"),
    )


def decode_frame(raw: str | bytes) -> Frame:
    """Deserializes raw text JSON or binary data into a Frame."""
    if isinstance(raw, bytes):
        if len(raw) >= 5 and raw[0] in BIN_TO_FRAME_TYPE:
            frame_type_id = raw[0]
            stream_id = struct.unpack("!I", raw[1:5])[0]
            frame_type = BIN_TO_FRAME_TYPE[frame_type_id]
            body_bytes = raw[5:]

            payload: dict[str, Any] = {}
            if frame_type == FrameType.STREAM_DATA:
                payload["chunk"] = base64.b64encode(body_bytes).decode("ascii")

            return Frame(type=frame_type, stream_id=stream_id, payload=payload)
        # Fall back to decoding UTF-8 JSON from bytes
        raw_str = raw.decode("utf-8")
    else:
        raw_str = raw

    data = json.loads(raw_str)
    return Frame(
        type=FrameType(data["type"]),
        stream_id=int(data.get("stream_id", 0)),
        payload=data.get("payload", {}),
    )


def encode_binary_data_frame(stream_id: int, chunk: bytes) -> bytes:
    """Packs a STREAM_DATA frame directly into efficient binary format."""
    header = struct.pack("!BI", BIN_FRAME_STREAM_DATA, stream_id)
    return header + chunk


def encode_binary_end_frame(stream_id: int) -> bytes:
    """Packs a STREAM_END frame directly into binary format."""
    return struct.pack("!BI", BIN_FRAME_STREAM_END, stream_id)
