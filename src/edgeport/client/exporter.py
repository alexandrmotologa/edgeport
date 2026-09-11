"""Export captured transactions to standard industry formats: HAR 1.2 and Postman v2.1."""

import http
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

from edgeport.client.storage import CapturedTransaction


def _status_phrase(status_code: int) -> str:
    try:
        return http.HTTPStatus(status_code).phrase
    except ValueError:
        return "Unknown"


def export_to_har(
    transactions: list[CapturedTransaction],
    base_url: str = "http://127.0.0.1:8080",
    creator_version: str = "0.1.0",
) -> dict:
    """Exports transactions to standard HAR (HTTP Archive) 1.2 format."""
    entries = []

    for t in transactions:
        started = datetime.fromtimestamp(t.timestamp, timezone.utc).isoformat()
        content_type = t.request_headers.get("content-type", "application/json")
        resp_content_type = t.response_headers.get("content-type", "application/json")

        # Parse query string parameters
        query_params = []
        if t.query_string:
            for k, v in parse_qsl(t.query_string, keep_blank_values=True):
                query_params.append({"name": k, "value": v})

        # Request headers
        req_headers = [{"name": k, "value": v} for k, v in t.request_headers.items()]
        resp_headers = [{"name": k, "value": v} for k, v in t.response_headers.items()]

        req_body_text = (
            t.request_body.decode("utf-8", errors="replace") if t.request_body else ""
        )
        resp_body_text = (
            t.response_body.decode("utf-8", errors="replace") if t.response_body else ""
        )

        full_url = f"{base_url.rstrip('/')}{t.full_url}"

        post_data = None
        if req_body_text:
            post_data = {
                "mimeType": content_type,
                "text": req_body_text,
            }

        entry = {
            "startedDateTime": started,
            "time": round(t.duration_ms, 2),
            "request": {
                "method": t.method,
                "url": full_url,
                "httpVersion": "HTTP/1.1",
                "cookies": [],
                "headers": req_headers,
                "queryString": query_params,
                "headersSize": -1,
                "bodySize": len(t.request_body),
            },
            "response": {
                "status": t.response_status,
                "statusText": _status_phrase(t.response_status),
                "httpVersion": "HTTP/1.1",
                "cookies": [],
                "headers": resp_headers,
                "content": {
                    "size": len(t.response_body),
                    "mimeType": resp_content_type,
                    "text": resp_body_text,
                },
                "redirectURL": "",
                "headersSize": -1,
                "bodySize": len(t.response_body),
            },
            "cache": {},
            "timings": {
                "blocked": 0,
                "dns": -1,
                "connect": -1,
                "send": 0,
                "wait": round(t.duration_ms, 2),
                "receive": 0,
                "ssl": -1,
            },
            "_edgeport_id": t.id,
            "_edgeport_provider": t.provider_hint,
        }
        if post_data:
            entry["request"]["postData"] = post_data

        entries.append(entry)

    return {
        "log": {
            "version": "1.2",
            "creator": {"name": "EdgePort", "version": creator_version},
            "pages": [],
            "entries": entries,
        }
    }


def export_to_postman(
    transactions: list[CapturedTransaction],
    collection_name: str = "EdgePort Intercepted Traffic",
    base_url: str = "http://127.0.0.1:8080",
) -> dict:
    """Exports transactions to Postman Collection v2.1.0 format."""
    items = []
    parsed_base = urlparse(base_url)
    default_host = [parsed_base.hostname or "127.0.0.1"]
    default_protocol = parsed_base.scheme or "http"
    default_port = str(parsed_base.port) if parsed_base.port else None

    for t in transactions:
        provider_tag = f"[{t.provider_hint}] " if t.provider_hint else ""
        item_name = f"{provider_tag}{t.method} {t.path} ({t.response_status})"

        headers = [
            {"key": k, "value": v, "type": "text"}
            for k, v in t.request_headers.items()
            if k.lower() != "content-length"
        ]

        req_body_text = t.request_body.decode("utf-8", errors="replace") if t.request_body else ""
        content_type = t.request_headers.get("content-type", "").lower()
        body_lang = "json" if "application/json" in content_type else "text"

        path_segments = [p for p in t.path.strip("/").split("/") if p]
        full_url = f"{base_url.rstrip('/')}{t.full_url}"

        query_list = []
        if t.query_string:
            for k, v in parse_qsl(t.query_string, keep_blank_values=True):
                query_list.append({"key": k, "value": v})

        url_obj: dict = {
            "raw": full_url,
            "protocol": default_protocol,
            "host": default_host,
            "path": path_segments,
        }
        if default_port:
            url_obj["port"] = default_port
        if query_list:
            url_obj["query"] = query_list

        request_obj: dict = {
            "method": t.method,
            "header": headers,
            "url": url_obj,
            "description": f"Intercepted request {t.id}",
        }

        if req_body_text:
            request_obj["body"] = {
                "mode": "raw",
                "raw": req_body_text,
                "options": {"raw": {"language": body_lang}},
            }

        resp_body_text = (
            t.response_body.decode("utf-8", errors="replace") if t.response_body else ""
        )
        is_json = "json" in t.response_headers.get("content-type", "")
        example_resp = {
            "name": f"Captured Response ({t.response_status})",
            "originalRequest": request_obj,
            "status": _status_phrase(t.response_status),
            "code": t.response_status,
            "_postman_previewlanguage": "json" if is_json else "text",
            "header": [{"key": k, "value": v} for k, v in t.response_headers.items()],
            "body": resp_body_text,
        }

        items.append({
            "name": item_name,
            "request": request_obj,
            "response": [example_resp],
        })

    return {
        "info": {
            "name": collection_name,
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            "description": "Captured HTTP requests and webhook payloads exported from EdgePort.",
        },
        "item": items,
    }


def save_har_file(
    transactions: list[CapturedTransaction],
    filepath: str | Path,
    base_url: str = "http://127.0.0.1:8080",
) -> Path:
    """Serializes transactions as a HAR file."""
    path = Path(filepath)
    data = export_to_har(transactions, base_url=base_url)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def save_postman_file(
    transactions: list[CapturedTransaction],
    filepath: str | Path,
    collection_name: str = "EdgePort Collection",
    base_url: str = "http://127.0.0.1:8080",
) -> Path:
    """Serializes transactions as a Postman collection file."""
    path = Path(filepath)
    data = export_to_postman(transactions, collection_name=collection_name, base_url=base_url)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path
