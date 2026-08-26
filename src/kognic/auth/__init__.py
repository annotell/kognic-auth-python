import logging
import os
from logging import NullHandler
from pathlib import Path

from kognic.auth._sunset import SunsetHandler, default_sunset_handler

logging.getLogger(__name__).addHandler(NullHandler())

__all__ = ["SunsetHandler", "default_sunset_handler"]

try:
    from ._version import __version__
except ImportError:
    __version__ = "0.0.0"

DEFAULT_HOST = "https://auth.app.kognic.com"
DEFAULT_KOGNIC_PLATFORM = "app.kognic.com"
DEFAULT_TOKEN_ENDPOINT_RELPATH = "/v1/auth/oauth/token"

# Methods safe to replay after a transient server error. Both the sync and the async client
# derive their retry policy from this set, so they cannot drift apart. Methods outside it —
# POST and PATCH — may have taken effect server-side even when the response never arrived,
# so a caller must decide for itself whether repeating the call is safe.
RETRYABLE_METHODS = frozenset({"HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE"})

# Growth rate of the delay between retries, shared so both clients wait for the same
# amount of time: the first retry is immediate, then 1s, then 2s.
RETRY_BACKOFF_FACTOR = 0.5

# Transient server errors worth another attempt.
RETRY_STATUS_CODES = (502, 503, 504)

# Attempts made after the initial request, for a total of four calls.
MAX_RETRIES = 3

DEFAULT_ENV_CONFIG_FILE_PATH = (
    Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "kognic" / "environments.json"
)

DEFAULT_CACHE_PATH = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "kognic-auth" / "tokens.json"
