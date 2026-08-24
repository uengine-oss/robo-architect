#!/usr/bin/env python3
"""Extract an Avro record as a robo-sync Event structure."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _type_name(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " | ".join(_type_name(item) for item in value)
    if isinstance(value, dict):
        logical = value.get("logicalType")
        base = value.get("type", "object")
        return f"{base}({logical})" if logical else _type_name(base)
    return str(value)


def extract(path: Path) -> dict:
    schema = json.loads(path.read_text(encoding="utf-8"))
    if schema.get("type") != "record" or not schema.get("name"):
        raise ValueError("Avro top-level schema must be a named record")
    return {
        "kind": "Event",
        "name": schema["name"],
        "namespace": schema.get("namespace"),
        "fields": [
            {
                "name": field["name"],
                "type": _type_name(field.get("type")),
                "required": not (
                    isinstance(field.get("type"), list) and "null" in field["type"]
                ),
                "hasDefault": "default" in field,
            }
            for field in schema.get("fields", [])
        ],
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: avro_extract.py <path-to-avsc-file>", file=sys.stderr)
        return 2
    try:
        print(json.dumps(extract(Path(argv[1])), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"avro_extract.py: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
