"""vinkius-connect — the Python SDK for Vinkius AI connectivity.

Ship AI features, not integration projects. Give every user of your AI app
their own connectors and AI capabilities.

Domain vocabulary: users have **connectors**; a connected connector is a
**connection**; the executable units the agent calls are **capabilities**.

Quick start::

    import vinkius_connect as vc

    vinkius = vc.Vinkius(app_id="vk_app_...", api_key="vk_app_sk_...")
    capabilities = await vinkius.user("alice_123").capabilities()

Use any async runner (``asyncio.run``, an ``async`` FastAPI handler, a
LangGraph/CrewAI agent loop, etc.).
"""

from . import adapters
from .core.errors import (
    AuthError,
    ConnectionError,
    ConfigError,
    ConnectorNotConnectedError,
    NotFoundError,
    NotImplementedError,
    NotImplementedError_,
    OverageError,
    ProtocolError,
    QuotaError,
    RateLimitError,
    ValidationError,
    VinkiusError,
)
from .core.cache import ResolverCache
from .fluent.capability import Capability, CapabilitySet
from .fluent.connector import Connector
from .fluent.context import SdkContext
from .fluent.credentials import CredentialsHandle
from .fluent.user import UserContext
from .fluent.vinkius import Vinkius
from .resources.app_users import AppUsersClient, CreateAppUserInput, UpdateAppUserInput
from .resources.catalog import CatalogClient
from .resources.connections import ConnectionsClient, CreateConnectionInput
from .resources.credentials import CredentialsClient, SetCredentialsInput
from .resources.tokens import ConnectionTokensClient, IssueTokenInput
from .types import (
    CapabilityQuery,
    CapabilityResult,
    ExecuteOptions,
    RequestOptions,
    VinkiusOptions,
)
from .version import VERSION

__all__ = [
    "Vinkius",
    "UserContext",
    "Connector",
    "CredentialsHandle",
    "Capability",
    "CapabilitySet",
    "SdkContext",
    "AppUsersClient",
    "CatalogClient",
    "ConnectionsClient",
    "CredentialsClient",
    "ConnectionTokensClient",
    "CreateAppUserInput",
    "UpdateAppUserInput",
    "CreateConnectionInput",
    "SetCredentialsInput",
    "IssueTokenInput",
    "ResolverCache",
    "VERSION",
    # errors
    "VinkiusError",
    "ConfigError",
    "AuthError",
    "NotFoundError",
    "ValidationError",
    "RateLimitError",
    "QuotaError",
    "OverageError",
    "ConnectorNotConnectedError",
    "NotImplementedError",
    "NotImplementedError_",
    "ConnectionError",
    "ProtocolError",
    # types
    "RequestOptions",
    "ExecuteOptions",
    "CapabilityQuery",
    "VinkiusOptions",
    "CapabilityResult",
    # adapters
    "adapters",
]
