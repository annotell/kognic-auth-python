import logging
from logging import NullHandler

logging.getLogger(__name__).addHandler(NullHandler())

__version__ = "1.8.0"

DEFAULT_HOST = "https://user.annotell.com"

REFRESH_TLL = 3*24*3600

