from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from typing import Any

from kognic.auth.cli import _configure_logging
from kognic.auth.env_config import DEFAULT_ENV_CONFIG_FILE_PATH, load_kognic_env_config, resolve_environment
from kognic.auth.internal.token_cache import make_cache
from kognic.auth.requests.base_client import create_session, make_token_provider

METHODS = ["get", "post", "put", "patch", "delete", "head", "options"]


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kog",
        description="Make authenticated HTTP requests to Kognic APIs",
    )
    parser.add_argument("method", metavar="METHOD", choices=METHODS, help=f"HTTP method ({', '.join(METHODS)})")
    parser.add_argument("url", metavar="URL", help="Full URL to call")
    parser.add_argument("-d", "--data", help="Request body (JSON string)")
    parser.add_argument(
        "-H",
        "--header",
        action="append",
        dest="headers",
        metavar="HEADER",
        help="Header in 'Key: Value' format (repeatable)",
    )
    parser.add_argument(
        "--env-config-file-path",
        default=DEFAULT_ENV_CONFIG_FILE_PATH,
        help=f"Environment config file path (default: {DEFAULT_ENV_CONFIG_FILE_PATH})",
    )
    parser.add_argument("--env", dest="env_name", help="Force a specific environment (skip URL-based matching)")
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=["json", "jsonl", "csv", "tsv", "table"],
        default="json",
        help="Output format: json (default), jsonl (one JSON object per line), csv, tsv, table (markdown)",
    )
    parser.add_argument(
        "--token-cache",
        choices=["auto", "keyring", "file", "none"],
        default="auto",
        help="Token cache backend: auto (default), keyring, file, or none. "
        "Auto will use keyring if available, otherwise file.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", default=False, help="Enable debug logging")
    return parser


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


def _extract_items(body: Any) -> list[Any] | None:
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        values = list(body.values())
        if len(values) == 1 and isinstance(values[0], list):
            return values[0]
    return None


def _stringify_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


def _print_delimited(items: list[Any], *, delimiter: str = ",") -> None:
    if not items:
        return
    fieldnames = _collect_fieldnames(items)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, delimiter=delimiter)
    writer.writeheader()
    for item in items:
        if isinstance(item, dict):
            writer.writerow({k: _stringify_value(v) for k, v in item.items()})
        else:
            writer.writerow({"value": _stringify_value(item)})
    print(buf.getvalue(), end="")


def _collect_fieldnames(items: list[Any]) -> list[str]:
    fieldnames: list[str] = []
    for item in items:
        if isinstance(item, dict):
            for key in item:
                if key not in fieldnames:
                    fieldnames.append(key)
    return fieldnames


def _print_table(items: list[Any]) -> None:
    if not items:
        return
    fieldnames = _collect_fieldnames(items)
    col_widths = [len(f) for f in fieldnames]
    rows: list[list[str]] = []
    for item in items:
        row = [
            _stringify_value(item.get(f, "")) if isinstance(item, dict) else _stringify_value(item) for f in fieldnames
        ]
        rows.append(row)
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))
    header = "| " + " | ".join(f.ljust(col_widths[i]) for i, f in enumerate(fieldnames)) + " |"
    separator = "|-" + "-|-".join("-" * w for w in col_widths) + "-|"
    print(header)
    print(separator)
    for row in rows:
        print("| " + " | ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(row)) + " |")


def _print_response(response: Any, *, output_format: str = "json") -> None:
    content_type = response.headers.get("Content-Type", "")
    if "application/json" in content_type:
        try:
            body = response.json()
        except (json.JSONDecodeError, ValueError):
            print(response.text)
            return
        if output_format in ("jsonl", "csv", "tsv", "table"):
            items = _extract_items(body)
            if items is not None:
                if output_format in ("csv", "tsv"):
                    _print_delimited(items, delimiter="\t" if output_format == "tsv" else ",")
                elif output_format == "table":
                    _print_table(items)
                else:
                    for item in items:
                        print(json.dumps(item))
                return
        print(json.dumps(body, indent=2))
    else:
        print(response.text)


def _create_authenticated_session(*, auth, auth_host, cache_mode: str = "auto"):
    provider = make_token_provider(auth=auth, auth_host=auth_host, token_cache=make_cache(cache_mode))
    return create_session(token_provider=provider)


def run(parsed: argparse.Namespace) -> int:
    try:
        headers = _parse_headers(parsed.headers) or {}
        data = _parse_body(parsed.data, headers)

        config = load_kognic_env_config(parsed.env_config_file_path)
        env = resolve_environment(config, parsed.url, parsed.env_name)

        session = _create_authenticated_session(
            auth=env.credentials,
            auth_host=env.auth_server,
            cache_mode=parsed.token_cache,
        )

        response = session.request(
            method=parsed.method.upper(),
            url=parsed.url,
            json=data if data is not None else None,
            headers=headers if headers else None,
        )

        _print_response(response, output_format=parsed.output_format)
        return 0 if response.ok else 1

    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def main(args: list[str] | None = None) -> None:
    parser = _create_parser()
    parsed = parser.parse_args(args)
    _configure_logging(verbose=parsed.verbose)
    sys.exit(run(parsed))
