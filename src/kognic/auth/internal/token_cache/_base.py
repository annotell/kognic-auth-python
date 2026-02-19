from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Optional

SERVICE_NAME = "kognic-auth"

# Tokens are considered expired this many seconds before their actual expiry,
# to avoid using a token that expires mid-request.
EXPIRY_MARGIN_SECONDS = 30


def make_key(auth_server: str, client_id: str) -> str:
    return f"{auth_server}:{client_id}"


def is_valid(token: dict) -> bool:
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
