import logging
from logging import NullHandler

logging.getLogger(__name__).addHandler(NullHandler())

__version__ = "2.0.1"

DEFAULT_HOST = "https://user.annotell.com"
