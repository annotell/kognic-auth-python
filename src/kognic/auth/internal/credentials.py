"""Package-internal credential resolution helpers.

These are shared by the requests and httpx clients. They live here rather than in
kognic.auth.credentials_parser so that cross-module use does not read as reaching
into another module's privates.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from kognic.auth.credentials import ApiCredentials

if TYPE_CHECKING:
    from kognic.auth.credentials_parser import ANY_AUTH_TYPE


def check_expiry(creds: ApiCredentials) -> None:
    """Raise ValueError if the credentials have an expires field that is in the past."""
    if creds.expires is None:
        return
    if datetime.now(timezone.utc) >= creds.expires:
        raise ValueError(f"Credentials expired at {creds.expires.isoformat()}")


def anonymous_credentials(client_id: str, client_secret: str) -> ApiCredentials:
    return ApiCredentials(
        client_id=client_id,
        client_secret=client_secret,
        email="",
        user_id=0,
        issuer="",
        name="",
    )


def resolve_credentials(
    auth: ANY_AUTH_TYPE = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
) -> Optional[ApiCredentials]:
    """
    Resolve credentials from either an auth input (which can be a variety of types)
    or from explicit client_id and client_secret parameters.
    Falls back to environment variables if neither are provided.
    Returns the full ApiCredentials object, or None if no credentials are found.
    """
    # Imported lazily: credentials_parser imports this module at import time.
    from kognic.auth.credentials_parser import get_credentials_from_system, resolve_any_credentials

    if client_id is not None and client_secret is not None:
        if auth is not None:
            raise ValueError("Choose either auth or client_id+client_secret")
        return anonymous_credentials(client_id, client_secret)
    elif auth is not None:
        return resolve_any_credentials(auth)

    return get_credentials_from_system()
