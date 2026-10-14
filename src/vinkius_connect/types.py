"""Public type contracts for the Vinkius Connect Python SDK.

Domain vocabulary: an application has end-users; each user has **connectors**
(integrations they connect, e.g. GitHub); a connected connector is a
**connection**; and the executable units the AI uses are **capabilities**.

Raw resource shapes match the API JSON (``snake_case``) and are represented as
plain ``dict`` at runtime (exactly what the wire returns). Structured,
behavior-bearing types are dataclasses / classes below.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal, Optional, Protocol

__all__ = [
    "JSONSchema",
    "AppUser",
    "Connection",
    "IssuedConnectionToken",
    "CatalogConnector",
    "CatalogConnectorDetail",
    "CapabilityResult",
    "CapabilityData",
    "ConnectorStatus",
    "RequestOptions",
    "ExecuteOptions",
    "CapabilityQuery",
    "HookInfo",
    "Hooks",
    "VinkiusOptions",
]

# A JSON Schema object (loosely typed: capability input schemas vary).
JSONSchema = dict[str, Any]

# Wire resource shapes (plain dicts, keyed by the API's snake_case fields).
# They are documented here for reference; runtime values are the parsed JSON.
AppUser = dict[str, Any]
Connection = dict[str, Any]
IssuedConnectionToken = dict[str, Any]
CatalogConnector = dict[str, Any]
CatalogConnectorDetail = dict[str, Any]
CapabilityData = dict[str, Any]

#: Derived state of a connector for a user.
ConnectorStatus = Literal["not_connected", "needs_credentials", "ready", "disabled"]


class _OnRequest(Protocol):
    def __call__(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        attempt: Optional[int] = None,
    ) -> None: ...


class _OnResponse(Protocol):
    def __call__(
        self,
        status: int,
        url: str,
        request_id: Optional[str] = None,
        body: Any = None,
        attempt: Optional[int] = None,
    ) -> None: ...


class Hooks(Protocol):
    """Observability hooks.

    ``headers`` and ``body`` are ALWAYS redacted before being handed to these
    callbacks — secrets never reach a hook. ``attempt`` is the 0-based retry
    attempt that produced the event.
    """

    on_request: Optional[Callable[..., None]]
    on_response: Optional[Callable[..., None]]


@dataclass
class CapabilityResult:
    """Result of a capability execution. ``is_error`` is a result, not a raise.

    ``content`` holds the (optionally multi-part) textual result. A capability
    failure comes back as ``is_error=True`` — so the agent loop can feed the
    error back to the model and recover.
    """

    content: list[dict[str, str]] = field(default_factory=list)
    is_error: bool = False
    #: Structured (parsed) output returned by the capability, when the
    #: connector provides it (``structuredContent``), surfaced verbatim.
    structured_content: Any = None

    def text(self) -> str:
        """Join the textual content parts with newlines (the common case)."""
        return "\n".join(part.get("text", "") for part in self.content)


@dataclass
class RequestOptions:
    """Optional per-request controls accepted by every SDK call."""

    #: Reserved for an optional cancellation handle; the SDK relies on
    #: standard task cancellation for timeouts.
    signal: Any = None
    #: Idempotency key forwarded as the ``Idempotency-Key`` header. Declaring it
    #: makes the request retry-safe: transport retries are enabled even for
    #: non-idempotent methods, and the server deduplicates replays.
    idempotency_key: Optional[str] = None
    #: Per-request deadline in milliseconds, overriding the client-level
    #: ``timeout_ms``. Covers both the connection wait and the body read.
    timeout_ms: Optional[int] = None


@dataclass
class ExecuteOptions(RequestOptions):
    """Per-request controls for capability execution (adds idempotency).

    The idempotency key so a retried execution (e.g. after a network timeout)
    does not duplicate side effects. Forwarded as the ``Idempotency-Key`` header.
    """


@dataclass
class CapabilityQuery:
    """Filter for ``CapabilitySet`` aggregation."""

    #: Restrict to these connector slugs (client-side filter before any call).
    include: Optional[list[str]] = None
    #: Exclude these connector slugs (client-side filter before any call).
    exclude: Optional[list[str]] = None
    #: Optional callback to observe a single connector's capability-list failure;
    #: by default such failures are swallowed so the rest still resolves.
    on_connector_error: Optional[Callable[[str, BaseException], None]] = None
    idempotency_key: Optional[str] = None
    timeout_ms: Optional[int] = None


#: Reserved payload for hooks (kept for API parity; redacted by the transport).
HookInfo = dict[str, Any]


@dataclass
class VinkiusOptions:
    """Options accepted by the :class:`~vinkius_connect.Vinkius` constructor.

    Pass to :class:`~vinkius_connect.Vinkius` (or as a plain ``dict`` of the
    same fields) to configure the client.
    """

    #: Public application id — the ``vk_app_*`` identifier (route key).
    app_id: str
    #: Secret application key — the ``vk_app_sk_*`` credential (Bearer auth).
    api_key: str
    #: Per-request timeout in milliseconds. Default: 30000.
    timeout_ms: Optional[int] = None
    #: Max automatic retries for idempotent requests. Default: 2.
    max_retries: Optional[int] = None
    #: An ``httpx.AsyncClient`` (or compatible object with async ``request``)
    #: to use for transport. Injected for tests / custom runtimes; when omitted
    #: the SDK builds its own ``httpx.AsyncClient``.
    client: Any = None
    #: Extra token appended to the default User-Agent.
    user_agent: Optional[str] = None
    #: Observability hooks (redacted) — an object with optional ``on_request`` /
    #: ``on_response`` callables.
    hooks: Any = None
    #: Controls how a capability's display name is namespaced across connectors.
    #: Default: ``(connector, name) -> f"{connector}__{name}"``.
    namespace_capability: Optional[Callable[[str, str], str]] = None


def _encode_payload(payload: Any) -> str:
    """JSON-encode a request body (``None`` -> empty string, no body)."""
    return json.dumps(payload)
