"""In-flight retry deduplication for per-UI Figma sync retries (spec 020).

Two collaborators (or the same collaborator across modal + Inspector badge) may
click 다시 시도 on the same UI within milliseconds. Without dedupe both clicks
would fire `CREATE_FRAME_IN_PAGE` to the Figma plugin and rely on the plugin's
idempotency. This module collapses concurrent retries into a single dispatch
whose outcome is shared via `asyncio.Future`.

Single-process scope is sufficient because the Figma plugin transport lives in
the FastAPI process; the deployment shape is single-worker (research D3).

Thread-safety: assumes asyncio single-threaded event loop. No locks needed.
"""

from __future__ import annotations

import asyncio
from typing import Any

from api.platform.observability.smart_logger import SmartLogger


class RetryDedupeStore:
    """Per-process map of in-flight retries keyed by UI id."""

    def __init__(self) -> None:
        self._inflight: dict[str, asyncio.Future[dict[str, Any]]] = {}

    def claim_or_join(self, ui_id: str) -> tuple[bool, asyncio.Future[dict[str, Any]]]:
        """Reserve `ui_id` for retry. Returns `(True, fresh_future)` for the
        first caller; `(False, existing_future)` for subsequent callers (which
        must `await` the future for the shared outcome).
        """
        existing = self._inflight.get(ui_id)
        if existing is not None and not existing.done():
            SmartLogger.log(
                "INFO",
                f"figma_binding.retry deduped: {ui_id}",
                category="figma_binding.retry.deduped",
                params={"uiId": ui_id},
            )
            return False, existing
        loop = asyncio.get_event_loop()
        fut: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._inflight[ui_id] = fut
        return True, fut

    def complete(self, ui_id: str, result: dict[str, Any]) -> None:
        fut = self._inflight.pop(ui_id, None)
        if fut is not None and not fut.done():
            fut.set_result(result)

    def fail(self, ui_id: str, exc: BaseException) -> None:
        fut = self._inflight.pop(ui_id, None)
        if fut is not None and not fut.done():
            fut.set_exception(exc)

    def is_inflight(self, ui_id: str) -> bool:
        fut = self._inflight.get(ui_id)
        return fut is not None and not fut.done()

    def inflight_set(self) -> set[str]:
        return {uid for uid, fut in self._inflight.items() if not fut.done()}


# Process-wide singleton.
_store: RetryDedupeStore | None = None


def get_store() -> RetryDedupeStore:
    global _store
    if _store is None:
        _store = RetryDedupeStore()
    return _store
