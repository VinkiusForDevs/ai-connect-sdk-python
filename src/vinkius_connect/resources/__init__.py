"""Low-level REST resource clients (1:1 with the Vinkius Cloud API).

These are the "control plane" building blocks that the fluent layer composes.
Every method takes an optional ``opts`` dict (``idempotency_key``,
``timeout_ms``) and returns the raw API JSON as a ``dict`` (or ``list``/``None``).
"""

from .app_users import AppUsersClient, CreateAppUserInput, UpdateAppUserInput
from .catalog import CatalogClient
from .connections import ConnectionsClient, CreateConnectionInput
from .credentials import CredentialsClient, SetCredentialsInput
from .tokens import ConnectionTokensClient, IssueTokenInput

__all__ = [
    "AppUsersClient",
    "CreateAppUserInput",
    "UpdateAppUserInput",
    "CatalogClient",
    "ConnectionsClient",
    "CreateConnectionInput",
    "CredentialsClient",
    "SetCredentialsInput",
    "ConnectionTokensClient",
    "IssueTokenInput",
]
