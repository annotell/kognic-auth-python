"""Keyring-based storage for Kognic API client credentials (full credentials file)."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from kognic.auth.credentials_parser import ApiCredentials

SERVICE_NAME = "kognic-credentials"
DEFAULT_PROFILE = "default"

log = logging.getLogger(__name__)


def _get_keyring():
    """Return the keyring module if a usable backend is available, else None."""
    try:
        import keyring

        backend = keyring.get_keyring()
        if "fail" in type(backend).__name__.lower():
            return None
        return keyring
    except Exception:
        return None


def load_credentials(profile: str = DEFAULT_PROFILE) -> Optional[ApiCredentials]:
    """Load full credentials from keyring, or None if not found."""
    kr = _get_keyring()
    if kr is None:
        return None
    try:
        stored = kr.get_password(SERVICE_NAME, profile)
        if stored is None:
            return None

        from kognic.auth.credentials_parser import parse_credentials

        return parse_credentials(json.loads(stored))
    except Exception:
        log.debug("Failed to load credentials from keyring", exc_info=True)
        return None


def save_credentials(creds: ApiCredentials, profile: str = DEFAULT_PROFILE) -> None:
    """Store full credentials in keyring. Raises RuntimeError if keyring is unavailable."""
    kr = _get_keyring()
    if kr is None:
        raise RuntimeError(
            "No usable keyring backend available. "
            "Install a keyring backend (e.g. 'pip install keyring') or use environment variables instead."
        )
    data = {
        "clientId": creds.client_id,
        "clientSecret": creds.client_secret,
        "email": creds.email,
        "userId": creds.user_id,
        "issuer": creds.issuer,
    }
    kr.set_password(SERVICE_NAME, profile, json.dumps(data))
    log.debug("Saved credentials to keyring for profile=%s", profile)


def clear_credentials(profile: str = DEFAULT_PROFILE) -> None:
    """Remove credentials from keyring. Silently does nothing if not found or keyring unavailable."""
    kr = _get_keyring()
    if kr is None:
        return
    try:
        kr.delete_password(SERVICE_NAME, profile)
        log.debug("Cleared credentials from keyring for profile=%s", profile)
    except Exception:
        log.debug("Failed to clear credentials from keyring", exc_info=True)
