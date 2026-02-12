from __future__ import annotations

import argparse
import logging
import sys
from types import ModuleType

from kognic.auth.cli import call, get_access_token

_SUBCOMMANDS: list[ModuleType] = [get_access_token, call]


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kognic-auth",
        description="Kognic authentication CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    for subcommand in _SUBCOMMANDS:
        subcommand.register_parser(subparsers)

    return parser


def _configure_logging() -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logging.getLogger("kognic.auth").addHandler(handler)
    logging.getLogger("kognic.auth").setLevel(logging.WARNING)


def main(args: list[str] | None = None) -> int:
    _configure_logging()
    parser = create_parser()
    parsed = parser.parse_args(args)

    for subcommand in _SUBCOMMANDS:
        if parsed.command == subcommand.COMMAND:
            return subcommand.run(parsed)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
