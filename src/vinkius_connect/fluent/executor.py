"""Factory for a CapabilityExecutor bound to one connection's runtime."""

from __future__ import annotations

from typing import Any, Optional

from ..core.runtime import RuntimeClient
from .capability import CapabilityExecutor

__all__ = ["make_executor"]


def make_executor(runtime: RuntimeClient) -> CapabilityExecutor:
    """Bind an executor to a connection's runtime client.

    Execution runs against the runtime client; the connection's ``vk_live_*``
    token is embedded in its ``mcp_url``, so no API auth headers are added here.
    """

    async def executor(
        raw_name: str,
        args: Optional[dict],
        opts: Optional[dict],
    ) -> Any:
        opts = opts or {}
        return await runtime.call_tool(
            raw_name,
            args,
            idempotency_key=opts.get("idempotency_key"),
            timeout_ms=opts.get("timeout_ms"),
        )

    return executor
