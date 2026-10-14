"""Framework adapters.

Zero-dependency converters that turn Vinkius capabilities into each framework's
native **tool** format (each framework's own term). Where a framework needs one
of its own factories, you inject it — no peer dependency, no version coupling.

Submodules (import directly from the package, e.g.
``from vinkius_connect.adapters import openai``):

* ``json_schema`` — neutral JSON Schema (lowest common denominator).
* ``openai`` — chat-completions tools.
* ``anthropic`` — Messages API tools.
* ``gemini`` — function declarations.
* ``langchain`` — LangChain tools (injected factory).
* ``llamaindex`` — LlamaIndex tools (injected factory).
* ``openai_agents`` — ``openai-agents`` function tools (injected factory).
* ``crewai`` — CrewAI tools (injected decorator).
"""

from . import (
    anthropic,
    crewai,
    gemini,
    json_schema,
    langchain,
    llamaindex,
    openai,
    openai_agents,
    shared,
)

__all__ = [
    "anthropic",
    "crewai",
    "gemini",
    "json_schema",
    "langchain",
    "llamaindex",
    "openai",
    "openai_agents",
    "shared",
]
