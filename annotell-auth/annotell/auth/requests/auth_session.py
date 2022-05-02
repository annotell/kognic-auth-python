import logging
from typing import Optional
import requests
import threading
from authlib.integrations.requests_client import OAuth2Session
from authlib.common.errors import AuthlibBaseError

from annotell.auth.base.auth_client import AuthClient
from annotell.auth.credentials_parser import resolve_credentials
from annotell.auth import DEFAULT_HOST

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

    def __init__(self, *,
                 auth=None,
                 client_id: Optional[str] = None,
                 client_secret: Optional[str] = None,
                 host: str = DEFAULT_HOST):
        """
        There is a variety of ways to setup the authentication. See
        https://github.com/annotell/annotell-python/tree/master/annotell-auth
        :param auth: authentication credentials
        :param client_id: client id for authentication
        :param client_secret: client secret for authentication
        :param host: base url for authentication server
        """
        self.host = host
        self.token_url = "%s/v1/auth/oauth/token" % self.host

        client_id, client_secret = resolve_credentials(auth, client_id, client_secret)

        self.oauth_session = _FixedSession(
            client_id=client_id,
            client_secret=client_secret,
            token_endpoint_auth_method='client_secret_post',
            update_token=self._update_token,
            token_endpoint=self.token_url
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
                token = self.oauth_session.fetch_access_token(url=self.token_url)
                self._update_token(token)
        return self.oauth_session.session

