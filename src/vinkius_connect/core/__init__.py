"""Core infrastructure for the Vinkius Connect Python SDK.

Transport, retry, redaction, caching, pagination, error mapping, and the
MCP runtime client. These modules are the shared plumbing the fluent layer and
the low-level resource clients build on.
"""

from .cache import ResolverCache
from .errors import (
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
    map_http_error,
)
from .http import HttpClient, HttpClientConfig
from .pagination import normalize_paginated, page_iterator, unwrap_item, unwrap_list
from .pool import pooled_map
from .redact import redact_body, redact_headers, redact_url
from .retry import (
    DEFAULT_RETRY,
    RetryPolicy,
    backoff_delay,
    is_retryable_status,
    parse_retry_after,
    sleep,
)
from .runtime import RuntimeClient, RuntimeClientConfig
from .transport import Transport, TransportConfig, TransportRequest, TransportResult
from .validate import assert_external_id

__all__ = [
    "ResolverCache",
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
    "map_http_error",
    "HttpClient",
    "HttpClientConfig",
    "Transport",
    "TransportConfig",
    "TransportRequest",
    "TransportResult",
    "RetryPolicy",
    "DEFAULT_RETRY",
    "is_retryable_status",
    "backoff_delay",
    "parse_retry_after",
    "sleep",
    "redact_headers",
    "redact_url",
    "redact_body",
    "pooled_map",
    "normalize_paginated",
    "unwrap_list",
    "unwrap_item",
    "page_iterator",
    "assert_external_id",
    "RuntimeClient",
    "RuntimeClientConfig",
]
