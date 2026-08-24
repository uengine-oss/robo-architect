#!/usr/bin/env python3
"""Dependency-free Java structure extractor for robo-sync.

This is a deliberately conservative source extractor, not a Java compiler. It
tracks brace depth after masking comments and string bodies, then reports the
top-level type's persisted fields and methods. Event names passed as string
literals to ``publish`` are also reported so proposal validation can compare
Command/Event intent without executing the service.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


TYPE_RE = re.compile(r"\b(class|record|interface|enum)\s+(\w+)")
FIELD_RE = re.compile(
    r"^(?:public|protected|private)?\s*(?:static\s+)?(?:final\s+)?"
    r"([\w.$<>?,\[\]\s]+?)\s+(\w+)\s*(?:=[^;]*)?;$"
)
METHOD_RE = re.compile(
    r"^(?:public|protected|private)?\s*(?:static\s+)?(?:final\s+)?"
    r"(?:<[^>]+>\s*)?([\w.$<>?,\[\]\s]+?)\s+(\w+)\s*\((.*)\)"
    r"\s*(?:throws\s+[^\{]+)?\s*\{?$"
)


def _mask_comments(src: str) -> str:
    return re.sub(r"/\*.*?\*/|//[^\n]*", lambda m: "\n" * m.group(0).count("\n"), src,
                  flags=re.S)


def _split_params(raw: str) -> list[str]:
    parts: list[str] = []
    start = depth = 0
    for index, char in enumerate(raw):
        if char in "<([":
            depth += 1
        elif char in ">)]":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            parts.append(raw[start:index])
            start = index + 1
    if raw[start:].strip():
        parts.append(raw[start:])
    return parts


def _params(raw: str) -> list[dict]:
    result = []
    for part in _split_params(raw):
        clean = re.sub(r"@\w+(?:\([^)]*\))?\s*", "", part).strip()
        clean = re.sub(r"\bfinal\s+", "", clean)
        match = re.match(r"(.+?)\s+(\w+)$", clean)
        if match:
            result.append({"name": match.group(2), "type": " ".join(match.group(1).split())})
    return result


def _without_annotations(value: str) -> str:
    """Remove declaration annotations accumulated before a field/method."""
    previous = None
    while previous != value:
        previous = value
        value = re.sub(r"^\s*@\w+(?:\.\w+)*(?:\([^)]*\))?\s*", "", value)
    return value.strip()


def extract(path: Path) -> dict:
    original = path.read_text(encoding="utf-8", errors="replace")
    src = _mask_comments(original)
    type_match = TYPE_RE.search(src)
    if not type_match:
        raise ValueError("Java class/record/interface/enum declaration not found")
    declaration, name = type_match.groups()
    body_start = src.find("{", type_match.end())
    if body_start < 0:
        raise ValueError("Java type body not found")

    lower = str(path).lower().replace("\\", "/")
    if "/domain/" in lower:
        kind = "Aggregate"
    elif "/application/" in lower or "/usecase" in lower:
        kind = "Command"
    elif "/event" in lower or "/kafka/" in lower:
        kind = "Event"
    elif "/readmodel" in lower or "/projection" in lower:
        kind = "ReadModel"
    else:
        kind = "JavaType"

    fields: list[dict] = []
    methods: list[dict] = []
    depth = 1
    statement = ""
    index = body_start + 1
    while index < len(src) and depth > 0:
        char = src[index]
        if char == "{":
            if depth == 1:
                candidate = _without_annotations(" ".join(statement.split()))
                match = METHOD_RE.match(candidate + " {")
                if match and match.group(2) != name:
                    methods.append({
                        "name": match.group(2),
                        "returnType": " ".join(match.group(1).split()),
                        "parameters": _params(match.group(3)),
                    })
                statement = ""
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 1:
                statement = ""
        elif depth == 1:
            statement += char
            if char == ";":
                candidate = _without_annotations(" ".join(statement.split()))
                match = FIELD_RE.match(candidate)
                if match and "(" not in candidate:
                    fields.append({"name": match.group(2), "type": " ".join(match.group(1).split())})
                statement = ""
        index += 1

    # Records declare their state in the header rather than the body.
    if declaration == "record":
        header = src[type_match.end():body_start]
        record_match = re.search(r"\((.*)\)", header, flags=re.S)
        if record_match:
            fields = _params(record_match.group(1))

    emitted = sorted(set(re.findall(
        r"\.publish\s*\([^;]*?\"([A-Z][A-Za-z0-9]+)\"",
        src, flags=re.S,
    )))
    enum_values = []
    for enum_match in re.finditer(r"\benum\s+(\w+)\s*\{([^}]+)\}", src, flags=re.S):
        values = re.split(r",", enum_match.group(2).split(";")[0])
        enum_values.append({
            "name": enum_match.group(1),
            "values": [re.sub(r"\(.*", "", value).strip() for value in values if value.strip()],
        })

    return {
        "kind": kind,
        "name": name,
        "declaration": declaration,
        "fields": fields,
        "methods": methods,
        "emittedEvents": emitted,
        "enums": enum_values,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: java_extract.py <path-to-java-file>", file=sys.stderr)
        return 2
    try:
        print(json.dumps(extract(Path(argv[1])), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(f"java_extract.py: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
