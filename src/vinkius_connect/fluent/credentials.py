"""CredentialsHandle — high-level credential management for one connection.

Operates on an EXISTING connection (it never connects implicitly). The flat
``set(values)`` map is wrapped into the HTTP ``{ credentials: values }``
envelope so the wire shape never leaks into the SDK surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from ..core.errors import ProtocolError
from ..resources.catalog import CatalogClient
from ..resources.credentials import CredentialsClient

if TYPE_CHECKING:
    from .connector import Connector
    from .context import SdkContext
    from .user import UserContext

__all__ = ["CredentialsHandle"]


class CredentialsHandle:
    def __init__(self, ctx: "SdkContext", user: "UserContext", connector: "Connector") -> None:
        self._ctx = ctx
        self._user = user
        self._connector = connector

    async def schema(self, opts: Optional[dict] = None) -> dict:
        """The credential schema this connector requires (from the catalog).

        Cached (non-secret, stable data — per the cache golden rule, no
        credential VALUES ever pass through here, only field descriptors).
        """
        opts = opts or {}
        key = f"credential-schema:{self._connector.slug}"

        async def compute() -> dict:
            detail = await CatalogClient(self._ctx.http).get(
                self._connector.slug,
                {"idempotency_key": opts.get("idempotency_key"), "timeout_ms": opts.get("timeout_ms")},
            )
            return detail.get("credential_schema") or {}

        return await self._ctx.cache.resolve(key, compute)

    async def status(self, opts: Optional[dict] = None) -> dict:
        """Which credential keys are configured (never the values)."""
        opts = opts or {}
        connection_id = await self._connector.resolve_connection_id(opts)
        return await self._client(connection_id).status(opts)

    async def set(self, values: dict, opts: Optional[dict] = None) -> dict:
        """Store credentials (validated server-side against the schema)."""
        opts = opts or {}
        connection_id = await self._connector.resolve_connection_id(opts)
        return await self._client(connection_id).set({"credentials": values}, opts)

    def _client(self, connection_id: str) -> CredentialsClient:
        return CredentialsClient(
            self._ctx.http, self._ctx.app_id, self._user.external_id, connection_id
        )
