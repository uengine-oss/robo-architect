# Phase 0 Research: Generation Output Language Policy

**Feature**: 031-generation-language-policy
**Date**: 2026-05-28

Resolves the single spec-level NEEDS CLARIFICATION (FR-010) and the implicit design questions surfaced during plan-template Technical Context filling.

---

## D1 — Transport channel for the per-request language tag

**Decision**: Use the standard HTTP `Accept-Language` header, set globally by the frontend HTTP client.

**Rationale**:
- It is the IETF-standard header for exactly this purpose (RFC 7231 §5.3.5). FastAPI/Starlette already exposes it on `request.headers`. No new wire-format invention.
- Adding a global Axios/fetch interceptor that injects the header is a single change point that every existing and future endpoint inherits for free (FR-005 / FR-008).
- It is observable in browser devtools, in server access logs, and in network captures — debuggable by anyone without product knowledge.
- It does not pollute request body schemas (FR-013): no Pydantic model changes, no new query parameters, no breaking changes to existing API contracts.
- Standard caching layers (CDNs, reverse proxies) understand `Accept-Language` semantics natively, which matters if a future caching layer is added.

**Alternatives considered**:
- **Custom header (e.g., `X-Robo-Language`)**: rejected. Reinvents `Accept-Language` for no gain; loses CDN/proxy semantics; not idiomatic.
- **Request-body field on every endpoint**: rejected. Violates FR-013 (existing contracts unchanged) and FR-008 (every endpoint must opt in — exactly the opposite of "single chokepoint").
- **Query parameter (`?lang=ko-KR`)**: rejected. Pollutes every URL, breaks URL-based caching, ugly in browser network tab, and requires per-endpoint code to read it.
- **Cookie**: rejected. Cookies suit per-session server-side state; this value is client-owned and changes only when the user opens Settings.

**Note on `Accept-Language` value format**: the spec restricts to a single BCP-47 tag (not the full q-weighted list browsers send by default — e.g. `ko-KR,ko;q=0.9,en-US;q=0.8`). The frontend interceptor sets the header to a single canonical tag (the user's chosen Language), overriding the browser's auto-generated multi-value list. This sidesteps q-value parsing on the server.

---

## D2 — Server-side fallback when no `Accept-Language` header is present (resolves FR-010)

**Decision**: Default to **`en-US`**, overridable via the environment variable `GENERATION_LANGUAGE_DEFAULT`.

**Rationale**:
- The fallback fires only when the request bypasses the SPA (FR-010 specifies external API clients, CLIs, scripts, automation, MCP bridges). Those callers are typically technical/developer-facing — English is the lowest-friction default for that audience.
- The product's existing spec documentation (`specs/023-electron-desktop-app/spec.md`, all prior spec.md files) is written in English. The CLAUDE.md project context and constitution are in English. The product's *generated artifacts default* for unauthenticated callers should match this convention.
- The env-var escape hatch (`GENERATION_LANGUAGE_DEFAULT`) lets a single-language team (e.g., an all-Korean deployment) flip to `ko-KR` without code changes. This satisfies the deployment-flexibility requirement implicit in Constitution Principle VI (provider-agnostic, configuration-driven).
- The SPA path is unaffected: SPA users always receive a header derived from `navigator.language` or their explicit Settings selection. The fallback only governs the edge case where no header is present at all.

**Alternatives considered**:
- **`ko-KR`** (current primary user base): rejected as the *code-level* default. Hard-codes a single team's preference into the platform. The env-var override means a Korean-team deployment achieves the same effect without lock-in.
- **Detect from `User-Agent` / IP geolocation**: rejected. Heuristic, unreliable, privacy-sensitive, and not testable. Adds infrastructure (GeoIP database) for marginal value.
- **Refuse the request (HTTP 400)**: rejected. Breaks every existing external integration on day one — direct violation of FR-013 (no breaking changes to existing API contracts).
- **Match the LLM provider's default**: rejected. Provider defaults are opaque, change without notice, and differ across providers (OpenAI vs Anthropic vs Google), violating Constitution VI.

**Open question, deferred to /speckit-clarify**: Should the env-var name be `GENERATION_LANGUAGE_DEFAULT` or namespaced under an existing convention (e.g., `ROBO_GENERATION_LANGUAGE_DEFAULT`)? The codebase has both styles (`LLM_PROVIDER` is unprefixed; `AI_AUDIT_LOG_ENABLED` is `AI_` prefixed). Pick during T002 or in clarification.

---

## D3 — Where to inject the language directive in the LLM call path

**Decision**: A new shared `build_system_message(content: str) -> SystemMessage` helper in `api/platform/llm_messages.py`. Every existing `SystemMessage(content=...)` call site in `api/features/` is refactored to call this helper. The helper reads the current language from the ContextVar (D4) and appends a deterministic, short directive to the content.

**Rationale**:
- Aligns with Constitution VI (provider-agnostic): operates at the LangChain `SystemMessage` layer, which all three providers (`ChatOpenAI` / `ChatAnthropic` / `ChatGoogleGenerativeAI` in [api/platform/llm.py](../../../../api/platform/llm.py)) consume identically.
- Minimally invasive per-call-site change: `SystemMessage(content="...")` → `build_system_message("...")`. Mechanical, easy to grep-audit, easy to enforce.
- One change-point for the directive's wording. If product later wants a richer instruction ("Respond in {tag}. Use natural sentence structure for that language..."), the change is in one file.
- Token-cheap: the appended directive is < 60 characters (~20 tokens). Acceptable overhead even for high-frequency LLM calls.
- Testable: a unit test for the helper covers the entire policy; the regression test (D5) covers enforcement.

**Alternatives considered**:
- **Wrap `get_llm()` to return a model that auto-injects on every `invoke()`**: rejected. LangChain chat models don't have a clean "transform messages before send" hook that survives `invoke` / `astream` / `stream` / `batch` / LangGraph binding. A wrapper that overrides every method becomes a maintenance burden and breaks the moment a node uses `llm.with_structured_output(...)` or `llm.bind_tools(...)` (which return new objects). The SystemMessage-builder approach sidesteps this.
- **Inject at the HumanMessage layer (append to the user prompt)**: rejected. System messages are the LLM's most reliable instruction channel; user-message instructions are easier for the model to misinterpret as content.
- **Inject only at the highest agent/graph node (e.g., LangGraph entry)**: rejected. Many features call `llm.invoke()` directly without a graph wrapper; the chokepoint would miss them. Working at the message-construction layer covers both bare calls and graph nodes.
- **Use LangChain's `RunnableWithMessageHistory` or `RunnableConfig`**: rejected. Adds dependency on LangChain idioms the codebase doesn't already use; per-call instead of per-message; harder to enforce than a one-symbol rename.
- **Append the directive to the user/Human message instead of system**: rejected for the same reason as the dedicated alternative above — weaker model adherence.

---

## D4 — Server-side ContextVar pattern for the per-request language

**Decision**: A new `api/platform/language.py` module exposing a `ContextVar[str | None]` plus `set_request_language(tag)` / `get_request_language() -> str` (with fallback to `GENERATION_LANGUAGE_DEFAULT`). Pattern is a direct copy of the existing `_request_id_var` in [api/platform/observability/request_logging.py](../../../../api/platform/observability/request_logging.py).

**Rationale**:
- Same pattern already in use for `request_id` — proven to survive async boundaries within a single FastAPI request.
- The companion `_current_session` ContextVar in [api/features/ingestion/ingestion_llm_runtime.py](../../../../api/features/ingestion/ingestion_llm_runtime.py) shows the codebase trusts this pattern for cross-cutting per-request state injection into LLM calls.
- ContextVar is thread-safe and asyncio-safe; survives `await` boundaries; resets automatically per request scope when used with FastAPI middleware.
- Zero leakage between concurrent requests when set by middleware (verified by the existing `_request_id_var` working correctly).

**Alternatives considered**:
- **Pass language as a parameter through every function call**: rejected. Would require changing every function signature down the call tree — exact opposite of "single chokepoint" (FR-008).
- **Module-level global variable**: rejected. Not async-safe; leaks across concurrent requests; would corrupt outputs under any load.
- **Pass via FastAPI `Depends(...)` injection**: rejected. Requires every endpoint to declare the dependency — same per-endpoint burden as FR-013 wants to avoid.

---

## D5 — Enforcement mechanism for the single-chokepoint rule (FR-008, FR-015, SC-005)

**Decision**: An AST-based pytest regression in `api/tests/regression/test_language_chokepoint.py`. The test walks every `.py` file under `api/features/`, AST-parses, and asserts that no `ast.Call` of the form `SystemMessage(content=...)` (or `SystemMessage(...)` positional) exists. The only legal call site is `api/platform/llm_messages.py` itself, which is explicitly excluded.

**Rationale**:
- AST parsing avoids false positives from comments / docstrings that a raw `grep` would flag.
- The test runs in CI on every PR; a developer who imports `SystemMessage` and uses it directly fails the test immediately, with an error message pointing them at `build_system_message`.
- Concrete realization of FR-015 and SC-005: the "regression test that fails if any new LLM call site bypasses the chokepoint" is not aspirational — it is a real artifact in `api/tests/regression/`.
- Provides a documentation surface: the test's failure message can include a one-paragraph explanation of why `build_system_message` is mandatory.

**Alternatives considered**:
- **Code-review checklist / lint rule comment**: rejected. Humans drift; the test does not.
- **Custom Ruff/flake8 rule**: rejected as v1 — heavier setup than AST-in-pytest, no clear win, and Ruff plugin ecosystem for project-specific rules is still maturing. Can be migrated later if maintenance becomes annoying.
- **Runtime check (raise if `SystemMessage` is invoked without context)**: rejected. Catches drift only at runtime, in features that happen to be exercised; the AST test catches drift at PR time.

**Coverage note**: the AST test catches direct `SystemMessage(content=...)` calls. It does NOT catch a developer who builds the message string outside and constructs the helper differently. The helper's design (it accepts the user's content unmodified and appends the directive) means any string-content path passes through it harmlessly. We accept this residual risk as acceptable — the test catches the > 95% case (the literal LangChain constructor).

---

## D6 — Mechanical refactor scope and approach

**Decision**: Refactor all 74 occurrences of `SystemMessage(content=...)` across the 20 audited files in a single PR alongside the platform-layer additions. Bulk find-and-replace with manual review per file.

**Rationale**:
- Half-finished migration violates FR-008 (single chokepoint) and SC-004 (100% of existing features honor Language). Leaving some call sites untouched defeats the entire purpose.
- The change is purely mechanical: a sed-grade rename. Review per file is for sanity, not for design.
- Doing it in one PR makes the regression test (D5) green at the same moment as the platform additions — never a window where the test exists but fails.
- Git history stays clean: one "introduce language policy" commit / PR rather than 20 stragglers.

**Alternatives considered**:
- **Stage migration over multiple PRs (one per feature directory)**: rejected. Each interim PR either leaves the regression test red (breaks CI) or omits the test (loses enforcement). Both are bad.
- **Adapter shim: keep both `SystemMessage(...)` and `build_system_message(...)` valid, deprecate later**: rejected. Adds complexity for zero benefit; FR-008 is binary (chokepoint exists or doesn't).

**Risk register for the refactor**:
- A few call sites may build `SystemMessage` with `additional_kwargs` or named-construction patterns the simple rename misses. Manual per-file pass handles these — flag any non-trivial pattern in the per-file commit message for reviewer attention.
- Tests that hard-code expected system-message strings will need updating to account for the appended directive. The new builder accepts an optional `_skip_language_directive=True` for test fixtures that need byte-for-byte determinism — used sparingly and documented.

---

## D7 — Frontend store + interceptor design

**Decision**: New Pinia store at `frontend/src/app/language.store.js`, mirroring the structure of [theme.store.js](../../../../frontend/src/app/theme.store.js). New module `frontend/src/services/httpClient.js` (or a modification to the existing one — audit during T002) installs an Axios request interceptor that reads from the store and sets `Accept-Language`.

**Rationale**:
- The Pinia + localStorage pattern is already idiomatic in this codebase ([theme.store.js](../../../../frontend/src/app/theme.store.js), [terminology.store](../../../../frontend/src/features/terminology/terminology.store.js)). Reusing the pattern shortens review and aligns with Constitution Principle V (mirror existing structure).
- A single Axios interceptor inherits to every endpoint call — frontend-side equivalent of FR-008's single chokepoint.
- The store exposes a reactive `language` ref so the [SettingsPanel.vue](../../../../frontend/src/app/layout/SettingsPanel.vue) `<select>` element binds naturally with `v-model`.
- `navigator.language` is read once at store init for the default value, mirroring how `theme.store.js` reads `localStorage.app_theme` at init.

**Alternatives considered**:
- **`fetch` wrapper with global header injection**: viable, but `axios.interceptors.request.use(...)` is more idiomatic in Vue 3 SPAs and likely already in the codebase (verify in T002). If the codebase uses `fetch`, mirror the pattern there instead.
- **Per-call header passing**: rejected for the same per-endpoint-burden reason as D1/D3 backend variants.
- **Store reads `Accept-Language` from `<html lang>` attribute**: rejected. `navigator.language` is the canonical source; the `<html lang>` attribute is a presentation concern.

---

## D8 — Treatment of preserved user-input vs. generated content (FR-007, FR-009, FR-012)

**Decision**: The language directive applies *only* to the LLM-generation step. No translation, paraphrasing, or normalization is performed on user-supplied text (event labels, role names, action descriptions) at any layer. Stored `displayName` values from the existing Domain Terminology mode are passed through to prompts verbatim and rendered as-is in UI.

**Rationale**:
- FR-009 is explicit: only newly generated, summarized, or rephrased content is subject to the policy.
- FR-012 makes the orthogonality with Domain Terminology mode explicit: the two settings compose cleanly because they operate at different layers (Language at LLM-prompt construction; Domain Terminology at UI display selection).
- Mixed-language inputs (Korean event labels + English Language setting) produce outputs where Korean nouns appear inside English narrative — this is the expected, desired behavior for teams that label domain artifacts in their own language but document them in English for distribution.

**Alternatives considered**:
- **Translate user input to selected Language on the fly**: rejected. Violates FR-009. Would silently corrupt domain identifiers, which by Constitution Principle II are domain-vocabulary-bearing.
- **Reject mixed-language input with a warning**: rejected. Mixed input is a legitimate use case (per the spec assumption above); a warning would be noise.

---

## Summary table — all NEEDS CLARIFICATION resolved

| ID | Question | Resolution | Where applied |
|---|---|---|---|
| FR-010 | Server-side fallback language? | `en-US`, overridable via `GENERATION_LANGUAGE_DEFAULT` env var (D2) | data-model.md §Server-side Language Context |
| — | Transport channel? | `Accept-Language` standard header (D1) | contracts/language-policy-contract.md |
| — | Where to inject in the LLM path? | Shared `build_system_message()` in `api/platform/llm_messages.py` (D3) | data-model.md §Generated Natural-Language Output |
| — | How to enforce the chokepoint? | AST regression test in `api/tests/regression/` (D5) | tasks.md (forthcoming) |
| — | Frontend storage pattern? | Pinia + localStorage mirroring `theme.store.js` (D7) | data-model.md §Effective Language (client-side) |
| — | Refactor approach? | All 74 call sites in one PR; AST test fails until 100% complete (D6) | tasks.md (forthcoming) |

No remaining NEEDS CLARIFICATION blocks the design. Proceed to Phase 1.
