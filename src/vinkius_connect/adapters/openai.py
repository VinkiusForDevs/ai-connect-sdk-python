"""OpenAI adapter.

Converts Vinkius capabilities into OpenAI's chat-completions **tool** format
(OpenAI's own technical term for these). Zero-dependency: uses plain dicts
compatible with the ``openai`` Python SDK — no import of ``openai``.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..types import CapabilityResult
from .shared import find_capability, normalize_params, parse_args, validate_tool_name

__all__ = [
    "validate_openai_function_name",
    "to_openai_tools",
    "run_openai_tool_call",
]

#: OpenAI tool-function names must be 1–64 chars of ``[a-zA-Z0-9_-]``. The SDK
#: namespaces capabilities as ``connector__name``, which can violate this (too
#: long, or containing dots/spaces from a connector or capability name).
OPENAI_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
OPENAI_NAME_MAX = 64


def validate_openai_function_name(name: str) -> None:
    validate_tool_name(name, "OpenAI", OPENAI_NAME_RE, OPENAI_NAME_MAX)


def to_openai_tools(capabilities) -> list[dict]:
    """Convert Vinkius capabilities to OpenAI chat-completions ``tools``."""
    tools = []
    for capability in capabilities:
        validate_openai_function_name(capability.name)
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": capability.name,
                    "description": capability.description,
                    "parameters": normalize_params(capability.input_schema),
                },
            }
        )
    return tools


async def run_openai_tool_call(
    capabilities,
    call: Any,
    opts: Optional[dict] = None,
) -> CapabilityResult:
    """Execute the Vinkius capability named by an OpenAI tool call.

    ``call`` is an OpenAI ``tool_call`` — a dict (``{"function": {"name",
    "arguments"}}``) or an SDK object exposing the same attributes.
    """
    fn = call["function"] if isinstance(call, dict) else call.function
    name = fn["name"] if isinstance(fn, dict) else fn.name
    arguments = fn["arguments"] if isinstance(fn, dict) else fn.arguments
    capability = find_capability(capabilities, name)
    return await capability.execute(parse_args(arguments), opts)
