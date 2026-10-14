"""Anthropic adapter.

Converts Vinkius capabilities into the Anthropic Messages API **tool** format
(Anthropic's own term). Zero-dependency: uses plain dicts compatible with the
``anthropic`` Python SDK — no import required.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..types import CapabilityResult
from .shared import find_capability, normalize_params, validate_tool_name

__all__ = [
    "validate_anthropic_tool_name",
    "to_anthropic_tools",
    "run_anthropic_tool_use",
]

#: Anthropic tool names must be 1–128 chars of ``[a-zA-Z0-9_-]``.
ANTHROPIC_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
ANTHROPIC_NAME_MAX = 128


def validate_anthropic_tool_name(name: str) -> None:
    validate_tool_name(name, "Anthropic", ANTHROPIC_NAME_RE, ANTHROPIC_NAME_MAX)


def to_anthropic_tools(capabilities) -> list[dict]:
    """Convert Vinkius capabilities to Anthropic Messages ``tools``."""
    tools = []
    for capability in capabilities:
        validate_anthropic_tool_name(capability.name)
        tools.append(
            {
                "name": capability.name,
                "description": capability.description,
                "input_schema": normalize_params(capability.input_schema),
            }
        )
    return tools


async def run_anthropic_tool_use(
    capabilities,
    use: Any,
    opts: Optional[dict] = None,
) -> CapabilityResult:
    """Execute the Vinkius capability named by an Anthropic ``tool_use`` block.

    ``use`` is an Anthropic tool_use — a dict (``{"name", "input"}``) or an SDK
    object exposing the same attributes.
    """
    name = use["name"] if isinstance(use, dict) else use.name
    input_ = (use.get("input") if isinstance(use, dict) else getattr(use, "input", None)) or {}
    capability = find_capability(capabilities, name)
    return await capability.execute(input_, opts)
