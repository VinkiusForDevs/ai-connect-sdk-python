"""Map a Connection dict to its derived connector status / summary."""

from __future__ import annotations

from typing import Optional

__all__ = ["derive_status", "summarize"]


def derive_status(connection: dict) -> str:
    """The backend owns "readiness" (``Connection["ready"]``); the SDK only maps it.

    ``not_connected`` is handled by the caller when no connection matches.
    """
    if connection.get("status") != "active":
        return "disabled"
    return "ready" if connection.get("ready") else "needs_credentials"


def summarize(connection: dict) -> dict:
    """Produce a connector summary: ``{slug, status, connection_id?}``."""
    slug = connection.get("slug") or connection.get("name")
    summary: dict = {
        "slug": slug,
        "status": derive_status(connection),
    }
    if connection.get("id"):
        summary["connection_id"] = connection["id"]
    return summary
