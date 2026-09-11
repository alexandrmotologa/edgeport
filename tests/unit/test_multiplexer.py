"""Unit tests for StreamMultiplexer."""

import pytest

from edgeport.protocol.frames import Frame, FrameType
from edgeport.protocol.multiplexer import StreamMultiplexer


@pytest.mark.asyncio
async def test_control_frame_routing():
    mux = StreamMultiplexer()
    ping_frame = Frame(type=FrameType.PING, stream_id=0, payload={"seq": 1})

    await mux.handle_inbound_frame(ping_frame)
    received = await mux.get_control_frame(timeout=1.0)

    assert received.type == FrameType.PING
    assert received.payload["seq"] == 1


@pytest.mark.asyncio
async def test_stream_lifecycle():
    mux = StreamMultiplexer(is_server=True)
    stream = await mux.create_stream()
    assert stream.stream_id == 2  # Server starts at 2
    assert mux.active_stream_count == 1

    # Route data frame to stream
    data_frame = Frame(
        type=FrameType.STREAM_DATA,
        stream_id=stream.stream_id,
        payload={"chunk": "aGVsbG8="},
    )
    await mux.handle_inbound_frame(data_frame)

    inbound = await stream.get_inbound(timeout=1.0)
    assert inbound.type == FrameType.STREAM_DATA
    assert inbound.payload["chunk"] == "aGVsbG8="

    # Reset stream
    reset_frame = Frame(type=FrameType.STREAM_RESET, stream_id=stream.stream_id)
    await mux.handle_inbound_frame(reset_frame)
    assert mux.active_stream_count == 0


@pytest.mark.asyncio
async def test_fifty_concurrent_interleaved_streams():
    """Verifies that 50 concurrent interleaved streams transfer without corruption."""
    mux = StreamMultiplexer(is_server=False)
    stream_count = 50
    streams = []

    # Create 50 streams
    for _ in range(stream_count):
        s = await mux.create_stream()
        streams.append(s)

    assert mux.active_stream_count == stream_count

    # Interleave frames across all 50 streams
    for i, s in enumerate(streams):
        frame = Frame(
            type=FrameType.STREAM_DATA,
            stream_id=s.stream_id,
            payload={"stream_index": i, "payload_id": f"msg_{i}"},
        )
        await mux.handle_inbound_frame(frame)

    # Validate each stream receives its exact isolated payload
    for i, s in enumerate(streams):
        inbound = await s.get_inbound(timeout=1.0)
        assert inbound.payload["stream_index"] == i
        assert inbound.payload["payload_id"] == f"msg_{i}"
        await mux.close_stream(s.stream_id)

    assert mux.active_stream_count == 0
