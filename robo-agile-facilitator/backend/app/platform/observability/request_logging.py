from __future__ import annotations

import contextvars
import hashlib
import json
import time
import uuid
from typing import Any, Mapping, Sequence

try:
    # FastAPI uses Starlette's Request.
    from starlette.requests import Request
except Exception:  # pragma: no cover
    Request = Any  # type: ignore


_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


def new_request_id(prefix: str = "req") -> str:
    """Create a short, human-friendly request id for log correlation."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def set_request_id(request_id: str | None) -> None:
    _request_id_var.set(request_id)


def get_request_id() -> str | None:
    return _request_id_var.get()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def summarize_for_log(
    value: Any,
    *,
    max_depth: int = 5,
    max_str: int = 800,
    max_list: int = 80,
    max_dict_items: int = 200,
) -> Any:
    """
    Summarize potentially-large payloads for logging while keeping reproduction context:
    - Long strings: keep len, sha256, preview
    - Large lists/dicts: truncate with counts
    """
    if max_depth <= 0:
        return {"__truncated__": True, "__type__": type(value).__name__}

    if value is None:
        return None

    if isinstance(value, (int, float, bool)):
        return value

    if isinstance(value, str):
        if len(value) <= max_str:
            return value
        return {
            "__type__": "str",
            "__len__": len(value),
            "__sha256__": sha256_text(value),
            "__preview__": value[: max_str // 2],
            "__suffix__": value[- max_str // 4 :],
        }

    if isinstance(value, (bytes, bytearray)):
        return {"__type__": type(value).__name__, "__len__": len(value)}

    if isinstance(value, Mapping):
        items = list(value.items())
        out: dict[str, Any] = {}
        for k, v in items[:max_dict_items]:
            out[str(k)] = summarize_for_log(
                v,
                max_depth=max_depth - 1,
                max_str=max_str,
                max_list=max_list,
                max_dict_items=max_dict_items,
            )
        if len(items) > max_dict_items:
            out["__truncated_items__"] = len(items) - max_dict_items
        return out

    if _is_sequence(value):
        seq = list(value)
        out_list = [
            summarize_for_log(
                x,
                max_depth=max_depth - 1,
                max_str=max_str,
                max_list=max_list,
                max_dict_items=max_dict_items,
            )
            for x in seq[:max_list]
        ]
        if len(seq) > max_list:
            out_list.append({"__truncated_items__": len(seq) - max_list})
        return out_list

    # Last resort: try JSON serialization, else repr
    try:
        json.dumps(value)
        return value
    except Exception:
        return {"__type__": type(value).__name__, "__repr__": repr(value)[:max_str]}


def http_context(request: Request) -> dict[str, Any]:
    """
    Common request context for all API logs.
    NOTE: Do not include raw headers by default to avoid leaking secrets.
    """
    rid = get_request_id()
    client_host = getattr(getattr(request, "client", None), "host", None)
    return {
        "request_id": rid,
        "http": {
            "method": getattr(request, "method", None),
            "path": str(getattr(getattr(request, "url", None), "path", None)),
            "query": dict(getattr(request, "query_params", {}) or {}),
            "path_params": dict(getattr(request, "path_params", {}) or {}),
            "client_host": client_host,
        },
    }


class RequestTimer:
    """Small helper for measuring durations in middleware."""

    def __init__(self) -> None:
        self._t0 = time.perf_counter()

    def ms(self) -> int:
        return int((time.perf_counter() - self._t0) * 1000)


