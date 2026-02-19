from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from kognic.auth import DEFAULT_CACHE_PATH
from kognic.auth.internal.token_cache._base import TokenCache, is_valid, make_key

log = logging.getLogger(__name__)


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
            key = make_key(auth_server, client_id)
            token = self._load_all().get(key)
            if token is None:
                return None
            if not is_valid(token):
                log.debug("Cached file token expired or missing expires_at, discarding")
                return None
            log.debug("Using cached token from file (key=%s)", key)
            return token
        except Exception:
            log.debug("Failed to load token from file cache", exc_info=True)
            return None

    def save(self, auth_server: str, client_id: str, token: dict) -> None:
        try:
            key = make_key(auth_server, client_id)
            data = self._load_all()
            data[key] = token
            self._save_all(data)
            log.debug("Saved token to file cache for key=%s", key)
        except Exception:
            log.debug("Failed to save token to file cache", exc_info=True)

    def clear(self, auth_server: str, client_id: str) -> None:
        try:
            key = make_key(auth_server, client_id)
            data = self._load_all()
            if key in data:
                del data[key]
                self._save_all(data)
            log.debug("Cleared cached token from file cache for key=%s", key)
        except Exception:
            log.debug("Failed to clear token from file cache", exc_info=True)
