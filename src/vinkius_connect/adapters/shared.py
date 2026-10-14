"""Shared helpers for framework adapters."""

from __future__ import annotations

import json
from typing import Optional

from ..core.errors import ConfigError, NotFoundError
from ..fluent.capability import Capability

__all__ = [
    "normalize_params",
    "parse_args",
    "find_capability",
    "validate_tool_name",
]


def normalize_params(schema: Optional[dict]) -> dict:
    """Ensure a usable JSON Schema object for function/tool parameters."""
    if isinstance(schema, dict) and len(schema) > 0:
        return schema
    return {"type": "object", "properties": {}}


def parse_args(raw: str) -> dict:
    """Parse a JSON arguments string into a dict, tolerating malformed input.

    The platform validates tool input, so an unparsable payload executes as an
    empty argument set and surfaces as an ``is_error`` tool result the model can
    recover from — rather than raising mid agent-loop.
    """
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def find_capability(capabilities, name: str) -> Capability:
    """Find a capability by display name or raw name, throwing when absent."""
    for capability in capabilities:
        if capability.name == name or capability.raw_name == name:
            return capability
    raise NotFoundError(f"Unknown capability: {name}")


def validate_tool_name(name: str, platform: str, pattern, max_length: int) -> None:
    """Guard against tool names a platform would reject (length/charset).

    Throws a clear :class:`ConfigError` up front instead of a cryptic platform
    400 at call time.
    """
    if len(name) > max_length or not pattern.match(name):
        raise ConfigError(
            f'Capability "{name}" cannot be exposed as a {platform} tool name: it must be '
            f"{max_length} char(s) or fewer and match {pattern.pattern!r} (got {len(name)} char(s)). "
            "Override VinkiusOptions.namespace_capability to produce platform-compatible names."
        )
