"""Status derivation tests (mirrors test/status.test.ts)."""

from __future__ import annotations

from vinkius_connect.fluent.status import derive_status, summarize


def test_derive_status_ready():
    assert derive_status({"status": "active", "ready": True}) == "ready"


def test_derive_status_needs_credentials():
    assert derive_status({"status": "active", "ready": False}) == "needs_credentials"


def test_derive_status_disabled():
    assert derive_status({"status": "disabled", "ready": True}) == "disabled"


def test_summarize():
    s = summarize({"id": "c1", "slug": "github", "name": "GitHub", "status": "active", "ready": True})
    assert s == {"slug": "github", "status": "ready", "connection_id": "c1"}
    # Falls back to name when slug is null.
    s2 = summarize({"id": "c2", "slug": None, "name": "GitHub", "status": "active", "ready": False})
    assert s2["slug"] == "GitHub"
    assert s2["status"] == "needs_credentials"
