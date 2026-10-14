"""Secret redaction for observability hooks.

The SDK never logs by default, but any data handed to a user-provided hook is
scrubbed first so that credentials, tokens, and Authorization headers can never
leak through logging.
"""

from __future__ import annotations

import re
from typing import Any, MutableSet

__all__ = ["redact_headers", "redact_url", "redact_body"]

REDACTED = "[REDACTED]"
MAX_DEPTH = 6

#: Header names whose values must never be surfaced.
SECRET_HEADERS = {"authorization", "idempotency-key", "cookie", "set-cookie"}

#: Object keys (case-insensitive) whose values must never be surfaced.
SECRET_KEYS = {
    "authorization",
    "apikey",
    "api_key",
    "token",
    "access_token",
    "refresh_token",
    "mcp_url",
    "credentials",
    "password",
    "secret",
    "client_secret",
}

_LIVE_TOKEN = re.compile(r"vk_live_[A-Za-z0-9_-]+")


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Return a copy of headers with secret values redacted."""
    return {
        key: (REDACTED if key.lower() in SECRET_HEADERS else value)
        for key, value in headers.items()
    }


def redact_url(url: str) -> str:
    """Mask any ``vk_live_*`` path segment in a URL.

    The data-plane runtime endpoint embeds its bearer token in the path
    (``{RUNTIME}/{vk_live_*}/mcp``), so the raw URL must never reach an
    observability hook.
    """
    return _LIVE_TOKEN.sub(REDACTED, url)


def redact_body(value: Any) -> Any:
    """Deep-clone a value, redacting any property whose key looks like a secret.

    Depth-limited and cycle-safe.
    """
    return _clone(value, 0, set())


def _clone(value: Any, depth: int, seen: MutableSet[int]) -> Any:
    if value is None or not isinstance(value, (dict, list)):
        return value
    if depth >= MAX_DEPTH:
        return "[TRUNCATED]"
    if id(value) in seen:
        return "[CIRCULAR]"
    seen.add(id(value))
    try:
        if isinstance(value, list):
            return [_clone(item, depth + 1, seen) for item in value]
        record: dict[str, Any] = {}
        for key, val in value.items():
            record[key] = REDACTED if str(key).lower() in SECRET_KEYS else _clone(val, depth + 1, seen)
        return record
    finally:
        # Backtrack: only the ACTIVE recursion path counts as a cycle. Shared
        # (diamond) references that appear twice but do not loop must clone
        # again instead of being flagged [CIRCULAR].
        seen.discard(id(value))
