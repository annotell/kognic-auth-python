from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from kognic.auth.config import DEFAULT_CONFIG_PATH, load_config, resolve_context
from kognic.auth.requests.auth_session import RequestsAuthSession

COMMAND = "call"


def register_parser(subparsers: argparse._SubParsersAction) -> None:
    call_parser = subparsers.add_parser(
        COMMAND,
        help="Make an authenticated HTTP request to a Kognic API",
    )
    call_parser.add_argument("url", metavar="URL", help="Full URL to call")
    call_parser.add_argument(
        "-X",
        "--request",
        dest="method",
        default="GET",
        metavar="METHOD",
        help="HTTP method (default: GET)",
    )
    call_parser.add_argument("-d", "--data", help="Request body (JSON string)")
    call_parser.add_argument(
        "-H",
        "--header",
        action="append",
        dest="headers",
        metavar="HDR",
        help="Header in 'Key: Value' format (repeatable)",
    )
    call_parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"Config file path (default: {DEFAULT_CONFIG_PATH})",
    )
    call_parser.add_argument(
        "--context", dest="context_name", help="Force a specific context (skip URL-based matching)"
    )


def _parse_headers(raw: list[str] | None) -> dict[str, str] | None:
    if not raw:
        return None
    headers: dict[str, str] = {}
    for h in raw:
        if ": " not in h:
            raise ValueError(f"Invalid header format '{h}'. Expected 'Key: Value'.")
        key, value = h.split(": ", 1)
        headers[key] = value
    return headers


def _parse_body(raw: str | None, headers: dict[str, str]) -> Any:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON data: {e}") from e
    headers.setdefault("Content-Type", "application/json")
    return data


def _print_response(response: Any) -> None:
    content_type = response.headers.get("Content-Type", "")
    if "application/json" in content_type:
        try:
            print(json.dumps(response.json(), indent=2))
        except (json.JSONDecodeError, ValueError):
            print(response.text)
    else:
        print(response.text)


def run(parsed: argparse.Namespace) -> int:
    try:
        config = load_config(parsed.config)
        context = resolve_context(config, parsed.url, parsed.context_name)

        session = RequestsAuthSession(
            auth=context.credentials,
            host=context.auth_server,
        )

        headers = _parse_headers(parsed.headers) or {}
        data = _parse_body(parsed.data, headers)

        response = session.session.request(
            method=parsed.method.upper(),
            url=parsed.url,
            json=data if data is not None else None,
            headers=headers if headers else None,
        )

        _print_response(response)
        return 0 if response.ok else 1

    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
