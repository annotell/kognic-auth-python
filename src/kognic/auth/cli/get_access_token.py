from __future__ import annotations

import argparse
import sys

from kognic.auth import DEFAULT_HOST
from kognic.auth.config import DEFAULT_CONFIG_PATH, load_config
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
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"Config file path (default: {DEFAULT_CONFIG_PATH})",
    )
    token_parser.add_argument(
        "--context",
        dest="context_name",
        help="Use a specific context from the config file",
    )


def run(parsed: argparse.Namespace) -> int:
    try:
        host = parsed.server
        credentials = parsed.credentials

        if parsed.context_name:
            config = load_config(parsed.config)
            if parsed.context_name not in config.contexts:
                print(f"Error: Unknown context: {parsed.context_name}", file=sys.stderr)
                return 1
            ctx = config.contexts[parsed.context_name]
            if host is None:
                host = ctx.auth_server
            if credentials is None:
                credentials = ctx.credentials

        session = RequestsAuthSession(
            auth=credentials,
            host=host or DEFAULT_HOST,
        )
        # Access .session to trigger token fetch
        _ = session.session
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
