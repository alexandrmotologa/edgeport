"""Tests for mock webhook template generator and signatures."""

import json

import pytest

from edgeport.mock.templates import generate_mock_webhook, list_mock_templates


def test_list_mock_templates() -> None:
    templates = list_mock_templates()
    assert len(templates) >= 6
    providers = {t["provider"] for t in templates}
    assert "stripe" in providers
    assert "github" in providers
    assert "shopify" in providers


def test_generate_stripe_mock_signed() -> None:
    secret = "whsec_test_secret_123"
    headers, payload_str = generate_mock_webhook(
        "stripe", "payment_intent.succeeded", secret=secret
    )

    data = json.loads(payload_str)
    assert data["type"] == "payment_intent.succeeded"
    assert "stripe-signature" in headers
    assert headers["stripe-signature"].startswith("t=")
    assert "v1=" in headers["stripe-signature"]


def test_generate_github_mock_signed() -> None:
    secret = "gh_test_secret_456"
    headers, payload_str = generate_mock_webhook("github", "push", secret=secret)

    data = json.loads(payload_str)
    assert data["repository"]["name"] == "edgeport"
    assert headers["x-github-event"] == "push"
    assert headers["x-hub-signature-256"].startswith("sha256=")


def test_generate_shopify_mock_signed() -> None:
    secret = "shpss_test_secret_789"
    headers, payload_str = generate_mock_webhook("shopify", "orders/create", secret=secret)

    data = json.loads(payload_str)
    assert data["id"] == 820982911946154508
    assert headers["x-shopify-topic"] == "orders/create"
    assert "x-shopify-hmac-sha256" in headers


def test_generate_unknown_provider_or_event_raises() -> None:
    with pytest.raises(ValueError, match="Unknown provider"):
        generate_mock_webhook("unknown_service", "ping")

    with pytest.raises(ValueError, match="Unknown event"):
        generate_mock_webhook("stripe", "non_existent_event")
