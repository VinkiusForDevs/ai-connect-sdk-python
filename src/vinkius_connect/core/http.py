"""The HTTP client: transport-based, dependency-light, runtime-agnostic.

Responsibilities:

* Bearer auth with the ``vk_app_sk_*`` key (never logged).
* Automatic retries (idempotent requests only) with full-jitter backoff,
  honoring ``Retry-After``.
* Consistent error mapping (see :func:`~vinkius_connect.core.errors.map_http_error`).
* Redacted observability hooks.

Transport mechanics (timeout, retries, hooks) live in
:class:`~vinkius_connect.core.transport.Transport` and are shared with the
data-plane :class:`~vinkius_connect.core.runtime.RuntimeClient`.
"""

from __future__ import annotations

import json
from typing import Any, Optional
from urllib.parse import urlencode, urlsplit, urlunsplit

from .errors import map_http_error
from .retry import RetryPolicy
from .transport import Transport, TransportConfig, TransportRequest, TransportResult

__all__ = ["HttpClient", "HttpClientConfig"]

#: Header carrying the public app id — the API authenticates it against the key.
APP_ID_HEADER = "x-vinkius-app-id"


class HttpClientConfig:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        app_id: str,
        timeout_ms: int,
        retry: RetryPolicy,
        client: Any,
        user_agent: str,
        hooks: Optional[Any] = None,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        #: Public application id (``vk_app_*``) — sent on every request as the tenant binding.
        self.app_id = app_id
        self.timeout_ms = timeout_ms
        self.retry = retry
        self.client = client
        self.user_agent = user_agent
        self.hooks = hooks

    def transport(self) -> Transport:
        return Transport(
            TransportConfig(
                timeout_ms=self.timeout_ms,
                retry=self.retry,
                client=self.client,
                user_agent=self.user_agent,
                hooks=self.hooks,
            )
        )


class HttpClient:
    def __init__(self, cfg: HttpClientConfig) -> None:
        self.cfg = cfg
        self._transport = cfg.transport()

    async def get(self, path: str, *, query: Optional[dict[str, Any]] = None, **req: Any) -> Any:
        return await self.request("GET", path, query=query, **req)

    async def post(self, path: str, body: Any = None, *, query: Optional[dict[str, Any]] = None, **req: Any) -> Any:
        return await self.request("POST", path, body=body, query=query, **req)

    async def put(self, path: str, body: Any = None, *, query: Optional[dict[str, Any]] = None, **req: Any) -> Any:
        return await self.request("PUT", path, body=body, query=query, **req)

    async def patch(self, path: str, body: Any = None, *, query: Optional[dict[str, Any]] = None, **req: Any) -> Any:
        return await self.request("PATCH", path, body=body, query=query, **req)

    async def delete(self, path: str, *, query: Optional[dict[str, Any]] = None, **req: Any) -> Any:
        return await self.request("DELETE", path, query=query, **req)

    async def request(
        self,
        method: str,
        path: str,
        *,
        body: Any = None,
        query: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        idempotent: Optional[bool] = None,
        idempotency_key: Optional[str] = None,
        timeout_ms: Optional[int] = None,
    ) -> Any:
        """Issue one logical HTTP request and return the parsed JSON body.

        ``idempotent`` forces retry-safety. It defaults to True for
        GET/PUT/DELETE and False otherwise. Declaring an ``idempotency_key`` is
        itself a retry-safety declaration: the server deduplicates replays, so a
        request carrying one is retried even when its method is not idempotent.
        """
        url = self._build_url(path, query)
        hdrs = self._build_headers(headers, has_body=body is not None, idempotency_key=idempotency_key)
        if idempotent is None:
            idempotent = method in ("GET", "PUT", "DELETE")
        retryable = idempotent or idempotency_key is not None

        body_text = None if body is None else json.dumps(body)
        result = await self._transport.send(
            TransportRequest(
                url=url,
                method=method,
                headers=hdrs,
                body=body_text,
                retryable=retryable,
                label="Request",
                timeout_ms=timeout_ms,
            )
        )
        if 200 <= result.status < 300:
            return result.body
        raise map_http_error(result.status, result.body, result.request_id, result.retry_after_ms)

    # ── helpers ─────────────────────────────────────────────────────────

    def _build_url(self, path: str, query: Optional[dict[str, Any]]) -> str:
        base = self.cfg.base_url.rstrip("/")
        full = f"{base}{path if path.startswith('/') else '/' + path}"
        if query:
            pairs = {k: str(v) for k, v in query.items() if v is not None}
            if pairs:
                sep = "&" if "?" in full else "?"
                full = f"{full}{sep}{urlencode(pairs)}"
        return full

    def _build_headers(
        self,
        extra: Optional[dict[str, str]],
        *,
        has_body: bool,
        idempotency_key: Optional[str],
    ) -> dict[str, str]:
        headers = {
            "authorization": f"Bearer {self.cfg.api_key}",
            APP_ID_HEADER: self.cfg.app_id,
            "accept": "application/json",
            "user-agent": self.cfg.user_agent,
        }
        if extra:
            headers.update(extra)
        if has_body:
            headers["content-type"] = "application/json"
        if idempotency_key:
            headers["idempotency-key"] = idempotency_key
        return headers
