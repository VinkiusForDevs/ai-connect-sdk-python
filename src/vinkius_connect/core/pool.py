"""Concurrency-limited asyncio pooling."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Sequence

__all__ = ["pooled_map"]


async def pooled_map(
    items: Sequence[Any],
    limit: int,
    fn: Callable[[Any, int], Awaitable[Any]],
) -> list[Any]:
    """Map over ``items`` with at most ``limit`` in-flight coroutines.

    Order of results matches the order of ``items``. Per-item failures are not
    swallowed here; the caller handles them.
    """
    results: list[Any] = [None] * len(items)
    semaphore = asyncio.Semaphore(max(1, limit))

    async def run(index: int, item: Any) -> None:
        async with semaphore:
            results[index] = await fn(item, index)

    if items:
        await asyncio.gather(*(run(index, item) for index, item in enumerate(items)))
    return results
