"""Concurrency-limited promise/asyncio pooling."""

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

    Order of results matches the order of ``items``. Failures are propagated
    by the caller (the SDK catches per-item errors in the fan-out that uses
    this helper), not swallowed here.
    """
    results: list[Any] = [None] * len(items)
    semaphore = asyncio.Semaphore(max(1, limit))

    async def run(index: int, item: Any) -> None:
        async with semaphore:
            results[index] = await fn(item, index)

    if items:
        await asyncio.gather(*(run(index, item) for index, item in enumerate(items)))
    return results
