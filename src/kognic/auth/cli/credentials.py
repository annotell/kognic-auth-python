from __future__ import annotations

import argparse
import sys

from kognic.auth.credentials_parser import parse_credentials
from kognic.auth.internal.credential_store import DEFAULT_PROFILE, clear_credentials, save_credentials

COMMAND = "credentials"


def register_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        COMMAND,
        help="Manage stored credentials in the system keyring",
    )
    subs = parser.add_subparsers(dest="credentials_action")

    load_p = subs.add_parser("load", help="Load credentials from a JSON file into the system keyring")
    load_p.add_argument("file", metavar="FILE", help="Path to credentials JSON file")
    load_p.add_argument(
        "--env",
        default=DEFAULT_PROFILE,
        metavar="ENV",
        help=f"Keyring profile name to store credentials under (default: {DEFAULT_PROFILE}). "
        "Use the environment name from environments.json to link credentials to that environment "
        "(e.g. --env production → use 'keyring://production' in your config).",
    )

    clear_p = subs.add_parser("clear", help="Remove stored credentials from the system keyring")
    clear_p.add_argument(
        "--env",
        default=DEFAULT_PROFILE,
        metavar="ENV",
        help=f"Keyring profile name to clear (default: {DEFAULT_PROFILE}).",
    )

    return parser


def run(parsed: argparse.Namespace) -> int:
    if parsed.credentials_action == "load":
        return _run_load(parsed)
    if parsed.credentials_action == "clear":
        return _run_clear(parsed)
    return 0


def _run_load(parsed: argparse.Namespace) -> int:
    try:
        creds = parse_credentials(parsed.file)
        save_credentials(creds, parsed.env)
        print(f"Credentials for client_id={creds.client_id!r} stored in keyring (profile={parsed.env!r})")
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except (KeyError, ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _run_clear(parsed: argparse.Namespace) -> int:
    try:
        clear_credentials(parsed.env)
        print(f"Credentials cleared from keyring (profile={parsed.env!r})")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
