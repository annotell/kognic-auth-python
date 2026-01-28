import argparse
import sys

from kognic.auth import DEFAULT_HOST


def create_parser():
    parser = argparse.ArgumentParser(
        prog="kognic-auth",
        description="Kognic authentication CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # get-access-token subcommand
    token_parser = subparsers.add_parser(
        "get-access-token",
        help="Generate an access token for Kognic API authentication",
    )
    token_parser.add_argument(
        "--server",
        default=DEFAULT_HOST,
        help=f"Authentication server URL (default: {DEFAULT_HOST})",
    )
    token_parser.add_argument(
        "--credentials",
        metavar="FILE",
        help="Path to JSON credentials file. If not provided, credentials are read from environment variables.",
    )

    return parser


def get_access_token(parsed):
    try:
        from kognic.auth.requests.auth_session import RequestsAuthSession
    except ImportError:
        print("Error: requests library is required. Install with: pip install kognic-auth[requests]", file=sys.stderr)
        return 1

    try:
        session = RequestsAuthSession(
            auth=parsed.credentials,
            host=parsed.server,
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


def main(args=None):
    parser = create_parser()
    parsed = parser.parse_args(args)

    if parsed.command == "get-access-token":
        return get_access_token(parsed)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
