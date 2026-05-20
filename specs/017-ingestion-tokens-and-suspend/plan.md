# Implementation Plan: Ingestion Token Counter + Granular Suspend

**Branch**: `figma-integration` (017 lands on the same branch as 016/018) | **Date**: 2026-05-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/017-ingestion-tokens-and-suspend/spec.md`

## Summary

Two tightly-coupled UX upgrades for the ingestion flow:

1. **Live token counter** — every LLM call's prompt+completion tokens are tallied per ingestion session and surfaced in the floating status panel within 2 s of each call. Cumulative + per-phase breakdown. Provider-agnostic via LangChain `BaseCallbackHandler` reading `AIMessage.usage_metadata`, with a `tiktoken` fallback flagged `approximate=True`.

2. **Granular suspend** — every LLM call boundary (and every wireframe-service call boundary, treated as LLM-equivalent) becomes a cooperative cancellation point via `async with session_call_slot(session):`. A suspend click halts new dispatches within 5 s in the common case and within 30 s worst-case (one in-flight call must finish — provider can't be told to abort mid-stream). The gate also fires inside the FR-017 retry stack from spec 016, and inside the new bulk-flush call sites from spec 018.

Both ship together because they share the same instrumentation surface — `ingestion_llm_runtime.get_llm()` is where we attach the callback (US1) and around every call site is where we wrap the gate (US2). Splitting into two PRs would mean editing the same call sites twice.

## Technical Context

**Language/Version**: Python 3.11+ (backend), Vue 3 (frontend)
**Primary Dependencies**:
- Backend: FastAPI, LangChain (`langchain-core`, `langchain-openai`, `langchain-anthropic`, `langchain-google-genai`), Neo4j Python driver, `tiktoken` (NEW — fallback tokenizer), `httpx` (existing — wireframe service).
- Frontend: Vue 3 + Pinia (`navigator.store.js`), the existing `RequirementsIngestionModal.vue` SSE consumer.

**Storage**: Transient — token totals live on the in-memory `IngestionSession` object only. No Neo4j schema changes. The session's existing TTL cleanup applies as-is.

**Testing**: Manual SSE inspection (`quickstart.md` Steps 1–5) plus unit tests for the callback (mock LangChain response → assert ledger update) and the suspend gate (mock session.is_cancelled=True → assert `CancelledError`). pytest infra is not yet bootstrapped in this repo (see 018 deferred T009/T010 note); tests are deferred to the same follow-up unless the user prioritizes earlier.

**Target Platform**: Same as the rest of robo-architect — Linux/macOS server backend, modern browser frontend.

**Project Type**: Backend-heavy with thin frontend additive. The frontend just reads two new optional fields off the existing `progress` SSE event (no new components, no new endpoints).

**Performance Goals**:
- Token tally overhead: ≤ 5 ms per LLM call (tiktoken on a 4 k-token prompt is ~1 ms; provider-reported counts are zero-cost).
- Suspend latency: median ≤ 5 s, P99 ≤ 30 s (set by single-call timeout).
- Counter update visibility: ≤ 2 s after LLM call return (SC-003).

**Constraints**:
- MUST NOT mid-stream-abort an in-flight LLM call (provider limitation; spec 017 FR-005 acknowledges).
- MUST NOT lose previously persisted Neo4j work on suspend (FR-010).
- MUST keep Constitution VI (provider-agnostic) — no provider-specific code paths.
- MUST NOT introduce new Neo4j schema (transient session state only).

**Scale/Scope**:
- Sessions: 1–10 concurrent typical. Token counts: 1k–500k per session.
- Phase count: ~12 (matches existing IngestionPhase enum).
- LLM call sites touched: ~40 across the ingestion phases (every `llm.invoke(...)` / `ainvoke(...)`, plus the FR-017 retry stack, plus bulk-flush wrappers from 018).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Evidence |
|---|---|---|
| I. Graph-as-Source-of-Truth | ✅ PASS | No Neo4j schema changes; token totals are transient session state. Suspend MUST NOT lose persisted work (FR-010), preserving the graph as the single source of truth. |
| II. Event Storming Vocabulary | ✅ PASS | Feature is infrastructure (telemetry + cancellation); no domain-language additions. SSE field names (`tokens`, `suspendState`) describe runtime state, not domain entities. |
| III. Streaming-First UX | ✅ PASS | Token counter relies on the existing SSE stream — extends the `progress` event with two optional fields. Suspend state is also surfaced via SSE. No request/response polling introduced. |
| IV. Human-in-the-Loop on Mutations | ✅ PASS | Suspend is a user-initiated action; gate is cooperative (waits for explicit click). Token counter is read-only display. No autonomous mutations introduced. |
| V. Feature-Modular Architecture | ✅ PASS | All changes scoped to `api/features/ingestion/` (token callback, suspend gate utility, phase wrap-throughs) and `frontend/src/features/requirementsIngestion/`. No cross-feature imports. |
| VI. Provider-Agnostic LLM Runtime | ✅ PASS | Token capture goes through LangChain's standardized `usage_metadata` (works on OpenAI/Anthropic/Google adapters identically). The `tiktoken` fallback is only invoked when `usage_metadata` is absent and is itself provider-agnostic. The suspend gate is in pure Python — provider-independent. |
| VII. Observable by Default | ✅ PASS | New SmartLogger categories: `ingestion.tokens.call` (per-call ledger; debug-level), `ingestion.tokens.session_total` (per-phase summary), `ingestion.suspend.gate` (each gate firing with phase context). All carry the existing correlation ID. |

**Initial Constitution gate: PASS — no exceptions claimed.**

## Project Structure

### Documentation (this feature)

```text
specs/017-ingestion-tokens-and-suspend/
├── plan.md              # This file
├── research.md          # Phase 0 — D1..D5 decisions (already complete)
├── data-model.md        # Phase 1 — IngestionSession deltas + SSE field shapes
├── quickstart.md        # Phase 1 — manual smoke steps
├── contracts/
│   └── sse-events.md    # Phase 1 — extended progress event schema
└── tasks.md             # NOT created here; produced by /speckit-tasks
```

### Source Code (repository root)

```text
api/
├── features/
│   └── ingestion/
│       ├── ingestion_llm_runtime.py           # MODIFY — bind token-tally callback per session
│       ├── ingestion_sessions.py              # MODIFY — add tokens_total / tokens_by_phase /
│       │                                       #         tokens_approximate / tokens_last_call /
│       │                                       #         suspend_state fields to IngestionSession
│       ├── suspend_gate.py                    # NEW — `session_call_slot()` async ctx manager
│       ├── token_callback.py                  # NEW — LangChain BaseCallbackHandler
│       ├── ingestion_workflow_runner.py       # MODIFY — emit tokens/suspendState on progress
│       │                                       #         events; transition suspend_state machine
│       ├── router.py                          # MODIFY — /cancel endpoint flips suspend_state to
│       │                                       #         "suspending"
│       └── workflow/
│           └── phases/                         # MODIFY (each phase) — wrap LLM calls with
│               ├── user_stories.py             # session_call_slot(); wrap bulk-flush calls too
│               ├── events.py                   # (so 018's bulk writes are gated, not just LLM)
│               ├── commands.py
│               ├── aggregates.py
│               ├── policies.py
│               ├── readmodels.py
│               ├── ui_wireframes.py             # also gate _render_jsx & FR-017 retries
│               ├── gwt.py
│               ├── bounded_contexts.py
│               ├── events_from_user_stories.py
│               ├── link_command_to_events.py
│               ├── user_story_sequencing.py
│               └── _suspend_gate_stub.py        # DELETE — was placeholder; now real
├── platform/
│   └── env.py                                  # MODIFY — `LLM_TOKENIZER_FALLBACK` env (optional)
└── (no new platform modules)

frontend/
└── src/
    └── features/
        └── requirementsIngestion/
            └── ui/
                └── RequirementsIngestionModal.vue  # MODIFY — read tokens / suspendState from
                                                    #         progress events; render chip; show
                                                    #         "suspending..." mid-state
```

**Structure Decision**: Backend-heavy, thin frontend. All new logic lives under `api/features/ingestion/` (per Constitution V), composed of two new files (`suspend_gate.py`, `token_callback.py`) and edits to ~14 existing phase files plus the runtime wiring. Frontend changes are confined to one Vue component since the SSE additions are field-level (no new event types).

## Cross-cutting: interaction with 018 (Ingestion Batch Persist)

Spec 018 replaced ~7 ingestion phases' per-row Neo4j MERGE with one `bulk_create_<entity>` call per phase (or per Aggregate sub-batch). Spec 017's suspend gate must wrap **both**:

1. Each LLM call (the original spec 017 contract).
2. Each bulk-flush call (`ctx.client.bulk_create_*` / `bulk_link_*` / `bulk_set_*`).

This is because 018's flush is now the dominant *non-LLM* I/O along with wireframe-service calls — a suspend that arrives between LLM finish and bulk flush should still halt the flush (per FR-005's "no further side effects after suspend").

Spec 018 already created a no-op stub at `api/features/ingestion/_suspend_gate_stub.py` exactly so this integration would be one-line per call site. The 017 implementation replaces that stub with the real `suspend_gate.session_call_slot` and updates the imports.

The 018 plan.md already notes this composition (§ "Cross-cutting: interaction with 017"); 017's plan re-confirms it from the other side.

## Cross-cutting: interaction with 016 (Figma Document Binding)

Spec 016 introduced the FR-017 reliability retry stack (transport-level / agent fallback / wrapper retry) for `_render_jsx` calls. Spec 017's gate fires **inside** each retry — so a suspended session's retries exit cleanly within 5 s instead of grinding through the worst-case ~24-minute retry chain.

Spec 016 also introduced `bulk_sync.sync_batch` for FigmaBinding. Its per-UI loop's `send_and_wait` plugin transport is a natural cancel boundary; the 017 gate goes in front of each `send_and_wait`.

## Complexity Tracking

> Constitution Check passed without exceptions; no complexity violations to justify.

## Phase 0 — Research (status: COMPLETE)

See [research.md](research.md). Five decisions documented:

- **D1** — Provider-agnostic token capture via LangChain `BaseCallbackHandler` + `usage_metadata`.
- **D2** — `tiktoken` fallback when `usage_metadata` absent; flag `approximate=True`.
- **D3** — `async with session_call_slot(session):` cooperative cancellation pattern.
- **D4** — Extend existing `progress` SSE event with optional `tokens` and `suspendState` fields (no new event types).
- **D5** — Token totals are transient (session-lifetime); cross-session aggregation is a future feature.

Plus two cross-cutting notes — interaction with the 016 FR-017 retry stack and with 016's bulk_sync.

## Phase 1 — Design & Contracts (status: COMPLETE)

- [data-model.md](data-model.md) — IngestionSession field deltas (`tokens_total`, `tokens_by_phase`, `tokens_approximate`, `tokens_last_call`, `suspend_state`) and the suspend lifecycle state machine.
- [contracts/sse-events.md](contracts/sse-events.md) — extended `progress` event schema with `tokens` and `suspendState` fields. No new endpoints, no new event types.
- [quickstart.md](quickstart.md) — 5 manual verification steps covering live counter, suspend at boundary, suspend during fan-out, reconnect, and failure modes.

## Constitution Check (post-design)

Re-checked all 7 principles after Phase 1 artifacts. **Result: PASS — no new violations introduced.**

Specifically verified:

- The data-model lists no new Neo4j labels/properties/relationships → Principle I holds.
- The SSE contract preserves the existing event type and adds optional fields → Principle III (streaming-first) and backwards compatibility both hold.
- The suspend gate is described as cooperative; no force-cancel of in-flight LLM requests → consistent with Principle IV (no autonomous mutations beyond what the user explicitly clicked away from).
- Provider-agnostic capture confirmed via the `usage_metadata` decision → Principle VI holds.

## Out of Scope (locked in by this plan)

- Cost-in-currency display (token × price). A future feature.
- Cross-session aggregation reporting ("how much did I spend this week?"). A future feature; the design supports it additively (D5's note on how a future `:IngestionRun` node can be added).
- Resume of a suspended session. The spec is explicit: suspend is terminal.
- Mid-stream LLM provider request abort. Provider limitation; spec FR-005 explicitly accepts the in-flight call may finish.
- pytest unit test infrastructure bootstrap. Same status as 018 — deferred until a pytest harness lands repo-wide.

## Status

Phase 0 ✅ • Phase 1 ✅ • Constitution gates ✅ • Ready for `/speckit-tasks`.
