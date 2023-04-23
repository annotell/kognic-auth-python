import logging
from logging import NullHandler
from ._version import __version__
logging.getLogger(__name__).addHandler(NullHandler())

DEFAULT_HOST = "https://auth.app.kognic.com"
