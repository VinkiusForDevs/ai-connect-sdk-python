"""Capability and CapabilitySet: the agent-facing units of a user's connectors.

A :class:`Capability` is executable and framework-neutral. :class:`CapabilitySet`
is a ``list`` subclass with ergonomic helpers.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Optional

from ..core.errors import ProtocolError
from ..types import CapabilityResult

__all__ = [
    "Capability",
    "CapabilitySet",
    "build_capability",
    "CapabilityExecutor",
]

#: Executes a capability at the runtime.
#: Signature: ``(raw_name, args, opts) -> Awaitable[CapabilityResult]``. The
#: runtime target (a connection's ``mcp_url``, which embeds its ``vk_live_*``
#: token) is bound into the executor when the capability is built, so the
#: signature carries no routing coordinates.
CapabilityExecutor = Callable[
    [str, Optional[dict], Optional[dict]], Awaitable[CapabilityResult]
]


class Capability:
    """An executable, framework-neutral capability bound to one connection."""

    def __init__(self, executor: CapabilityExecutor, *, init: dict) -> None:
        self._executor = executor
        #: Slug of the connector this capability belongs to.
        self.connector: str = init["connector"]
        #: Connection id used to route execution.
        self.connection_id: str = init["connection_id"]
        #: Display name, namespaced across connectors (e.g. ``github__create_issue``).
        self.name: str = init["name"]
        #: Raw name as the connector exposes it (e.g. ``create_issue``).
        self.raw_name: str = init["raw_name"]
        self.title: Optional[str] = init.get("title")
        self.description: str = init.get("description") or ""
        self.input_schema: dict = init.get("input_schema") or {}

    async def execute(
        self,
        args: Optional[dict] = None,
        opts: Optional[dict] = None,
    ) -> CapabilityResult:
        """Execute this capability at the runtime.

        ``is_error=True`` results are returned, not thrown — so the agent loop
        can feed the error back to the model and recover.
        """
        return await self._executor(self.raw_name, args, opts)


def build_capability(data: Optional[dict], *, ctx: dict) -> "Capability":
    """Build a :class:`Capability` from a raw :data:`CapabilityData` payload.

    ``ctx`` carries: ``connector``, ``connection_id``, ``namespace`` (callable),
    ``executor``.
    """
    raw_name = (data or {}).get("name")
    if not isinstance(raw_name, str) or not raw_name.strip():
        raise ProtocolError(
            "Capability payload is missing a non-empty name.",
            code="protocol_error",
            details=data,
        )
    connector = ctx.get("connector")
    connection_id = ctx.get("connection_id")
    if not connector or not connection_id:
        raise ProtocolError(
            "Capability payload is missing connector routing metadata.",
            code="protocol_error",
            details={"connector": connector, "connection_id": connection_id},
        )
    namespace = ctx["namespace"]
    return Capability(
        ctx["executor"],
        init={
            "connector": connector,
            "connection_id": connection_id,
            "name": namespace(connector, raw_name),
            "raw_name": raw_name,
            "title": (data or {}).get("title") or None,
            "description": (data or {}).get("description") or "",
            "input_schema": (data or {}).get("input_schema") or {},
        },
    )


class CapabilitySet(list):
    """A ``list`` of :class:`Capability` with ergonomic helpers."""

    @classmethod
    def from_capabilities(cls, capabilities) -> "CapabilitySet":
        """Build a CapabilitySet from an iterable of capabilities."""
        return cls(list(capabilities))

    def for_connector(self, slug: str) -> "CapabilitySet":
        """Capabilities belonging to a specific connector slug."""
        return CapabilitySet.from_capabilities(
            [c for c in self if c.connector == slug]
        )

    def find_capability(self, name: str) -> Optional["Capability"]:
        """Find a capability by display name or raw name."""
        for capability in self:
            if capability.name == name or capability.raw_name == name:
                return capability
        return None
