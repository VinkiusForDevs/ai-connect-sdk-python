"""Connector — a lazy handle to one connector for a user.

``user.connector("github")`` performs no network call. The connection is
addressed by the user's ``external_id`` directly; the connection id is resolved
on demand and memoized for the handle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from ..core.errors import ConnectorNotConnectedError, ProtocolError
from ..core.runtime import RuntimeClient
from ..resources.connections import ConnectionsClient
from .capability import CapabilitySet, build_capability
from .context import SdkContext
from .credentials import CredentialsHandle
from .executor import make_executor
from .status import derive_status

if TYPE_CHECKING:
    from .user import UserContext

__all__ = ["Connector"]


class Connector:
    def __init__(self, ctx: SdkContext, user: UserContext, slug: str) -> None:
        self._ctx = ctx
        self._user = user
        self.slug = slug
        self._connection_id: Optional[str] = None
        #: Runtime client for this connection.
        self._runtime_client: Optional[RuntimeClient] = None
        #: Connection id the memoized runtime client was provisioned for.
        self._provisioned_for: Optional[str] = None
        #: In-flight (or settled) token provisioning, shared by concurrent callers.
        self._provisioning: Optional[Any] = None
        self._provisioned_url: Optional[str] = None
        #: Credential management for this connector (operates on an existing connection).
        self.credentials = CredentialsHandle(ctx, user, self)

    def _connections(self) -> ConnectionsClient:
        return ConnectionsClient(self._ctx.http, self._ctx.app_id, self._user.external_id)

    async def connect(self, opts: Optional[dict] = None) -> dict:
        """Connect this connector for the user (get-or-create; idempotent), then
        provision the connection's ``vk_live_*`` data-plane token.

        The returned Connection carries ``runtime_url``, the only surface for
        listing and executing this connection's tools. Callers should persist
        it; the URL (and its embedded token) is returned only here.
        """
        opts = opts or {}
        connection = await self._connections().create(
            {"connector": self.slug},
            {"idempotency_key": opts.get("idempotency_key"), "timeout_ms": opts.get("timeout_ms")},
        )
        self._connection_id = connection.get("id")
        runtime_url = await self._provision_runtime(connection["id"], opts)
        out = dict(connection)
        out["runtime_url"] = runtime_url
        return out

    async def disconnect(self, opts: Optional[dict] = None) -> None:
        """Disconnect this connector for the user."""
        opts = opts or {}
        connection_id = await self.resolve_connection_id(opts)
        await self._connections().delete(
            connection_id,
            {"idempotency_key": opts.get("idempotency_key"), "timeout_ms": opts.get("timeout_ms")},
        )
        self._connection_id = None
        self._runtime_client = None
        self._provisioned_for = None
        self._provisioned_url = None
        self._provisioning = None

    async def status(self, opts: Optional[dict] = None) -> str:
        """Current readiness state."""
        connection = await self._find_connection(opts or {})
        return derive_status(connection) if connection else "not_connected"

    async def capabilities(self, opts: Optional[dict] = None) -> CapabilitySet:
        """Capabilities exposed by this connector, listed directly from the runtime."""
        opts = opts or {}
        runtime, connection_id = await self._resolve_runtime(opts)
        return await self._list_capabilities(runtime, connection_id, opts)

    async def capabilities_for_connection(
        self, connection_id: str, opts: Optional[dict] = None
    ) -> CapabilitySet:
        """List capabilities for an ALREADY-KNOWN connection id.

        Skips the connection lookup entirely (used by the user.capabilities()
        fan-out).
        """
        self._connection_id = connection_id
        runtime, _ = await self._resolve_runtime(opts or {})
        return await self._list_capabilities(runtime, connection_id, opts or {})

    async def _list_capabilities(
        self, runtime: RuntimeClient, connection_id: str, opts: dict
    ) -> CapabilitySet:
        raw = await runtime.list_tools(
            idempotency_key=opts.get("idempotency_key"),
            timeout_ms=opts.get("timeout_ms"),
        )
        executor = make_executor(runtime)
        return CapabilitySet.from_capabilities(
            [
                build_capability(
                    data,
                    ctx={
                        "connector": self.slug,
                        "connection_id": connection_id,
                        "namespace": self._ctx.namespace,
                        "executor": executor,
                    },
                )
                for data in raw
            ]
        )

    async def resolve_connection_id(self, opts: Optional[dict] = None) -> str:
        """Resolve (and memoize) this connector's connection id, or throw if not connected."""
        opts = opts or {}
        if self._connection_id is not None:
            return self._connection_id
        connection = await self._find_connection(opts)
        if not connection:
            raise ConnectorNotConnectedError(
                f'Connector "{self.slug}" is not connected for this user — call connect() first.'
            )
        return connection["id"]

    async def _resolve_runtime(
        self, opts: dict
    ) -> tuple[RuntimeClient, str]:
        connection_id = await self.resolve_connection_id(opts)
        if self._runtime_client is not None:
            return self._runtime_client, connection_id
        await self._provision_runtime(connection_id, opts)
        return self._runtime_client, connection_id

    async def _provision_runtime(self, connection_id: str, opts: dict) -> str:
        """Mint the connection's data-plane token and memoize a runtime client from its mcp_url.

        Memo hits are keyed by connection id: a NEW connection (e.g. after a
        delete + reconnect) must never inherit the previous token's mcp_url.
        The in-flight provisioning coroutine is shared, so parallel callers
        never race into a double mint.
        """
        if self._provisioned_for == connection_id and self._provisioned_url is not None:
            return self._provisioned_url
        if self._provisioning is not None:
            return await self._provisioning

        async def attempt() -> str:
            issued = await self._connections().tokens(connection_id).issue(
                {}, {"idempotency_key": opts.get("idempotency_key"), "timeout_ms": opts.get("timeout_ms")}
            )
            if not issued.get("mcp_url"):
                raise ProtocolError(
                    "Token provisioning did not return a runtime URL (mcp_url).",
                    code="protocol_error",
                    details={"connection_id": connection_id},
                )
            self._runtime_client = self._ctx.runtime(issued["mcp_url"])
            self._provisioned_for = connection_id
            self._provisioned_url = issued["mcp_url"]
            return issued["mcp_url"]

        import asyncio

        task = asyncio.ensure_future(attempt())
        self._provisioning = task
        try:
            result = await task
            return result
        finally:
            # Clear the in-flight handle on BOTH success and failure: on success the
            # memo lives in ``provisioned_url``/``provisioned_for``; on failure a
            # later call must retry. A settled task must never be reused for a
            # different connection id.
            if self._provisioning is task:
                self._provisioning = None

    async def _find_connection(self, opts: dict) -> Optional[dict]:
        connections = await self._connections().list(
            {"idempotency_key": opts.get("idempotency_key"), "timeout_ms": opts.get("timeout_ms")}
        )
        match = next(
            (c for c in connections if c.get("slug") == self.slug or c.get("id") == self.slug),
            None,
        )
        self._connection_id = match.get("id") if match else None
        return match
