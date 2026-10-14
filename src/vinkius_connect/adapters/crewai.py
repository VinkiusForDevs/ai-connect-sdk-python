"""CrewAI adapter (Python).

CrewAI is a Python agent framework; the neutral
:func:`~vinkius_connect.adapters.json_schema.to_json_schema_tools` output is the
lowest-common-denominator bridge. This module goes one step further and builds
genuine CrewAI tools via the injected ``@tool`` decorator so they can be
attached to a ``Crew`` / ``Agent``.

Because connector JSON Schemas are not Python-annotated, each tool is wrapped
as a single ``params`` argument (a JSON object or string) — the platform (and
the Vinkius data plane) owns input validation.

Example::

    from crewai.tools import tool
    tools = to_crewai_tools(await user.capabilities(), tool)
    crew = Crew(agents=[agent], tasks=[task], tools=tools)
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable

from ..fluent.capability import Capability
from .shared import normalize_params

__all__ = ["to_crewai_tools", "execute_capability_sync"]


def execute_capability_sync(capability: Capability, args: dict) -> str:
    """Run an async capability from a synchronous context and return its text.

    Handles both a fresh loop (``asyncio.run``) and an already-running loop
    (run in a worker thread so we never nest event loops).
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(capability.execute(args)).text()

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, capability.execute(args)).result()


def _coerce_params(params: Any) -> dict:
    if isinstance(params, dict):
        return params
    if isinstance(params, str) and params:
        try:
            parsed = json.loads(params)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}


def to_crewai_tools(capabilities, tool_factory: Callable):
    """Convert Vinkius capabilities to CrewAI tools using the injected ``@tool``.

    ``tool_factory`` is CrewAI's ``@tool`` decorator (or a compatible
    ``func -> Tool`` factory). Each returned tool takes a single ``params``
    argument (JSON object or string) and executes the capability synchronously.
    """
    tools = []
    for capability in capabilities:
        cap = capability

        def _execute(params: Any = "", _cap: Capability = cap) -> str:
            return execute_capability_sync(_cap, _coerce_params(params))

        _execute.__name__ = capability.name
        _execute.__doc__ = capability.description or capability.name
        _execute._vinkius_input_schema = normalize_params(capability.input_schema)

        decorated = tool_factory(_execute)
        if decorated is not None:
            tools.append(decorated)
    return tools
