import logging
from datetime import datetime, timedelta
from typing import Optional

from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.oauth2.rfc6749 import OAuth2Token

from annotell.auth import DEFAULT_HOST, REFRESH_TLL
from annotell.auth.base.auth_client import AuthClient
from annotell.auth.base.refresh_expiry_fix import RefreshTokenExpiryFixOAuth2Client
from annotell.auth.credentials_parser import resolve_credentials
from asyncio import Lock

log = logging.getLogger(__name__)


class _AsyncFixedClient(AsyncOAuth2Client, RefreshTokenExpiryFixOAuth2Client):
    pass


class HttpxAuthAsyncClient(AuthClient):
    def __init__(self, *,
                 auth=None,
                 client_id: Optional[str] = None,
                 client_secret: Optional[str] = None,
                 host: str = DEFAULT_HOST,
                 refresh_ttl=REFRESH_TLL):
        """
        There is a variety of ways to setup the authentication. See
        https://github.com/annotell/annotell-python/tree/master/annotell-auth
        :param auth: authentication credentials
        :param client_id: client id for authentication
        :param client_secret: client secret for authentication
        :param host: base url for authentication server
        :param refresh_ttl: Hint for refresh token expiry check
        """
        self.host = host
        self.token_url = "%s/v1/auth/oauth/token" % self.host
        self._refresh_ttl = refresh_ttl

        client_id, client_secret = resolve_credentials(auth, client_id, client_secret)

        self._oauth_client = _AsyncFixedClient(
            client_id=client_id,
            client_secret=client_secret,
            update_token=self._update_token,
            token_endpoint=self.token_url,
            grant_type="client_credentials"
        )

        self._expires_at = None
        self._refresh_expires_at = None
        self._lock = Lock()

    @property
    def token(self):
        return self._oauth_client.token

    async def _update_token(self, token: OAuth2Token, refresh_token=None, access_token=None):
        token["refresh_expires_at"] = datetime.utcnow() + timedelta(seconds=self._refresh_ttl)
        self._oauth_client.token = token
        self._log_new_token()

    async def session(self) -> AsyncOAuth2Client:
        if not self.token:
            async with self._lock:
                token = await self._oauth_client.fetch_token()
                await self._update_token(token)
        return self._oauth_client

