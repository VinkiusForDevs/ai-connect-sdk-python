"""A fake httpx-style async client for tests (the Python analogue of the
TypeScript SDK's mock ``fetch``).

Records every request and returns queued responses. Supports raising errors to
simulate network failures.
"""

from __future__ import annotations

import json
from typing import Any, Optional

__all__ = ["FakeResponse", "FakeClient"]


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        json_body: Any = None,
        text: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        self.status_code = status_code
        # Expose headers as a case-insensitive dict-like ATTRIBUTE (httpx parity),
        # since the transport does ``response.headers.get(name)``.
        self.headers = _CaseInsensitiveDict({k.lower(): v for k, v in (headers or {}).items()})
        if text is not None:
            self.text = text
        else:
            self.text = "" if json_body is None else json.dumps(json_body)


class _CaseInsensitiveDict(dict):
    def get(self, key, default=None):
        return super().get(key.lower(), default)


class FakeClient:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self._queue: list[Any] = []
        #: Optional URL-based router: when set, takes priority over the queue.
        self.handler: Optional[Any] = None

    def route(self, handler) -> "FakeClient":
        """Install a ``handler(request_dict) -> response-or-exception`` router.

        Used for deterministic, URL-keyed responses (needed for concurrent
        fan-out where request order is non-deterministic).
        """
        self.handler = handler
        return self

    def enqueue(self, *responses: Any) -> "FakeClient":
        self._queue.extend(responses)
        return self

    def enqueue_error(self, error: Exception) -> "FakeClient":
        self._queue.append(error)
        return self

    @property
    def last(self) -> Optional[dict[str, Any]]:
        return self.requests[-1] if self.requests else None

    @property
    def body_of(self) -> Any:
        """Parsed JSON body of the last request (or raw text)."""
        last = self.last
        if last is None or last.get("content") is None:
            return None
        text = last["content"].decode("utf-8") if isinstance(last["content"], (bytes, bytearray)) else last["content"]
        try:
            return json.loads(text)
        except (ValueError, TypeError):
            return text

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[dict[str, str]] = None,
        content: Any = None,
        timeout: Any = None,
        **_: Any,
    ) -> Any:
        self.requests.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "content": content,
                "timeout": timeout,
            }
        )
        record = self.requests[-1]
        if self.handler is not None:
            return self.handler(record)
        if not self._queue:
            return FakeResponse(200, {})
        item = self._queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def aclose(self) -> None:  # pragma: no cover - no-op in fake
        pass
