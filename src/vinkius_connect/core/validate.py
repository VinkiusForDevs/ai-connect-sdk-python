"""Input guards for the low-level API.

App users are addressed by their client-supplied ``external_id`` — the value is
placed directly into the request path (``/apps/{app}/users/{external_id}/...``).
The API resolves the user by ``(application_id, external_id)`` from the
authenticated app context, so the client never resolves or holds a Vinkius id.

The value must be URL-path-safe: percent-encoding handles most characters, but
a ``/`` (encoded ``%2F``) and whitespace are rejected by common routing layers,
so we reject them up front with a clear error.
"""

from __future__ import annotations

import re

from .errors import ConfigError

__all__ = ["assert_external_id", "UNSAFE_EXTERNAL_ID"]

UNSAFE_EXTERNAL_ID = re.compile(r"[\s/\\]")


def assert_external_id(value: str) -> None:
    """Throw unless ``value`` is a usable, URL-path-safe external id."""
    if not isinstance(value, str) or len(value) == 0 or len(value) > 255:
        raise ConfigError("`externalId` must be a non-empty string of at most 255 characters.")
    if UNSAFE_EXTERNAL_ID.search(value):
        raise ConfigError(
            f'Invalid externalId {value!r}: it must not contain whitespace, "/" or "\\".'
        )
