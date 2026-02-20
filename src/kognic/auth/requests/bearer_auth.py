"""Bearer token auth handler for requests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import requests
from requests.auth import AuthBase

if TYPE_CHECKING:
    from kognic.auth.requests.auth_session import RequestsAuthSession


class KognicBearerAuth(AuthBase):
    """Injects a Bearer token from a RequestsAuthSession into each request.

    Handles 401 responses by invalidating the cached token and retrying once.
    """

    def __init__(self, provider: RequestsAuthSession) -> None:
        self._provider = provider

    def __call__(self, r: requests.PreparedRequest) -> requests.PreparedRequest:
        r.headers["Authorization"] = f"Bearer {self._provider.ensure_token()['access_token']}"
        r.register_hook("response", self._handle_401)
        return r

    def _handle_401(self, r: requests.Response, **kwargs) -> requests.Response:
        if r.status_code != 401:
            return r
        self._provider.invalidate_token()
        _ = r.content  # drain socket so connection can be reused
        prep = r.request.copy()
        prep.headers["Authorization"] = f"Bearer {self._provider.ensure_token()['access_token']}"
        _r = r.connection.send(prep, **kwargs)
        _r.history.append(r)
        return _r
