"""Multiplexes concurrent logical HTTP streams over a single connection."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from enum import StrEnum

from .frames import Frame, FrameType
from .serializer import (
    encode_binary_data_frame,
    encode_binary_end_frame,
    encode_frame,
)


class StreamState(StrEnum):
    IDLE = "IDLE"
    OPEN = "OPEN"
    HALF_CLOSED_LOCAL = "HALF_CLOSED_LOCAL"
    HALF_CLOSED_REMOTE = "HALF_CLOSED_REMOTE"
    CLOSED = "CLOSED"


class MultiplexedStream:
    """Represents an isolated logical stream multiplexed over the tunnel."""

    def __init__(self, stream_id: int) -> None:
        self.stream_id = stream_id
        self.state = StreamState.OPEN
        self.inbound_queue: asyncio.Queue[Frame] = asyncio.Queue()
        self.created_at = time.time()
        self._closed = asyncio.Event()

    def push_inbound(self, frame: Frame) -> None:
        if not self._closed.is_set():
            self.inbound_queue.put_nowait(frame)

    async def get_inbound(self, timeout: float | None = None) -> Frame:
        if timeout is not None:
            return await asyncio.wait_for(self.inbound_queue.get(), timeout=timeout)
        return await self.inbound_queue.get()

    def close(self) -> None:
        self.state = StreamState.CLOSED
        self._closed.set()


class StreamMultiplexer:
    """Manages active concurrent streams over a persistent transport connection."""

    def __init__(
        self,
        send_raw_callback: Callable[[str | bytes], Awaitable[None]] | None = None,
        is_server: bool = False,
    ) -> None:
        self.send_raw = send_raw_callback
        self.is_server = is_server
        self._streams: dict[int, MultiplexedStream] = {}
        self._control_queue: asyncio.Queue[Frame] = asyncio.Queue()
        # Even IDs for server-initiated streams, odd for client (convention)
        self._stream_id_counter = 2 if is_server else 1
        self._lock = asyncio.Lock()

    def next_stream_id(self) -> int:
        sid = self._stream_id_counter
        self._stream_id_counter += 2
        return sid

    async def create_stream(self, stream_id: int | None = None) -> MultiplexedStream:
        """Registers a new multiplexed stream."""
        async with self._lock:
            if stream_id is None:
                stream_id = self.next_stream_id()
            stream = MultiplexedStream(stream_id)
            self._streams[stream_id] = stream
            return stream

    def get_stream(self, stream_id: int) -> MultiplexedStream | None:
        return self._streams.get(stream_id)

    async def close_stream(self, stream_id: int) -> None:
        """Closes and removes a stream from the active table."""
        async with self._lock:
            stream = self._streams.pop(stream_id, None)
            if stream:
                stream.close()

    async def handle_inbound_frame(self, frame: Frame) -> None:
        """Routes an incoming frame to either control queue or active stream."""
        if frame.stream_id == 0:
            self._control_queue.put_nowait(frame)
            return

        stream = self.get_stream(frame.stream_id)

        if frame.type == FrameType.STREAM_OPEN:
            if not stream:
                # Inbound request stream received
                stream = await self.create_stream(frame.stream_id)
            stream.push_inbound(frame)
            return

        if not stream:
            # Received data or headers for a non-existent or closed stream
            return

        stream.push_inbound(frame)

        if frame.type in (FrameType.STREAM_END, FrameType.STREAM_RESET):
            if frame.type == FrameType.STREAM_RESET:
                await self.close_stream(frame.stream_id)

    async def send_frame(self, frame: Frame) -> None:
        """Encodes and transmits a Frame object."""
        if not self.send_raw:
            raise RuntimeError("Outbound send callback not configured")
        raw_text = encode_frame(frame)
        await self.send_raw(raw_text)

    async def send_binary_data(self, stream_id: int, chunk: bytes) -> None:
        """Transmits a fast binary STREAM_DATA frame."""
        if not self.send_raw:
            raise RuntimeError("Outbound send callback not configured")
        bin_frame = encode_binary_data_frame(stream_id, chunk)
        await self.send_raw(bin_frame)

    async def send_binary_end(self, stream_id: int) -> None:
        """Transmits a binary STREAM_END frame."""
        if not self.send_raw:
            raise RuntimeError("Outbound send callback not configured")
        bin_frame = encode_binary_end_frame(stream_id)
        await self.send_raw(bin_frame)

    async def get_control_frame(self, timeout: float | None = None) -> Frame:
        """Awaits a control frame (stream_id == 0)."""
        if timeout is not None:
            return await asyncio.wait_for(self._control_queue.get(), timeout=timeout)
        return await self._control_queue.get()

    @property
    def active_stream_count(self) -> int:
        return len(self._streams)
