"""Connection credentials (low-level, 1:1 with the API).

    GET /apps/{app}/users/{externalId}/mcps/{connection}/credentials  -> CredentialStatus
    PUT  (same)  body { credentials: { KEY: value } }                 -> CredentialStatus

Values are write-only: the API never returns them, only which keys are set.
NOTE the low-level ``set`` takes the raw HTTP envelope ``{ credentials: {...} }``;
the high-level :class:`~vinkius_connect.fluent.credentials.CredentialsHandle`
accepts the flat map instead.
"""

from __future__ import annotations

import urllib.parse
from typing import Optional

from ..core.http import HttpClient
from ..core.validate import assert_external_id

__all__ = ["CredentialsClient", "SetCredentialsInput"]


class SetCredentialsInput(dict):
    """The raw HTTP envelope — ``credentials: {KEY: value}``."""


class CredentialsClient:
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
        return f"/apps/{app}/users/{user}/mcps/{connection}/credentials"

    async def status(self, opts: Optional[dict] = None) -> dict:
        """Which credential keys are configured (never the values)."""
        opts = opts or {}
        return await self._http.get(
            self._base(),
            idempotency_key=opts.get("idempotency_key"),
            timeout_ms=opts.get("timeout_ms"),
        )

    async def set(self, input: dict, opts: Optional[dict] = None) -> dict:
        """Store credentials, validated server-side against the connector schema."""
        opts = opts or {}
        return await self._http.put(
            self._base(),
            input,
            idempotency_key=opts.get("idempotency_key"),
            timeout_ms=opts.get("timeout_ms"),
        )
