"""Forwards HTTP requests to the target local service."""

import time

import httpx

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
}


class LocalForwarder:
    """Dispatches tunneled requests to a local HTTP service."""

    def __init__(
        self,
        target_base_url: str = "http://127.0.0.1:8080",
        timeout: float = 30.0,
    ) -> None:
        self.target_base_url = target_base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=False)

    async def forward(
        self,
        method: str,
        path: str,
        query_string: str = "",
        headers: dict[str, str] | None = None,
        body: bytes = b"",
    ) -> tuple[int, dict[str, str], bytes, float]:
        """Sends the request to the local service and captures the response.

        Returns:
            Tuple of (status_code, response_headers, response_body_bytes, duration_ms)
        """
        headers = headers or {}
        forward_headers = {
            k: v for k, v in headers.items() if k.lower() not in HOP_BY_HOP_HEADERS
        }

        full_url = f"{self.target_base_url}{path}"
        if query_string:
            full_url = f"{full_url}?{query_string}"

        start_time = time.perf_counter()
        try:
            resp = await self._client.request(
                method=method,
                url=full_url,
                headers=forward_headers,
                content=body,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000

            resp_headers = {
                k: v
                for k, v in resp.headers.items()
                if k.lower() not in HOP_BY_HOP_HEADERS
            }

            return resp.status_code, resp_headers, resp.content, duration_ms

        except httpx.ConnectError:
            duration_ms = (time.perf_counter() - start_time) * 1000
            err_body = (
                f"EdgePort: Connection refused to local target {self.target_base_url}. "
                "Ensure your local service is running."
            ).encode("utf-8")
            return 502, {"content-type": "text/plain"}, err_body, duration_ms

        except httpx.TimeoutException:
            duration_ms = (time.perf_counter() - start_time) * 1000
            err_body = (
                f"EdgePort: Request to local target {self.target_base_url} timed out "
                f"after {self.timeout}s."
            ).encode("utf-8")
            return 504, {"content-type": "text/plain"}, err_body, duration_ms

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            err_body = f"EdgePort Local Forwarding Error: {exc}".encode("utf-8")
            return 500, {"content-type": "text/plain"}, err_body, duration_ms

    async def close(self) -> None:
        await self._client.aclose()
