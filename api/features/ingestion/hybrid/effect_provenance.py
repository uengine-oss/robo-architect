"""Normalize Analyzer WRITES operations for Architect consumers."""
from __future__ import annotations

from typing import Iterable


_EXACT_OPS = {"READ", "INSERT", "UPDATE", "DELETE", "MERGE", "TRUNCATE"}
_WRITE_ACCESS = {"WRITE", "READ_WRITE"}
_SOURCES = {"SCANNER", "LLM_INFERRED", "UNRESOLVED"}


def normalize_write_effect(effect: object) -> dict[str, str] | None:
    """Normalize one direct table-write fact and discard reads."""
    if not isinstance(effect, dict):
        return None
    table = effect.get("table")
    if not isinstance(table, str) or not table.strip():
        return None
    table = table.strip()

    raw_op = effect.get("op")
    op = raw_op.strip().upper() if isinstance(raw_op, str) else "UNKNOWN"
    if op not in _EXACT_OPS:
        op = "UNKNOWN"

    raw_access = effect.get("access")
    access = raw_access.strip().upper() if isinstance(raw_access, str) else ""
    if not access:
        access = "READ" if op == "READ" else "WRITE"
    if access not in {"READ", *_WRITE_ACCESS} or access == "READ":
        return None

    raw_source = effect.get("op_source")
    source = raw_source.strip().upper() if isinstance(raw_source, str) else "UNRESOLVED"
    if source not in _SOURCES:
        source = "UNRESOLVED"
    if source == "UNRESOLVED":
        op = "UNKNOWN"
    elif op == "UNKNOWN" and source in {"SCANNER", "LLM_INFERRED"}:
        source = "UNRESOLVED"

    return {
        "table": table,
        "access": access,
        "op": op,
        "op_source": source,
    }


def merge_write_effects(*sources: Iterable[object]) -> list[dict[str, str]]:
    """Stable union of write effects without upgrading evidence authority."""
    seen: set[tuple[str, str, str, str]] = set()
    out: list[dict[str, str]] = []
    for source in sources:
        for raw in source or []:
            effect = normalize_write_effect(raw)
            if effect is None:
                continue
            key = (
                effect["table"],
                effect["access"],
                effect["op"],
                effect["op_source"],
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(effect)
    return out


def render_write_effect(effect: object) -> str:
    """Render authority without converting UNKNOWN into an event verb."""
    normalized = normalize_write_effect(effect)
    if normalized is None:
        return ""
    table = normalized["table"]
    op = normalized["op"]
    source = normalized["op_source"]
    if op == "UNKNOWN":
        return f"WRITE `{table}` [op unresolved]"
    return f"{op} `{table}` [{source}]"
