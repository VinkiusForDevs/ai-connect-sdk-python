"""Shared transport core: one fetch loop with per-request timeout, full-jitter
retries honoring ``Retry-After``, and redacted observability hooks.

Both the control plane (:class:`~vinkius_connect.core.http.HttpClient`) and the
data plane (:class:`~vinkius_connect.core.runtime.RuntimeClient`) go through here
so timeout, retry, and hook semantics can never drift apart.

The transport talks to any object with an async ``request`` method (by default
an ``httpx.AsyncClient``), so it is injectable for tests / custom runtimes —
the Python analogue of the TypeScript SDK's injectable ``fetch``.

Hooks receive ONLY redacted data: secret headers are masked and any
``vk_live_*`` path segment in the URL (the data-plane token) is replaced.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Optional

try:  # httpx is the default transport; import lazily so the pure core stays
    import httpx  # type: ignore
except Exception:  # pragma: no cover - httpx is a hard runtime dependency
    httpx = None  # type: ignore

from .errors import ConnectionError
from .redact import redact_body, redact_headers, redact_url
from .retry import backoff_delay, is_retryable_status, parse_retry_after, sleep
from .retry import RetryPolicy

__all__ = ["Transport", "TransportConfig", "TransportRequest", "TransportResult"]


@dataclass
class TransportConfig:
    timeout_ms: int
    retry: RetryPolicy
    client: Any  # object with async ``request``
    user_agent: str
    hooks: Optional[Any] = None


@dataclass
class TransportRequest:
    url: str
    method: str
    headers: dict[str, str]
    body: Optional[str] = None
    #: Whether transport-level failures and transient statuses may be retried.
    retryable: bool = False
    #: Noun used in error messages, e.g. "Request" / "Runtime request".
    label: str = "Request"
    #: Per-request deadline (ms), overriding ``TransportConfig.timeout_ms``.
    timeout_ms: Optional[int] = None


@dataclass
class TransportResult:
    status: int
    body: Any
    request_id: Optional[str] = None
    retry_after_ms: Optional[int] = None


class Transport:
    def __init__(self, cfg: TransportConfig) -> None:
        self.cfg = cfg

    async def send(self, req: TransportRequest) -> TransportResult:
        """Send one logical request, retrying transient failures when retryable.

        Returns the final response (ok or not) — the caller maps non-ok statuses
        to typed errors, since control-plane and data-plane contracts differ.
        """
        max_attempts = (self.cfg.retry.max_retries + 1) if req.retryable else 1
        timeout_s = (req.timeout_ms if req.timeout_ms is not None else self.cfg.timeout_ms) / 1000.0

        attempt = 0
        while True:
            self._emit_request(req, attempt)

            response: Any
            try:
                response = await self._fetch(req, timeout_s)
            except Exception as error:  # noqa: BLE001 - transport boundary
                # asyncio.CancelledError is a BaseException and propagates as-is.
                if req.retryable and attempt < max_attempts - 1:
                    await self._pause(req, attempt, None)
                    attempt += 1
                    continue
                if self._is_timeout(error):
                    raise ConnectionError(
                        f"{req.label} timed out after {int(timeout_s * 1000)}ms", cause=error
                    ) from error
                raise ConnectionError(f"{req.label} failed", cause=error) from error

            request_id = self._extract_request_id(response)
            # Read the body within the same request window. httpx reads the
            # body eagerly under the same timeout (no separate stalled-stream
            # race needed), so ``.text`` is available here.
            body = self._parse_body(getattr(response, "text", "") or "")
            retry_after_ms = parse_retry_after(self._header(response, "retry-after"))

            self._emit_response(req, response.status_code, request_id, body, attempt)

            if 200 <= response.status_code < 300:
                return TransportResult(response.status_code, body, request_id, retry_after_ms)

            if req.retryable and is_retryable_status(response.status_code) and attempt < max_attempts - 1:
                await self._pause(req, attempt, retry_after_ms)
                attempt += 1
                continue

            return TransportResult(response.status_code, body, request_id, retry_after_ms)

    # ── internals ────────────────────────────────────────────────────────

    async def _fetch(self, req: TransportRequest, timeout_s: float) -> Any:
        content = req.body.encode("utf-8") if req.body is not None else None
        return await self.cfg.client.request(
            req.method,
            req.url,
            headers=req.headers,
            content=content,
            timeout=timeout_s,
        )

    async def _pause(self, req: TransportRequest, attempt: int, retry_after_ms: Optional[int]) -> None:
        await sleep(backoff_delay(attempt, self.cfg.retry, retry_after_ms))

    def _is_timeout(self, error: BaseException) -> bool:
        if isinstance(error, asyncio.TimeoutError):
            return True
        if httpx is not None and isinstance(error, httpx.TimeoutException):
            return True
        return False

    @staticmethod
    def _header(response: Any, name: str) -> Optional[str]:
        headers = getattr(response, "headers", None)
        if headers is None:
            return None
        try:
            return headers.get(name)
        except AttributeError:  # plain dict-style headers
            return headers.get(name)

    @staticmethod
    def _extract_request_id(response: Any) -> Optional[str]:
        for name in ("x-request-id", "x-vinkius-request-id"):
            value = response.headers.get(name)
            if value:
                return value
        return None

    @staticmethod
    def _parse_body(text: str) -> Any:
        if not text:
            return None
        try:
            return json.loads(text)
        except (ValueError, TypeError):
            return text

    def _emit_request(self, req: TransportRequest, attempt: int) -> None:
        hooks = self.cfg.hooks
        if hooks is None:
            return
        on_request = getattr(hooks, "on_request", None)
        if on_request is None:
            return
        on_request(
            req.method,
            redact_url(req.url),
            redact_headers(req.headers),
            attempt,
        )

    def _emit_response(
        self,
        req: TransportRequest,
        status: int,
        request_id: Optional[str],
        body: Any,
        attempt: int,
    ) -> None:
        hooks = self.cfg.hooks
        if hooks is None:
            return
        on_response = getattr(hooks, "on_response", None)
        if on_response is None:
            return
        on_response(
            status,
            redact_url(req.url),
            request_id,
            redact_body(body),
            attempt,
        )
