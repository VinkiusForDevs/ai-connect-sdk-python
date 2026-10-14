"""Pagination tests (mirrors test/pagination.test.ts)."""

from __future__ import annotations

import pytest

from vinkius_connect.core.errors import ProtocolError
from vinkius_connect.core.pagination import normalize_paginated, page_iterator, unwrap_item, unwrap_list


def test_normalize_paginated_full_envelope():
    body = {"data": [1, 2], "meta": {"total": 2}, "links": {"next": "x"}}
    out = normalize_paginated(body)
    assert out["data"] == [1, 2]
    assert out["meta"] == {"total": 2}
    assert out["links"] == {"next": "x"}


def test_normalize_paginated_bare_data():
    out = normalize_paginated({"data": ["a"]})
    assert out["data"] == ["a"]
    assert "meta" not in out
    assert "links" not in out


def test_normalize_paginated_rejects_bad_shape():
    with pytest.raises(ProtocolError):
        normalize_paginated({"data": "not-a-list"})
    with pytest.raises(ProtocolError):
        normalize_paginated([1, 2])  # bare top-level array is not a list envelope


def test_unwrap_list_bare_and_envelope():
    assert unwrap_list([1, 2]) == [1, 2]
    assert unwrap_list({"data": [3, 4]}) == [3, 4]


def test_unwrap_item_envelope_and_fallback():
    assert unwrap_item({"data": {"id": "x"}}) == {"id": "x"}
    # No `data` key -> return the body itself.
    assert unwrap_item({"ok": True}) == {"ok": True}
    # Empty DELETE -> None body returns None.
    assert unwrap_item(None) is None


async def test_page_iterator_single_page():
    first = {"data": [1, 2, 3]}  # no meta -> single page

    async def fetch(page):
        raise AssertionError("should not fetch more pages")

    items = [i async for i in page_iterator(first, fetch)]
    assert items == [1, 2, 3]


async def test_page_iterator_multi_page():
    pages = {1: {"data": ["a", "b"], "meta": {"current_page": 1, "last_page": 2}},
             2: {"data": ["c"], "meta": {"current_page": 2, "last_page": 2}}}
    calls = []

    async def fetch(page):
        calls.append(page)
        return pages[page]

    items = [i async for i in page_iterator(pages[1], fetch)]
    assert items == ["a", "b", "c"]
    assert calls == [2]
