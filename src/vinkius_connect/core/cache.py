"""A small TTL cache for non-secret resolution data.

GOLDEN RULE: the cache is an optimization, never a source of authorization.
Only non-secret, stable values belong here (e.g. catalog credential schemas).
Credentials, Authorization headers, and any ``vk_live_*`` MUST NEVER be cached
— and never even reach the SDK.
"""

from __future__ import annotations

import time
from typing import Any, Awaitable, Callable, Generic, Optional, TypeVar

__all__ = ["ResolverCache"]

_V = TypeVar("_V")


class _Entry(Generic[_V]):
    def __init__(self, value: _V, expires_at: float) -> None:
        self.value = value
        self.expires_at = expires_at


class ResolverCache:
    """In-memory TTL cache for stable, non-secret resolution data."""

    def __init__(self, ttl_ms: int = 5 * 60 * 1000) -> None:
        self._ttl_ms = ttl_ms
        self._store: dict[str, _Entry[Any]] = {}

    def _now_ms(self) -> float:
        return time.monotonic() * 1000.0

    def get(self, key: str) -> Any:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.expires_at <= self._now_ms():
            del self._store[key]
            return None
        return entry.value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = _Entry(value, self._now_ms() + self._ttl_ms)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    async def resolve(self, key: str, compute: "Callable[[], Awaitable[Any]]") -> Any:
        """Return the cached value or compute, cache, and return it.

        ``compute`` is a no-arg callable returning an awaitable (typically an
        async function). It is invoked and awaited only on a cache miss; the
        result is cached and returned.
        """
        cached = self.get(key)
        if cached is not None:
            return cached
        value = await compute()
        self.set(key, value)
        return value
