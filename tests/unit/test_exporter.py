"""Tests for HAR 1.2 and Postman v2.1 exporters."""

from edgeport.client.exporter import export_to_har, export_to_postman
from edgeport.client.storage import CapturedTransaction


def test_export_to_har_format() -> None:
    txn = CapturedTransaction(
        id="txn_test_01",
        method="POST",
        path="/api/webhooks",
        query_string="mode=live&test=1",
        request_headers={"content-type": "application/json", "stripe-signature": "t=123,v1=abc"},
        request_body=b'{"object": "event", "status": "paid"}',
        response_status=200,
        response_headers={"content-type": "application/json"},
        response_body=b'{"received": true}',
        duration_ms=45.2,
    )

    har = export_to_har([txn], base_url="https://edgeport.local")
    assert "log" in har
    assert har["log"]["version"] == "1.2"
    assert len(har["log"]["entries"]) == 1

    entry = har["log"]["entries"][0]
    assert entry["time"] == 45.2
    assert entry["request"]["method"] == "POST"
    assert entry["request"]["url"] == "https://edgeport.local/api/webhooks?mode=live&test=1"
    assert entry["request"]["postData"]["text"] == '{"object": "event", "status": "paid"}'
    assert entry["response"]["status"] == 200
    assert entry["response"]["statusText"] == "OK"
    assert entry["response"]["content"]["text"] == '{"received": true}'
    assert entry["_edgeport_provider"] == "Stripe"


def test_export_to_postman_format() -> None:
    txn = CapturedTransaction(
        id="txn_test_02",
        method="POST",
        path="/github/events",
        query_string="",
        request_headers={"content-type": "application/json", "x-github-event": "push"},
        request_body=b'{"ref": "refs/heads/main"}',
        response_status=204,
        response_headers={"content-type": "text/plain"},
        response_body=b"",
        duration_ms=12.0,
    )

    col = export_to_postman([txn], collection_name="Test Suite Export", base_url="http://127.0.0.1:8000")
    assert col["info"]["name"] == "Test Suite Export"
    assert "collection.json" in col["info"]["schema"]
    assert len(col["item"]) == 1

    item = col["item"][0]
    assert "POST /github/events" in item["name"]
    assert item["request"]["method"] == "POST"
    assert item["request"]["body"]["raw"] == '{"ref": "refs/heads/main"}'
    assert len(item["response"]) == 1
    assert item["response"][0]["code"] == 204
