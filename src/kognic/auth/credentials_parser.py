import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union, cast

from kognic.auth.credentials import ApiCredentials
from kognic.auth.internal import credentials_store
from kognic.auth.internal.credentials import anonymous_credentials, check_expiry
from kognic.auth.internal.credentials import resolve_credentials as _resolve_credentials

# Back-compat: these were importable under these private names before they moved.
_check_expiry = check_expiry
_anonymous_credentials = anonymous_credentials

ANY_AUTH_TYPE = Union[str, "os.PathLike[str]", Tuple[str, str], "ApiCredentials", Dict[str, Any], None]

REQUIRED_CREDENTIALS_FILE_KEYS = [
    "clientId",
    "clientSecret",
    "email",
    "userId",
    "issuer",
]


def _parse_datetime(s: str) -> datetime:
    """Parse an ISO 8601 datetime string into a timezone-aware datetime.

    Handles Z suffix and sub-microsecond precision (truncated to microseconds).
    """
    s = s.replace("Z", "+00:00")
    s = re.sub(r"(\.\d{6})\d+", r"\1", s)
    return datetime.fromisoformat(s)


def _parse_optional_datetime(s: Optional[str]) -> Optional[datetime]:
    """Parse an optional datetime string, returning None if absent or unparseable."""
    if s is None:
        return None
    try:
        return _parse_datetime(s)
    except Exception:
        return None


def parse_credentials(path: Union[str, "os.PathLike[str]", Dict[str, Any]]) -> ApiCredentials:
    if isinstance(path, dict):
        credentials = path
    else:
        absolute_path = Path(path).expanduser().resolve()
        try:
            loaded: Any = json.loads(absolute_path.read_text())
        except FileNotFoundError:
            raise FileNotFoundError(f"Could not find API Credentials file at {path}") from None

        if not isinstance(loaded, dict):
            raise AttributeError(f"Could not json dict from {path}")
        # json.loads yields Any; isinstance narrows it to dict[Unknown, Unknown], so restate
        # the key/value types the credentials file is documented to have.
        credentials = cast(Dict[str, Any], loaded)

    for k in REQUIRED_CREDENTIALS_FILE_KEYS:
        if k not in credentials:
            raise KeyError(f"Missing key {k} in credentials file")

    return ApiCredentials(
        client_id=credentials["clientId"],
        client_secret=credentials["clientSecret"],
        email=credentials["email"],
        user_id=credentials["userId"],
        issuer=credentials["issuer"],
        name=credentials.get("name", "API Credentials"),
        created=_parse_optional_datetime(credentials.get("created")),
        expires=_parse_optional_datetime(credentials.get("expires")),
        scopes=credentials.get("scopes", []),
    )


def get_credentials_from_env() -> tuple[Optional[str], Optional[str]]:
    """
    Deprecated
    :return:
    """
    creds = get_credentials_from_system()
    if creds:
        return creds.client_id, creds.client_secret
    return None, None


def get_credentials_from_system() -> Optional[ApiCredentials]:
    creds = os.getenv("KOGNIC_CREDENTIALS")
    if creds:
        return parse_credentials(creds)

    client_id = os.getenv("KOGNIC_CLIENT_ID")
    client_secret = os.getenv("KOGNIC_CLIENT_SECRET")

    if client_id and client_secret:
        return _anonymous_credentials(client_id, client_secret)

    keyring_creds = credentials_store.load_credentials()
    if keyring_creds:
        return keyring_creds

    return None


def resolve_any_credentials(auth: ANY_AUTH_TYPE) -> ApiCredentials:
    """
    Resolve credentials from a variety of input types
    :param auth:
    :return:
    """

    if isinstance(auth, tuple):
        if len(auth) != 2:
            raise ValueError("Credentials tuple must be tuple of (client_id, client_secret)")
        creds = anonymous_credentials(*auth)
    elif isinstance(auth, ApiCredentials):
        creds = auth
    elif isinstance(auth, dict):
        creds = parse_credentials(auth)
    elif isinstance(auth, (str, os.PathLike)):
        path = str(auth)
        if path.startswith("keyring://"):
            profile = path[len("keyring://") :]
            creds = credentials_store.load_credentials(profile)
            if not creds:
                raise ValueError(
                    f"No credentials found in keyring for profile '{profile}'. "
                    f"Run 'kognic-auth credentials put <file> --env {profile}' to store them."
                )
        elif not path.endswith(".json"):
            raise ValueError(f"Bad auth credentials file, must be json: {path}")
        else:
            creds = parse_credentials(auth)
    else:
        # unreasonable type, but we want to be defensive in case of user error
        raise ValueError(f"Unsupported auth type: {type(auth)}")

    return creds


def resolve_credentials(
    auth: ANY_AUTH_TYPE = None, client_id: Optional[str] = None, client_secret: Optional[str] = None
) -> tuple[Optional[str], Optional[str]]:
    """
    Resolve credentials from either an auth input (which can be a variety of types)
    or from explicit client_id and client_secret parameters.
    Falls back to environment variables if neither are provided.
    :param auth:
    :param client_id:
    :param client_secret:
    :return:
    """
    creds = _resolve_credentials(auth, client_id, client_secret)
    if creds is None:
        return None, None
    return creds.client_id, creds.client_secret


if __name__ == "__main__":
    creds: Optional[ApiCredentials] = get_credentials_from_system()
    if creds:
        # Avoid printing secrets; only indicate that credentials were loaded.
        print(f"Loaded credentials for client_id={creds.client_id!r}")
