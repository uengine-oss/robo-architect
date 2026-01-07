from __future__ import annotations

import contextvars
import datetime as _dt
import hashlib
import json
import time
import uuid
from enum import Enum
from typing import Any, Mapping, Sequence

try:
    # FastAPI uses Starlette's Request.
    from starlette.requests import Request
except Exception:  # pragma: no cover
    Request = Any  # type: ignore

try:  # optional
    from pydantic import BaseModel
except Exception:  # pragma: no cover
    BaseModel = None  # type: ignore


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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def summarize_for_log(
    value: Any,
    *,
    max_depth: int = 5,
    max_str: int = 800,
    # NOTE: We default to large limits for reproducibility.
    # SmartLogger will offload large params into `logs/details/*.json` automatically.
    max_list: int = 5000,
    max_dict_items: int = 5000,
) -> Any:
    """
    Convert values into JSON-serializable structures for logging.

    NOTE:
    - We intentionally preserve full strings by default (no truncation/sha-only summaries),
      because SmartLogger can offload large params to `logs/details/*.json`.
    - We still keep a max_depth guard to avoid infinite recursion / cycles.
    """

    # Track object identity to avoid infinite recursion on cyclic structures.
    seen: set[int] = set()

    def _to_jsonable(v: Any, depth: int) -> Any:
        if depth <= 0:
            return {"__truncated__": True, "__type__": type(v).__name__}

        if v is None:
            return None

        if isinstance(v, (int, float, bool)):
            return v

        # Preserve full strings (no truncation).
        if isinstance(v, str):
            return v

        # Avoid logging raw bytes; keep metadata only.
        if isinstance(v, (bytes, bytearray)):
            try:
                h = sha256_bytes(bytes(v))
            except Exception:
                h = None
            return {"__type__": type(v).__name__, "__len__": len(v), "__sha256__": h}

        # Datetime/date/time objects
        if isinstance(v, (_dt.datetime, _dt.date, _dt.time)):
            try:
                return v.isoformat()
            except Exception:
                return str(v)

        # Enums
        if isinstance(v, Enum):
            return v.value

        # Pydantic models
        if BaseModel is not None and isinstance(v, BaseModel):  # type: ignore[arg-type]
            try:
                return _to_jsonable(v.model_dump(mode="json"), depth - 1)
            except Exception:
                try:
                    return _to_jsonable(v.model_dump(), depth - 1)
                except Exception:
                    return {"__type__": type(v).__name__, "__repr__": repr(v)}

        # Prevent cycles
        vid = id(v)
        if vid in seen:
            return {"__cycle__": True, "__type__": type(v).__name__}
        seen.add(vid)

        # Mappings
        if isinstance(v, Mapping):
            items = list(v.items())
            out: dict[str, Any] = {}
            # Keep legacy limits as a safety valve, but preserve strings within.
            for k, vv in items[:max_dict_items]:
                out[str(k)] = _to_jsonable(vv, depth - 1)
            if len(items) > max_dict_items:
                out["__truncated_items__"] = len(items) - max_dict_items
            return out

        # Sequences (lists/tuples/etc)
        if _is_sequence(v):
            seq = list(v)
            out_list = [_to_jsonable(x, depth - 1) for x in seq[:max_list]]
            if len(seq) > max_list:
                out_list.append({"__truncated_items__": len(seq) - max_list})
            return out_list

        # Sets
        if isinstance(v, set):
            out_list = [_to_jsonable(x, depth - 1) for x in list(v)[:max_list]]
            if len(v) > max_list:
                out_list.append({"__truncated_items__": len(v) - max_list})
            return out_list

        # Last resort: try JSON serialization, else repr
        try:
            json.dumps(v)
            return v
        except Exception:
            return {"__type__": type(v).__name__, "__repr__": repr(v)}

    # Keep signature args for backwards compatibility even though strings are not truncated now.
    _ = max_str
    return _to_jsonable(value, max_depth)


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


