"""CLI token cache using the system keyring.

This module is used ONLY by the CLI commands, not the library API.
All keyring imports are lazy so the module works when keyring is not installed.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

log = logging.getLogger(__name__)

SERVICE_NAME = "kognic-auth"

# Tokens are considered expired this many seconds before their actual expiry,
# to avoid using a token that expires mid-request.
EXPIRY_MARGIN_SECONDS = 30


def _keyring_available() -> bool:
    """Check if the keyring package is installed and a usable backend exists."""
    try:
        import keyring

        backend = keyring.get_keyring()
        # The "fail" backend is not usable
        if "fail" in type(backend).__name__.lower():
            return False
        return True
    except Exception:
        return False


def _make_key(auth_server: str, client_id: str) -> str:
    return f"{auth_server}:{client_id}"


def load_cached_token(auth_server: str, client_id: str) -> Optional[dict]:
    """Load a non-expired token from the keyring.

    Returns the token dict if found and still valid, otherwise None.
    """
    if not _keyring_available():
        return None
    try:
        import keyring

        key = _make_key(auth_server, client_id)
        stored = keyring.get_password(SERVICE_NAME, key)
        if stored is None:
            return None
        token = json.loads(stored)
        expires_at = token.get("expires_at")
        if expires_at is None:
            log.debug("Cached token has no expires_at, discarding")
            return None
        if time.time() >= (expires_at - EXPIRY_MARGIN_SECONDS):
            log.debug("Cached token expired, discarding")
            return None
        log.debug("Using cached token from keyring (expires_at=%s)", expires_at)
        return token
    except Exception:
        log.debug("Failed to load token from keyring", exc_info=True)
        return None


def save_token(auth_server: str, client_id: str, token: dict) -> None:
    """Save a token dict to the keyring. Silently ignores errors."""
    if not _keyring_available():
        return
    try:
        import keyring

        key = _make_key(auth_server, client_id)
        keyring.set_password(SERVICE_NAME, key, json.dumps(token))
        log.debug("Saved token to keyring for key=%s", key)
    except Exception:
        log.debug("Failed to save token to keyring", exc_info=True)


def clear_token(auth_server: str, client_id: str) -> None:
    """Remove a cached token from the keyring. Silently ignores errors."""
    if not _keyring_available():
        return
    try:
        import keyring

        key = _make_key(auth_server, client_id)
        keyring.delete_password(SERVICE_NAME, key)
        log.debug("Cleared cached token from keyring for key=%s", key)
    except Exception:
        log.debug("Failed to clear token from keyring", exc_info=True)
