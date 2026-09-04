import logging
from asyncio import Lock
from typing import Any, Dict, List, Optional

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client

from kognic.auth import DEFAULT_HOST, DEFAULT_TOKEN_ENDPOINT_RELPATH
from kognic.auth.base.auth_client import AuthClient
from kognic.auth.credentials_parser import ANY_AUTH_TYPE, check_expiry, resolve_api_credentials

log: logging.Logger = logging.getLogger(__name__)


class _AsyncFixedClient(AsyncOAuth2Client):
    async def _refresh_token(self, url: str, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        try:
            return await super(_AsyncFixedClient, self)._refresh_token(url, *args, **kwargs)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                log.info("Refresh token expired, resetting auth session")
                return await self.fetch_token()
            raise


class HttpxAuthAsyncClient(AuthClient):
    def __init__(
        self,
        *,
        auth: ANY_AUTH_TYPE = None,
        host: str = DEFAULT_HOST,
        token_endpoint: str = DEFAULT_TOKEN_ENDPOINT_RELPATH,
        scopes: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the async auth client.

        Args:
            auth: Authentication credentials - path to credentials file or (client_id, client_secret) tuple
            host: Base url for authentication server
            token_endpoint: Relative path to the token endpoint
            scopes: OAuth2 scopes to request, e.g. ["api:read", "api:write"].
            **kwargs: Additional params to pass into Httpx Client Constructor
        """
        self.host: str = host
        self.token_url: str = f"{host}{token_endpoint}"

        creds = resolve_api_credentials(auth)
        if creds:
            check_expiry(creds)

        client_id = creds.client_id if creds else None
        client_secret = creds.client_secret if creds else None

        if scopes is None and creds and creds.scopes:
            scopes = creds.scopes

        self._oauth_client: _AsyncFixedClient = _AsyncFixedClient(
            client_id=client_id,
            client_secret=client_secret,
            update_token=self._update_token,
            token_endpoint=self.token_url,
            grant_type="client_credentials",
            scope=" ".join(scopes) if scopes else None,
            **kwargs,
        )
        self._oauth_client.register_compliance_hook("access_token_response", AuthClient.check_rate_limit)
        self._oauth_client.register_compliance_hook("refresh_token_response", AuthClient.check_rate_limit)

        self._lock = Lock()

    @property
    def token(self) -> Optional[Dict[str, Any]]:
        return self._oauth_client.token

    async def _update_token(
        self, token: Dict[str, Any], access_token: Optional[str] = None, refresh_token: Optional[str] = None
    ) -> None:
        self._log_new_token()

    @property
    async def session(self) -> httpx.AsyncClient:
        if not self.token:
            async with self._lock:
                # check again when coming out of the lock that the token is still not set
                if not self.token:
                    token = await self._oauth_client.fetch_token()
                    await self._update_token(token)
        return self._oauth_client

    async def close(self) -> None:
        await self._oauth_client.aclose()
