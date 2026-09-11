"""Webhook request replay engine and diff generator."""

import difflib
import time
from dataclasses import dataclass

from .forwarder import LocalForwarder
from .storage import CapturedTransaction, TransactionStore


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
    ) -> ReplayResult:
        """Re-dispatches a previously captured request to the local target."""
        original = self.store.get(transaction_id)
        if not original:
            raise KeyError(f"Transaction with ID '{transaction_id}' not found in store")

        headers = dict(original.request_headers)
        if custom_headers:
            headers.update(custom_headers)

        status, resp_headers, resp_body, duration_ms = await self.forwarder.forward(
            method=original.method,
            path=original.path,
            query_string=original.query_string,
            headers=headers,
            body=original.request_body,
        )

        replayed_txn = CapturedTransaction(
            method=original.method,
            path=original.path,
            query_string=original.query_string,
            request_headers=headers,
            request_body=original.request_body,
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
