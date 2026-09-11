"""Wire protocol frame definitions."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class FrameType(StrEnum):
    # Control frames (stream_id == 0)
    REGISTER_TUNNEL = "REGISTER_TUNNEL"
    TUNNEL_READY = "TUNNEL_READY"
    TUNNEL_ERROR = "TUNNEL_ERROR"
    PING = "PING"
    PONG = "PONG"

    # Stream frames (stream_id > 0)
    STREAM_OPEN = "STREAM_OPEN"
    STREAM_HEADERS = "STREAM_HEADERS"
    STREAM_DATA = "STREAM_DATA"
    STREAM_END = "STREAM_END"
    STREAM_RESET = "STREAM_RESET"


class Frame(BaseModel):
    """Base wire frame exchanged between client and relay."""

    type: FrameType
    stream_id: int = 0
    payload: dict[str, Any] = Field(default_factory=dict)


# Payload helper models for validation and convenience
class RegisterTunnelPayload(BaseModel):
    subdomain: str
    token: str | None = None
    basic_auth: str | None = None


class TunnelReadyPayload(BaseModel):
    subdomain: str
    public_url: str
    assigned_at: float


class TunnelErrorPayload(BaseModel):
    code: str
    message: str


class StreamOpenPayload(BaseModel):
    method: str
    path: str
    headers: dict[str, str] = Field(default_factory=dict)
    query_string: str = ""
    remote_ip: str = ""


class StreamHeadersPayload(BaseModel):
    status: int
    headers: dict[str, str] = Field(default_factory=dict)


class StreamDataPayload(BaseModel):
    chunk: str  # Base64 encoded byte chunk


class StreamResetPayload(BaseModel):
    reason: str = "UNKNOWN"
