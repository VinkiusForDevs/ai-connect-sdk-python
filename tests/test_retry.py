"""Retry policy / backoff math tests (mirrors test/retry.test.ts)."""

from __future__ import annotations

import pytest

from vinkius_connect.core.retry import (
    DEFAULT_RETRY,
    backoff_delay,
    is_retryable_status,
    parse_retry_after,
    RetryPolicy,
)


def test_default_retry_policy():
    assert DEFAULT_RETRY.max_retries == 2
    assert DEFAULT_RETRY.base_delay_ms == 250
    assert DEFAULT_RETRY.max_delay_ms == 4000


def test_is_retryable_status():
    assert is_retryable_status(429)
    assert is_retryable_status(502)
    assert is_retryable_status(503)
    assert is_retryable_status(504)
    assert not is_retryable_status(400)
    assert not is_retryable_status(404)
    assert not is_retryable_status(200)
    assert not is_retryable_status(500)


def test_backoff_honors_retry_after_hint_capped():
    p = RetryPolicy(max_retries=2, base_delay_ms=250, max_delay_ms=4000)
    # A positive hint wins, capped at max_delay_ms.
    assert backoff_delay(0, p, 1000) == 1000
    assert backoff_delay(0, p, 99999) == 4000
    # 0 is treated as NO hint -> full jitter (bounded by the window).
    d = backoff_delay(0, p, 0)
    assert 0 <= d <= min(p.max_delay_ms, p.base_delay_ms)


def test_backoff_full_jitter_grows_with_attempt():
    p = RetryPolicy(max_retries=5, base_delay_ms=250, max_delay_ms=4000)
    # Attempt 0 window = 250; attempt 5 window capped at 4000.
    w0 = min(p.max_delay_ms, p.base_delay_ms * 1)
    for _ in range(50):
        assert 0 <= backoff_delay(0, p) <= w0
    # A high attempt must stay within the capped window.
    for _ in range(50):
        assert 0 <= backoff_delay(5, p) <= 4000


def test_parse_retry_after_delta_seconds():
    assert parse_retry_after("3") == 3000
    assert parse_retry_after("0") == 0
    assert parse_retry_after("-5") == 0  # negative clamps to 0
    assert parse_retry_after(None) is None
    assert parse_retry_after("") is None
    assert parse_retry_after("not-a-number") is None


def test_parse_retry_after_http_date():
    # A far-future date gives a positive delay; a past date clamps to 0.
    assert parse_retry_after("Thu, 01 Jan 1970 00:00:00 GMT") == 0
    future = parse_retry_after("Fri, 01 Jan 2999 00:00:00 GMT")
    assert future is not None and future > 0
