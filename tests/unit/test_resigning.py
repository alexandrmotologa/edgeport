"""Unit tests for webhook signature generation and resigning."""

import base64
import hashlib
import hmac

from edgeport.client.replay import resign_webhook_payload


def test_stripe_webhook_resigning():
    secret = "whsec_test123"
    body = b'{"event":"charge.captured","amount":1000}'
    headers = {"content-type": "application/json"}

    resigned = resign_webhook_payload("Stripe", body, secret, headers)

    assert "stripe-signature" in resigned
    sig_header = resigned["stripe-signature"]
    assert "t=" in sig_header
    assert "v1=" in sig_header

    # Verify signature manually
    parts = dict(p.split("=", 1) for p in sig_header.split(","))
    t = parts["t"]
    v1 = parts["v1"]

    expected_sig = hmac.new(
        secret.encode("utf-8"),
        f"{t}.".encode("utf-8") + body,
        hashlib.sha256,
    ).hexdigest()
    assert v1 == expected_sig


def test_github_webhook_resigning():
    secret = "gh_secret_456"
    body = b'{"ref":"refs/heads/main","commits":[]}'
    headers = {"x-github-event": "push"}

    resigned = resign_webhook_payload("GitHub", body, secret, headers)

    assert "x-hub-signature-256" in resigned
    sig_header = resigned["x-hub-signature-256"]
    assert sig_header.startswith("sha256=")

    expected_sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    assert sig_header == f"sha256={expected_sig}"


def test_shopify_webhook_resigning():
    secret = "shpss_secret_789"
    body = b'{"id":12345,"total_price":"99.99"}'
    headers = {}

    resigned = resign_webhook_payload("Shopify", body, secret, headers)

    assert "x-shopify-hmac-sha256" in resigned
    sig_header = resigned["x-shopify-hmac-sha256"]

    raw = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(raw).decode("ascii")
    assert sig_header == expected
