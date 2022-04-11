import logging
from datetime import datetime
from typing import Optional
import requests
from authlib.integrations.requests_client import OAuth2Session
from authlib.common.errors import AuthlibBaseError
from .credentials_parser import resolve_credentials
import threading
from annotell.auth import DEFAULT_HOST

log = logging.getLogger(__name__)


# https://docs.authlib.org/en/latest/client/oauth2.html
class AuthSession:
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

        self.oauth_session = OAuth2Session(
            client_id=client_id,
            client_secret=client_secret,
            token_endpoint_auth_method='client_secret_post',
            update_token=self._update_token,
            token_endpoint=self.token_url
        )

        self._token = None
        self._expires_at = None
        self._lock = threading.RLock()

    def _log_new_token(self):
        log.info(f"Got new token, with ttl={self._token['expires_in']} and expires {self._expires_at} UTC")

    def _update_token(self, token, access_token=None, refresh_token=None):
        self._token = token
        self._log_new_token()

    def init(self):
        self.fetch_token()

    def fetch_token(self):
        log.debug("Fetching token")
        with self._lock:
            self._token = self.oauth_session.fetch_access_token(url=self.token_url)
            self._expires_at = datetime.utcfromtimestamp(self._token['expires_at'])
        self._log_new_token()

    @property
    def token(self):
        return self._token

    @property
    def access_token(self):
        return self._token.get('access_token') if self._token is not None else None

    @property
    def session(self):
        with self._lock:
            if not self._token:
                self.init()
        return self.oauth_session.session


class FaultTolerantAuthRequestSession:
    """An object that can be used like a requests.Session that handles token refresh.
    It is not a drop in replacement for requests.Session since this does not forward all methods.
    We just expose the subset we need"""

    def __init__(self, auth=None, host=DEFAULT_HOST):
        self.auth = auth
        self.host = host
        self._oauth_session = AuthSession(auth=auth, host=host)
        self._lock = threading.Lock()

    @property
    def request_session(self) -> requests.Session:
        return self._oauth_session.session

    @property
    def headers(self):
        return self.request_session.headers

    def get(self, *args, **kwargs) -> requests.Response:
        return self._query('get', *args, **kwargs)

    def post(self, *args, **kwargs) -> requests.Response:
        return self._query('post', *args, **kwargs)

    def put(self, *args, **kwargs) -> requests.Response:
        return self._query('put', *args, **kwargs)

    def patch(self, *args, **kwargs) -> requests.Response:
        return self._query('patch', *args, **kwargs)

    def delete(self, *args, **kwargs) -> requests.Response:
        return self._query('delete', *args, **kwargs)

    def _query(self, fun_name, *args, **kwargs):
        # add retry if the token has expired, this can happen when the session
        # is left open for many hours without any queries

        # need to resolve this on the fly since the request session will change on reset
        def fun():
            return getattr(self.request_session, fun_name)(*args, **kwargs)

        def reset_and_retry():
            log.warning("Got invalid token, resetting auth session")
            with self._lock:
                self._oauth_session = AuthSession(auth=self.auth, host=self.host)
            return fun()

        try:
            return fun()
        except AuthlibBaseError as e:
            if e.error == "invalid_token":
                return reset_and_retry()
            raise
        except requests.exceptions.HTTPError as e:
            # with authlib >= 1.0.0
            if e.response.status_code == 401 and "invalid_token" == e.response.json().get("error"):
                return reset_and_retry()
            raise
