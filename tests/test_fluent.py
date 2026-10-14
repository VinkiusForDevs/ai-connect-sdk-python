"""Fluent-layer tests: UserContext, Connector, Capability, Credentials,
and the user.capabilities() fan-out (mirrors test/user, test/connector,
test/capabilities, test/credentials)."""

from __future__ import annotations

import pytest

from fake_client import FakeClient, FakeResponse
from vinkius_connect import Vinkius
from vinkius_connect.core.errors import ConnectorNotConnectedError, VinkiusError
from vinkius_connect.fluent.capability import CapabilitySet

from conftest import make_vinkius

GITHUB_TOOLS = [
    {"name": "create_issue", "title": "Create", "description": "Open an issue",
     "inputSchema": {"type": "object"}},
    {"name": "list_repos", "description": "List repos", "inputSchema": {}},
]
SLACK_TOOLS = [{"name": "post_message", "description": "Send a message",
                "inputSchema": {"type": "object"}}]


def _conns():
    return [
        {"id": "cg", "slug": "github", "name": "GitHub", "status": "active", "ready": True},
        {"id": "cs", "slug": "slack", "name": "Slack", "status": "active", "ready": True},
    ]


def _route(slack_fail: bool = False):
    def handler(record):
        url, method = record["url"], record["method"]
        if method == "GET" and url.endswith("/users/alice_123/mcps"):
            return FakeResponse(200, {"data": _conns()})
        if method == "POST" and url.endswith("/mcps/cg/tokens"):
            return FakeResponse(200, {"data": {
                "id": "tg", "name": "g", "is_enabled": True,
                "token": "vk_live_g", "mcp_url": "https://rt/vk_live_g/mcp"}})
        if method == "POST" and url.endswith("/mcps/cs/tokens"):
            return FakeResponse(200, {"data": {
                "id": "ts", "name": "s", "is_enabled": True,
                "token": "vk_live_s", "mcp_url": "https://rt/vk_live_s/mcp"}})
        if url == "https://rt/vk_live_g/mcp":
            return FakeResponse(200, {"jsonrpc": "2.0", "id": 1,
                                      "result": {"tools": GITHUB_TOOLS}})
        if url == "https://rt/vk_live_s/mcp":
            if slack_fail:
                return FakeResponse(500, {"error": "down"})
            return FakeResponse(200, {"jsonrpc": "2.0", "id": 1,
                                      "result": {"tools": SLACK_TOOLS}})
        return FakeResponse(404, {"error": "not found"})
    return handler


async def test_user_get_roundtrip():
    fc = FakeClient().enqueue(FakeResponse(200, {"data": {"id": "u1", "external_id": "alice_123"}}))
    v = make_vinkius(fc)
    user = await v.user("alice_123").get()
    assert user == {"id": "u1", "external_id": "alice_123"}


async def test_user_ensure_is_upsert():
    fc = FakeClient().enqueue(FakeResponse(200, {"data": {"id": "u1"}}))
    v = make_vinkius(fc)
    await v.user("alice_123").ensure({"team": "acme"})
    assert fc.body_of == {"external_id": "alice_123", "metadata": {"team": "acme"}}


async def test_connector_connect_provisions_token_and_memoizes():
    fc = FakeClient()
    fc.enqueue(
        FakeResponse(200, {"data": {"id": "c1", "slug": "github", "status": "active", "ready": False}}),
        FakeResponse(200, {"data": {"id": "t1", "is_enabled": True,
                                    "token": "vk_live_a", "mcp_url": "https://rt/vk_live_a/mcp"}}),
    )
    v = make_vinkius(fc)
    conn = await v.user("alice_123").connector("github").connect()
    assert conn["id"] == "c1"
    assert conn["runtime_url"] == "https://rt/vk_live_a/mcp"
    # Two control-plane requests: create connection + issue token.
    assert len(fc.requests) == 2
    assert fc.requests[0]["url"].endswith("/users/alice_123/mcps")
    assert fc.requests[1]["url"].endswith("/users/alice_123/mcps/c1/tokens")


async def test_capabilities_for_connection_uses_runtime_and_namespace():
    fc = FakeClient().route(_route(slack_fail=False))
    v = make_vinkius(fc)
    github = v.user("alice_123").connector("github")
    caps = await github.capabilities_for_connection("cg", {})
    assert isinstance(caps, CapabilitySet)
    assert [c.name for c in caps] == ["github__create_issue", "github__list_repos"]
    # The namespaced display name includes the connector slug.
    create = caps.find_capability("github__create_issue")
    assert create is not None and create.raw_name == "create_issue"
    assert caps.find_capability("create_issue") is not None  # raw-name lookup


async def test_capability_execute_dispatches_to_runtime():
    fc = FakeClient()
    fc.enqueue(
        # 1) connections list (must be an array) — resolve the connection id.
        FakeResponse(200, {"data": [
            {"id": "c1", "slug": "github", "status": "active", "ready": True}]}),
        # 2) mint the data-plane token -> mcp_url.
        FakeResponse(200, {"data": {"id": "t1", "is_enabled": True,
                                    "mcp_url": "https://rt/vk_live_a/mcp"}}),
        # 3) tools/list from the runtime.
        FakeResponse(200, {"jsonrpc": "2.0", "id": 1, "result": {"tools": [
            {"name": "create_issue", "description": "Open an issue",
             "inputSchema": {"type": "object"}}]}}),
        # 4) tools/call result.
        FakeResponse(200, {"jsonrpc": "2.0", "id": 1, "result": {
            "content": [{"type": "text", "text": "issue #42 opened"}], "isError": False}}),
    )
    v = make_vinkius(fc)
    github = v.user("alice_123").connector("github")
    caps = await github.capabilities()
    result = await caps.find_capability("github__create_issue").execute(
        {"owner": "acme", "repo": "product", "title": "x"}
    )
    assert result.content[0]["text"] == "issue #42 opened"
    assert result.is_error is False
    # The runtime tools/call request carries the args.
    call_req = [r for r in fc.requests if r["url"] == "https://rt/vk_live_a/mcp"][-1]
    import json as _json
    assert _json.loads(call_req["content"])["params"]["arguments"] == {
        "owner": "acme", "repo": "product", "title": "x"}


async def test_user_capabilities_fanout_merges_ready_connectors():
    fc = FakeClient().route(_route(slack_fail=False))
    v = make_vinkius(fc)
    caps = await v.user("alice_123").capabilities()
    names = [c.name for c in caps]
    assert "github__create_issue" in names
    assert "github__list_repos" in names
    assert "slack__post_message" in names
    assert len(caps) == 3
    # Per-connector grouping helper.
    assert len(caps.for_connector("github")) == 2
    assert len(caps.for_connector("slack")) == 1


async def test_user_capabilities_is_failure_tolerant():
    errors: list[str] = []
    fc = FakeClient().route(_route(slack_fail=True))
    v = make_vinkius(fc)
    caps = await v.user("alice_123").capabilities(
        {"on_connector_error": lambda slug, err: errors.append(slug)}
    )
    # Slack's runtime is failing; github still resolves.
    assert [c.name for c in caps] == ["github__create_issue", "github__list_repos"]
    assert errors == ["slack"]


async def test_user_capabilities_all_failed_raises():
    def both_fail(record):
        url = record["url"]
        if record["method"] == "GET" and url.endswith("/users/alice_123/mcps"):
            return FakeResponse(200, {"data": _conns()})
        if url.endswith("/tokens"):
            return FakeResponse(200, {"data": {"id": "t", "is_enabled": True,
                                                "mcp_url": "https://rt/vk_live_x/mcp"}})
        return FakeResponse(500, {"error": "runtime down"})

    fc = FakeClient().route(both_fail)
    v = make_vinkius(fc)
    with pytest.raises(VinkiusError):
        await v.user("alice_123").capabilities()


async def test_include_filter_restricts_connectors():
    fc = FakeClient().route(_route(slack_fail=False))
    v = make_vinkius(fc)
    caps = await v.user("alice_123").capabilities({"include": ["github"]})
    assert [c.name for c in caps] == ["github__create_issue", "github__list_repos"]


async def test_exclude_filter():
    fc = FakeClient().route(_route(slack_fail=False))
    v = make_vinkius(fc)
    caps = await v.user("alice_123").capabilities({"exclude": ["github"]})
    assert [c.name for c in caps] == ["slack__post_message"]


async def test_custom_namespace_capability():
    fc = FakeClient().route(_route(slack_fail=False))
    v = make_vinkius(fc, namespace_capability=lambda c, n: f"{c}:{n}")
    caps = await v.user("alice_123").capabilities({"include": ["github"]})
    assert [c.name for c in caps] == ["github:create_issue", "github:list_repos"]


async def test_not_connected_raises_on_missing_connection():
    fc = FakeClient().enqueue(FakeResponse(200, {"data": []}))  # empty connection list
    v = make_vinkius(fc)
    github = v.user("alice_123").connector("github")
    with pytest.raises(ConnectorNotConnectedError):
        await github.resolve_connection_id()


async def test_credentials_schema_and_status():
    def handler(record):
        url, method = record["url"], record["method"]
        if method == "GET" and url.endswith("/users/alice_123/mcps"):
            return FakeResponse(200, {"data": [
                {"id": "cg", "slug": "github", "status": "active", "ready": True}]})
        if url.endswith("/mcps/cg/credentials"):
            if method == "GET":
                return FakeResponse(200, {"schema": {"GITHUB_TOKEN": {"type": "string"}},
                                          "configured": {"GITHUB_TOKEN": False}})
            return FakeResponse(200, {"schema": {}, "configured": {"GITHUB_TOKEN": True}})
        return FakeResponse(404, {"error": "not found"})

    fc = FakeClient().route(handler)
    v = make_vinkius(fc)
    github = v.user("alice_123").connector("github")
    status = await github.credentials.status()
    assert status["configured"]["GITHUB_TOKEN"] is False
    out = await github.credentials.set({"GITHUB_TOKEN": "ghp_x"})
    assert out["configured"]["GITHUB_TOKEN"] is True
    # set wraps the flat map into the HTTP { credentials: {...} } envelope.
    put_req = [r for r in fc.requests if r["method"] == "PUT"][-1]
    import json as _json
    assert _json.loads(put_req["content"]) == {"credentials": {"GITHUB_TOKEN": "ghp_x"}}


async def test_credentials_schema_cached_from_catalog():
    fc = FakeClient()
    fc.enqueue(FakeResponse(200, {"data": {
        "id": "github", "slug": "github", "credential_schema": {"GITHUB_TOKEN": {"type": "string"}}}}))
    v = make_vinkius(fc)
    schema = await v.user("alice_123").connector("github").credentials.schema()
    assert schema == {"GITHUB_TOKEN": {"type": "string"}}
    # Second call is a cache hit -> no extra catalog request.
    requests_before = len(fc.requests)
    schema2 = await v.user("alice_123").connector("github").credentials.schema()
    assert schema2 == schema
    assert len(fc.requests) == requests_before
