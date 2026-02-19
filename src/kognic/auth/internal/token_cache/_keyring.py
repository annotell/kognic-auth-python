from __future__ import annotations

import json
import logging
from typing import Optional

from kognic.auth.internal.token_cache._base import SERVICE_NAME, TokenCache, is_valid, make_key

log = logging.getLogger(__name__)

_KEYRING_MISSING = object()  # sentinel: import attempted but unavailable


class KeyringTokenCache(TokenCache):
    """Token cache backed by the system keyring."""

    def __init__(self) -> None:
        self._keyring_module = None  # not yet resolved

    def _keyring(self):
        """Return the keyring module if usable, else None. Result is cached."""
        if self._keyring_module is _KEYRING_MISSING:
            return None
        if self._keyring_module is not None:
            return self._keyring_module
        try:
            import keyring

            backend = keyring.get_keyring()
            if "fail" in type(backend).__name__.lower():
                raise RuntimeError("unusable keyring backend")
            self._keyring_module = keyring
        except Exception:
            self._keyring_module = _KEYRING_MISSING
            return None
        return self._keyring_module

    def load(self, auth_server: str, client_id: str) -> Optional[dict]:
        kr = self._keyring()
        if kr is None:
            return None
        try:
            key = make_key(auth_server, client_id)
            stored = kr.get_password(SERVICE_NAME, key)
            if stored is None:
                return None
            token = json.loads(stored)
            if not is_valid(token):
                log.debug("Cached keyring token expired or missing expires_at, discarding")
                return None
            log.debug("Using cached token from keyring (key=%s)", key)
            return token
        except Exception:
            log.debug("Failed to load token from keyring", exc_info=True)
            return None

    def save(self, auth_server: str, client_id: str, token: dict) -> None:
        kr = self._keyring()
        if kr is None:
            return
        try:
            key = make_key(auth_server, client_id)
            kr.set_password(SERVICE_NAME, key, json.dumps(token))
            log.debug("Saved token to keyring for key=%s", key)
        except Exception:
            log.debug("Failed to save token to keyring", exc_info=True)

    def clear(self, auth_server: str, client_id: str) -> None:
        kr = self._keyring()
        if kr is None:
            return
        try:
            key = make_key(auth_server, client_id)
            kr.delete_password(SERVICE_NAME, key)
            log.debug("Cleared cached token from keyring for key=%s", key)
        except Exception:
            log.debug("Failed to clear token from keyring", exc_info=True)
