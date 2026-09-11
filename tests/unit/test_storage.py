"""Unit tests for TransactionStore and CapturedTransaction."""

from edgeport.client.storage import (
    CapturedTransaction,
    TransactionStore,
    detect_webhook_provider,
)


def test_webhook_provider_detection():
    stripe_headers = {"stripe-signature": "t=123,v1=abc", "content-type": "application/json"}
    github_headers = {"x-github-event": "push", "x-hub-signature-256": "sha256=..."}
    unknown_headers = {"content-type": "text/html"}

    assert detect_webhook_provider(stripe_headers) == "Stripe"
    assert detect_webhook_provider(github_headers) == "GitHub"
    assert detect_webhook_provider(unknown_headers) is None


def test_captured_transaction_formatting():
    txn = CapturedTransaction(
        method="POST",
        path="/webhook",
        request_headers={"stripe-signature": "sig123"},
        request_body=b'{"event": "charge.succeeded"}',
        response_status=200,
        response_body=b'{"ok": true}',
    )

    assert txn.provider_hint == "Stripe"
    assert "charge.succeeded" in txn.formatted_request_body
    assert "ok" in txn.formatted_response_body

    curl = txn.to_curl("http://localhost:3000")
    assert "curl -X POST" in curl
    assert "http://localhost:3000/webhook" in curl
    assert "-H 'stripe-signature: sig123'" in curl


def test_transaction_store_and_subscriptions():
    store = TransactionStore(maxlen=5)
    notified = []

    store.subscribe(lambda t: notified.append(t.id))

    t1 = CapturedTransaction(path="/1")
    t2 = CapturedTransaction(path="/2")

    store.add(t1)
    store.add(t2)

    assert len(store) == 2
    assert store.get(t1.id) == t1
    assert notified == [t1.id, t2.id]
