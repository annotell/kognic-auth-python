"""User-Agent string handling for HTTP clients."""

import sys
from typing import Optional

from kognic.auth import __version__

_PY_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def get_user_agent(http_lib_version: str, client_name: Optional[str] = None) -> str:
    """Build User-Agent string for HTTP requests.

    Args:
        http_lib_version: The HTTP library and version (e.g., "requests/2.31.0")
        client_name: Optional client name to append

    Returns:
        User-Agent string like "kognic-auth/1.0.0 python/3.11.0 requests/2.31.0 MyClient"
    """
    base = f"kognic-auth/{__version__} python/{_PY_VERSION} {http_lib_version}"

    if client_name:
        return f"{base} {client_name}"
    return base
