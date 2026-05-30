# Contract: Generation Output Language Policy

**Feature**: 031-generation-language-policy
**Date**: 2026-05-28
**Status**: Phase 1 design

This document defines the externally-visible contracts introduced by this feature. Per Constitution Principle V and the spec's FR-013 ("no breaking changes to existing API contracts"), the surface added by this feature is intentionally minimal: a single HTTP header and a single shared backend helper function.

---

## Contract 1 — HTTP transport: `Accept-Language` request header

### Surface

Every outbound HTTP request from the SPA frontend (and from any client wishing to participate in the language policy — Electron shell, scripted clients, MCP bridges) attaches the standard `Accept-Language` request header.

### Format

```
Accept-Language: <single BCP-47 tag>
```

**Examples**:

```
Accept-Language: ko-KR
Accept-Language: en-US
Accept-Language: ja-JP
Accept-Language: zh-CN
Accept-Language: af-ZA
```

### Rules

| Rule | Source | Notes |
|---|---|---|
| Single tag only (no `q=` weight list) | This feature's normalization | The SPA's HTTP interceptor sets the value to the user's single chosen tag, overriding the browser's auto-generated multi-value list (`ko-KR,ko;q=0.9,en-US;q=0.8`). If a client sends a multi-value list, the server takes element [0] after splitting on `,` and strips any `;q=...` suffix. |
| BCP-47 character set: `[A-Za-z0-9-]+`, length 2–35 | Server-side validation | Anything else is treated as "header absent" — falls through to the server-side default. |
| Case normalization: language subtag lowercased, region subtag uppercased | Server-side normalization | `ko-kr` and `KO-KR` both become `ko-KR` for consistency in downstream prompts and logs. |
| Header absence is valid | This feature's fallback | Server applies the default from `GENERATION_LANGUAGE_DEFAULT` env var (defaults to `en-US`). See research.md §D2. |

### Compatibility guarantees

- **Backward compatible**: existing clients that do NOT send the header continue to work unchanged. They receive output in the server-side default language.
- **No request-body shape changes** anywhere. No endpoint's request model is modified.
- **No response-body shape changes**. Generated text comes back in the requested language; the JSON structure is identical to today.
- **No response header is set in return** by this feature. The server does not echo `Content-Language` — adding it later is a non-breaking enhancement if a downstream consumer needs it.

### Server-side behavior

For every HTTP request received:

1. Middleware reads `request.headers.get("accept-language")`.
2. Normalizes per the rules above.
3. If the normalized value is non-empty and passes validation: stores it via `api.platform.language.set_request_language(tag)`.
4. Otherwise: stores `None` (which `get_request_language()` resolves to the env default at read time).
5. The middleware adds the resolved tag as a structured field on the request log entry (extension of [request_logging.py::http_context()](../../../../../../api/platform/observability/request_logging.py)) for traceability.

### Failure modes

| Scenario | Behavior |
|---|---|
| Header absent | Default language applied. Request succeeds. |
| Header value is a malformed string | Logged as a warning; treated as header-absent. Request succeeds in default language. |
| Header value contains an exotic-but-valid BCP-47 tag (e.g., `af-ZA`) | Passed through to the LLM unchanged. LLM responds on a best-effort basis. (FR-011 in spec.) |
| Header value is excessively long (> 35 chars) | Truncated to 35 chars with a warning log. Defense against pathological inputs. |

---

## Contract 2 — Backend chokepoint: `api.platform.llm_messages.build_system_message`

### Surface

A single new module exposing exactly one public function. All `api/features/` code that constructs `SystemMessage` instances MUST go through this function. Direct use of `langchain_core.messages.SystemMessage` in `api/features/` is forbidden and enforced by the AST regression test.

### Signature

```python
# api/platform/llm_messages.py

from langchain_core.messages import SystemMessage

def build_system_message(content: str) -> SystemMessage:
    """
    Construct a SystemMessage with the feature-031 language directive appended.

    The user-supplied `content` is preserved verbatim at the front of the message.
    A short instruction (~20 tokens) is appended after a blank line, directing
    the LLM to respond in the per-request language (resolved via
    `api.platform.language.get_request_language()`).

    The appended directive also reinforces FR-007 / FR-009: user-supplied labels
    and domain identifiers are preserved verbatim by the LLM and are not
    translated to the response language.
    """
    ...
```

### Rules

| Rule | Reason |
|---|---|
| Accepts exactly one positional argument: `content: str`. No keyword arguments, no `additional_kwargs`. | Keeps the API surface minimal. Extend the signature when (not if) a real need arises — not pre-emptively. |
| Returns a `langchain_core.messages.SystemMessage`. | Drop-in for every existing call site. No downstream LangChain code needs to change. |
| Appends the directive at the end of `content`, separated by `\n\n`. Never prepends. Never modifies `content`. | Caller-authored instructions retain primacy. The directive is supplemental, not authoritative-replacing. |
| Reads the per-request language via `api.platform.language.get_request_language()`. Falls back to env default if no per-request language is set. | Single source of truth for the active language. No parameter threading. |
| The directive's wording is centralized in this module (one constant). | Future product changes to the wording (e.g., "Respond in {tag}. Use natural sentence structure for that language.") happen in one place. |
| Test-only escape: optional kwarg `_skip_language_directive: bool = False`. When True, returns a plain `SystemMessage` with no appended directive. The AST regression test asserts this kwarg is never passed from `api/features/` code (only from `api/tests/` code). | Some test fixtures need byte-for-byte deterministic system messages. Single sanctioned escape, narrowly scoped. |

### Enforcement contract

`api/tests/regression/test_language_chokepoint.py` MUST exist and MUST fail under any of the following conditions:

1. A `.py` file under `api/features/` (any subdirectory, any depth) contains an `ast.Call` whose function reference resolves to `langchain_core.messages.SystemMessage` (either via direct constructor `SystemMessage(...)` or via aliased import).
2. A `.py` file under `api/features/` passes the `_skip_language_directive=True` kwarg to `build_system_message`.
3. The shared builder is moved or renamed without updating the test's exclusion list.

Test failure message MUST include the offending file:line and a one-paragraph explanation pointing the developer at `build_system_message` and at this contract document.

---

## Contract 3 — Frontend chokepoint: `useLanguageStore` + global `window.fetch` patch

> **Mechanism revision (during implementation, T002 audit)**: the original plan
> specified an Axios request interceptor. The codebase has no axios dependency
> and uses raw `window.fetch()` directly from ~50 feature-local `*.api.js`
> modules and inline component blocks. Migrating every caller would defeat
> the "single chokepoint" property (FR-008). Instead, the chokepoint is a
> **global `window.fetch` patch installed once at app bootstrap** — every
> caller (existing and future) inherits the `Accept-Language` header for free.
> Functionally equivalent to the Axios interceptor pattern, deployed at a
> different platform boundary.

### Surface

| Module | Path | Public API |
|---|---|---|
| Pinia store | [frontend/src/app/language.store.js](../../../../../../frontend/src/app/language.store.js) | `useLanguageStore()` exposing `{ language: Ref<string>, setLanguage(tag: string): void, initLanguage(): void }` |
| Fetch interceptor | [frontend/src/app/httpInterceptor.js](../../../../../../frontend/src/app/httpInterceptor.js) | `installLanguageFetchInterceptor(): void` — idempotent global `window.fetch` patch. Reads from `useLanguageStore()` on every call, sets `Accept-Language` on the outbound request (preserving any caller-set value). |
| Settings UI | [frontend/src/app/layout/SettingsPanel.vue](../../../../../../frontend/src/app/layout/SettingsPanel.vue) | New "Language" section with a free-form `<input>` + `<datalist>` of recommended tags (`ko-KR`, `en-US`, `ja-JP`, `zh-CN`), bound via `v-model` (through a computed wrapper that delegates to `setLanguage()` for validation + persistence). |
| Bootstrap wiring | [frontend/src/main.js](../../../../../../frontend/src/main.js) | After Pinia registration: `useLanguageStore()` (forces eager init) + `installLanguageFetchInterceptor()`. |

### Rules

| Rule | Reason |
|---|---|
| Every outbound HTTP request that may trigger backend LLM work MUST flow through the shared HTTP client (Axios/fetch wrapper). | The interceptor is the chokepoint; bypassing it = language directive missing. |
| The store MUST be initialized at app startup (during `main.js` bootstrap) so the interceptor always finds a value. | Lazy init at first request risks a missing header on early requests. |
| The store MUST NOT call `localStorage.setItem` during init — only on explicit `setLanguage(tag)`. | Preserves the "follow browser locale until user explicitly chooses" semantics (US1 + data-model.md §Effective Language §Lifecycle step 1). |
| Settings UI MUST allow free-form entry of any BCP-47 tag, with a `<datalist>` of recommended tags (`ko-KR`, `en-US`, `ja-JP`, `zh-CN`) as suggestions. | FR-011 requires accepting any BCP-47 tag without erroring. |

### Failure modes

| Scenario | Behavior |
|---|---|
| `localStorage` is unavailable (private browsing, disabled) | Store falls back to `navigator.language` on every load; no persistence. UI shows the resolved language. No crash. |
| `navigator.language` is also unavailable (some test environments) | Store falls back to `'en-US'`. UI shows `en-US`. |
| User pastes invalid input into the Settings field | Store rejects with a `console.warn`; reactive `language` stays at previous value. UI may show a non-blocking validation message in v2. |
| HTTP interceptor fails to install | Caught at app startup; surfaced as a console error. Requests proceed without the header; backend applies default language. Degrades gracefully. |

---

## Non-Contracts — what this feature deliberately does NOT introduce

| Surface | Why not |
|---|---|
| No new REST/JSON endpoints | The feature is fully transport-layer + chokepoint helper. Settings live entirely on the client; per-request state lives entirely in the request scope. |
| No new request-body fields on any existing endpoint | FR-013 explicit. |
| No new response headers (e.g., `Content-Language`) | Not needed by any current consumer. Trivially addable as a non-breaking enhancement if a future client wants it. |
| No new Pydantic models, no new Neo4j node labels / relationship types / properties | FR-014 explicit; Constitution Principle I satisfied. |
| No changes to `api/platform/llm.py::get_llm()` signature or behavior | Constitution Principle VI boundary preserved untouched. Language operates one layer up (message construction). |
| No `Content-Language` translation pipeline | Out of spec scope. Spec assumption: LLM follows the instruction with reasonable fidelity. No retry-on-wrong-language logic. |
| No UI internationalization (menu labels, tooltips) | Explicit non-goal in spec. UI i18n is a separate feature. |
| No retroactive translation of stored artifacts | Explicit non-goal in spec (SC-007). |

---

## Compatibility matrix

| Caller class | Before this feature | After this feature | Action required |
|---|---|---|---|
| SPA (in browser) | No language header sent | `Accept-Language` set to user's choice or `navigator.language` | None — automatic via interceptor |
| Electron shell hosting the SPA | Inherits browser behavior | Same — inherits the SPA-side interceptor | None |
| External REST clients (scripts, MCP bridges, curl) | No language header sent | Server applies env default (`en-US` unless overridden) | Optional: set `Accept-Language` header to get a specific output language |
| Test fixtures with hard-coded expected system-message strings | Worked | Will fail unless updated to expect the trailing directive | Update fixtures or use `_skip_language_directive=True` |
| New generation feature added in 2026-Q3 (hypothetical) | N/A | Inherits language policy automatically via `build_system_message` | None — chokepoint enforced by AST regression test |
