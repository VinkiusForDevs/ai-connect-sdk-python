"""Google Gemini adapter.

Converts Vinkius capabilities into Gemini **function declarations** (Gemini's
own term). Zero-dependency: returns plain dicts compatible with the Google
``google-genai`` SDK; no import required.

Example::

    decls = to_gemini_tools(await user.capabilities())
    response = await model.generate_content({
        "contents": contents,
        "tools": [{"function_declarations": decls}],
    })
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..types import CapabilityResult
from .shared import find_capability, normalize_params, validate_tool_name

__all__ = [
    "validate_gemini_function_name",
    "to_gemini_tools",
    "run_gemini_function_call",
]

#: Gemini function names: a letter or underscore followed by letters, numbers,
#: and underscores, max 64 chars. Hyphens are not allowed, so connector slugs
#: like ``google-calendar`` would be rejected; they are validated up front.
GEMINI_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
GEMINI_NAME_MAX = 64


def validate_gemini_function_name(name: str) -> None:
    validate_tool_name(name, "Gemini", GEMINI_NAME_RE, GEMINI_NAME_MAX)


def to_gemini_tools(capabilities) -> list[dict]:
    """Convert Vinkius capabilities to Gemini function declarations."""
    out: list[dict] = []
    for capability in capabilities:
        validate_gemini_function_name(capability.name)
        out.append(
            {
                "name": capability.name,
                "description": capability.description,
                "parameters": normalize_params(capability.input_schema),
            }
        )
    return out


async def run_gemini_function_call(
    capabilities,
    call: Any,
    opts: Optional[dict] = None,
) -> CapabilityResult:
    """Execute the Vinkius capability named by a Gemini function call.

    ``call`` is a Gemini function call — a dict (``{"name", "args"}``) or an
    SDK part object exposing the same attributes.
    """
    name = call["name"] if isinstance(call, dict) else call.name
    args = (
        call.get("args")
        if isinstance(call, dict)
        else getattr(call, "args", None)
    ) or {}
    capability = find_capability(capabilities, name)
    return await capability.execute(args, opts)
