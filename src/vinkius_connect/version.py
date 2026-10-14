"""SDK version.

The single source of truth is the distribution version declared in
``pyproject.toml``. When the package is installed, ``importlib.metadata``
returns that exact value, so it never drifts. When running from a source tree
(not installed), a dev sentinel is used.
"""

from importlib import metadata as _metadata

__all__ = ["VERSION"]

try:
    VERSION: str = _metadata.version("vinkius-connect")
except _metadata.PackageNotFoundError:  # running from a source tree
    VERSION = "0.1.0-dev"
