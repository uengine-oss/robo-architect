"""Cooperative cancellation gate for ingestion (spec 017 / D3).

Every LLM call site, every wireframe-service call (`_render_jsx`), and every
spec-018 bulk-flush call wraps its call in `async with session_call_slot(session):`.
The gate awaits one microtask to give the cancel handler a chance to run, then
checks `session.is_cancelled`. If set, it raises `asyncio.CancelledError` which
propagates up to the workflow runner's outer `except CancelledError` handler
(already present from the existing cancel flow) — that handler emits the final
`suspended` SSE event.

This pattern is *cooperative*: a single in-flight LLM call cannot be aborted
mid-stream (most providers do not support that), so the gate only stops *new*
dispatches. The worst-case suspend latency is therefore bounded by the longest
single in-flight call (typically 30–60 s for an LLM phase, 120 s for
`_render_jsx`).

Why a context manager and not a plain `if session.is_cancelled: raise`:
- The `async with ...:` form makes every call site visually consistent
  ("anywhere I see this, suspend is handled correctly").
- `asyncio.sleep(0)` inside `__aenter__` lets the event loop service the cancel
  task before the check — important when the cancel arrives between LLM-call
  scheduling and dispatch.
- A future enhancement (rate limiting, audit-log of every gated call) can be
  added inside the context manager without touching every call site.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncIterator

from api.platform.observability.smart_logger import SmartLogger

if TYPE_CHECKING:
    from api.features.ingestion.ingestion_sessions import IngestionSession


@asynccontextmanager
async def session_call_slot(session: "IngestionSession | None") -> AsyncIterator[None]:
    """Cooperative cancel point.

    - Awaits a microtask so the cancel handler has a chance to run.
    - If `session.is_cancelled`, transitions `suspend_state` to "suspended"
      (or leaves it at "suspending" — the workflow's CancelledError handler
      flips it to "suspended" once it actually unwinds) and raises
      `asyncio.CancelledError`.
    - Otherwise yields control to the wrapped call.

    A `None` session is allowed for safety (e.g. ad-hoc LLM calls outside
    the workflow); the gate is a no-op in that case.
    """
    if session is None:
        yield
        return

    # Give the cancel handler a turn (e.g. /api/ingest/{id}/cancel handler
    # may be on the same loop and just set is_cancelled).
    await asyncio.sleep(0)

    if getattr(session, "is_cancelled", False):
        SmartLogger.log(
            "INFO",
            f"ingestion.suspend.gate fired phase={getattr(session, 'current_phase', '')}",
            category="ingestion.suspend.gate",
            params={
                "session_id": getattr(session, "id", None),
                "phase": getattr(session, "current_phase", ""),
            },
        )
        raise asyncio.CancelledError("ingestion suspended")

    yield
