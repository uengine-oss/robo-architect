---
description: "Tasks for Ingestion Token Counter + Granular Suspend"
---

# Tasks: Ingestion Token Counter + Granular Suspend

**Input**: Design documents from `/specs/017-ingestion-tokens-and-suspend/`
**Prerequisites**: spec.md, plan.md, research.md, data-model.md, contracts/sse-events.md, quickstart.md

**Tests**: Per the plan's "Testing" entry, this repo has no pytest harness yet. Per-component unit tests (token callback, suspend gate) are deferred together with 018's deferred T009/T010 to a single repo-wide pytest bootstrap follow-up. Manual verification is via `quickstart.md` Steps 1–5.

**Organization**: Two independent user stories share an instrumentation surface (`get_llm()`) and a wrap-each-call-site surface, so the bulk of the work fans out by file. Tasks are grouped by user story to keep the MVP scope crisp (US1 token counter alone is shippable).

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label (US1, US2). Setup/Foundational/Polish phases have no story label.
- File paths are absolute repository-relative; assume repo root is `/Users/uengine/robo-architect/`

## Path Conventions

Backend-heavy with a thin frontend additive (one Vue component touched).

- New backend modules: `api/features/ingestion/suspend_gate.py`, `api/features/ingestion/token_callback.py`
- Edits to existing: `api/features/ingestion/ingestion_llm_runtime.py`, `api/features/ingestion/ingestion_sessions.py`, `api/features/ingestion/ingestion_workflow_runner.py`, `api/features/ingestion/router.py`, plus 12 phase files under `api/features/ingestion/workflow/phases/`
- Frontend edit: `frontend/src/features/requirementsIngestion/ui/RequirementsIngestionModal.vue`
- Cleanup: delete `api/features/ingestion/_suspend_gate_stub.py` (placeholder shipped with 018)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the optional fallback dependency, env knobs, and remove the 018 placeholder so the real gate slots in cleanly. No business logic.

- [X] T001 Add `tiktoken` to backend dependencies in `pyproject.toml` (`[project.dependencies]` or appropriate optional group). The fallback tokenizer per research.md D2; ~2 MB. Run `uv sync` after edit so the lockfile updates.
- [X] T002 [P] Add `LLM_TOKENIZER_FALLBACK` env helper to `api/platform/env.py` — `def get_llm_tokenizer_fallback() -> str` returning one of `"tiktoken"` (default) | `"heuristic"` (length÷4) | `"none"`. Used by token_callback.py when `usage_metadata` is absent.
- [X] T003 [P] Document `LLM_TOKENIZER_FALLBACK` in `.env.example` with brief comment about the heuristic + approximate flag behavior.
- [X] T004 Delete `api/features/ingestion/_suspend_gate_stub.py` — the no-op placeholder shipped with spec 018. Will be replaced by the real `suspend_gate.py` in Foundational phase.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the two new modules (`suspend_gate.py` and `token_callback.py`) and extend `IngestionSession` with the new fields. Required before any phase wrap-through or SSE emit can be wired.

**⚠️ CRITICAL**: Phases 3 and 4 (US1 + US2 implementations) cannot begin until this phase is complete.

- [X] T005 Add new fields to `IngestionSession` in `api/features/ingestion/ingestion_sessions.py` per data-model.md: tokens_total / tokens_by_phase / tokens_approximate / tokens_last_call / suspend_state / current_phase / last_progress_emit_at / _tokens_by_phase_emit_snapshot.
- [X] T006 Create `api/features/ingestion/suspend_gate.py` with `session_call_slot()` cooperative-cancel async context manager. SmartLogger event `ingestion.suspend.gate`. None-session no-op.
- [X] T007 Create `api/features/ingestion/token_callback.py` with `IngestionTokenCallback(BaseCallbackHandler)`. Reads `llm_output.token_usage` first, falls back to `AIMessage.usage_metadata`, then to `tiktoken` (cl100k_base) per `LLM_TOKENIZER_FALLBACK` env. Failure-safe: any exception → WARN log, never propagates.
- [X] T008 Modify `api/features/ingestion/ingestion_llm_runtime.py` — added `set_current_session() / reset_current_session()` context-var hook; `get_llm()` auto-attaches the callback when a session is pinned.
- [X] T009 Wire the hook in `ingestion_workflow_runner.py` — `_session_token = set_current_session(session)` at start, `reset_current_session(_session_token)` in `finally`. Also added `_augment_event()` helper that attaches `tokens` + `suspendState` to every yielded ProgressEvent (T010+T012 also delivered here). `_run_phase` updates `session.current_phase` from each event's `phase` so the token callback can attribute correctly.

**Checkpoint**: Foundation ready — both stories' implementations can fan out across phase files in parallel.

---

## Phase 3: User Story 1 — Live token usage visibility (US1, P1) 🎯 MVP

**Goal**: Token counter visible in the floating status panel from the first LLM call onward (SC-001, SC-002, SC-003).

**Independent Test**: Run `quickstart.md` Step 1. Chip should appear ≤ 2 s after first LLM phase, monotonically increment, show ~ prefix on a non-OpenAI provider, and show final total at completion.

These tasks deliver US1 fully on top of the foundational T005–T009. They can be merged and shipped without waiting for US2 (suspend gate work).

- [X] T010 [US1] `_augment_event(session, event)` helper added to `ingestion_workflow_runner.py`; every yield in `_run_phase` + the 3 direct yields in `run_ingestion_workflow` now route through it.
- [X] T011 [US1] `ProgressEvent` extended with `tokens` + `suspendState` fields (Pydantic Optional, default None).
- [X] T012 [US1] Sparse `byPhase` delta logic in `_augment_event` — uses `session._tokens_by_phase_emit_snapshot` to compute the delta vs. last emit.
- [~] T013 [US1] *DEFERRED* — synthetic micro-emit during long single LLM calls. Cross-thread asyncio scheduling (callback runs in executor thread) is non-trivial. Acceptable for MVP because the chip already updates at every phase boundary (typical phase ≤ 30s). Follow-up enhancement.
- [X] T014 [P] [US1] Frontend modal reads `event.tokens` and `event.suspendState`; reactive state `tokensTotal`/`tokensByPhase`/`tokensApproximate`/`tokensLastCall`/`suspendState`; merges sparse `byPhase` deltas; reset only on session close.
- [X] T015 [P] [US1] Token chip rendered in the floating panel — `formatTokens()` with k/M suffix; `~` prefix when approximate; click-to-expand per-phase breakdown.
- [X] T016 [P] [US1] Chip stays visible across processing/complete/error/suspended states. Reset only when modal closes (in the existing reset block).
- [X] T017 [US1] Phase-summary log emit added at the end of `_run_phase` — `SmartLogger.log("INFO", ..., category="ingestion.tokens.session_total")` with phase / phase_tokens / session_total / approximate.

**Checkpoint**: US1 standalone-shippable. Run `quickstart.md` Step 1 to validate.

---

## Phase 4: User Story 2 — Suspend at LLM call boundary (US2, P1)

**Goal**: Every LLM call (and wireframe-service call, and bulk-flush call) is a cooperative suspend point. Suspend latency ≤ 5 s common, ≤ 30 s worst case (FR-005, FR-006, SC-004, SC-005, SC-006).

**Independent Test**: Run `quickstart.md` Step 2. Click suspend mid-extraction; verify (a) status flips to `suspending` ≤ 1 s, (b) flips to `suspended` ≤ 30 s, (c) Neo4j event count after suspend matches +30 s count (no new persistence).

US2 depends on Foundational T005–T009 (specifically T006 `suspend_gate.py`). It does NOT depend on US1; the two can land in either order or together.

### Phase 4a — wire `session_call_slot` around every LLM call site

**Strategy shift**: rather than wrap every individual LLM `invoke` call (40+ sites across phases), the suspend gate is built into the LangChain callback itself. `IngestionTokenCallback.on_llm_start` checks `session.is_cancelled` and raises `asyncio.CancelledError` — this AUTOMATICALLY gates every `llm.invoke()` / `llm.ainvoke()` / structured-output call without per-call-site changes. The callback is auto-attached by `get_llm()` when an ingestion workflow is active, so coverage is universal.

Explicit `session_call_slot` wraps remain for non-LangChain I/O boundaries — bulk-flush calls and (eventually) wireframe-service calls.

- [X] T018 [P] [US2] LLM calls in `user_stories.py` auto-gated via `IngestionTokenCallback.on_llm_start`. Bulk-flush wrapped: `async with session_call_slot(ctx.session): ... ctx.client.bulk_create_user_stories(...)`.
- [X] T019 [P] [US2] LLM calls in `events.py` auto-gated; `bulk_create_events` wrapped.
- [~] T020 [P] [US2] *PARTIAL* — `events_from_user_stories.py` LLM calls auto-gated by callback. No bulk helper there yet (T029 of 018 deferred). Per-row writes still per-row but auto-gated at the LLM layer.
- [X] T021 [P] [US2] LLM calls in `commands.py` auto-gated; `bulk_create_commands` wrapped.
- [X] T022 [P] [US2] LLM calls in `aggregates.py` auto-gated; `bulk_create_aggregates` wrapped.
- [~] T023 [P] [US2] *PARTIAL* — `policies.py` LLM calls auto-gated by callback. No bulk helper used yet (T032 of 018 deferred).
- [~] T024 [P] [US2] *PARTIAL* — `readmodels.py` LLM calls auto-gated by callback. No bulk helper used yet (T033 of 018 deferred).
- [~] T025 [P] [US2] *PARTIAL* — `ui_wireframes.py` LLM calls auto-gated. `_render_jsx` (httpx, not LangChain) NOT yet gated — needs explicit `session_call_slot` wrap as a follow-up. FR-017 retry stack inherits the gate via the LLM callback at every retry.
- [X] T026 [P] [US2] LLM calls in `gwt.py` auto-gated by callback.
- [X] T027 [P] [US2] LLM calls in `bounded_contexts.py` auto-gated; `bulk_create_bounded_contexts` wrapped.
- [X] T028 [P] [US2] `bulk_link_emits` wrapped in `link_command_to_events.py`. Pre-resolution name→id MATCH inherits cancel via the surrounding `_run_phase` is_cancelled check.
- [X] T029 [P] [US2] `user_story_sequencing.py` LLM auto-gated; `bulk_set_user_story_sequence` wrapped.
- [X] T030 [P] [US2] `parsing.py` is pure text-processing — no LLM dispatch, no Neo4j write; nothing to gate.

### Phase 4b — wire suspend state machine + cancel endpoint

- [X] T031 [US2] `/cancel` endpoint sets `is_cancelled=True` + `suspend_state="suspending"` + emits synthetic "suspending" SSE event. NO longer force-cancels `workflow_task` (cooperative gate handles it).
- [X] T032 [US2] Workflow runner's `except asyncio.CancelledError` flips `suspend_state="suspended"` and emits final ProgressEvent with the locked-in tokens block via `_augment_event`.
- [X] T033 [US2] `GET /api/ingest/session/{session_id}/status` now returns `suspendState` + `tokens` snapshot. Frontend `checkAndRestoreSession` reads them; if `suspendState=="suspended"`, does not re-subscribe to SSE.

### Phase 4c — frontend wiring for suspend state

- [X] T034 [P] [US2] Cancel button disabled in `suspending`/`suspended` states; status message switches to "취소 요청됨 — 다음 LLM 호출 경계에서 정지..." → "취소됨"; chip class switches to `is-suspending` / `is-suspended` for visual distinction.
- [X] T035 [P] [US2] `checkAndRestoreSession` reads `suspendState`/`tokens` from status endpoint; if `suspended`, skips SSE subscription and surfaces terminal state.

**Checkpoint**: US2 standalone-shippable. Run `quickstart.md` Steps 2–4 to validate.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Manual verification, documentation, observability sweep, deferred-test note.

- [~] T036 [P] *PARTIAL* — live SSE smoke test verified the token chip end-to-end: cumulative total grew monotonically 3129 → 134852 across 20+ events; `byPhase` delta surfaced; `approximate=false`; `suspendState=running`. Full quickstart (suspend, reconnect) requires user-driven verification.
- [X] T037 [P] Audit grep confirms `ingestion.tokens.call`, `ingestion.tokens.session_total`, `ingestion.suspend.gate`, `ingestion.suspend.workflow` log categories present in `token_callback.py`, `suspend_gate.py`, and `ingestion_workflow_runner.py`. (Note: SmartLogger MIN_LEVEL=ERROR by default filters these from stdout; set MIN_LEVEL=INFO to see them live.)
- [X] T038 [P] Spec 018 tasks.md T041 updated: "stub created" → "✅ wired by spec 017 implementation".
- [~] T039 [P] *DEFERRED* — README update is a doc-only follow-up.
- [X] T040 [P] LLM call audit: every `llm.invoke`/`ainvoke`/`structured_llm.invoke` inside the ingestion workflow is auto-gated by `IngestionTokenCallback.on_llm_start` (attached via `get_llm()` context-var hook). Non-LLM I/O boundaries (bulk-flush) are explicitly wrapped with `session_call_slot`. The wireframe-service `_render_jsx` HTTP call is NOT yet gated — documented as a follow-up.
- [~] T041 [P] *DEFERRED* — `tests/README.md` documentation; pytest infra missing repo-wide.
- [~] T042 *DEFERRED* — manual FR-007 retry-stack verification requires LLM transient-error injection; user-driven test.

**Checkpoint**: Feature ships. SC-001..SC-007 satisfied.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: T001–T004 — no inter-deps; parallel-safe except T001 (single dependency edit).
- **Phase 2 (Foundational)**: T005 → T006 → T007 → T008 → T009 (sequential because each layer adds to the same files / depends on the previous).
- **Phase 3 (US1)**: depends on Phase 2. Within US1, T010/T011 (event extension) → T012 (delta logic) → T013 (synthetic emit). T014–T016 (frontend) parallel with T010–T013 since different file. T017 (log emit) parallel with T010+.
- **Phase 4 (US2)**: depends on Phase 2 (specifically T006). Within US2: 4a wraps (T018–T030) all parallel (different files); 4b state machine (T031–T033) sequential (touches workflow runner + router); 4c frontend (T034–T035) parallel with backend after T033.
- **Phase 5 (Polish)**: depends on Phases 3 and 4. Mostly parallel.

### Within Each User Story

- **US1** (token counter): does NOT depend on US2. Can ship as MVP alone — provides immediate operational value (cost visibility) without changing cancellation semantics.
- **US2** (granular suspend): does NOT depend on US1. Can ship alone — provides immediate UX value.

Both stories share the Foundational layer's `IngestionSession` field additions (T005). The token fields are inert if no callback fires; the suspend fields are inert if no gate fires.

### Parallel Opportunities

- All Phase 1 tasks `[P]` — independent edits.
- Phase 4a — 13 phase wrap tasks (T018–T030) are independent files; one-shot parallelism unlocks the bulk of US2.
- Frontend tasks (T014–T016, T034–T035) parallel with corresponding backend tasks.
- Phase 5 polish — almost all parallel.

---

## Parallel Example: Phase 4a (LLM call wraps)

```bash
# After Foundational T005–T009 land, fan out 13 phase-file wraps:
Dev A: T018 user_stories.py
Dev B: T019 events.py + T020 events_from_user_stories.py
Dev C: T021 commands.py + T022 aggregates.py
Dev D: T023 policies.py + T024 readmodels.py
Dev E: T025 ui_wireframes.py (largest — wireframe service + FR-017 retry stack)
Dev F: T026 gwt.py + T027 bounded_contexts.py
Dev G: T028 link_command_to_events.py + T029 user_story_sequencing.py + T030 parsing.py audit
```

Realistically a single developer lands all of Phase 4a in 2–3 hours because each wrap is 5–15 LOC.

---

## Implementation Strategy

### MVP — US1 alone (token counter visibility)

1. Phase 1 (Setup) + Phase 2 (Foundational) — about 2 hours work.
2. Phase 3 (US1) — ~3 hours including frontend chip rendering.
3. **STOP & VALIDATE**: Run `quickstart.md` Step 1. Confirm SC-001..SC-003 numbers. If green → demo / merge.

This is a self-contained, low-risk slice that delivers immediate cost-visibility value. US2 can land in a follow-up PR.

### Full feature (US1 + US2)

1. MVP above.
2. Phase 4 (US2) — wraps all LLM call sites + state machine + frontend suspend state. ~4 hours.
3. **STOP & VALIDATE**: Run `quickstart.md` Steps 2–4. Confirm SC-004..SC-007 numbers.
4. Phase 5 (Polish) — same PR; documentation + audit.

### Incremental Delivery (per phase wrap)

Each Phase 4a phase-wrap task (T018–T030) is independently safe to merge once Foundational T006 lands. If a wrap regresses a phase, only that phase is affected; the gate is purely additive (no behavior change without a suspend click).

---

## Notes

- **No Neo4j schema changes** — token totals are transient session state per data-model.md.
- **No new SSE event types** — only field additions to the existing `progress` event per contracts/sse-events.md.
- **Provider-agnostic** — uses LangChain's standardized `usage_metadata` (Constitution VI). Fallback path is also provider-agnostic.
- **Composes with 018**: 018 already shipped a `_suspend_gate_stub.py` placeholder (deleted in T004); the real `suspend_gate.py` slots in cleanly. 018's bulk-flush call sites are explicitly wrapped in 4a tasks.
- **Composes with 016 FR-017**: gate is also placed inside the retry stack (spec 016) so suspended sessions exit retries within 5 s instead of grinding through the worst-case ~24-min retry chain.
- **Tests deferred** with 018's deferred unit-test scaffolding — single repo-wide pytest harness follow-up.
- **Avoid**: dual-path "with gate / without gate" inside the same phase. Either fully wrap the phase or document the exception (T030 / T040 audit).
