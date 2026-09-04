# Local stub for the slice of authlib this package uses.
#
# authlib ships no py.typed, and the published types-Authlib stubs leave nearly every
# parameter and return unannotated, so both leave these members Unknown under strict.
# Signatures mirror authlib/integrations/httpx_client/oauth2_client.py and
# authlib/oauth2/client.py; keep them in sync when bumping authlib.
from typing import Any, Callable, Dict, Optional

import httpx

class AsyncOAuth2Client(httpx.AsyncClient):
    token: Optional[Dict[str, Any]]
    scope: Optional[str]

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
    async def fetch_token(
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
    async def _refresh_token(
        self,
        url: str,
        refresh_token: Optional[str] = ...,
        body: str = ...,
        headers: Optional[Dict[str, str]] = ...,
        auth: Any = ...,
        **kwargs: Any,
    ) -> Dict[str, Any]: ...
    def register_compliance_hook(self, hook_type: str, hook: Callable[..., Any]) -> None: ...
