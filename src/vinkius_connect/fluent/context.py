"""Shared runtime context threaded through the fluent layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..core.cache import ResolverCache
from ..core.http import HttpClient
from ..core.runtime import RuntimeClient

__all__ = ["SdkContext"]


@dataclass
class SdkContext:
    #: Control-plane HTTP client (Bearer + app-id binding).
    http: HttpClient
    #: Public application id (``vk_app_*``).
    app_id: str
    #: Shared, process-scoped TTL cache for NON-SECRET, stable resolution data
    #: (e.g. catalog credential schemas). Per the cache golden rule, secrets —
    #: credentials and anything ``vk_live_*`` — must NEVER enter this cache.
    cache: ResolverCache
    #: How a capability's display name is namespaced across connectors.
    namespace: Callable[[str, str], str]
    #: Build a client for the MCP runtime — the ONLY surface for tool listing and
    #: execution. Given a connection's ``mcp_url`` (which embeds its
    #: ``vk_live_*`` token), returns a client that talks JSON-RPC directly.
    runtime: Callable[[str], RuntimeClient]
