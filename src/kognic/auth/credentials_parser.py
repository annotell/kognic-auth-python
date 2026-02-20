import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from kognic.auth.internal import credentials_store

ANY_AUTH_TYPE = Union[str, os.PathLike, tuple, "ApiCredentials", dict, None]

REQUIRED_CREDENTIALS_FILE_KEYS = [
    "clientId",
    "clientSecret",
    "email",
    "userId",
    "issuer",
]


@dataclass
class ApiCredentials:
    client_id: str
    client_secret: str
    email: str
    user_id: int
    issuer: str


def parse_credentials(path: Union[str, os.PathLike, dict]) -> ApiCredentials:
    if isinstance(path, dict):
        credentials = path
    else:
        try:
            credentials = json.loads(Path(path).read_text())
        except FileNotFoundError:
            raise FileNotFoundError(f"Could not find Api Credentials file at {path}") from None

    if not isinstance(credentials, dict):
        raise AttributeError(f"Could not json dict from {path}")

    for k in REQUIRED_CREDENTIALS_FILE_KEYS:
        if k not in credentials:
            raise KeyError(f"Missing key {k} in credentials file")

    return ApiCredentials(
        client_id=credentials.get("clientId"),
        client_secret=credentials.get("clientSecret"),
        email=credentials.get("email"),
        user_id=credentials.get("userId"),
        issuer=credentials.get("issuer"),
    )


def get_credentials_from_env() -> tuple[Optional[str], Optional[str]]:
    creds = os.getenv("KOGNIC_CREDENTIALS")
    if creds:
        client_credentials = parse_credentials(creds)
        return client_credentials.client_id, client_credentials.client_secret

    client_id = os.getenv("KOGNIC_CLIENT_ID")
    client_secret = os.getenv("KOGNIC_CLIENT_SECRET")

    if client_id and client_secret:
        return client_id, client_secret

    keyring_creds = credentials_store.load_credentials()
    if keyring_creds:
        return keyring_creds.client_id, keyring_creds.client_secret

    return client_id, client_secret


def resolve_credentials(
    auth: ANY_AUTH_TYPE = None, client_id: Optional[str] = None, client_secret: Optional[str] = None
) -> tuple[Optional[str], Optional[str]]:
    has_credentials_tuple = client_id is not None and client_secret is not None

    if has_credentials_tuple:
        if auth is not None:
            raise ValueError("Choose either auth or client_id+client_secret")

    elif isinstance(auth, tuple):
        if len(auth) != 2:
            raise ValueError("Credentials tuple must be tuple of (client_id, client_secret)")
        client_id, client_secret = auth
    elif isinstance(auth, ApiCredentials):
        client_id = auth.client_id
        client_secret = auth.client_secret
    elif isinstance(auth, dict):
        creds = parse_credentials(auth)
        client_id = creds.client_id
        client_secret = creds.client_secret
    elif isinstance(auth, (str, os.PathLike)):
        path = str(auth)
        if path.startswith("keyring://"):
            profile = path[len("keyring://") :]
            keyring_creds = credentials_store.load_credentials(profile)
            if keyring_creds:
                client_id, client_secret = keyring_creds.client_id, keyring_creds.client_secret
            else:
                raise ValueError(
                    f"No credentials found in keyring for profile '{profile}'. "
                    f"Run 'kognic-auth credentials put <file> --env {profile}' to store them."
                )
        elif not path.endswith(".json"):
            raise ValueError(f"Bad auth credentials file, must be json: {path}")
        else:
            creds = parse_credentials(auth)
            client_id = creds.client_id
            client_secret = creds.client_secret
    elif auth is not None:
        # unreasonable type, but we want to be defensive in case of user error
        raise ValueError(f"Unsupported auth type: {type(auth)}")

    if not client_id and not client_secret:
        client_id, client_secret = get_credentials_from_env()

    return client_id, client_secret


if __name__ == "__main__":
    client_id, client_secret = get_credentials_from_env()
    # Avoid printing secrets; only indicate that credentials were loaded.
    print(f"Loaded credentials for client_id={client_id!r}")
