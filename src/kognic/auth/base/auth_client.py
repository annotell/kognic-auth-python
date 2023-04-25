import base64
import json
from datetime import datetime
import logging
from typing import Optional

log = logging.getLogger(__name__)


class AuthClient:
    def _log_new_token(self):
        log.info(f"Got new token, with ttl={self.token['expires_in']} and expires {self.expires_at} UTC")

    @property
    def access_token(self):
        return self.token['access_token'] if self.token else None

    @property
    def claims(self) -> Optional[dict]:
        """
        For introspection, no validation is done.
        :return:
        """
        if self.token:
            return json.loads(base64.b64decode(self.access_token.split(".")[1] + '=='))

    @property
    def expires_at(self):
        return datetime.utcfromtimestamp(self.token['expires_at']) if self.token else None

    @property
    def token(self):
        raise NotImplementedError
