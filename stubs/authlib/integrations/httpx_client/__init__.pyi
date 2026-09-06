from typing import Any, Callable, Mapping

import httpx

from authlib.oauth2.client import OAuth2Client
from authlib.oauth2.rfc6749 import OAuth2Token

__all__ = ["AsyncOAuth2Client"]

class AsyncOAuth2Client(OAuth2Client, httpx.AsyncClient):
    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        token_endpoint_auth_method: str | None = None,
        revocation_endpoint_auth_method: str | None = None,
        scope: str | None = None,
        state: str | None = None,
        redirect_uri: str | None = None,
        token: Mapping[str, Any] | None = None,
        token_placement: str = "header",
        update_token: Callable[..., Any] | None = None,
        leeway: int = 60,
        *,
        grant_type: str | None = None,
        token_endpoint: str | None = None,
        **kwargs: Any,
    ) -> None: ...
    async def fetch_token(self, url: str | None = None, **kwargs: Any) -> OAuth2Token: ...  # pyright: ignore[reportIncompatibleMethodOverride]
    async def _refresh_token(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        url: str,
        refresh_token: str | None = None,
        body: str = "",
        headers: Mapping[str, str] | None = None,
        auth: Any = ...,
        **kwargs: Any,
    ) -> OAuth2Token: ...
