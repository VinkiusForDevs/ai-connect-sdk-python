"""Catalog discovery.

    GET /catalog/mcps                    -> paginated CatalogConnector
    GET /catalog/mcps/{slug}            -> CatalogConnectorDetail (+ credential_schema)
    GET /marketplace/search?q=...&page= -> marketplace-ranked search results

Catalog listing/detail use the internal MCP data-plane routes. Search uses the
public marketplace endpoint so SDK consumers receive the same ranking and
results as the Vinkius website.
"""

from __future__ import annotations

import urllib.parse
from typing import Any, AsyncIterator, Optional

from ..core.http import HttpClient
from ..core.pagination import normalize_paginated, page_iterator, unwrap_item

__all__ = ["CatalogClient"]


def _normalize_marketplace_search(body: Any) -> list[dict]:
    if not isinstance(body, dict):
        return []
    results = body.get("results")
    if not isinstance(results, list):
        return []

    normalized = []
    for connector in results:
        if not isinstance(connector, dict):
            continue
        normalized.append(
            {
                "id": connector.get("id"),
                "slug": connector.get("slug"),
                "title": connector.get("title"),
                "short_description": connector.get("short_description"),
                "publisher_type": connector.get("publisher_type"),
                "listing_type": connector.get("listing_type", connector.get("server_type", "")),
                "requires_buyer_auth": connector.get(
                    "requires_buyer_auth",
                    connector.get("requires_auth", False),
                ),
                "server_type": connector.get("server_type"),
                "tools_count": connector.get("tools_count"),
            }
        )
    return normalized


class CatalogClient:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def list(self, opts: Optional[dict] = None) -> dict:
        """List public connectors (page-based, 50 per page)."""
        opts = opts or {}
        body = await self._http.get(
            "/catalog/mcps",
            query={"page": opts.get("page")},
            idempotency_key=opts.get("idempotency_key"),
            timeout_ms=opts.get("timeout_ms"),
        )
        return normalize_paginated(body)

    async def iterate(self, opts: Optional[dict] = None) -> AsyncIterator[dict]:
        """Iterate every catalog connector across all pages.

        Seeds with the explicitly-requested page (if given), so a caller can
        resume from a known page; otherwise starts at the first page.
        """
        opts = opts or {}

        async def fetch_page(page: int) -> dict:
            return await self.list({**opts, "page": page})

        first = await self.list(opts)
        async for item in page_iterator(first, fetch_page):
            yield item

    async def get(self, slug: str, opts: Optional[dict] = None) -> dict:
        """Fetch a single connector by slug (or uuid), including its credential schema."""
        opts = opts or {}
        path = f"/catalog/mcps/{urllib.parse.quote(slug, safe='')}"
        body = await self._http.get(
            path,
            idempotency_key=opts.get("idempotency_key"),
            timeout_ms=opts.get("timeout_ms"),
        )
        return unwrap_item(body)

    async def search(self, query: str, opts: Optional[dict] = None) -> list[dict]:
        """Search using the same endpoint and ranking as the Vinkius marketplace."""
        opts = opts or {}
        body = await self._http.get(
            "/marketplace/search",
            query={"q": query, "page": opts.get("page", 1)},
            idempotency_key=opts.get("idempotency_key"),
            timeout_ms=opts.get("timeout_ms"),
        )
        return _normalize_marketplace_search(body)
