"""Retry policy and backoff math.

Retries apply only to idempotent requests and only for transient statuses
(429, 502, 503, 504) or network errors. Backoff uses full jitter to avoid
thundering-herd retries; a ``Retry-After`` header, when present, wins.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from typing import Optional

__all__ = [
    "RetryPolicy",
    "DEFAULT_RETRY",
    "is_retryable_status",
    "backoff_delay",
    "parse_retry_after",
    "sleep",
]


@dataclass
class RetryPolicy:
    max_retries: int
    base_delay_ms: int
    max_delay_ms: int


#: Default retry policy: 2 retries, 250 ms base, 4000 ms cap.
DEFAULT_RETRY = RetryPolicy(max_retries=2, base_delay_ms=250, max_delay_ms=4000)


def is_retryable_status(status: int) -> bool:
    """Whether an HTTP status is worth retrying."""
    return status in (429, 502, 503, 504)


def backoff_delay(attempt: int, policy: RetryPolicy, retry_after_ms: Optional[int] = None) -> int:
    """Compute the delay (ms) before the next attempt (0-indexed).

    A positive ``retry_after_ms`` (server hint) wins, capped at
    ``policy.max_delay_ms``. ``retry_after_ms == 0`` is treated as NO hint:
    honoring it exactly would make simultaneous clients hammer the server in
    lockstep — full jitter instead. Without a hint, full jitter over an
    exponentially growing window.
    """
    if retry_after_ms is not None and retry_after_ms > 0:
        return min(retry_after_ms, policy.max_delay_ms)
    window = min(policy.max_delay_ms, policy.base_delay_ms * (2 ** attempt))
    return round(random.uniform(0, window))


def parse_retry_after(header_value: Optional[str]) -> Optional[int]:
    """Parse a ``Retry-After`` header (delta-seconds or HTTP-date) into ms."""
    if not header_value:
        return None
    try:
        seconds = float(header_value)
    except ValueError:
        seconds = None
    if seconds is not None:
        return max(0, int(seconds * 1000))
    # HTTP-date form: parse relative to now.
    from email.utils import parsedate_to_datetime

    try:
        as_date = parsedate_to_datetime(header_value)
        if as_date is not None:
            import time

            return max(0, int((as_date.timestamp() - time.time()) * 1000))
    except (TypeError, ValueError):
        pass
    return None


async def sleep(ms: int) -> None:
    """Async sleep in milliseconds."""
    await asyncio.sleep(ms / 1000.0)
