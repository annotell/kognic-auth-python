import logging
from logging import NullHandler

logging.getLogger(__name__).addHandler(NullHandler())

try:
    from ._version import __version__
except ImportError:
    __version__ = "0.0.0"

DEFAULT_HOST = "https://auth.app.kognic.com"
DEFAULT_TOKEN_ENDPOINT_RELPATH = "/v1/auth/oauth/token"
