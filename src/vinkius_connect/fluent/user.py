"""UserContext — a lazy handle to one end-user's connectors and capabilities.

``vinkius.user("usr_123")`` performs zero network calls and stores nothing but
the client's ``external_id``. Every operation addresses the API by that
external_id directly — the SDK never resolves nor holds an internal user id.
"""

from __future__ import annotations

from typing import Any, Optional

from ..core.pool import pooled_map
from ..core.validate import assert_external_id
from ..resources.app_users import AppUsersClient
from .capability import CapabilitySet
from .connector import Connector
from .context import SdkContext
from .status import summarize

__all__ = ["UserContext"]


class UserContext:
    def __init__(self, ctx: SdkContext, external_id: str) -> None:
        assert_external_id(external_id)
        self._ctx = ctx
        self.external_id = external_id
        self._users = AppUsersClient(ctx.http, ctx.app_id)

    async def ensure(self, metadata: Optional[dict] = None) -> dict:
        """Explicitly upsert the user (e.g. to attach metadata up front). Optional.

        Returns the :class:`AppUser` dict.
        """
        input: dict[str, Any] = {"external_id": self.external_id}
        if metadata:
            input["metadata"] = metadata
        return await self._users.create(input)

    async def get(self, opts: Optional[dict] = None) -> dict:
        """Fetch the underlying user resource."""
        return await self._users.get(self.external_id, opts or {})

    def connector(self, slug: str) -> Connector:
        """Lazy handle to one connector."""
        return Connector(self._ctx, self, slug)

    async def connectors(self, opts: Optional[dict] = None) -> list[dict]:
        """Connected connectors for this user, with derived status."""
        connections = await self._users.connections(self.external_id).list(opts or {})
        return [summarize(c) for c in connections]

    async def capabilities(self, query: Optional[dict] = None) -> CapabilitySet:
        """Aggregated, executable capabilities across the user's ready connectors.

        Tools are listed and executed exclusively at the MCP runtime — the sole
        metered, revocable surface. Because each connection is billed and
        kill-switched independently by its own ``vk_live_*`` token, aggregation
        is a fan-out over the connected connectors (each resolves its own
        runtime), not a single API call. Only ``ready`` connectors are included;
        the rest cannot list tools until connected/credentialed.

        ``query`` may carry: ``include`` / ``exclude`` (slug lists),
        ``on_connector_error`` (callback), and request controls
        (``idempotency_key``, ``timeout_ms``).

        For a single connector, prefer
        ``user.connector(slug).capabilities()`` — it avoids listing every
        connection.
        """
        query = query or {}
        include = set(query["include"]) if query.get("include") else None
        exclude = set(query["exclude"]) if query.get("exclude") else None

        summaries = await self.connectors(
            {
                "idempotency_key": query.get("idempotency_key"),
                "timeout_ms": query.get("timeout_ms"),
            }
        )
        targets = [
            s
            for s in summaries
            if s["status"] == "ready"
            and (include is None or s["slug"] in include)
            and (exclude is None or s["slug"] not in exclude)
        ]

        # Failure-tolerant, concurrency-limited fan-out: one flaky runtime must
        # not sink the whole aggregation (all-failed still raises), and N
        # connectors do not open N simultaneous sockets.
        max_fanout_concurrency = 8
        first_error: Optional[BaseException] = None

        async def one(target: dict, _index: int = 0) -> Optional[CapabilitySet]:
            nonlocal first_error
            try:
                if target.get("connection_id") is not None:
                    return await self.connector(target["slug"]).capabilities_for_connection(
                        target["connection_id"],
                        {
                            "idempotency_key": query.get("idempotency_key"),
                            "timeout_ms": query.get("timeout_ms"),
                        },
                    )
                return await self.connector(target["slug"]).capabilities(
                    {
                        "idempotency_key": query.get("idempotency_key"),
                        "timeout_ms": query.get("timeout_ms"),
                    }
                )
            except BaseException as error:  # isolated failure — never sinks the batch
                if first_error is None:
                    first_error = error
                on_error = query.get("on_connector_error")
                if on_error is not None:
                    on_error(target["slug"], error)
                return None

        settled = await pooled_map(
            targets, max_fanout_concurrency, one
        )

        failures = sum(1 for s in settled if s is None)
        if failures > 0 and failures == len(targets):
            raise first_error

        all_caps = CapabilitySet()
        for s in settled:
            if s is not None:
                all_caps.extend(s)
        return all_caps
