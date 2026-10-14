"""Error mapping tests (mirrors test/errors.test.ts)."""

from __future__ import annotations

from vinkius_connect.core.errors import (
    AuthError,
    map_http_error,
    NotFoundError,
    OverageError,
    ProtocolError,
    QuotaError,
    RateLimitError,
    ValidationError,
    VinkiusError,
)


def test_map_http_error_401_403():
    e = map_http_error(401, {"message": "nope"}, "req-1")
    assert isinstance(e, AuthError)
    assert e.status == 401
    assert e.code == "auth_error"
    assert e.request_id == "req-1"
    assert e.details == {"message": "nope"}


def test_map_http_error_404():
    e = map_http_error(404, {"error": "missing"}, "req-2")
    assert isinstance(e, NotFoundError)
    assert e.code == "not_found"
    # Message prefers `error` when `message` absent.
    assert e.message == "missing"


def test_map_http_error_422_validation():
    e = map_http_error(422, {"message": "bad", "errors": {"a": ["x"]}}, None)
    assert isinstance(e, ValidationError)
    assert e.code == "validation_error"
    assert e.errors == {"a": ["x"]}


def test_map_http_error_402_overage():
    e = map_http_error(402, {"error": "over", "upgrade_url": "https://up"}, "r")
    assert isinstance(e, OverageError)
    assert e.code == "overage_blocked"
    assert e.upgrade_url == "https://up"


def test_map_http_error_429_rate_limit():
    e = map_http_error(429, {"message": "slow down"}, "r", retry_after_ms=1500)
    assert isinstance(e, RateLimitError)
    assert e.code == "rate_limit"
    assert e.retry_after_ms == 1500


def test_map_http_error_429_quota_when_mcp_shaped():
    # A data-plane 429 carrying an upgrade_url / isError is a QuotaError.
    e = map_http_error(429, {"upgrade_url": "https://up"}, "r")
    assert isinstance(e, QuotaError)
    assert e.code == "quota_exceeded"
    assert e.upgrade_url == "https://up"


def test_map_http_error_generic_api_error():
    e = map_http_error(500, {"message": "boom"}, "r")
    assert isinstance(e, VinkiusError)
    assert e.code == "api_error"
    assert e.status == 500
    assert e.message == "boom"


def test_pick_message_from_content_array():
    e = map_http_error(400, {"content": [{"type": "text", "text": "inner"}]}, None)
    assert e.message == "inner"


def test_fallback_message_when_no_message():
    e = map_http_error(418, {}, None)
    assert e.message == "Request failed with status 418"


def test_error_is_exception_with_attrs():
    e = ProtocolError("bad shape", code="protocol_error", details={"x": 1})
    assert isinstance(e, Exception)
    assert e.code == "protocol_error"
    assert e.details == {"x": 1}
    assert str(e) == "bad shape"
