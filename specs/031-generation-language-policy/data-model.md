# Phase 1 Data Model: Generation Output Language Policy

**Feature**: 031-generation-language-policy
**Date**: 2026-05-28

This feature deliberately introduces **no new persisted schema** — neither in Neo4j nor in Pydantic request/response models. The "data" model is a small set of in-memory and client-storage entities that govern the per-request language directive. Each entity is enumerated below with its fields, lifecycle, validation, and relationship to existing entities.

---

## Entity 1 — Effective Language (client-side)

**Storage**: Browser `localStorage`, key `app_language`. Held in memory as a reactive Pinia store (`useLanguageStore`) at `frontend/src/app/language.store.js`.

**Fields**:

| Field | Type | Required | Default | Validation |
|---|---|---|---|---|
| `language` | `string` (BCP-47 tag) | Yes | derived from `navigator.language` on first init | Non-empty; max 35 chars (BCP-47 upper bound); printable ASCII only (defense against `localStorage` corruption). No format-strictness beyond that — any BCP-47-ish string is accepted (see D2/D8 in research.md, FR-011 in spec). |

**Lifecycle**:

1. **Initialization**: On store creation (Pinia `defineStore` setup function), read `localStorage.getItem('app_language')`. If absent / empty / fails validation, fall back to `navigator.language` (a browser-provided BCP-47 tag like `ko-KR`, `en-US`, `ja-JP`). The store does NOT call `localStorage.setItem` at init — the persisted entry is created lazily on the first explicit user change, so a user who never touches Settings retains the natural "follow browser locale" behavior even if their browser locale changes between sessions.

2. **Mutation**: `setLanguage(tag: string)` validates the tag, updates the reactive ref, and writes to `localStorage`. Triggers a `language-changed` event the HTTP interceptor consumes (or reads the store directly on next call).

3. **Read**: The Axios/fetch interceptor reads `useLanguageStore().language` on every outbound request to set the `Accept-Language` header.

4. **Reset**: User clearing `localStorage` (browser-level action — no in-app "Reset" button in v1) restores the `navigator.language`-derived behavior at next page load. No special handling required; the lazy-persistence pattern from step 1 makes this automatic.

**Validation rules**:

- `tag.length >= 2 && tag.length <= 35`
- `/^[A-Za-z0-9-]+$/` (BCP-47 character set: letters, digits, hyphens)
- Empty / null / undefined → use default (`navigator.language || 'en-US'` if even `navigator.language` is missing in some test environments).
- Any non-conforming input from `localStorage` (e.g., user manually pasted garbage in devtools) is logged via `console.warn` and replaced with `navigator.language`. No silent failure.

**Relationship to other entities**:

- **Composes with** Theme (existing [theme.store.js](../../../../frontend/src/app/theme.store.js)) — both are independent user preferences in the Settings panel. Switching one does not affect the other.
- **Composes with** Domain Terminology (existing [terminology.store](../../../../frontend/src/features/terminology/terminology.store.js)) — orthogonal per FR-012. The Terminology toggle picks `displayName` vs `name` for *existing* domain entities; Language picks the language of *newly generated* natural-language prose. Both can be set independently.

---

## Entity 2 — Language Context (server-side, per-request)

**Storage**: Python `contextvars.ContextVar[str | None]`, defined in new module `api/platform/language.py`. Lives entirely in process memory; per FastAPI request scope; never persisted to disk or Neo4j.

**Fields** (module-level):

| Symbol | Type | Notes |
|---|---|---|
| `_request_language_var` | `ContextVar[str \| None]` | Internal; default `None`. Direct access discouraged outside the module. |

**Public API of `api/platform/language.py`**:

| Function | Signature | Notes |
|---|---|---|
| `set_request_language` | `(tag: str \| None) -> None` | Called by the language middleware once per request. Setting to `None` clears the var. |
| `get_request_language` | `() -> str` | Returns the var's value, OR falls back to `os.environ.get("GENERATION_LANGUAGE_DEFAULT", "en-US")` if unset (per D2 in research.md, resolves FR-010). Always returns a non-empty string — never `None`. |
| `clear_request_language` | `() -> None` | Convenience for middleware cleanup; equivalent to `set_request_language(None)`. |

**Lifecycle**:

1. **Set**: The language middleware (new, registered in `api/main.py` after the existing request-id middleware) reads `request.headers.get("accept-language")`, validates / normalizes it to a single BCP-47 tag (takes the first comma-separated entry, strips q-values), and calls `set_request_language(tag)`. If the header is absent or unparseable, `set_request_language(None)` is called — the lookup later falls through to the env default.

2. **Read**: Called by `api/platform/llm_messages.py::build_system_message()` on every system-message construction. Also surfaced into the structured log context via a one-line addition to `api/platform/observability/request_logging.py::http_context()` so every request log carries the resolved language.

3. **Reset**: ContextVar resets automatically when the request's asyncio task / context terminates. No manual cleanup needed in middleware (ContextVar's nature; differs from a module-level global).

**Validation rules**:

- Header value normalization: split on `,`, take element [0], strip whitespace, strip `;q=...` suffix if present, lowercase the language part / uppercase the region part for consistency (`ko-kr` → `ko-KR`).
- If after normalization the tag is empty or violates BCP-47 character set, treat as absent.
- Length cap (35 chars) before storing; truncate (with warning log) if exceeded — defense against pathological header values.

**Relationship to other entities**:

- **Mirrors the pattern of** `_request_id_var` in [api/platform/observability/request_logging.py](../../../../api/platform/observability/request_logging.py). Side-by-side coexistence — both are set by middleware, both are read across the entire request lifecycle.
- **Read by** every shared SystemMessage construction (see Entity 3 below).
- **Not read by** business-logic code directly. The chokepoint design (D3) keeps language usage confined to `api/platform/llm_messages.py` so per-feature code stays oblivious.

---

## Entity 3 — Generated Natural-Language Output (governed by the chokepoint)

**Storage**: Not a stored entity — describes the *behavior* of LLM-produced text under this feature's policy.

**Lifecycle / construction rule**:

Every LLM invocation in `api/features/` that builds a `langchain_core.messages.SystemMessage` MUST construct it via the shared builder:

```python
# Old (forbidden after this feature ships):
from langchain_core.messages import SystemMessage
system_msg = SystemMessage(content="You are a DDD expert analyzing user stories.")

# New (required):
from api.platform.llm_messages import build_system_message
system_msg = build_system_message("You are a DDD expert analyzing user stories.")
```

The builder appends (at the end of the content string, after a blank line) a deterministic short directive:

```
\n\nRespond in {tag} for all natural-language content. Preserve verbatim
any domain identifiers and user-supplied labels.
```

where `{tag}` is the result of `get_request_language()`. The "preserve verbatim" clause is the textual reinforcement of FR-007 / FR-009 (do not translate user-supplied event labels, role names, etc.).

**Validation rules**:

- The builder MUST NOT mutate the user-supplied content string — it appends only. Original instructions remain in place; the directive trails them.
- The builder accepts an optional `_skip_language_directive: bool = False` parameter, used **only** in tests that need deterministic byte-for-byte system-message strings. Production code MUST NOT pass this parameter — enforced by the AST regression test (which can include this check as a secondary assertion).
- The builder takes only `content: str`; it does not accept LangChain `additional_kwargs` in v1 to keep the API surface minimal. If a downstream use case ever needs `additional_kwargs`, extend the builder rather than bypassing it.

**Enforcement**:

- AST regression test at `api/tests/regression/test_language_chokepoint.py` walks every `.py` under `api/features/`, AST-parses, and FAILS if any `ast.Call` whose `func.id == "SystemMessage"` is encountered. Only `api/platform/llm_messages.py` is excluded.
- Test failure message points at the offending file:line and instructs the developer to use `build_system_message`.

**Relationship to other entities**:

- **Reads from** Entity 2 (Language Context) on every construction.
- **Used by** every existing LLM generation feature (see plan.md §Project Structure for the 20-file refactor list) and every future generation feature added thereafter.
- **Does not affect** non-LLM output paths (graph projections, BPMN exports, JSON serializations of stored entities).

---

## Non-Entities — explicit non-changes

The following are explicitly NOT modified by this feature, to make non-regression auditable:

| Non-change | Why it matters |
|---|---|
| Neo4j schema (`docs/cypher/schema/*.cypher`) | Per Constitution I + FR-014. Nothing is added or altered. |
| Existing Pydantic request/response models in `api/features/*/contracts/*.py` | Per FR-013. No request-body shape changes. The header is read at middleware layer. |
| `api/platform/llm.py::get_llm()` | Per Constitution VI. The LLM factory boundary is preserved untouched. Language injection happens at the message-construction layer, one step earlier. |
| `desktop/` Electron shell ([specs/023-electron-desktop-app/plan.md](../../../../specs/023-electron-desktop-app/plan.md)) | The shell hosts the SPA which reads `navigator.language` natively. No shell-side code changes; this feature is inert for the desktop work until the SPA itself starts attaching `Accept-Language` — at which point the shell-hosted SPA gets the benefit for free. |
| Existing stored `UserStory.acceptance_criteria`, `Event.description`, etc. | Per SC-007. No retroactive translation. Existing records keep their original-language content forever. |

---

## State transitions

The only stateful entity is **Effective Language** (client-side). Its lifecycle is a simple two-state-with-transient pattern:

```
┌──────────────────────────┐                  ┌──────────────────────────┐
│ derived-from-navigator   │  user opens      │ explicit-user-choice     │
│ (no localStorage entry)  │  Settings,       │ (localStorage written)   │
│                          │  picks a tag     │                          │
│ default = navigator.lang │ ─────────────→   │ default = stored tag     │
└──────────────────────────┘                  └──────────────────────────┘
            ▲                                              │
            │                                              │
            │  user clears                                 │  user changes
            │  localStorage                                │  selection
            │  (browser-level)                             │  (writes new tag)
            └──────────────────────────────────────────────┘
```

There are no other states. There is no "syncing" state, no "saving" state, no "loading" state — the localStorage write is synchronous and immediate.

The **Language Context** (server-side) has no state transitions in the user-facing sense — it is set once per request by the middleware and read N times during that request's LLM calls. The ContextVar's reset is implicit in the request lifecycle (not a logical transition).
