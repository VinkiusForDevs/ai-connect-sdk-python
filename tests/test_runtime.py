"""RuntimeClient JSON-RPC tests."""

from __future__ import annotations

import json

import pytest

from fake_client import FakeClient, FakeResponse
from vinkius_connect.core.errors import AuthError, NotFoundError, ProtocolError
from vinkius_connect.core.retry import DEFAULT_RETRY
from vinkius_connect.core.runtime import RuntimeClient, RuntimeClientConfig, _extract_envelope
from vinkius_connect.types import CapabilityResult


def _runtime(fake: FakeClient, url: str = "https://runtime/vk_live_t/mcp") -> RuntimeClient:
    return RuntimeClient(
        url,
        RuntimeClientConfig(
            timeout_ms=1000,
            retry=DEFAULT_RETRY,
            client=fake,
            user_agent="vinkius-connect/test",
        ),
    )


async def test_list_tools_parses_jsonrpc_and_normalizes():
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "tools": [
                {"name": "create_issue", "title": "Create", "description": "d",
                 "inputSchema": {"type": "object"}},
            ]
        },
    }
    fc = FakeClient().enqueue(FakeResponse(200, payload))
    tools = await _runtime(fc).list_tools()
    assert tools[0]["name"] == "create_issue"
    assert tools[0]["input_schema"] == {"type": "object"}
    # camelCase inputSchema is coerced to snake_case input_schema.
    assert "inputSchema" not in tools[0]


async def test_list_tools_rejects_missing_tools_array():
    fc = FakeClient().enqueue(FakeResponse(200, {"jsonrpc": "2.0", "id": 1, "result": {}}))
    with pytest.raises(ProtocolError):
        await _runtime(fc).list_tools()


async def test_call_tool_returns_capability_result():
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "content": [{"type": "text", "text": "done"}],
            "isError": False,
            "structuredContent": {"ok": True},
        },
    }
    fc = FakeClient().enqueue(FakeResponse(200, payload))
    result = await _runtime(fc).call_tool("create_issue", {"title": "x"})
    assert isinstance(result, CapabilityResult)
    assert result.content == [{"type": "text", "text": "done"}]
    assert result.is_error is False
    assert result.structured_content == {"ok": True}
    assert fc.body_of["method"] == "tools/call"
    assert fc.body_of["params"] == {"name": "create_issue", "arguments": {"title": "x"}}


async def test_call_tool_is_error_is_a_result_not_a_throw():
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"content": [{"type": "text", "text": "oops"}], "isError": True},
    }
    fc = FakeClient().enqueue(FakeResponse(200, payload))
    result = await _runtime(fc).call_tool("x", None)
    assert result.is_error is True


async def test_runtime_maps_jsonrpc_error_to_protocolerror():
    payload = {"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "bad"}}
    fc = FakeClient().enqueue(FakeResponse(200, payload))
    with pytest.raises(ProtocolError) as exc:
        await _runtime(fc).call_tool("x", {})
    assert exc.value.message == "bad"


async def test_runtime_maps_http_403_to_autherror():
    fc = FakeClient().enqueue(FakeResponse(403, {"error": "revoked"}))
    with pytest.raises(AuthError) as exc:
        await _runtime(fc).list_tools()
    assert exc.value.message == "revoked"


async def test_runtime_maps_http_404_to_notfound():
    fc = FakeClient().enqueue(FakeResponse(404, {"error": "unknown"}))
    with pytest.raises(NotFoundError):
        await _runtime(fc).list_tools()


async def test_runtime_maps_5xx_to_connectionerror():
    # 503 is a transient, retryable status. tools/list is idempotent, so it
    # exhausts the default 2 retries (3 attempts) before mapping to connection_error.
    fc = FakeClient().enqueue(
        FakeResponse(503, {"error": "x"}),
        FakeResponse(503, {"error": "x"}),
        FakeResponse(503, {"error": "x"}),
    )
    rt = _runtime(fc)
    from vinkius_connect.core.errors import VinkiusError

    with pytest.raises(VinkiusError) as exc:
        await rt.list_tools()
    assert exc.value.code == "connection_error"
    # tools/list is idempotent -> it retried (3 attempts with default policy).
    assert len(fc.requests) == DEFAULT_RETRY.max_retries + 1


async def test_sse_stream_last_frame_wins():
    sse = "data: {\"jsonrpc\": \"2.0\", \"id\": 1, \"result\": {\"tools\": []}}\n\n"
    sse += "data: " + json.dumps(
        {"jsonrpc": "2.0", "id": 1, "result": {"tools": [{"name": "t1"}]}}
    )
    fc = FakeClient().enqueue(FakeResponse(200, text=sse))
    tools = await _runtime(fc).list_tools()
    # The last data frame is the authoritative one.
    assert tools == [{"name": "t1", "title": None, "description": None, "input_schema": {}}]


def test_sse_non_json_frames_are_ignored():
    sse = ": comment\ndata: not-json\ndata: {\"a\": 1}\n"
    assert _extract_envelope(sse) == {"a": 1}


def test_non_sse_json_passes_through():
    assert _extract_envelope({"a": 1}) == {"a": 1}
