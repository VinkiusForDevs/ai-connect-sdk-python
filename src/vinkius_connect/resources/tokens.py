"""Connection tokens (low-level, 1:1 with the API).

    POST /apps/{app}/users/{externalId}/mcps/{connection}/tokens  -> IssuedConnectionToken

A token is the ``vk_live_*`` data-plane credential bound to one connection. The
API returns its plaintext AND its runtime ``mcp_url`` ONLY on this create call —
they are never re-fetchable. Every tool call through the runtime is metered
against this token, and the user can disable/delete it (kill switch).

The SDK provisions exactly one token per connection at ``connect()`` time and
remembers its runtime URL; it never silently re-mints on execution, so a revoked
token fails closed instead of quietly billing a fresh one.
"""

from __future__ import annotations

import urllib.parse
from typing import Optional

from ..core.http import HttpClient
from ..core.pagination import unwrap_item
from ..core.validate import assert_external_id

__all__ = ["ConnectionTokensClient", "IssueTokenInput"]


class IssueTokenInput(dict):
    """Optional label for the token (shown in the dashboard) — ``name``."""


class ConnectionTokensClient:
    def __init__(self, http: HttpClient, app_id: str, external_id: str, connection_id: str) -> None:
        assert_external_id(external_id)
        self._http = http
        self._app_id = app_id
        self._external_id = external_id
        self._connection_id = connection_id

    def _base(self) -> str:
        app = urllib.parse.quote(self._app_id)
        user = urllib.parse.quote(self._external_id, safe="")
        connection = urllib.parse.quote(self._connection_id, safe="")
        return f"/apps/{app}/users/{user}/mcps/{connection}/tokens"

    async def issue(self, input: Optional[dict] = None, opts: Optional[dict] = None) -> dict:
        """Mint a data-plane token; the response carries the one-time plaintext + mcp_url."""
        opts = opts or {}
        input = input or {}
        body = await self._http.post(
            self._base(),
            {"name": input["name"]} if input.get("name") is not None else {},
            # Not retry-safe: each POST mints a distinct token. Never auto-retry.
            idempotent=False,
            idempotency_key=opts.get("idempotency_key"),
            timeout_ms=opts.get("timeout_ms"),
        )
        return unwrap_item(body)
