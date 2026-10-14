"""external_id validation tests (mirrors test/validate.test.ts)."""

from __future__ import annotations

import pytest

from vinkius_connect.core.errors import ConfigError
from vinkius_connect.core.validate import assert_external_id


def test_valid_external_id():
    assert_external_id("alice_123")
    assert_external_id("usr-91827")
    assert_external_id("a" * 255)


def test_rejects_empty_and_oversized():
    with pytest.raises(ConfigError):
        assert_external_id("")
    with pytest.raises(ConfigError):
        assert_external_id("a" * 256)


def test_rejects_unsafe_chars():
    for bad in ["has/slash", "has\\backslash", "has space", "\ttab", "new\nline"]:
        with pytest.raises(ConfigError):
            assert_external_id(bad)


def test_rejects_non_string():
    with pytest.raises(ConfigError):
        assert_external_id(123)  # type: ignore[arg-type]
