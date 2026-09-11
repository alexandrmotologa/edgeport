"""In-memory storage and event emitter for captured HTTP transactions."""

import json
import shlex
import time
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

WEBHOOK_SIGNATURE_HEADERS = {
    "stripe-signature": "Stripe",
    "x-hub-signature-256": "GitHub",
    "x-github-event": "GitHub",
    "x-shopify-hmac-sha256": "Shopify",
    "x-slack-signature": "Slack",
    "x-twilio-signature": "Twilio",
}


def detect_webhook_provider(headers: dict[str, str]) -> str | None:
    """Identifies the webhook provider based on signature headers."""
    lowered = {k.lower(): v for k, v in headers.items()}
    for header, provider in WEBHOOK_SIGNATURE_HEADERS.items():
        if header in lowered:
            return provider
    return None


@dataclass
class CapturedTransaction:
    """Represents a fully intercepted HTTP request and response pair."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    timestamp: float = field(default_factory=time.time)
    method: str = "GET"
    path: str = "/"
    query_string: str = ""
    request_headers: dict[str, str] = field(default_factory=dict)
    request_body: bytes = b""
    response_status: int = 200
    response_headers: dict[str, str] = field(default_factory=dict)
    response_body: bytes = b""
    duration_ms: float = 0.0
    provider_hint: str | None = None
    replayed_from_id: str | None = None

    def __post_init__(self) -> None:
        if not self.provider_hint:
            self.provider_hint = detect_webhook_provider(self.request_headers)

    @property
    def full_url(self) -> str:
        if self.query_string:
            return f"{self.path}?{self.query_string}"
        return self.path

    @property
    def formatted_request_body(self) -> str:
        """Returns JSON pretty-printed string or decoded UTF-8 text."""
        if not self.request_body:
            return ""
        try:
            parsed = json.loads(self.request_body)
            return json.dumps(parsed, indent=2)
        except Exception:
            return self.request_body.decode("utf-8", errors="replace")

    @property
    def formatted_response_body(self) -> str:
        if not self.response_body:
            return ""
        try:
            parsed = json.loads(self.response_body)
            return json.dumps(parsed, indent=2)
        except Exception:
            return self.response_body.decode("utf-8", errors="replace")

    def to_curl(self, target_base_url: str = "http://localhost:8080") -> str:
        """Generates an executable cURL command replicating this request."""
        base = target_base_url.rstrip("/")
        url = f"{base}{self.full_url}"
        parts = ["curl", "-X", shlex.quote(self.method)]

        # Add headers
        for k, v in self.request_headers.items():
            if k.lower() not in ("content-length", "host"):
                parts.extend(["-H", shlex.quote(f"{k}: {v}")])

        # Add body
        if self.request_body:
            try:
                body_str = self.request_body.decode("utf-8")
                parts.extend(["-d", shlex.quote(body_str)])
            except UnicodeDecodeError:
                parts.extend(["--data-binary", "@-"])

        parts.append(shlex.quote(url))
        return " ".join(parts)


class TransactionStore:
    """Bounded ring-buffer storing captured transactions with subscriber support."""

    def __init__(self, maxlen: int = 500) -> None:
        self._items: deque[CapturedTransaction] = deque(maxlen=maxlen)
        self._by_id: dict[str, CapturedTransaction] = {}
        self._subscribers: list[Callable[[CapturedTransaction], None]] = []

    def add(self, transaction: CapturedTransaction) -> None:
        """Stores a transaction and notifies subscribers."""
        self._items.append(transaction)
        self._by_id[transaction.id] = transaction
        self._notify(transaction)

    def get(self, transaction_id: str) -> CapturedTransaction | None:
        return self._by_id.get(transaction_id)

    def all(self) -> list[CapturedTransaction]:
        return list(self._items)

    def subscribe(self, callback: Callable[[CapturedTransaction], None]) -> None:
        self._subscribers.append(callback)

    def _notify(self, transaction: CapturedTransaction) -> None:
        for cb in self._subscribers:
            try:
                cb(transaction)
            except Exception:
                pass

    def clear(self) -> None:
        self._items.clear()
        self._by_id.clear()

    def __len__(self) -> int:
        return len(self._items)
