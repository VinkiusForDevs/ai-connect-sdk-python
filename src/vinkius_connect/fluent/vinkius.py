"""Vinkius — the SDK root, scoped to a single application.

Holds the only secret the integrator manages (``vk_app_sk_*``) and the public
app id (``vk_app_*``). Validates configuration eagerly and fails fast with a
clear :class:`ConfigError`.
"""

from __future__ import annotations

import sys
import warnings
from typing import Any, Optional
from urllib.parse import urlparse

from ..core.cache import ResolverCache
from ..core.errors import ConfigError
from ..core.http import HttpClient, HttpClientConfig
from ..core.retry import DEFAULT_RETRY
from ..core.runtime import RuntimeClient, RuntimeClientConfig
from ..resources.app_users import AppUsersClient
from ..resources.catalog import CatalogClient
from ..types import VinkiusOptions
from ..version import VERSION
from .context import SdkContext
from .user import UserContext

__all__ = ["Vinkius"]

DEFAULT_BASE_URL = "https://api.vinkius.com"
DEFAULT_TIMEOUT_MS = 30_000


class Vinkius:
    def __init__(self, options: Optional[VinkiusOptions | dict] = None, **kwargs: Any) -> None:
        opts = self._coerce_options(options, kwargs)

        app_id = opts.app_id
        api_key = opts.api_key

        if not (isinstance(app_id, str) and app_id.startswith("vk_app_") and not app_id.startswith("vk_app_sk_")):
            raise ConfigError(
                '`appId` must be a public application id starting with "vk_app_" (not the secret key).'
            )
        if not (isinstance(api_key, str) and api_key.startswith("vk_app_sk_")):
            raise ConfigError(
                '`apiKey` must be a secret application key starting with "vk_app_sk_."'
            )

        base_url = _normalize_base_url(opts.base_url or DEFAULT_BASE_URL)
        _warn_if_insecure(base_url)

        timeout_ms = opts.timeout_ms or DEFAULT_TIMEOUT_MS
        retry = DEFAULT_RETRY if opts.max_retries is None else DEFAULT_RETRY.__class__(
            max_retries=opts.max_retries,
            base_delay_ms=DEFAULT_RETRY.base_delay_ms,
            max_delay_ms=DEFAULT_RETRY.max_delay_ms,
        )
        user_agent = _build_user_agent(opts.user_agent)

        # Transport: an injected httpx.AsyncClient (or compatible) wins; otherwise
        # the SDK builds and owns its own so callers can ``await aclose()``.
        client = opts.client
        self._owns_client = client is None
        if self._owns_client:
            import httpx

            client = httpx.AsyncClient(timeout=timeout_ms / 1000.0)

        http_cfg = HttpClientConfig(
            base_url=base_url,
            api_key=api_key,
            app_id=app_id,
            timeout_ms=timeout_ms,
            retry=retry,
            client=client,
            user_agent=user_agent,
            hooks=opts.hooks,
        )
        http = HttpClient(http_cfg)

        self._ctx = SdkContext(
            http=http,
            app_id=app_id,
            cache=ResolverCache(),
            namespace=opts.namespace_capability or (lambda connector, name: f"{connector}__{name}"),
            # The runtime is the sole execution surface; its config mirrors the API
            # client's transport settings but carries no API auth (the mcp_url
            # embeds the vk_live_* token). Hooks apply to the data plane too.
            runtime=lambda mcp_url: RuntimeClient(
                mcp_url,
                RuntimeClientConfig(
                    timeout_ms=timeout_ms,
                    retry=retry,
                    client=client,
                    user_agent=user_agent,
                    hooks=opts.hooks,
                ),
            ),
        )
        self._client = client

        #: Catalog discovery.
        self.catalog = CatalogClient(http)
        #: Low-level users client, scoped to this application.
        self.users = AppUsersClient(http, app_id)

    # ── lifecycle ───────────────────────────────────────────────────────

    async def aclose(self) -> None:
        """Close the underlying HTTP client when the SDK owns it.

        A no-op for injected clients the caller manages themselves.
        """
        if self._owns_client and self._client is not None:
            await self._client.aclose()

    async def __aenter__(self) -> "Vinkius":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    # ── fluent entrypoint ───────────────────────────────────────────────

    def user(self, external_id: str) -> UserContext:
        """A lazy, zero-request handle to one end-user's capabilities."""
        if not isinstance(external_id, str) or len(external_id) == 0:
            raise ConfigError("`externalId` must be a non-empty string.")
        if external_id.startswith("vk_app_user_"):
            raise ConfigError(
                '`externalId` must be YOUR user id (e.g. "alice_123"), not a Vinkius internal id. '
                "The SDK resolves identifiers automatically from the external_id you provide."
            )
        return UserContext(self._ctx, external_id)

    # ── internals ───────────────────────────────────────────────────────

    @staticmethod
    def _coerce_options(options: Optional[VinkiusOptions | dict], kwargs: dict) -> VinkiusOptions:
        if isinstance(options, dict):
            kwargs = {**options, **kwargs}
            return VinkiusOptions(
                app_id=kwargs.get("app_id", ""),
                api_key=kwargs.get("api_key", ""),
                base_url=kwargs.get("base_url"),
                timeout_ms=kwargs.get("timeout_ms"),
                max_retries=kwargs.get("max_retries"),
                client=kwargs.get("client"),
                user_agent=kwargs.get("user_agent"),
                hooks=kwargs.get("hooks"),
                namespace_capability=kwargs.get("namespace_capability"),
            )
        if options is None:
            options = VinkiusOptions(app_id=kwargs.get("app_id", ""), api_key=kwargs.get("api_key", ""))
            for field in (
                "base_url",
                "timeout_ms",
                "max_retries",
                "client",
                "user_agent",
                "hooks",
                "namespace_capability",
            ):
                if field in kwargs:
                    setattr(options, field, kwargs[field])
            return options
        return options


def _normalize_base_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError
        return url.rstrip("/")
    except ValueError:
        raise ConfigError(f"Invalid baseUrl: {url}")


def _warn_if_insecure(base_url: str) -> None:
    try:
        parsed = urlparse(base_url)
        host = parsed.hostname or ""
        is_local = (
            host in ("localhost", "127.0.0.1")
            or host == "::1"
            or host.endswith(".localhost")
        )
        if parsed.scheme == "http" and not is_local:
            warnings.warn(
                "[vinkius] baseUrl uses insecure http:// on a non-local host; use https:// in production.",
                stacklevel=2,
            )
    except ValueError:
        # already validated
        return


def _build_user_agent(extra: Optional[str]) -> str:
    runtime = f" python/{sys.version.split()[0]}"
    base = f"vinkius-connect/{VERSION}{runtime}"
    return f"{base} {extra}" if extra else base
