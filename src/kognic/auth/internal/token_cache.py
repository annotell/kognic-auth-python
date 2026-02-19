"""Token cache backends.

All keyring imports are lazy so the module works when keyring is not installed.
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from kognic.auth import DEFAULT_CACHE_PATH

log = logging.getLogger(__name__)

SERVICE_NAME = "kognic-auth"

# Tokens are considered expired this many seconds before their actual expiry,
# to avoid using a token that expires mid-request.
EXPIRY_MARGIN_SECONDS = 30


def _make_key(auth_server: str, client_id: str) -> str:
    return f"{auth_server}:{client_id}"


def _is_valid(token: dict) -> bool:
    expires_at = token.get("expires_at")
    if expires_at is None:
        return False
    return time.time() < (expires_at - EXPIRY_MARGIN_SECONDS)


class TokenCache(ABC):
    """Abstract base class for token caches."""

    @abstractmethod
    def load(self, auth_server: str, client_id: str) -> Optional[dict]:
        """Return a non-expired token dict, or None."""

    @abstractmethod
    def save(self, auth_server: str, client_id: str, token: dict) -> None:
        """Persist a token dict. Silently ignores errors."""

    @abstractmethod
    def clear(self, auth_server: str, client_id: str) -> None:
        """Remove a cached token. Silently ignores errors."""


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
            key = _make_key(auth_server, client_id)
            stored = kr.get_password(SERVICE_NAME, key)
            if stored is None:
                return None
            token = json.loads(stored)
            if not _is_valid(token):
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
            key = _make_key(auth_server, client_id)
            kr.set_password(SERVICE_NAME, key, json.dumps(token))
            log.debug("Saved token to keyring for key=%s", key)
        except Exception:
            log.debug("Failed to save token to keyring", exc_info=True)

    def clear(self, auth_server: str, client_id: str) -> None:
        kr = self._keyring()
        if kr is None:
            return
        try:
            key = _make_key(auth_server, client_id)
            kr.delete_password(SERVICE_NAME, key)
            log.debug("Cleared cached token from keyring for key=%s", key)
        except Exception:
            log.debug("Failed to clear token from keyring", exc_info=True)


class FileTokenCache(TokenCache):
    """Token cache backed by a JSON file on disk."""

    def __init__(self, path: Path = DEFAULT_CACHE_PATH) -> None:
        self.path = path

    def _load_all(self) -> dict:
        try:
            return json.loads(self.path.read_text())
        except FileNotFoundError:
            return {}
        except Exception:
            log.debug("Failed to read token cache file", exc_info=True)
            return {}

    def _save_all(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2))

    def load(self, auth_server: str, client_id: str) -> Optional[dict]:
        try:
            key = _make_key(auth_server, client_id)
            token = self._load_all().get(key)
            if token is None:
                return None
            if not _is_valid(token):
                log.debug("Cached file token expired or missing expires_at, discarding")
                return None
            log.debug("Using cached token from file (key=%s)", key)
            return token
        except Exception:
            log.debug("Failed to load token from file cache", exc_info=True)
            return None

    def save(self, auth_server: str, client_id: str, token: dict) -> None:
        try:
            key = _make_key(auth_server, client_id)
            data = self._load_all()
            data[key] = token
            self._save_all(data)
            log.debug("Saved token to file cache for key=%s", key)
        except Exception:
            log.debug("Failed to save token to file cache", exc_info=True)

    def clear(self, auth_server: str, client_id: str) -> None:
        try:
            key = _make_key(auth_server, client_id)
            data = self._load_all()
            if key in data:
                del data[key]
                self._save_all(data)
            log.debug("Cleared cached token from file cache for key=%s", key)
        except Exception:
            log.debug("Failed to clear token from file cache", exc_info=True)


def make_cache(mode: str) -> TokenCache | None:
    """Return a TokenCache for the given mode, or None for 'none'.

    Modes:
      auto    – keyring if available, file otherwise (default)
      keyring – system keyring only
      file    – file-based cache only
      none    – no caching
    """
    if mode == "none":
        return None
    if mode == "file":
        return FileTokenCache()
    if mode == "keyring":
        return KeyringTokenCache()
    # auto
    candidate = KeyringTokenCache()
    if candidate._keyring() is not None:
        return candidate
    return FileTokenCache()
