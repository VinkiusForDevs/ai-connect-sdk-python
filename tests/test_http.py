"""HttpClient and transport tests."""

from __future__ import annotations

import httpx
import pytest

from fake_client import FakeClient, FakeResponse
from vinkius_connect import NotFoundError, Vinkius, VinkiusError
from vinkius_connect.core.errors import ConnectionError

from conftest import make_vinkius


async def test_get_sends_auth_and_appid_headers():
    fc = FakeClient().enqueue(FakeResponse(200, {"data": {"ok": True}}))
    v = make_vinkius(fc)
    out = await v.users.get("alice_123")
    assert out == {"ok": True}
    last = fc.last
    assert last["method"] == "GET"
    assert last["url"].endswith("/apps/vk_app_test/users/alice_123")
    assert last["headers"]["authorization"] == "Bearer vk_app_sk_test"
    assert last["headers"]["x-vinkius-app-id"] == "vk_app_test"
    assert "vinkius-connect/" in last["headers"]["user-agent"]


async def test_post_serializes_body_and_sets_content_type():
    fc = FakeClient().enqueue(FakeResponse(200, {"data": {"id": "c1"}}))
    v = make_vinkius(fc)
    await v.users.connections("alice_123").create({"connector": "github"})
    last = fc.last
    assert last["method"] == "POST"
    assert last["headers"]["content-type"] == "application/json"
    assert fc.body_of == {"catalog_mcp_id": "github"}


async def test_query_params_are_encoded():
    fc = FakeClient().enqueue(FakeResponse(200, {"data": []}))
    v = make_vinkius(fc)
    await v.users.list({"status": "active", "page": 2})
    assert "status=active" in fc.last["url"]
    assert "page=2" in fc.last["url"]
    assert fc.last["url"].split("?")[0].endswith("/users")


async def test_idempotency_key_header():
    fc = FakeClient().enqueue(FakeResponse(200, {"data": {}}))
    v = make_vinkius(fc)
    await v.users.get("alice_123", {"idempotency_key": "idem-1"})
    assert fc.last["headers"]["idempotency-key"] == "idem-1"


async def test_404_raises_notfound():
    fc = FakeClient().enqueue(FakeResponse(404, {"message": "nope"}))
    v = make_vinkius(fc)
    with pytest.raises(NotFoundError):
        await v.users.get("ghost")


async def test_non_idempotent_post_is_not_retried():
    fc = FakeClient().enqueue(FakeResponse(503, {"message": "down"}))
    v = make_vinkius(fc)
    with pytest.raises(VinkiusError) as exc:
        # Token mint is the non-idempotent POST (idempotent=False, no key).
        await v.users.connections("alice_123").tokens("c1").issue()
    # Not retried: a final 503 maps to the generic api_error (503 is not itself
    # a mapped status, and the request was not retry-safe).
    assert exc.value.code == "api_error"
    assert len(fc.requests) == 1  # non-idempotent POST -> one attempt


async def test_transient_503_is_retried_for_idempotent_get():
    fc = FakeClient().enqueue(
        FakeResponse(503, {"message": "down"}),
        FakeResponse(200, {"data": {"ok": True}}),
    )
    v = make_vinkius(fc)
    out = await v.users.get("alice_123")
    assert out == {"ok": True}
    assert len(fc.requests) == 2


async def test_retry_after_is_honored():
    fc = FakeClient().enqueue(
        FakeResponse(429, {"message": "slow"}, headers={"retry-after": "0"}),
        FakeResponse(200, {"data": {"ok": 1}}),
    )
    v = make_vinkius(fc, max_retries=1)
    out = await v.users.get("alice_123")
    assert out == {"ok": 1}


async def test_network_error_wrapped_as_connectionerror():
    # A retryable GET (idempotent) exhausts the default 2 retries on a
    # persistent network error before surfacing ConnectionError.
    fc = FakeClient().enqueue(
        httpx.ConnectError("boom"),
        httpx.ConnectError("boom"),
        httpx.ConnectError("boom"),
    )
    v = make_vinkius(fc)
    with pytest.raises(ConnectionError) as exc:
        await v.users.get("alice_123")
    assert exc.value.code == "connection_error"
    assert len(fc.requests) == 3


def test_hooks_receive_redacted_data():
    events = {"req": [], "res": []}

    class Hooks:
        def on_request(self, method, url, headers, attempt):
            events["req"].append((method, url, headers, attempt))

        def on_response(self, status, url, request_id, body, attempt):
            events["res"].append((status, url, request_id, body, attempt))

    import asyncio

    fc = FakeClient().enqueue(FakeResponse(200, {"data": {"token": "sek"}}))
    v = make_vinkius(fc, hooks=Hooks())
    asyncio.run(v.users.get("alice_123"))
    method, url, headers, attempt = events["req"][0]
    assert method == "GET"
    assert headers["authorization"] == "[REDACTED]"
    assert "vk_app_sk_test" not in str(headers)
    status, url2, request_id, body, attempt2 = events["res"][0]
    assert status == 200
    assert body["data"]["token"] == "[REDACTED]"


async def test_default_endpoint_is_fixed():
    # The Vinkius endpoint is immutable: there is no public base_url option.
    fc = FakeClient().enqueue(FakeResponse(200, {"data": {}}))
    v = make_vinkius(fc)
    await v.users.get("alice_123")
    assert fc.last["url"].startswith("https://api.vinkius.com/apps/")
