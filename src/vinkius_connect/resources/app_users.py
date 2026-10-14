"""Application end-users (low-level).

    GET/POST         /apps/{app}/users
    GET/PATCH/DELETE /apps/{app}/users/{externalId}

Users are addressed by their client-supplied ``external_id``. ``create`` is
idempotent: the API upserts by ``(application_id, external_id)``.

Tool listing and execution run through the runtime per connection, not here.
"""

from __future__ import annotations

import urllib.parse
from typing import Any, AsyncIterator, Optional

from ..core.http import HttpClient
from ..core.pagination import normalize_paginated, page_iterator, unwrap_item
from ..core.validate import assert_external_id

__all__ = [
    "AppUsersClient",
    "CreateAppUserInput",
    "UpdateAppUserInput",
]


class CreateAppUserInput(dict):
    """Input for :meth:`AppUsersClient.create`.

    ``external_id`` (required), ``status``, ``metadata``.
    """


class UpdateAppUserInput(dict):
    """Input for :meth:`AppUsersClient.update`. ``status``, ``metadata``."""


class AppUsersClient:
    def __init__(self, http: HttpClient, app_id: str) -> None:
        self._http = http
        self._app_id = app_id

    def _base(self) -> str:
        return f"/apps/{urllib.parse.quote(self._app_id)}/users"

    def _user_path(self, external_id: str) -> str:
        assert_external_id(external_id)
        return f"{self._base()}/{urllib.parse.quote(external_id, safe='')}"

    async def create(self, input: dict, opts: Optional[dict] = None) -> dict:
        """Get-or-create a user by external id (idempotent)."""
        opts = opts or {}
        assert_external_id(input["external_id"])
        body = await self._http.post(
            self._base(),
            input,
            idempotent=True,
            idempotency_key=opts.get("idempotency_key"),
            timeout_ms=opts.get("timeout_ms"),
        )
        return unwrap_item(body)

    async def get(self, external_id: str, opts: Optional[dict] = None) -> dict:
        opts = opts or {}
        body = await self._http.get(
            self._user_path(external_id),
            idempotency_key=opts.get("idempotency_key"),
            timeout_ms=opts.get("timeout_ms"),
        )
        return unwrap_item(body)

    async def update(self, external_id: str, patch: dict, opts: Optional[dict] = None) -> dict:
        opts = opts or {}
        body = await self._http.patch(
            self._user_path(external_id),
            patch,
            idempotency_key=opts.get("idempotency_key"),
            timeout_ms=opts.get("timeout_ms"),
        )
        return unwrap_item(body)

    async def delete(self, external_id: str, opts: Optional[dict] = None) -> None:
        opts = opts or {}
        await self._http.delete(
            self._user_path(external_id),
            idempotency_key=opts.get("idempotency_key"),
            timeout_ms=opts.get("timeout_ms"),
        )

    async def list(self, opts: Optional[dict] = None) -> dict:
        """List users (page-based, supports ``status`` and ``page``)."""
        opts = opts or {}
        body = await self._http.get(
            self._base(),
            query={"status": opts.get("status"), "page": opts.get("page")},
            idempotency_key=opts.get("idempotency_key"),
            timeout_ms=opts.get("timeout_ms"),
        )
        return normalize_paginated(body)

    async def iterate(self, opts: Optional[dict] = None) -> AsyncIterator[dict]:
        """Iterate every user across all pages (auto-follows ``?page=``)."""
        opts = opts or {}

        async def fetch_page(page: int) -> dict:
            return await self.list({**opts, "page": page})

        first = await self.list(opts)
        async for item in page_iterator(first, fetch_page):
            yield item

    def connections(self, external_id: str):
        """Scoped connections client for a specific user."""
        from .connections import ConnectionsClient

        return ConnectionsClient(self._http, self._app_id, external_id)
