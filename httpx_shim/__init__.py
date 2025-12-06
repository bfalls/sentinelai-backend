"""Minimal httpx-compatible shim for offline testing."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from urllib import parse, request, error as urllib_error


class RequestError(Exception):
    """Base exception for request issues."""


class TimeoutException(RequestError):
    """Raised when a request exceeds the configured timeout."""


class HTTPStatusError(RequestError):
    """Raised when a non-2xx status code is returned."""

    def __init__(self, message: str, request=None, response=None):
        super().__init__(message)
        self.request = request
        self.response = response


class Response:
    """Lightweight HTTP response object."""

    def __init__(self, status_code: int, text: str = "", json=None, json_data=None):
        self.status_code = status_code
        self.text = text
        self._json_data = json if json is not None else json_data

    def json(self):
        if self._json_data is not None:
            return self._json_data
        try:
            return json.loads(self.text)
        except json.JSONDecodeError:
            raise ValueError("Response does not contain valid JSON") from None

    def raise_for_status(self):
        if self.status_code >= 400:
            raise HTTPStatusError(
                f"HTTP status {self.status_code}", request=None, response=self
            )


class MockTransport:
    """Callable transport used for tests to stub responses."""

    def __init__(self, handler):
        self.handler = handler

    def __call__(self, request):
        return self.handler(request)


class AsyncClient:
    """Simplified async HTTP client compatible with a subset of httpx APIs."""

    def __init__(self, timeout: float | None = None, transport=None):
        self.timeout = timeout or 10.0
        self.transport = transport

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, params: dict | None = None):
        if self.transport:
            request_obj = SimpleNamespace(url=url, params=params)
            response = self.transport(request_obj)
            if asyncio.iscoroutine(response):
                response = await response
            return response
        return await asyncio.to_thread(self._perform_request, url, params)

    def _perform_request(self, url: str, params: dict | None):
        full_url = url
        if params:
            query = parse.urlencode(params, doseq=True)
            separator = "&" if parse.urlparse(url).query else "?"
            full_url = f"{url}{separator}{query}"
        try:
            with request.urlopen(full_url, timeout=self.timeout) as resp:
                text = resp.read().decode()
                status_code = getattr(resp, "status", 200)
                try:
                    json_data = json.loads(text)
                except json.JSONDecodeError:
                    json_data = None
                return Response(status_code=status_code, text=text, json_data=json_data)
        except urllib_error.URLError as exc:  # pragma: no cover - network dependent
            if isinstance(exc.reason, TimeoutError):
                raise TimeoutException(str(exc))
            raise RequestError(str(exc))


__all__ = [
    "AsyncClient",
    "HTTPStatusError",
    "MockTransport",
    "RequestError",
    "Response",
    "TimeoutException",
]
