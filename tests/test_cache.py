"""ResolverCache tests."""

from __future__ import annotations

import asyncio

from vinkius_connect.core.cache import ResolverCache


async def test_get_set_delete_clear():
    c = ResolverCache(ttl_ms=60_000)
    assert c.get("k") is None
    c.set("k", 42)
    assert c.get("k") == 42
    c.delete("k")
    assert c.get("k") is None
    c.set("a", 1)
    c.set("b", 2)
    c.clear()
    assert c.get("a") is None and c.get("b") is None


async def test_ttl_expiry():
    c = ResolverCache(ttl_ms=1)  # expires ~immediately
    c.set("k", "v")
    await asyncio.sleep(0.002)
    assert c.get("k") is None


async def test_resolve_caches_and_skips_compute_on_hit():
    c = ResolverCache()
    calls = 0

    async def compute():
        nonlocal calls
        calls += 1
        return {"x": calls}

    first = await c.resolve("k", compute)
    second = await c.resolve("k", compute)
    assert first == {"x": 1}
    assert second == {"x": 1}
    assert calls == 1  # compute ran once; the second call was a cache hit
