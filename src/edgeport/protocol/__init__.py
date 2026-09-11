"""Protocol framing and stream multiplexing package."""

from .frames import Frame, FrameType
from .multiplexer import MultiplexedStream, StreamMultiplexer, StreamState
from .serializer import decode_frame, encode_frame

__all__ = [
    "Frame",
    "FrameType",
    "MultiplexedStream",
    "StreamMultiplexer",
    "StreamState",
    "decode_frame",
    "encode_frame",
]
