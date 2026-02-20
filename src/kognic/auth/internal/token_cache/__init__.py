"""Token cache backends for cross-process token persistence.

All keyring imports are lazy so the module works when keyring is not installed.
"""

from __future__ import annotations

from kognic.auth.internal.token_cache._base import TokenCache
from kognic.auth.internal.token_cache._file import FileTokenCache
from kognic.auth.internal.token_cache._keyring import KeyringTokenCache


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


__all__ = ["TokenCache", "KeyringTokenCache", "FileTokenCache", "make_cache"]
