from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from typing import Any

from kognic.auth.env_config import DEFAULT_CONFIG_PATH, load_kognic_env_config, resolve_environment
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
        "--env-config-file-path",
        default=DEFAULT_CONFIG_PATH,
        help=f"Environment config file path (default: {DEFAULT_CONFIG_PATH})",
    )
    call_parser.add_argument("--env", dest="env_name", help="Force a specific environment (skip URL-based matching)")
    call_parser.add_argument(
        "--format",
        dest="output_format",
        choices=["json", "jsonl", "csv", "tsv", "table"],
        default="json",
        help="Output format: json (default), jsonl (one JSON object per line), csv, tsv, table (markdown)",
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


def run(parsed: argparse.Namespace) -> int:
    try:
        config = load_kognic_env_config(parsed.env_config_file_path)
        env = resolve_environment(config, parsed.url, parsed.env_name)

        session = RequestsAuthSession(
            auth=env.credentials,
            host=env.auth_server,
        )

        headers = _parse_headers(parsed.headers) or {}
        data = _parse_body(parsed.data, headers)

        response = session.session.request(
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
