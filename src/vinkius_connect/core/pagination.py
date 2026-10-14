"""Pagination normalization.

Some list endpoints return a length-aware envelope (``{ data, links, meta }``);
others return only ``{ data: [...] }``. This module coerces both into a dict
with a ``data`` key (and optional ``meta``/``links``) and exposes the raw list
when a plain array is expected.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Awaitable, Callable, Optional

from .errors import ProtocolError

__all__ = ["normalize_paginated", "unwrap_list", "unwrap_item", "page_iterator"]


def _list_envelope(body: Any) -> dict:
    if not isinstance(body, dict) or not isinstance(body.get("data"), list):
        raise ProtocolError(
            "Expected a list response shaped as an array or { data: [...] }.",
            code="protocol_error",
            details=body,
        )
    return body


def normalize_paginated(body: Any) -> dict:
    """Normalize a valid list response into a ``{ data, meta?, links? }`` dict."""
    raw = _list_envelope(body)
    result: dict[str, Any] = {"data": raw["data"]}
    if raw.get("meta"):
        result["meta"] = raw["meta"]
    if raw.get("links"):
        result["links"] = raw["links"]
    return result


def unwrap_list(body: Any) -> list:
    """Unwrap a ``{ data: [...] }`` (or bare array) response into a plain list."""
    if isinstance(body, list):
        return body
    return _list_envelope(body)["data"]


def unwrap_item(body: Any) -> Any:
    """Unwrap a single-resource ``{ data: {...} }`` response.

    Falls back to the body itself when there is no ``data`` key (e.g. an empty
    DELETE response).
    """
    if isinstance(body, dict) and "data" in body and body["data"] is not None:
        return body["data"]
    return body


async def page_iterator(
    first: dict,
    fetch_page: Callable[[int], Awaitable[dict]],
) -> AsyncIterator[Any]:
    """Walk every page of a page-based list, yielding each item in order.

    Starts from ``first`` (already fetched), then advances ``meta.current_page``
    until ``meta.last_page`` is reached. ``fetch_page`` must fetch the given
    1-based page number. A single-page response (no ``meta``) yields exactly once.
    """
    current = first
    meta = current.get("meta") or {}
    page = meta.get("current_page") or 1
    while True:
        for item in current["data"]:
            yield item
        last_page = meta.get("last_page") or page
        if page >= last_page:
            return
        current = await fetch_page(page + 1)
        meta = current.get("meta") or {}
        page += 1
