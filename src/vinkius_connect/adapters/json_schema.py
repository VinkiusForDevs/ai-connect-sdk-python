"""Neutral JSON Schema adapter.

The lowest common denominator: converts Vinkius capabilities into plain function
definitions ``{ name, description, parameters }`` (JSON Schema). Use it with any
OpenAI-compatible provider not listed here, or as the bridge for a custom agent
loop / a framework outside this SDK (e.g. wrapping a capability as a CrewAI
tool).
"""

from __future__ import annotations

from typing import Any, Optional

from ..fluent.capability import Capability
from ..types import CapabilityResult
from .shared import find_capability, normalize_params

__all__ = ["to_json_schema_tools", "execute_by_name"]


def to_json_schema_tools(capabilities) -> list[dict]:
    """Convert Vinkius capabilities to neutral JSON Schema tool definitions."""
    return [
        {
            "name": capability.name,
            "description": capability.description,
            "parameters": normalize_params(capability.input_schema),
        }
        for capability in capabilities
    ]


async def execute_by_name(
    capabilities,
    name: str,
    args: Optional[dict] = None,
    opts: Optional[dict] = None,
) -> CapabilityResult:
    """Execute a capability by (namespaced or raw) name — a generic dispatch helper."""
    capability = find_capability(capabilities, name)
    return await capability.execute(args or {}, opts)
