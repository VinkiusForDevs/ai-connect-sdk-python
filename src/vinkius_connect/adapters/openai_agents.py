"""OpenAI Agents SDK adapter (Python, ``openai-agents``).

Builds function tools for the Python ``openai-agents`` SDK — distinct from the
chat-completions :mod:`openai` adapter. Inject the SDK's own ``function_tool``
factory; the capability's JSON Schema is passed as raw parameters with
``strict=False``, so the platform (not the model) owns input validation.

Example::

    from agents import Agent, function_tool
    tools = to_openai_agents_tools(await user.capabilities(), function_tool)
    agent = Agent(name="assistant", instructions="...", tools=tools)
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from ..fluent.capability import Capability
from .shared import normalize_params

__all__ = ["to_openai_agents_tools"]


def to_openai_agents_tools(
    capabilities,
    tool_factory: Callable[[Callable[[dict], Awaitable[str]], str, str], Any],
):
    """Convert Vinkius capabilities to ``openai-agents`` function tools.

    ``tool_factory`` mirrors ``agents.function_tool``: it is called as
    ``tool_factory(func, name, description)`` and must return a tool object.
    The capability's JSON Schema is exposed verbatim on the wrapped function so
    the platform validates inputs server-side (raw JSON Schema, not strict
    mode).
    """
    tools = []
    for capability in capabilities:
        cap = capability

        async def func(args: dict, _cap: Capability = cap) -> str:
            result = await _cap.execute(args)
            return result.text()

        # Attach the raw JSON Schema so the platform owns validation.
        func.description = capability.description
        func.parameters = normalize_params(capability.input_schema)
        func.strict = False
        tools.append(tool_factory(func, capability.name, capability.description))
    return tools
