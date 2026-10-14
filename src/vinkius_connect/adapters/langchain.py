"""LangChain adapter.

Builds LangChain **tools** (LangChain's term). Zero-dependency: instead of
importing ``langchain-core``, you inject LangChain's own tool factory so the
returned objects are genuine LangChain tools (bindable to a model).

Example::

    from langchain_core.tools import StructuredTool
    tools = to_langchain_tools(await user.capabilities(),
                               lambda f, c: StructuredTool.from_function(f, **c))
    model = chat.bind_tools(tools)
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from ..fluent.capability import Capability
from .shared import normalize_params

__all__ = ["to_langchain_tools"]

#: LangChain tool factory — a callable ``(func, config) -> Tool``. ``func`` is
#: an async function taking a dict input and returning a string; ``config``
#: carries ``name``, ``description``, and ``args_schema``.
LangChainToolFactory = Callable[
    [Callable[[dict], Awaitable[str]], dict], Any
]


def to_langchain_tools(capabilities, tool_factory: LangChainToolFactory):
    """Convert Vinkius capabilities to LangChain tools using the injected factory."""
    tools = []
    for capability in capabilities:
        cap = capability

        async def func(input: dict, _cap: Capability = cap) -> str:
            result = await _cap.execute(input)
            return result.text()

        tools.append(
            tool_factory(
                func,
                {
                    "name": capability.name,
                    "description": capability.description,
                    "args_schema": normalize_params(capability.input_schema),
                },
            )
        )
    return tools
