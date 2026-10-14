"""Catalog client tests."""

from __future__ import annotations

from fake_client import FakeClient, FakeResponse
from conftest import make_vinkius


async def test_catalog_list_paginated():
    fc = FakeClient().enqueue(FakeResponse(200, {
        "data": [{"id": "github", "slug": "github", "title": "GitHub"}],
        "meta": {"current_page": 1, "last_page": 2, "total": 2},
        "links": {"next": "p2"},
    }))
    v = make_vinkius(fc)
    page = await v.catalog.list({"page": 1})
    assert page["data"][0]["slug"] == "github"
    assert page["meta"]["last_page"] == 2


async def test_catalog_get_detail_includes_credential_schema():
    fc = FakeClient().enqueue(FakeResponse(200, {"data": {
        "id": "github", "slug": "github", "title": "GitHub",
        "credential_schema": {"GITHUB_TOKEN": {"type": "string"}},
    }}))
    v = make_vinkius(fc)
    detail = await v.catalog.get("github")
    assert detail["credential_schema"]["GITHUB_TOKEN"]["type"] == "string"


async def test_catalog_search_normalizes_marketplace_shape():
    fc = FakeClient().enqueue(FakeResponse(200, {
        "results": [
            {"id": "gh", "slug": "github", "title": "GitHub",
             "short_description": "code", "publisher_type": "first_party",
             "requires_auth": True, "server_type": "remote", "tools_count": 12},
        ],
        "has_more": False,
    }))
    v = make_vinkius(fc)
    results = await v.catalog.search("code")
    assert results[0]["slug"] == "github"
    # listing_type falls back to server_type; requires_buyer_auth falls back to requires_auth.
    assert results[0]["listing_type"] == "remote"
    assert results[0]["requires_buyer_auth"] is True


async def test_catalog_search_empty_when_no_results_key():
    fc = FakeClient().enqueue(FakeResponse(200, {"has_more": False}))
    v = make_vinkius(fc)
    assert await v.catalog.search("x") == []
