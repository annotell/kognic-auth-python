import logging
from logging import NullHandler

logging.getLogger(__name__).addHandler(NullHandler())

__version__ = "3.0.1"

DEFAULT_HOST = "https://auth.app.kognic.com"
