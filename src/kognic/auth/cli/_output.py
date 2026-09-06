from __future__ import annotations

import csv
import io
import json
from typing import Any, cast


def _extract_items(body: Any) -> list[Any] | None:
    # isinstance() narrows Any to list[Unknown] / dict[Unknown, Unknown]; the contents
    # are arbitrary decoded JSON, so restate that as Any.
    if isinstance(body, list):
        return cast("list[Any]", body)
    if isinstance(body, dict):
        values = list(cast("dict[str, Any]", body).values())
        if len(values) == 1 and isinstance(values[0], list):
            return cast("list[Any]", values[0])
    return None


def _stringify_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


def _collect_fieldnames(items: list[Any]) -> list[str]:
    fieldnames: list[str] = []
    for item in items:
        if isinstance(item, dict):
            for key in cast("dict[str, Any]", item):
                if key not in fieldnames:
                    fieldnames.append(key)
    return fieldnames


def _print_delimited(items: list[Any], *, delimiter: str = ",") -> None:
    if not items:
        return
    fieldnames = _collect_fieldnames(items)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, delimiter=delimiter)
    writer.writeheader()
    for item in items:
        if isinstance(item, dict):
            writer.writerow({str(k): _stringify_value(v) for k, v in cast("dict[str, Any]", item).items()})
        else:
            writer.writerow({"value": _stringify_value(item)})
    print(buf.getvalue(), end="")


def _print_table(items: list[Any]) -> None:
    if not items:
        return
    fieldnames = _collect_fieldnames(items)
    col_widths = [len(f) for f in fieldnames]
    rows: list[list[str]] = []
    for item in items:
        row = [
            _stringify_value(cast("dict[str, Any]", item).get(f, ""))
            if isinstance(item, dict)
            else _stringify_value(item)
            for f in fieldnames
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


def print_response(response: Any, *, output_format: str = "json") -> None:
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
