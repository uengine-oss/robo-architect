"""robo-cluster MCP 호출을 proposal provenance로 전달하는 typed stream marker 계약."""
from __future__ import annotations

import json

MARKER = "LEGACY_TOOL_EVENT::"
SEARCH_TOOL = "cluster_retrieve"
DETAIL_TOOL = "node_detail"


def tool_kind(tool_name: str) -> str | None:
    if tool_name.endswith(SEARCH_TOOL):
        return "search"
    if tool_name.endswith(DETAIL_TOOL):
        return "detail"
    return None


def encode_event(*, phase: str, kind: str, tool_use_id: str, tool_name: str,
                 tool_input: dict | None = None, content: str | None = None) -> str:
    event = {
        "phase": phase,
        "kind": kind,
        "toolUseId": tool_use_id,
        "toolName": tool_name,
    }
    if tool_input is not None:
        event["input"] = tool_input
    if content is not None:
        event["content"] = content
    return MARKER + json.dumps(event, ensure_ascii=False, default=str, separators=(",", ":"))


def is_event(line: str) -> bool:
    return line.startswith(MARKER)


def decode_event(line: str) -> dict:
    if not is_event(line):
        raise ValueError("not a legacy tool event")
    event = json.loads(line[len(MARKER):])
    if event.get("phase") not in {"request", "result"}:
        raise ValueError("invalid legacy tool event phase")
    if event.get("kind") not in {"search", "detail"}:
        raise ValueError("invalid legacy tool event kind")
    if not event.get("toolUseId"):
        raise ValueError("legacy tool event missing toolUseId")
    return event
