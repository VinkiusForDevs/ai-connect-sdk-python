"""Connections for a user (low-level).

A connection is an established connector for a user. Creating one connects the
connector (get-or-create user + connection; idempotent per user+connector).
The SDK exposes these as "connections".
"""

from __future__ import annotations

import urllib.parse
from typing import Optional

from ..core.http import HttpClient
from ..core.pagination import unwrap_item, unwrap_list
from ..core.validate import assert_external_id

__all__ = ["ConnectionsClient", "CreateConnectionInput"]


class CreateConnectionInput(dict):
    """Input for :meth:`ConnectionsClient.create`. ``connector`` is a slug or catalog id."""


class ConnectionsClient:
    def __init__(self, http: HttpClient, app_id: str, external_id: str) -> None:
        assert_external_id(external_id)
        self._http = http
        self._app_id = app_id
        #: The client's external_id (addresses the user directly).
        self._external_id = external_id

    def _base(self) -> str:
        app = urllib.parse.quote(self._app_id)
        user = urllib.parse.quote(self._external_id, safe="")
        return f"/apps/{app}/users/{user}/mcps"

    async def list(self, opts: Optional[dict] = None) -> list[dict]:
        """List the user's connections (not paginated; empty for an unknown user)."""
        opts = opts or {}
        body = await self._http.get(
            self._base(),
            idempotency_key=opts.get("idempotency_key"),
            timeout_ms=opts.get("timeout_ms"),
        )
        return unwrap_list(body)

    async def create(self, input: dict, opts: Optional[dict] = None) -> dict:
        """Connect a catalog connector for the user (get-or-create; idempotent)."""
        opts = opts or {}
        body = await self._http.post(
            self._base(),
            {"catalog_mcp_id": input["connector"]},
            idempotent=True,
            idempotency_key=opts.get("idempotency_key"),
            timeout_ms=opts.get("timeout_ms"),
        )
        return unwrap_item(body)

    async def get(self, connection_id: str, opts: Optional[dict] = None) -> dict:
        opts = opts or {}
        path = f"{self._base()}/{urllib.parse.quote(connection_id, safe='')}"
        body = await self._http.get(
            path,
            idempotency_key=opts.get("idempotency_key"),
            timeout_ms=opts.get("timeout_ms"),
        )
        return unwrap_item(body)

    async def delete(self, connection_id: str, opts: Optional[dict] = None) -> None:
        opts = opts or {}
        path = f"{self._base()}/{urllib.parse.quote(connection_id, safe='')}"
        await self._http.delete(
            path,
            idempotency_key=opts.get("idempotency_key"),
            timeout_ms=opts.get("timeout_ms"),
        )

    def credentials(self, connection_id: str):
        """Credential management for this connection."""
        from .credentials import CredentialsClient

        return CredentialsClient(self._http, self._app_id, self._external_id, connection_id)

    def tokens(self, connection_id: str):
        """Data-plane token management (mints the ``vk_live_*`` + mcp_url)."""
        from .tokens import ConnectionTokensClient

        return ConnectionTokensClient(self._http, self._app_id, self._external_id, connection_id)
