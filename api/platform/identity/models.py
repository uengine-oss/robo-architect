"""Identity model (spec 032).

A minimal value-object representing the user a request is attributed to.
The launcher resolves this from `git config` on the host and propagates
it via the `X-User-Name` / `X-User-Email` headers (see
`specs/032-desktop-startup-picker/contracts/identity-header-contract.md`).

Lives in `api/platform/identity/` because attribution is cross-cutting
across every feature — see constitution Principle V.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

IdentitySource = Literal[
    # Renderer-side sources (forwarded opaquely in `X-User-Source` if a
    # future spec adds it; not currently surfaced in the wire format).
    "env",
    "project-local-git",
    "global-git",
    "system-git",
    "unknown-fallback",
    # Backend-side fallback when identity headers are absent or empty.
    "unknown-header-missing",
]


@dataclass(frozen=True)
class Actor:
    """The user a request is attributed to.

    Attached to `request.state.actor` by `IdentityMiddleware` for every
    inbound request. Feature handlers that care about audit attribution
    read it; those that don't, ignore it.

    roles: frozenset of role strings (e.g. {"ProductOwner"}).
           Defaults to {"ProductOwner"} so every user has approval rights
           until an explicit role management system is introduced.
           ProductOwner role bypasses the self-approval restriction.
    """

    name: str
    email: str
    source: IdentitySource
    roles: frozenset = frozenset({"ProductOwner"})

    def has_role(self, role: str) -> bool:
        return role in self.roles
