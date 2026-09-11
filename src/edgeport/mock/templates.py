"""Predefined mock webhook templates for popular developer services."""

import base64
import hashlib
import hmac
import json
import time
import uuid

TEMPLATES: dict[str, dict[str, dict]] = {
    "stripe": {
        "payment_intent.succeeded": {
            "id": "evt_1MtwBwLkdIwHu7ix28a3tqPa",
            "object": "event",
            "api_version": "2024-06-20",
            "created": 1726050000,
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_3MtwBwLkdIwHu7ix28a3tqPa",
                    "object": "payment_intent",
                    "amount": 2500,
                    "currency": "usd",
                    "status": "succeeded",
                    "payment_method_types": ["card"],
                    "customer": "cus_N7WqZt6h7P8k",
                    "receipt_email": "customer@example.com",
                    "description": "Subscription charge for Pro Plan",
                }
            },
        },
        "customer.subscription.created": {
            "id": "evt_1MtwBwLkdIwHu7ix28a3tqPb",
            "object": "event",
            "api_version": "2024-06-20",
            "created": 1726050010,
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "id": "sub_1MtwBwLkdIwHu7ix28a3tqPb",
                    "object": "subscription",
                    "customer": "cus_N7WqZt6h7P8k",
                    "status": "active",
                    "current_period_start": 1726050000,
                    "current_period_end": 1728642000,
                    "plan": {
                        "id": "plan_pro_monthly",
                        "amount": 4900,
                        "currency": "usd",
                        "interval": "month",
                    },
                }
            },
        },
        "charge.refunded": {
            "id": "evt_1MtwBwLkdIwHu7ix28a3tqPc",
            "object": "event",
            "api_version": "2024-06-20",
            "created": 1726050020,
            "type": "charge.refunded",
            "data": {
                "object": {
                    "id": "ch_3MtwBwLkdIwHu7ix28a3tqPc",
                    "object": "charge",
                    "amount": 2500,
                    "amount_refunded": 2500,
                    "refunded": True,
                    "currency": "usd",
                    "reason": "requested_by_customer",
                }
            },
        },
    },
    "github": {
        "push": {
            "ref": "refs/heads/main",
            "before": "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678",
            "after": "f6e5d4c3b2a10987654321fedcba09876543210f",
            "repository": {
                "id": 850123456,
                "name": "edgeport",
                "full_name": "alexandrmotologa/edgeport",
                "private": False,
                "html_url": "https://github.com/alexandrmotologa/edgeport",
            },
            "pusher": {
                "name": "alexandrmotologa",
                "email": "alexandrmotologa@users.noreply.github.com",
            },
            "commits": [
                {
                    "id": "f6e5d4c3b2a10987654321fedcba09876543210f",
                    "message": "feat: add webhook replay engine and security filters",
                    "timestamp": "2026-09-11T14:45:00Z",
                    "author": {
                        "name": "Alexandr Motologa",
                        "email": "alexandrmotologa@users.noreply.github.com",
                    },
                }
            ],
        },
        "pull_request": {
            "action": "opened",
            "number": 12,
            "pull_request": {
                "id": 987654321,
                "number": 12,
                "state": "open",
                "title": "feat(tunnel): implement bidirectional WebSocket streaming",
                "user": {"login": "contributor"},
                "body": "Fixes Vite HMR and real-time chat tunneling over EdgePort.",
                "created_at": "2026-09-11T14:40:00Z",
            },
            "repository": {
                "name": "edgeport",
                "full_name": "alexandrmotologa/edgeport",
            },
        },
        "ping": {
            "zen": "Keep it logically awesome.",
            "hook_id": 9923481,
            "hook": {
                "type": "Repository",
                "id": 9923481,
                "active": True,
                "events": ["push", "pull_request"],
            },
            "repository": {
                "name": "edgeport",
                "full_name": "alexandrmotologa/edgeport",
            },
        },
    },
    "shopify": {
        "orders/create": {
            "id": 820982911946154508,
            "admin_graphql_api_id": "gid://shopify/Order/820982911946154508",
            "email": "customer@shop.example.com",
            "total_price": "149.99",
            "subtotal_price": "139.99",
            "total_tax": "10.00",
            "currency": "USD",
            "financial_status": "paid",
            "line_items": [
                {
                    "id": 866550311764,
                    "title": "Minimalist Leather Backpack",
                    "quantity": 1,
                    "price": "139.99",
                }
            ],
            "customer": {
                "id": 1153156264,
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "customer@shop.example.com",
            },
        },
        "products/update": {
            "id": 632910392,
            "title": "Ultra-light Titanium Bottle",
            "vendor": "Alpine Gear",
            "product_type": "Accessories",
            "status": "active",
            "variants": [
                {
                    "id": 808950810,
                    "price": "45.00",
                    "sku": "TITANIUM-BTL-01",
                    "inventory_quantity": 120,
                }
            ],
        },
    },
    "generic": {
        "user.created": {
            "event_type": "user.created",
            "event_id": "evt_gen_01928374",
            "timestamp": "2026-09-11T14:45:00Z",
            "data": {
                "user_id": "usr_9981",
                "email": "newuser@domain.com",
                "organization_id": "org_5512",
                "plan": "starter",
            },
        }
    },
}


def list_mock_templates() -> list[dict[str, str]]:
    """Returns a list of all available provider and event names."""
    results = []
    for provider, events in TEMPLATES.items():
        for event_name in events:
            results.append({"provider": provider, "event": event_name})
    return results


def generate_mock_webhook(
    provider: str,
    event_type: str,
    secret: str | None = None,
) -> tuple[dict[str, str], str]:
    """Generates a realistic payload and signed headers for the given provider and event.

    Returns:
        (headers_dict, raw_json_payload_string)
    """
    prov_lower = provider.lower().strip()
    if prov_lower not in TEMPLATES:
        raise ValueError(
            f"Unknown provider '{provider}'. Available: {list(TEMPLATES.keys())}"
        )

    prov_events = TEMPLATES[prov_lower]
    if event_type not in prov_events:
        raise ValueError(
            f"Unknown event '{event_type}' for provider '{provider}'. "
            f"Available: {list(prov_events.keys())}"
        )

    payload_data = prov_events[event_type]
    payload_str = json.dumps(payload_data, indent=2)
    payload_bytes = payload_str.encode("utf-8")

    headers: dict[str, str] = {
        "content-type": "application/json",
        "user-agent": f"EdgePort-Mock-Sender/1.0 ({prov_lower})",
    }

    if prov_lower == "stripe":
        headers["stripe-version"] = "2024-06-20"
        if secret:
            ts = int(time.time())
            signed_payload = f"{ts}.".encode("utf-8") + payload_bytes
            sig = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
            headers["stripe-signature"] = f"t={ts},v1={sig}"
        else:
            headers["stripe-signature"] = f"t={int(time.time())},v1=mock_unsigned_signature"

    elif prov_lower == "github":
        delivery_id = str(uuid.uuid4())
        headers["x-github-event"] = event_type
        headers["x-github-delivery"] = delivery_id
        if secret:
            sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
            headers["x-hub-signature-256"] = f"sha256={sig}"
        else:
            headers["x-hub-signature-256"] = "sha256=mock_unsigned_signature"

    elif prov_lower == "shopify":
        headers["x-shopify-topic"] = event_type
        headers["x-shopify-shop-domain"] = "edgeport-store.myshopify.com"
        headers["x-shopify-webhook-id"] = str(uuid.uuid4())
        if secret:
            digest = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
            headers["x-shopify-hmac-sha256"] = base64.b64encode(digest).decode("utf-8")
        else:
            headers["x-shopify-hmac-sha256"] = "mock_unsigned_shopify_hmac"

    elif prov_lower == "generic":
        headers["webhook-id"] = f"msg_{uuid.uuid4().hex[:16]}"
        headers["webhook-timestamp"] = str(int(time.time()))
        if secret:
            sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
            headers["webhook-signature"] = f"v1,{sig}"

    return headers, payload_str
