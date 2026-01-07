"""
Event Storming Node Runtime (LLM + audit logging)

Business capability: provide consistent LLM runtime + audit toggles for the Event Storming agent nodes.
Kept local to the `event_storming` feature implementation (not a global "service" layer).
"""

from __future__ import annotations

from typing import Any

from api.platform.llm import get_llm as _platform_get_llm


def dump_model(obj: Any) -> Any:
    """Safely dump a pydantic model (v1/v2) for logging."""
    try:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
    except Exception:
        pass
    try:
        if hasattr(obj, "dict"):
            return obj.dict()
    except Exception:
        pass
    return {"__type__": type(obj).__name__, "__repr__": repr(obj)[:1000]}


def get_llm():
    """Get the configured LLM instance."""
    return _platform_get_llm()


