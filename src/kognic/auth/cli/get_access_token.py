from __future__ import annotations

import argparse
import sys

from kognic.auth import DEFAULT_HOST
from kognic.auth.cli.token_cache import make_cache
from kognic.auth.credentials_parser import resolve_credentials
from kognic.auth.env_config import DEFAULT_ENV_CONFIG_FILE_PATH, load_kognic_env_config
from kognic.auth.requests.auth_session import RequestsAuthSession

COMMAND = "get-access-token"


def register_parser(subparsers: argparse._SubParsersAction) -> None:
    token_parser = subparsers.add_parser(
        COMMAND,
        help="Generate an access token for Kognic API authentication",
    )
    token_parser.add_argument(
        "--server",
        default=None,
        help=f"Authentication server URL (default: {DEFAULT_HOST})",
    )
    token_parser.add_argument(
        "--credentials",
        metavar="FILE",
        help="Path to JSON credentials file. If not provided, credentials are read from environment variables.",
    )
    token_parser.add_argument(
        "--env-config-file-path",
        default=DEFAULT_ENV_CONFIG_FILE_PATH,
        help=f"Environment config file path (default: {DEFAULT_ENV_CONFIG_FILE_PATH})",
    )
    token_parser.add_argument(
        "--env",
        dest="env_name",
        help="Use a specific environment from the config file",
    )
    token_parser.add_argument(
        "--token-cache",
        choices=["auto", "keyring", "file", "none"],
        default="auto",
        help="Token cache backend: auto (default), keyring, file, or none",
    )


def run(parsed: argparse.Namespace) -> int:
    try:
        host = parsed.server
        credentials = parsed.credentials

        if parsed.env_name:
            config = load_kognic_env_config(parsed.env_config_file_path)
            if parsed.env_name not in config.environments:
                print(f"Error: Unknown environment: {parsed.env_name}", file=sys.stderr)
                return 1
            ctx = config.environments[parsed.env_name]
            if host is None:
                host = ctx.auth_server
            if credentials is None:
                credentials = ctx.credentials

        auth_host = host or DEFAULT_HOST

        cache = make_cache(parsed.token_cache)
        if cache is not None:
            try:
                client_id, _ = resolve_credentials(credentials)
            except Exception:
                client_id = None

            if client_id:
                cached = cache.load(auth_host, client_id)
                if cached:
                    print(cached["access_token"])
                    return 0

        session = RequestsAuthSession(
            auth=credentials,
            host=auth_host,
        )
        # Access .session to trigger token fetch
        _ = session.session

        # Save the freshly fetched token to the cache
        if cache is not None:
            token = session.token
            if isinstance(token, dict):
                cid = session.oauth_session.client_id
                if cid:
                    cache.save(auth_host, cid, token)

        print(session.access_token)
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error fetching token: {e}", file=sys.stderr)
        return 1
