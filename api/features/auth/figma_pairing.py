"""Short-lived, single-use pairing codes for the local Figma plugin."""

from __future__ import annotations

import secrets
import threading
import time

from api.features.auth.tokens import issue_plugin_token

_LOCK = threading.Lock()
_PENDING: dict[str, tuple[float, dict, str]] = {}
_CODE_TTL = 5 * 60


def create_code(claims: dict, graph: str) -> tuple[str, int]:
    code = secrets.token_urlsafe(9)
    with _LOCK:
        now = time.monotonic()
        for stale, (expires, _, _) in list(_PENDING.items()):
            if expires <= now:
                del _PENDING[stale]
        _PENDING[code] = (now + _CODE_TTL, claims, graph)
    return code, _CODE_TTL


def exchange_code(code: str) -> tuple[str, str] | None:
    with _LOCK:
        entry = _PENDING.pop(code, None)
    if not entry or entry[0] <= time.monotonic():
        return None
    _, claims, graph = entry
    return issue_plugin_token(claims, graph), graph
