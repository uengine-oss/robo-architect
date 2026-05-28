"""Identity-propagation middleware (spec 032 T010).

Reads `X-User-Name` (UTF-8 percent-encoded) and `X-User-Email` headers,
attaches `Actor` to `request.state.actor`. Missing or empty headers fall
back to ``unknown@<hostname>`` — the middleware NEVER 401s.

Trust model: local-loopback only. Anyone with shell access on the host
can curl with arbitrary identity headers — matches the desktop app's
"git user is the user" trust model. Do NOT register this middleware on
a public-facing deployment without first replacing it with an
authenticated one.
"""

from __future__ import annotations

import socket
import urllib.parse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from api.platform.identity.models import Actor
from api.platform.observability.smart_logger import SmartLogger


_HOSTNAME = socket.gethostname()


class IdentityMiddleware(BaseHTTPMiddleware):
    """Populate ``request.state.actor`` on every request.

    Order matters: register AFTER the correlation-id middleware so the
    actor log line carries the same request_id as the rest of the request.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        name_raw = request.headers.get("x-user-name", "").strip()
        email = request.headers.get("x-user-email", "").strip()

        if name_raw and email:
            try:
                name = urllib.parse.unquote(name_raw)
            except Exception:
                # Malformed percent-encoding → treat as raw bytes; we
                # don't want to 500 on a header decode.
                name = name_raw
            actor = Actor(name=name, email=email, source="env")
        else:
            actor = Actor(
                name="unknown user",
                email=f"unknown@{_HOSTNAME}",
                source="unknown-header-missing",
            )

        request.state.actor = actor

        SmartLogger.log(
            "INFO",
            "Request actor resolved.",
            category="api.identity.actor",
            params={
                "actor_email": actor.email,
                "actor_source": actor.source,
                # Name length only — full name may be non-ASCII and is
                # not needed for diagnostic purposes.
                "actor_name_len": len(actor.name),
            },
        )
        return await call_next(request)
