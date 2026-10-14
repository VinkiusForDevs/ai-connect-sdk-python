"""Redaction tests."""

from __future__ import annotations

from vinkius_connect.core.redact import redact_body, redact_headers, redact_url


def test_redact_headers_masks_secret_headers_only():
    out = redact_headers(
        {
            "Authorization": "Bearer vk_app_sk_x",
            "x-vinkius-app-id": "vk_app_x",
            "cookie": "a=b",
            "SET-COOKIE": "c=d",
            "Idempotency-Key": "k",
            "x-custom": "visible",
        }
    )
    assert out["Authorization"] == "[REDACTED]"
    assert out["cookie"] == "[REDACTED]"
    assert out["SET-COOKIE"] == "[REDACTED]"
    assert out["Idempotency-Key"] == "[REDACTED]"
    # Non-secret headers pass through untouched.
    assert out["x-vinkius-app-id"] == "vk_app_x"
    assert out["x-custom"] == "visible"


def test_redact_url_masks_live_tokens():
    url = "https://runtime.vinkius.com/vk_live_abc123XYZ_-/mcp"
    assert redact_url(url) == "https://runtime.vinkius.com/[REDACTED]/mcp"
    # Multiple tokens are all masked.
    assert "[REDACTED]" in redact_url("a/vk_live_1/b/vk_live_2/c")
    # Non-live URLs are unchanged.
    assert redact_url("https://api.vinkius.com/catalog/mcps") == "https://api.vinkius.com/catalog/mcps"


def test_redact_body_redacts_secret_keys_depth_first():
    value = {
        "token": "secret",
        "api_key": "k",
        "nested": {"password": "p", "list": [{"access_token": "a"}]},
        "plain": "kept",
        "naked": [1, 2, 3],
    }
    out = redact_body(value)
    assert out["token"] == "[REDACTED]"
    assert out["api_key"] == "[REDACTED]"
    assert out["nested"]["password"] == "[REDACTED]"
    assert out["nested"]["list"][0]["access_token"] == "[REDACTED]"
    assert out["plain"] == "kept"
    assert out["naked"] == [1, 2, 3]


def test_redact_body_does_not_mutate_input():
    original = {"credentials": {"x": 1}, "a": [1, {"b": 2}]}
    redact_body(original)
    assert original["credentials"] == {"x": 1}
    assert original["a"] == [1, {"b": 2}]


def test_redact_body_truncates_deep_structures():
    deep = {}
    cur = deep
    for i in range(20):
        cur["n"] = i
        cur["next"] = {}
        cur = cur["next"]
    out = redact_body(deep)
    s = str(out)
    assert "[TRUNCATED]" in s
