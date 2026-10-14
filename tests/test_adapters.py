"""Framework adapter tests (mirrors test/adapters.test.ts)."""

from __future__ import annotations

from vinkius_connect.adapters import (
    anthropic,
    crewai,
    gemini,
    json_schema,
    langchain,
    llamaindex,
    openai,
    openai_agents,
)
from vinkius_connect.fluent.capability import Capability, CapabilitySet


class _StubExecutor:
    """Records (raw_name, args) and returns a canned CapabilityResult."""

    def __init__(self, text="stub-result"):
        self.calls = []
        self._text = text

    async def __call__(self, raw_name, args, opts):
        self.calls.append((raw_name, args))
        from vinkius_connect.types import CapabilityResult

        return CapabilityResult(
            content=[{"type": "text", "text": self._text}], is_error=False
        )


def _caps(executor=None, connector="github"):
    ex = executor or _StubExecutor()
    set_ = CapabilitySet.from_capabilities([
        Capability(
            ex,
            init={
                "connector": connector,
                "connection_id": "c1",
                "name": f"{connector}__create_issue",
                "raw_name": "create_issue",
                "title": "Create",
                "description": "Open an issue",
                "input_schema": {"type": "object", "properties": {"title": {"type": "string"}}},
            },
        ),
        Capability(
            ex,
            init={
                "connector": connector,
                "connection_id": "c1",
                "name": f"{connector}__list_repos",
                "raw_name": "list_repos",
                "title": None,
                "description": "",
                "input_schema": {},
            },
        ),
    ])
    return ex, set_


# ── neutral json-schema ────────────────────────────────────────────────────


def test_to_json_schema_tools():
    ex, caps = _caps()
    tools = json_schema.to_json_schema_tools(caps)
    assert tools[0] == {
        "name": "github__create_issue",
        "description": "Open an issue",
        "parameters": {"type": "object", "properties": {"title": {"type": "string"}}},
    }
    # Empty schema normalizes to an empty object schema.
    assert tools[1]["parameters"] == {"type": "object", "properties": {}}


async def test_execute_by_name_dispatches():
    ex, caps = _caps()
    result = await json_schema.execute_by_name(caps, "github__create_issue", {"title": "x"})
    assert result.text() == "stub-result"
    assert ex.calls == [("create_issue", {"title": "x"})]


# ── openai ─────────────────────────────────────────────────────────────────


def test_to_openai_tools():
    ex, caps = _caps()
    tools = openai.to_openai_tools(caps)
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "github__create_issue"
    assert tools[0]["function"]["parameters"]["type"] == "object"


async def test_run_openai_tool_call_dict_form():
    ex, caps = _caps()
    call = {"function": {"name": "github__create_issue", "arguments": '{"title":"x"}'}}
    result = await openai.run_openai_tool_call(caps, call)
    assert result.text() == "stub-result"
    assert ex.calls == [("create_issue", {"title": "x"})]


async def test_run_openai_tool_call_object_form():
    ex, caps = _caps()

    class Fn:
        name = "github__list_repos"
        arguments = ""

    class Call:
        function = Fn()

    result = await openai.run_openai_tool_call(caps, Call())
    assert result.text() == "stub-result"
    assert ex.calls == [("list_repos", {})]


def test_openai_rejects_bad_name():
    ex, caps = _caps()

    class Long:
        name = "a" * 80
        description = ""
        input_schema = {}

    from vinkius_connect.core.errors import ConfigError

    with __import__("pytest").raises(ConfigError):
        openai.to_openai_tools([Long()])


# ── anthropic ──────────────────────────────────────────────────────────────


def test_to_anthropic_tools():
    ex, caps = _caps()
    tools = anthropic.to_anthropic_tools(caps)
    assert tools[0]["name"] == "github__create_issue"
    assert "input_schema" in tools[0]


async def test_run_anthropic_tool_use():
    ex, caps = _caps()
    result = await anthropic.run_anthropic_tool_use(caps, {"name": "github__create_issue", "input": {"title": "y"}})
    assert result.text() == "stub-result"
    assert ex.calls == [("create_issue", {"title": "y"})]


# ── gemini ─────────────────────────────────────────────────────────────────


def test_to_gemini_tools_validates_names():
    ex, caps = _caps()
    decls = gemini.to_gemini_tools(caps)
    assert decls[0]["name"] == "github__create_issue"
    assert "parameters" in decls[0]

    # A hyphenated connector would break Gemini naming -> validated up front.
    ex2, bad = _caps(connector="google-calendar")
    from vinkius_connect.core.errors import ConfigError
    import pytest

    with pytest.raises(ConfigError):
        gemini.to_gemini_tools(bad)


async def test_run_gemini_function_call():
    ex, caps = _caps()
    result = await gemini.run_gemini_function_call(caps, {"name": "github__list_repos", "args": {}})
    assert result.text() == "stub-result"


# ── langchain ──────────────────────────────────────────────────────────────


async def test_to_langchain_tools_injects_factory():
    ex, caps = _caps()
    seen = []

    def tool_factory(func, config):
        seen.append((func, config))
        return ("tool", config["name"], config["description"], config["args_schema"])

    tools = langchain.to_langchain_tools(caps, tool_factory)
    assert len(tools) == 2
    assert tools[0][1] == "github__create_issue"
    assert tools[0][3]["type"] == "object"
    # The injected func actually executes the capability.
    out = await seen[0][0]({"title": "z"})
    assert out == "stub-result"


# ── llamaindex ─────────────────────────────────────────────────────────────


async def test_to_llamaindex_tools_injects_factory():
    ex, caps = _caps()
    seen = []

    def tool_factory(func, name, description, schema):
        seen.append({"func": func, "name": name, "description": description, "schema": schema})
        return name

    tools = llamaindex.to_llamaindex_tools(caps, tool_factory)
    assert tools == ["github__create_issue", "github__list_repos"]
    out = await seen[0]["func"]({"title": "q"})
    assert out == "stub-result"
    assert seen[0]["schema"]["type"] == "object"


# ── openai-agents ──────────────────────────────────────────────────────────


def test_to_openai_agents_tools_injects_factory():
    ex, caps = _caps()
    seen = []

    def tool_factory(func, name, description):
        seen.append((func, name, description))
        return ("agent-tool", name)

    tools = openai_agents.to_openai_agents_tools(caps, tool_factory)
    assert tools[0] == ("agent-tool", "github__create_issue")
    # The raw JSON schema is exposed for platform-side validation.
    assert seen[0][0].parameters["type"] == "object"
    assert seen[0][0].strict is False


# ── crewai ─────────────────────────────────────────────────────────────────


def test_to_crewai_tools_injects_decorator():
    ex, caps = _caps()
    seen = []

    def tool_decorator(func):
        seen.append(func)
        return ("crew-tool", func.__name__)

    tools = crewai.to_crewai_tools(caps, tool_decorator)
    assert tools[0] == ("crew-tool", "github__create_issue")
    # The wrapped tool function executes the capability synchronously.
    out = seen[0]({"title": "crew"})
    assert out == "stub-result"
    assert ex.calls and ex.calls[0][0] == "create_issue"


# ── shared helpers ────────────────────────────────────────────────────────


def test_parse_args_tolerates_malformed():
    from vinkius_connect.adapters.shared import parse_args

    assert parse_args('{"a": 1}') == {"a": 1}
    assert parse_args("") == {}
    assert parse_args("not json") == {}
    assert parse_args("[1,2,3]") == {}  # non-object -> {}
