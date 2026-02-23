import json
import os
from pathlib import Path
from typing import Optional, Union

from kognic.auth.credentials import ApiCredentials
from kognic.auth.internal import credentials_store

ANY_AUTH_TYPE = Union[str, os.PathLike, tuple, "ApiCredentials", dict, None]

REQUIRED_CREDENTIALS_FILE_KEYS = [
    "clientId",
    "clientSecret",
    "email",
    "userId",
    "issuer",
]


def parse_credentials(path: Union[str, os.PathLike, dict]) -> ApiCredentials:
    if isinstance(path, dict):
        credentials = path
    else:
        try:
            credentials = json.loads(Path(path).read_text())
        except FileNotFoundError:
            raise FileNotFoundError(f"Could not find API Credentials file at {path}") from None

    if not isinstance(credentials, dict):
        raise AttributeError(f"Could not json dict from {path}")

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


def _anonymous_credentials(client_id: str, client_secret: str) -> ApiCredentials:
    return ApiCredentials(
        client_id=client_id,
        client_secret=client_secret,
        email="",
        user_id=0,
        issuer="",
        name="",
    )


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


def resolve_any_credentials(auth: ANY_AUTH_TYPE) -> Optional[ApiCredentials]:
    """
    Resolve credentials from a variety of input types
    :param auth:
    :return:
    """

    if isinstance(auth, tuple):
        if len(auth) != 2:
            raise ValueError("Credentials tuple must be tuple of (client_id, client_secret)")
        creds = _anonymous_credentials(*auth)
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
    has_credentials_tuple = client_id is not None and client_secret is not None

    if has_credentials_tuple:
        if auth is not None:
            raise ValueError("Choose either auth or client_id+client_secret")

    else:
        creds = resolve_any_credentials(auth)
        if creds:
            return creds.client_id, creds.client_secret

    if not client_id and not client_secret:
        client_id, client_secret = get_credentials_from_env()

    return client_id, client_secret


if __name__ == "__main__":
    creds = get_credentials_from_system()
    if creds:
        # Avoid printing secrets; only indicate that credentials were loaded.
        print(f"Loaded credentials for client_id={creds.client_id!r}")
