# Contract: Identity Header Propagation

**Surface**: two HTTP request headers attached to every request from the SPA to the FastAPI backend after launcher hand-off. **No new endpoint, no schema change.** A single platform-layer middleware reads them.

---

## Wire format

| Header | Type | Encoding | Example |
|---|---|---|---|
| `X-User-Name` | string | UTF-8 percent-encoded (per RFC 8187, but without the `UTF-8''` prefix because the charset is fixed) | `Jang%20Jin-young` |
| `X-User-Email` | string | ASCII (RFC 5322 not enforced) | `jyjang@uengine.org` |

**Both headers MUST be set together** by the renderer interceptor. If either is set, the other should be set. If neither is set, middleware falls back per `actor.source = 'unknown-header-missing'`.

**Empty string** is treated identically to "missing." Whitespace-only is treated as missing. The interceptor MUST NOT send `X-User-Name: ` (with empty value); it omits the header entirely.

---

## Frontend interceptor (`frontend/src/app/http.ts`)

Single source of truth. Runs once per outgoing request, reads `useSession().user`, attaches the two headers. If `useSession().user === null` (launcher hasn't entered yet — should be impossible in practice because the router guards against pre-launcher routes), the interceptor sends no identity headers and lets the backend fallback take over.

Pseudocode:

```ts
import { useSession } from '@/stores/session-store';

export function withIdentity(init: RequestInit = {}): RequestInit {
  const u = useSession().user;
  if (!u) return init;
  const headers = new Headers(init.headers);
  headers.set('X-User-Name', encodeURIComponent(u.name));
  headers.set('X-User-Email', u.email);
  return { ...init, headers };
}
```

(Concrete shape may use axios interceptor instead — same semantics.)

**Out of scope for the interceptor**:
- Identity rotation mid-request — not supported. A request that started under user A finishes under user A regardless of mid-flight identity changes.
- Multi-tab / multi-window — desktop app is single-instance per 023; no concern.

---

## Backend middleware (`api/platform/identity/middleware.py`)

A Starlette `BaseHTTPMiddleware` registered in `api/main.py` **before** all feature routers and **after** the existing correlation-ID middleware.

Behavior:

```python
class IdentityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        name = request.headers.get("x-user-name", "").strip()
        email = request.headers.get("x-user-email", "").strip()

        if name and email:
            request.state.actor = Actor(
                name=urllib.parse.unquote(name),
                email=email,
                source="env",  # opaque to the backend — see note below
            )
        else:
            request.state.actor = Actor(
                name="unknown user",
                email=f"unknown@{socket.gethostname()}",
                source="unknown-header-missing",
            )

        logger.info(
            "request_actor",
            correlation_id=request.state.correlation_id,
            actor_name_len=len(request.state.actor.name),
            actor_email=request.state.actor.email,
            actor_source=request.state.actor.source,
        )
        return await call_next(request)
```

**Notes on `source`**: the renderer-side `SessionUser.source` (env / project-local-git / global-git / system-git / unknown-fallback) is *not* propagated in headers — it's only meaningful in the launcher UI. The backend Actor has its own narrower source enum (`'env'` for "headers were present", `'unknown-header-missing'` for fallback). If a future spec needs richer attribution, a third header (`X-User-Source`) can be added without breaking this contract.

---

## Fallback contract

When headers are missing, malformed, or empty:

- Middleware sets `request.state.actor = Actor(name='unknown user', email=f'unknown@{hostname}', source='unknown-header-missing')`.
- The request is **not** rejected. Backend writes proceed normally.
- The "unknown user" attribution is what the follow-up history feature will record for these requests.

**Rationale**: the launcher explicitly allows unknown-user entry (FR-007, FR-029). Refusing the request on missing headers would break that scenario AND would break any internal/test/cron caller that doesn't go through the SPA.

---

## Security boundary

- Headers are **not** authenticated. Anyone with shell access on the host can curl the backend with any `X-User-Name` they want. This is the documented trust model (spec Assumption "Git identity is sufficient"). The desktop app is a local single-user tool; the backend listens on `127.0.0.1:<port>` (per 023 architecture).
- This contract is **not safe** for a public-facing deployment. If a future spec exposes this backend to a network beyond loopback, that spec MUST replace the identity mechanism with an authenticated one and either retire this middleware or gate it behind a deployment flag.

---

## Logging policy

| Field | Logged | Reason |
|---|---|---|
| `correlation_id` | yes | required by constitution VII |
| `actor.source` | yes | useful for debugging missing-header issues |
| `actor.email` | yes | identifier, not a secret (matches git's commit-author behavior) |
| `actor.name` | length only | full name may contain non-ASCII; length is enough for debugging without log-spam concerns |

Header values themselves are not echoed back to the client in any response. There is no `X-Actor-Echo` debug header.
