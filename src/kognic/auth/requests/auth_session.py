import logging
import threading
from typing import Optional

import requests
from authlib.common.errors import AuthlibBaseError
from authlib.integrations.requests_client import OAuth2Session

from kognic.auth import DEFAULT_HOST, DEFAULT_TOKEN_ENDPOINT_RELPATH
from kognic.auth.base.auth_client import AuthClient
from kognic.auth.credentials_parser import resolve_credentials

log = logging.getLogger(__name__)


class _FixedSession(OAuth2Session):
    def refresh_token(self, url, **kwargs):
        try:
            super(_FixedSession, self).refresh_token(url, **kwargs)
        except AuthlibBaseError as e:
            if e.error == "invalid_token":
                log.info("Refresh token expired, resetting auth session")
                return self.fetch_token()
            raise
        except requests.exceptions.HTTPError as e:
            # with authlib >= 1.0.0
            if e.response.status_code == 401 and "invalid_token" == e.response.json().get("error"):
                log.info("Refresh token expired, resetting auth session")
                return self.fetch_token()
            raise


# https://docs.authlib.org/en/latest/client/oauth2.html
class RequestsAuthSession(AuthClient):
    """
    Not thread safe
    """

    def __init__(
        self,
        *,
        auth=None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        host: str = DEFAULT_HOST,
        token_endpoint: str = DEFAULT_TOKEN_ENDPOINT_RELPATH,
        **kwargs,
    ):
        """
        There is a variety of ways to set up the authentication.
        :param auth: authentication credentials
        :param client_id: client id for authentication
        :param client_secret: client secret for authentication
        :param host: base url for authentication server
        :param token_endpoint: relative path to the token endpoint
        :param kwargs: additional params to pass into Client Constructor
        """
        self.host = host
        self.token_url = f"{host}{token_endpoint}"

        client_id, client_secret = resolve_credentials(auth, client_id, client_secret)

        self.oauth_session = _FixedSession(
            client_id=client_id,
            client_secret=client_secret,
            token_endpoint_auth_method="client_secret_post",
            update_token=self._update_token,
            token_endpoint=self.token_url,
            **kwargs,
        )

        self._lock = threading.RLock()

    @property
    def token(self):
        return self.oauth_session.token

    def _update_token(self, token, access_token=None, refresh_token=None):
        self._log_new_token()

    @property
    def session(self):
        if not self.token:
            with self._lock:
                if not self.token:
                    # check again when coming out of the lock that the token is still not set
                    token = self.oauth_session.fetch_access_token(url=self.token_url)
                    self._update_token(token)
        return self.oauth_session.session
