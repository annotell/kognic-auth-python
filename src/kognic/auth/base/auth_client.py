import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Protocol, TypeVar

log: logging.Logger = logging.getLogger(__name__)


class _HasStatusCode(Protocol):
    status_code: int


_ResponseT = TypeVar("_ResponseT", bound=_HasStatusCode)


class AuthClient:
    def _log_new_token(self) -> None:
        token = self.token or {}
        if "expires_in" in token:
            log.info(f"Got new token, with ttl={token['expires_in']} and expires {self.expires_at}")
        else:
            log.warning(f"Got new token that is likely not valid: missing expires_in but got {token.keys()}")

    @property
    def access_token(self) -> Optional[str]:
        return self.token["access_token"] if self.token else None

    @property
    def claims(self) -> Optional[Dict[str, Any]]:
        """
        For introspection, no validation is done.
        :return:
        """
        access_token = self.access_token
        if access_token is None:
            return None
        return json.loads(base64.b64decode(access_token.split(".")[1] + "=="))

    @property
    def expires_at(self) -> Optional[datetime]:
        return datetime.fromtimestamp(self.token["expires_at"], tz=timezone.utc) if self.token else None

    @property
    def token(self) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    @staticmethod
    def check_rate_limit(response: _ResponseT) -> _ResponseT:
        if response.status_code == 429:
            log.error("Client authentication rate limit exceeded! Please slow down.")
        return response
