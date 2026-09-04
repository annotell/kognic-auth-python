# Local stub for the slice of authlib this package uses. See the httpx_client stub
# for why. Signatures mirror authlib/integrations/requests_client/oauth2_session.py
# and authlib/oauth2/client.py; keep them in sync when bumping authlib.
from typing import Any, Callable, Dict, Optional

import requests

class OAuth2Session(requests.Session):
    token: Optional[Dict[str, Any]]
    scope: Optional[str]
    # authlib's OAuth2Client stores the transport session on itself; for OAuth2Session
    # that is the instance itself.
    session: requests.Session

    def __init__(
        self,
        client_id: Optional[str] = ...,
        client_secret: Optional[str] = ...,
        token_endpoint_auth_method: Optional[str] = ...,
        revocation_endpoint_auth_method: Optional[str] = ...,
        scope: Optional[str] = ...,
        redirect_uri: Optional[str] = ...,
        token: Optional[Dict[str, Any]] = ...,
        token_placement: str = ...,
        update_token: Optional[Callable[..., Any]] = ...,
        leeway: int = ...,
        **kwargs: Any,
    ) -> None: ...
    def fetch_token(
        self,
        url: Optional[str] = ...,
        body: str = ...,
        method: str = ...,
        headers: Optional[Dict[str, str]] = ...,
        auth: Any = ...,
        grant_type: Optional[str] = ...,
        state: Optional[str] = ...,
        **kwargs: Any,
    ) -> Dict[str, Any]: ...
    def fetch_access_token(self, url: Optional[str] = ..., **kwargs: Any) -> Dict[str, Any]: ...
    def refresh_token(
        self,
        url: Optional[str] = ...,
        refresh_token: Optional[str] = ...,
        body: str = ...,
        auth: Any = ...,
        headers: Optional[Dict[str, str]] = ...,
        **kwargs: Any,
    ) -> Dict[str, Any]: ...
    def register_compliance_hook(self, hook_type: str, hook: Callable[..., Any]) -> None: ...
