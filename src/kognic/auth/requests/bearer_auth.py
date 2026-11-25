"""Bearer token auth handler for requests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import requests
from requests.auth import AuthBase

from kognic.auth.requests._replay import rewind_for_replay

if TYPE_CHECKING:
    from kognic.auth.requests.auth_session import RequestsAuthSession


class KognicBearerAuth(AuthBase):
    """Injects a Bearer token from a RequestsAuthSession into each request.

    On a 401 for a request that still carries its Bearer header, the cached token is invalidated.
    The request is then sent once more with a fresh token if its body is replayable; otherwise
    the 401 is returned. A 401 for a request without its Bearer header is returned untouched.
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
        # requests strips the header on a redirect to a different origin (scheme, host, port); see ADR 0002.
        if not r.request.headers.get("Authorization", "").startswith("Bearer "):
            return r
        self._provider.invalidate_token()
        prep = r.request.copy()
        if not rewind_for_replay(prep):
            return r
        _ = r.content  # drain socket so connection can be reused
        prep.headers["Authorization"] = f"Bearer {self._provider.ensure_token()['access_token']}"
        _r = r.connection.send(prep, **kwargs)
        _r.history.append(r)
        return _r
