"""Platform-layer identity propagation (spec 032).

Reads `X-User-Name` / `X-User-Email` request headers populated by the
Electron launcher hand-off, attaches an `Actor` to `request.state.actor`
so feature routers can attribute writes without any further wiring.

Trust model: local-loopback only. Headers are NOT authenticated. Do not
deploy this middleware in a public-facing context — see
`specs/032-desktop-startup-picker/contracts/identity-header-contract.md`.
"""

from api.platform.identity.middleware import IdentityMiddleware
from api.platform.identity.models import Actor

__all__ = ["IdentityMiddleware", "Actor"]
