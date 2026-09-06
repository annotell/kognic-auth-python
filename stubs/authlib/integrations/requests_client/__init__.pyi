from typing import Any, Callable, Mapping

from authlib.oauth2.client import OAuth2Client
from authlib.oauth2.rfc6749 import OAuth2Token
from requests import Session

__all__ = ["OAuth2Session"]

class OAuth2Session(OAuth2Client, Session):
    # OAuth2Client sets self.session to the session it is constructed with; the requests
    # integration passes itself, so this is the OAuth2Session instance.
    session: Session

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
        default_timeout: float | tuple[float, float] | None = None,
        *,
        grant_type: str | None = None,
        token_endpoint: str | None = None,
        **kwargs: Any,
    ) -> None: ...
    def fetch_access_token(self, url: str | None = None, **kwargs: Any) -> OAuth2Token: ...
