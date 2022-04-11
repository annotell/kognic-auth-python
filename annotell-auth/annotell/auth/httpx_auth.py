import logging
from typing import Optional

from authlib.integrations.httpx_client import AsyncOAuth2Client
from annotell.auth import DEFAULT_HOST
from .credentials_parser import resolve_credentials
from asyncio import Lock

log = logging.getLogger(__name__)


class HttpxAuthClient:
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

        self.oauth_session = AsyncOAuth2Client(
            client_id=client_id,
            client_secret=client_secret,
            update_token=self._update_token,
            token_endpoint=self.token_url
        )

        self._token = None
        self._expires_at = None
        self._lock = Lock()

    def _log_new_token(self):
        log.info(f"Got new token, with ttl={self._token['expires_in']} and expires {self._expires_at} UTC")

    def _update_token(self, token, access_token=None, refresh_token=None):
        self._token = token
        self._log_new_token()

    @property
    def token(self):
        return self._token

    async def session(self) -> AsyncOAuth2Client:
        if not self._token:
            async with self._lock:
                await self.oauth_session.fetch_token()
        return self.oauth_session

