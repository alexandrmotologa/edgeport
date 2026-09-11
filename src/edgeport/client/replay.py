"""Webhook request replay engine, signature regenerator, and diff generator."""

import base64
import difflib
import hashlib
import hmac
import time
from dataclasses import dataclass

from .forwarder import LocalForwarder
from .storage import CapturedTransaction, TransactionStore


def resign_webhook_payload(
    provider: str,
    payload_bytes: bytes,
    secret: str,
    headers: dict[str, str],
) -> dict[str, str]:
    """Generates a valid HMAC signature with current timestamp for webhooks."""
    updated = dict(headers)
    now = int(time.time())

    if provider.lower() == "stripe":
        # Stripe: t=timestamp,v1=hex_hmac(secret, "{timestamp}.{payload}")
        signed_data = f"{now}.".encode("utf-8") + payload_bytes
        sig = hmac.new(secret.encode("utf-8"), signed_data, hashlib.sha256).hexdigest()
        updated["stripe-signature"] = f"t={now},v1={sig}"

    elif provider.lower() == "github":
        # GitHub: sha256=hex_hmac(secret, payload)
        sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
        updated["x-hub-signature-256"] = f"sha256={sig}"

    elif provider.lower() == "shopify":
        # Shopify: base64_hmac(secret, payload)
        raw_sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
        updated["x-shopify-hmac-sha256"] = base64.b64encode(raw_sig).decode("ascii")

    return updated


@dataclass
class ReplayResult:
    """Outcome of replaying a captured transaction against localhost."""

    original_id: str
    replayed_id: str
    original_status: int
    new_status: int
    status_match: bool
    body_diff: str
    duration_ms: float
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()


class ReplayEngine:
    """Replays intercepted HTTP requests against local endpoints."""

    def __init__(self, forwarder: LocalForwarder, store: TransactionStore) -> None:
        self.forwarder = forwarder
        self.store = store

    async def replay(
        self,
        transaction_id: str,
        custom_headers: dict[str, str] | None = None,
        override_body: bytes | None = None,
        override_method: str | None = None,
        override_path: str | None = None,
        webhook_secret: str | None = None,
    ) -> ReplayResult:
        """Re-dispatches a previously captured request to the local target."""
        original = self.store.get(transaction_id)
        if not original:
            raise KeyError(f"Transaction with ID '{transaction_id}' not found in store")

        method = override_method or original.method
        path = override_path or original.path
        body = override_body if override_body is not None else original.request_body

        headers = dict(original.request_headers)
        if custom_headers:
            headers.update(custom_headers)

        # Re-sign webhook if provider and secret are present
        if webhook_secret and original.provider_hint:
            headers = resign_webhook_payload(
                provider=original.provider_hint,
                payload_bytes=body,
                secret=webhook_secret,
                headers=headers,
            )

        status, resp_headers, resp_body, duration_ms = await self.forwarder.forward(
            method=method,
            path=path,
            query_string=original.query_string,
            headers=headers,
            body=body,
        )

        replayed_txn = CapturedTransaction(
            method=method,
            path=path,
            query_string=original.query_string,
            request_headers=headers,
            request_body=body,
            response_status=status,
            response_headers=resp_headers,
            response_body=resp_body,
            duration_ms=duration_ms,
            replayed_from_id=original.id,
            provider_hint=original.provider_hint,
        )
        self.store.add(replayed_txn)

        # Compute body diff
        orig_lines = original.formatted_response_body.splitlines()
        new_lines = replayed_txn.formatted_response_body.splitlines()
        diff_lines = list(
            difflib.unified_diff(
                orig_lines,
                new_lines,
                fromfile=f"original-{original.id}",
                tofile=f"replayed-{replayed_txn.id}",
                lineterm="",
            )
        )
        body_diff = "\n".join(diff_lines)

        return ReplayResult(
            original_id=original.id,
            replayed_id=replayed_txn.id,
            original_status=original.response_status,
            new_status=status,
            status_match=(original.response_status == status),
            body_diff=body_diff,
            duration_ms=duration_ms,
        )
