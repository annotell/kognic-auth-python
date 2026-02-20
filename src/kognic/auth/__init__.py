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

DEFAULT_ENV_CONFIG_FILE_PATH = (
    Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "kognic" / "environments.json"
)

DEFAULT_CACHE_PATH = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "kognic-auth" / "tokens.json"
