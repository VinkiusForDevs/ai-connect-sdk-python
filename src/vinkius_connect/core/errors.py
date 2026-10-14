"""Typed error hierarchy.

Every failure surfaces as a :class:`VinkiusError` subclass carrying ``status``,
a stable ``code``, and (when available) the server ``request_id``. Secrets are
never placed on error objects — ``details`` only ever holds the parsed API body,
which by contract never echoes credentials.
"""

from __future__ import annotations

from typing import Any, Optional

__all__ = [
    "VinkiusErrorCode",
    "VinkiusError",
    "ConfigError",
    "AuthError",
    "NotFoundError",
    "ValidationError",
    "RateLimitError",
    "QuotaError",
    "OverageError",
    "ConnectorNotConnectedError",
    "NotImplementedError_",
    "ConnectionError",
    "ProtocolError",
    "map_http_error",
]

# Stable, machine-readable error codes.
VinkiusErrorCode = str


class VinkiusError(Exception):
    """Base class for every error raised by the SDK."""

    def __init__(
        self,
        message: str,
        *,
        code: VinkiusErrorCode,
        status: int = 0,
        request_id: Optional[str] = None,
        details: Any = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(message)
        #: Human-readable message.
        self.message = message
        #: HTTP status (0 for client-side / transport errors).
        self.status = status
        #: Stable machine-readable code.
        self.code = code
        #: Server-provided request id, when present.
        self.request_id = request_id
        #: Parsed API response body (never contains secrets).
        self.details = details
        #: The original exception that caused this one, when any.
        self.cause = cause

    def __str__(self) -> str:  # keep the bare message as the repr
        return self.message


class ConfigError(VinkiusError):
    """Invalid SDK configuration (bad key prefixes, missing transport, etc.)."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.pop("code", None)
        super().__init__(message, code="config_error", **kwargs)
        self.name = "ConfigError"


class AuthError(VinkiusError):
    """401/403 — authentication or authorization failure."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.pop("code", None)
        super().__init__(message, code="auth_error", **kwargs)
        self.name = "AuthError"


class NotFoundError(VinkiusError):
    """404 — resource not found (also returned for cross-tenant access)."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.pop("code", None)
        super().__init__(message, code="not_found", **kwargs)
        self.name = "NotFoundError"


class ValidationError(VinkiusError):
    """422 — request validation failed."""

    def __init__(
        self,
        message: str,
        errors: Optional[dict[str, list[str]]] = None,
        **kwargs: Any,
    ) -> None:
        kwargs.pop("code", None)
        super().__init__(message, code="validation_error", **kwargs)
        self.name = "ValidationError"
        #: Field -> messages, as returned by the API.
        self.errors = errors or {}


class RateLimitError(VinkiusError):
    """429 — control-plane rate limit. Retried automatically for idempotent calls."""

    def __init__(self, message: str, retry_after_ms: Optional[int] = None, **kwargs: Any) -> None:
        kwargs.pop("code", None)
        super().__init__(message, code="rate_limit", **kwargs)
        self.name = "RateLimitError"
        #: Milliseconds to wait before retrying, if the server advertised it.
        self.retry_after_ms = retry_after_ms


class QuotaError(VinkiusError):
    """429 (data-plane) — plan quota exhausted."""

    def __init__(self, message: str, upgrade_url: Optional[str] = None, **kwargs: Any) -> None:
        kwargs.pop("code", None)
        super().__init__(message, code="quota_exceeded", **kwargs)
        self.name = "QuotaError"
        self.upgrade_url = upgrade_url


class OverageError(VinkiusError):
    """402 — overage blocked."""

    def __init__(self, message: str, upgrade_url: Optional[str] = None, **kwargs: Any) -> None:
        kwargs.pop("code", None)
        super().__init__(message, code="overage_blocked", **kwargs)
        self.name = "OverageError"
        self.upgrade_url = upgrade_url


class ConnectorNotConnectedError(VinkiusError):
    """Client-side — a connector slug is not connected for the user."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.pop("code", None)
        super().__init__(message, code="connector_not_connected", **kwargs)
        self.name = "ConnectorNotConnectedError"


class NotImplementedError_(VinkiusError):
    """A feature depends on an endpoint that is not yet available."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.pop("code", None)
        super().__init__(message, code="not_implemented", **kwargs)
        self.name = "NotImplementedError"


class ConnectionError(VinkiusError):
    """Network failure, timeout, or aborted request."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.pop("code", None)
        super().__init__(message, code="connection_error", **kwargs)
        self.name = "ConnectionError"


class ProtocolError(VinkiusError):
    """A successful HTTP response violated the documented API wire contract."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.pop("code", None)
        super().__init__(message, code="protocol_error", **kwargs)
        self.name = "ProtocolError"


# Public aliases so callers can use the natural Python names without shadowing
# the builtin ``NotImplementedError`` / ``ConnectionError``.
NotImplementedError = NotImplementedError_


# ── Mapping ─────────────────────────────────────────────────────────────────


def _as_record(value: Any) -> Optional[dict]:
    return value if isinstance(value, dict) else None


def _pick_message(body: Any, fallback: str) -> str:
    b = _as_record(body)
    if b:
        if isinstance(b.get("message"), str) and b["message"]:
            return b["message"]
        if isinstance(b.get("error"), str) and b["error"]:
            return b["error"]
        if isinstance(b.get("content"), list):
            for entry in b["content"]:
                c = _as_record(entry)
                if c and isinstance(c.get("text"), str) and c["text"]:
                    return c["text"]
    if isinstance(body, str) and body:
        return body
    return fallback


def _is_mcp_shaped(body: Any) -> bool:
    b = _as_record(body)
    return bool(b and (b.get("isError") is True or isinstance(b.get("upgrade_url"), str)))


def _pick_upgrade_url(body: Any) -> Optional[str]:
    b = _as_record(body)
    if b and isinstance(b.get("upgrade_url"), str):
        return b["upgrade_url"]
    return None


def _pick_errors(body: Any) -> dict[str, list[str]]:
    b = _as_record(body)
    errors = b.get("errors") if b else None
    if isinstance(errors, dict):
        return errors
    return {}


def map_http_error(
    status: int,
    body: Any,
    request_id: Optional[str],
    retry_after_ms: Optional[int] = None,
) -> VinkiusError:
    """Map an HTTP error response to the appropriate :class:`VinkiusError`."""
    base = {"status": status, "request_id": request_id, "details": body}
    message = _pick_message(body, f"Request failed with status {status}")

    if status in (401, 403):
        return AuthError(message, **base)
    if status == 404:
        return NotFoundError(message, **base)
    if status == 422:
        return ValidationError(message, _pick_errors(body), **base)
    if status == 402:
        return OverageError(message, upgrade_url=_pick_upgrade_url(body), **base)
    if status == 429:
        if _is_mcp_shaped(body):
            return QuotaError(message, upgrade_url=_pick_upgrade_url(body), **base)
        return RateLimitError(message, retry_after_ms=retry_after_ms, **base)
    return VinkiusError(message, code="api_error", **base)
