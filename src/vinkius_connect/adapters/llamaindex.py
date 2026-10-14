"""LlamaIndex adapter (Python).

Builds LlamaIndex **tools** (LlamaIndex's term). Zero-dependency: inject
LlamaIndex's own ``FunctionTool``/tool factory so the returned objects are
genuine, bindable LlamaIndex tools. Accepts raw JSON Schema — no Pydantic/Zod
required for the schema itself.

Example::

    from llama_index.core.tools import FunctionTool
    tools = to_llamaindex_tools(await user.capabilities(), FunctionTool.from_function)
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from ..fluent.capability import Capability
from .shared import normalize_params

__all__ = ["to_llamaindex_tools"]


def to_llamaindex_tools(capabilities, tool_factory: Callable[[Any, str, str, dict], Any]):
    """Convert Vinkius capabilities to LlamaIndex tools using the injected factory.

    ``tool_factory`` is called as ``tool_factory(func, name, description,
    schema)`` and must return a genuine LlamaIndex tool.
    """
    tools = []
    for capability in capabilities:
        cap = capability

        async def func(input: dict, _cap: Capability = cap) -> str:
            result = await _cap.execute(input)
            return result.text()

        tools.append(
            tool_factory(
                func,
                capability.name,
                capability.description,
                normalize_params(capability.input_schema),
            )
        )
    return tools
