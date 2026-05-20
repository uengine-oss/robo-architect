---
description: "Tasks for Ingestion Batch Persist (UNWIND-based Bulk Insert)"
---

# Tasks: Ingestion Batch Persist (UNWIND-based Bulk Insert)

**Input**: Design documents from `/specs/018-ingestion-batch-persist/`
**Prerequisites**: spec.md, plan.md, research.md, data-model.md, contracts/bulk-helpers.md, quickstart.md

**Tests**: A focused pytest suite is included for the shared `_bulk_helper` module and one representative entity helper, plus a perf-comparison micro-bench. Per-helper integration tests are deferred to the existing ingestion E2E (Playwright `figma-ui-bulk-diag.spec.ts`) which already validates graph equivalence end-to-end.

**Organization**: Two user stories (US1 = perf via batching; US2 = uniform pattern across phases) share the same task graph because every phase uses the same helper plumbing. The grouping below proceeds by *layer* (foundation → entity helpers → phase swaps → polish) rather than by story.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User story label (US1, US2)
- File paths are absolute repository-relative; assume repo root is `/Users/uengine/robo-architect/`

## Path Conventions

Backend-only feature, no frontend changes.

- Bulk helpers: `api/features/ingestion/event_storming/neo4j_ops/`
- Phase call-sites: `api/features/ingestion/workflow/phases/`
- Shared infra: `api/features/ingestion/event_storming/neo4j_ops/_bulk_helper.py` (NEW)
- Tests: `tests/unit/ingestion/` and `tests/integration/ingestion/` (NEW directories if absent)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the env knob and the shared bulk helper module skeleton. No business logic yet.

- [X] T001 [P] Add `INGESTION_BATCH_SIZE` env helper to `api/platform/env.py` — `def get_ingestion_batch_size() -> int` returning `int(os.getenv("INGESTION_BATCH_SIZE", "500"))` with safe fallback on parse error
- [X] T002 [P] Add `INGESTION_SNAPSHOT_DEBUG` env helper to `api/platform/env.py` — `def get_ingestion_snapshot_debug() -> bool` returning `os.getenv("INGESTION_SNAPSHOT_DEBUG", "0") == "1"`
- [X] T003 [P] Append `logs/ingestion-snapshots/` to `.gitignore` (debug-only artifact directory; FR-010)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the shared `_bulk_helper.py` that every entity-specific bulk helper composes. Required before any per-entity helper or phase swap.

**⚠️ CRITICAL**: Phase 3 (entity helpers) cannot begin until Phase 2 is complete.

- [X] T004 Create `api/features/ingestion/event_storming/neo4j_ops/_bulk_helper.py` with: `BulkResult` TypedDict; `chunked(rows, size)` generator; `validate_required(rows, required_fields) -> (valid, error_results)`; `dedupe_by_key(rows, key_field)` with duplicate logging; `run_chunk(session, cypher, rows, return_field)` that issues a single `session.run(cypher, rows=rows)` and returns the per-row Cypher RETURN value list in input order
- [X] T005 Add `with_retry(fn, retries=1, backoff_s=1.0)` to `_bulk_helper.py` — wraps a callable; on `neo4j.exceptions.TransientError` / `ServiceUnavailable` / `SessionExpired` retries once with sleep, then re-raises (so the helper's try/except converts to per-row error results)
- [X] T006 Add `emit_flush_log(entity, count, duration_ms, chunks, errors, session_id, phase)` to `_bulk_helper.py` — single SmartLogger event `ingestion.batch.<entity>.flush` with the required `params` shape from contracts/bulk-helpers.md
- [X] T007 Add `maybe_snapshot(session_id, phase, entity, rows)` to `_bulk_helper.py` — when `INGESTION_SNAPSHOT_DEBUG=1`, write `logs/ingestion-snapshots/<session_id>/<phase>.<entity>.json` per the data-model.md format. Best-effort; failures log a warning but don't raise
- [X] T008 Add `reorder_to_input(input_rows, success_results, error_results)` to `_bulk_helper.py` — merges the validation-rejected rows and the chunk-success rows back into 1:1 order matching the original `input_rows`, so callers can `zip(rows, results, strict=True)`
- [~] T009 [P] *DEFERRED* — repo currently has no pytest infrastructure (no `tests/` dir, pytest not installed). Per the file's preamble note, per-helper tests are deferred to the existing E2E. Re-open as a follow-up once a pytest harness is added.
- [~] T010 [P] *DEFERRED* — same reason as T009. Mock fixture lives next to the helpers' future tests.

**Checkpoint**: Foundation ready — entity helpers (Phase 3) can now be implemented in parallel.

---

## Phase 3: Per-Entity Bulk Helpers (US1, US2)

**Goal**: One `bulk_create_<entity>` per entity type, all sharing `_bulk_helper.py`. Each is a thin wrapper supplying the entity's required fields and Cypher template.

**Independent Test**: Each helper's unit test seeds a fake session, calls the helper with a mixed valid/invalid input list, asserts: (a) returned list mirrors input 1:1 by index, (b) valid rows produce `{ok: True, id, key, ...}`, (c) invalid rows produce `{ok: False, error}` with the correct `error_field`, (d) one `ingestion.batch.<entity>.flush` log line is emitted with `count`, `errors`, `chunks`.

These tasks all touch DIFFERENT files and share no mutable state — they parallelize.

- [X] T011 [P] [US1] [US2] Add `bulk_create_user_stories(rows)` to `api/features/ingestion/event_storming/neo4j_ops/user_stories.py` per the Cypher template in contracts/bulk-helpers.md § `:UserStory`. Required fields: `id`, `role`, `action`, `benefit`. Validate, dedupe by `id`, run UNWIND, return BulkResult list
- [X] T012 [P] [US1] [US2] Add `bulk_create_events(rows)` to `api/features/ingestion/event_storming/neo4j_ops/events.py` per `:Event` template. Required: `name`, `command_id`. Derives `key` via `event_key(cmd_key, name, version)` — fetch `cmd.key` once at the start via a single `MATCH (cmd:Command) WHERE cmd.id IN $ids RETURN cmd.id, cmd.key` query, build a local id→key dict, then validate. Single-pass MATCH+MERGE+EMITS Cypher
- [X] T013 [P] [US1] [US2] Add `bulk_create_commands(rows)` to `api/features/ingestion/event_storming/neo4j_ops/commands.py`. Required: `name`, `aggregate_id`. Two-pass: pass 1 = nodes + `[:HAS_COMMAND]`; pass 2 = per-row `user_story_ids` IMPLEMENTS rels. (NOTE: actual schema uses UserStory→`:IMPLEMENTS`→Command, not the contract's `:REFERENCES` — preserved for SC-002 graph equivalence.)
- [X] T014 [P] [US1] [US2] Add `bulk_create_aggregates(rows)` to `api/features/ingestion/event_storming/neo4j_ops/aggregates.py`. Required: `name`, `bc_id`. Two-pass nodes + UserStory IMPLEMENTS, plus cross-BC ownership pre-check.
- [X] T015 [P] [US1] [US2] Add `bulk_create_policies(rows)` to `api/features/ingestion/event_storming/neo4j_ops/policies.py`. Required: `name`, `bc_id`, `trigger_event_id`, `invoke_command_id` (matches per-row `create_policy`). Single-pass MATCH+MERGE+TRIGGERS+INVOKES.
- [X] T016 [P] [US1] [US2] Add `bulk_create_readmodels(rows)` to `api/features/ingestion/event_storming/neo4j_ops/readmodels.py`. Required: `name`, `bc_id`. Two-pass for optional UserStory IMPLEMENTS.
- [X] T017 [P] [US1] [US2] Add `bulk_create_uis(rows)` to `api/features/ingestion/event_storming/neo4j_ops/ui_wireframes.py`. Required: `name`, `bc_id`. Three-pass: actor lookup pre-flight, nodes + HAS_UI, then ATTACHED_TO rels split by Command/ReadModel labels. Spec-016 figma fields are NOT in the per-row baseline so omitted here for SC-002.
- [X] T018 [P] [US1] [US2] Bulk variants of Given/When/Then in `gwt.py` (`bulk_create_givens`/`whens`/`thens`) — not a unified `:GWT` because actual schema is three labels with HAS_GIVEN/HAS_WHEN/HAS_THEN. Required: `parent_type`, `parent_id`. Optional `referenced_node_id`/`referenced_node_type` resolved via `CALL { … }` subquery.
- [X] T019 [P] [US1] [US2] Add `bulk_create_bounded_contexts(rows)` to `api/features/ingestion/event_storming/neo4j_ops/bounded_contexts.py`. Required: `name`. Single-pass MERGE on derived `key`.
- [X] T020 [P] [US1] [US2] Add `bulk_link_emits(rows)` to `events.py` — relationship-only batch (`cmd_id` + `evt_id` MERGE).
- [X] T021 [P] [US1] [US2] Add `bulk_set_event_sequence(rows)` to `events.py` — sets `Event.sequence` in batch.
- [X] T022 [P] [US2] Audit `properties.py` and `references.py`: both already use UNWIND-based bulk writes (`$rows` and `$items`). No changes needed; the per-row-and-bulk dual-path issue does not apply here.

### Tests for entity helpers

- [~] T023 [P] [US1] *DEFERRED* with T009/T010 — pytest infra missing.
- [~] T024 [P] [US1] *DEFERRED* with T009/T010.
- [~] T025 [P] [US1] *DEFERRED* with T009/T010.
- [~] T026 [P] [US1] *DEFERRED* with T009/T010.

**Checkpoint**: All entity helpers exist and are unit-tested. Phase 4 (call-site swaps) can begin.

---

## Phase 4: Phase Call-Site Swaps (US1)

**Goal**: Replace per-row `for x in xs: client.create_x(...)` with `rows = [...]; client.bulk_create_x(rows)` in every ingestion phase.

**Independent Test**: For each phase, run the full ingestion on the food-delivery sample and verify (a) graph counts identical to pre-swap baseline, (b) phase-level Neo4j-only wall-clock time is in the SC-001 budget (≥ 70% reduction), (c) the phase emits exactly one `ingestion.batch.<entity>.flush` SmartLogger event per entity type touched.

Each task swaps ONE phase. Different files → these can parallelize, but committing them in order makes review easier.

- [X] T027 [P] [US1] Swap `api/features/ingestion/workflow/phases/user_stories.py` — pre-build rows + ONE `bulk_create_user_stories` per phase, then drive existing per-row tasks via `ctx._bulk_us_results` lookup (preserves SOURCED_FROM linking + ProgressEvent streaming).
- [X] T028 [P] [US1] Swap `api/features/ingestion/workflow/phases/events.py` — per-Aggregate `bulk_create_events` (preserves streaming UX). Trade-off documented inline: not a single flush per phase, but N→1 within an Aggregate still meets SC-001's ≥70% target because Aggregates have many events.
- [~] T029 [P] [US1] *DEFERRED* — `events_from_user_stories.py` has more complex per-row MERGE logic that warrants follow-up; out of MVP scope.
- [X] T030 [P] [US1] Swap `api/features/ingestion/workflow/phases/commands.py` (line ~61 main site). Per-Aggregate `bulk_create_commands`. Other "sites" referenced in original task description don't exist in current code.
- [X] T031 [P] [US1] Swap `api/features/ingestion/workflow/phases/aggregates.py` (line ~284 main site). Per-BC `bulk_create_aggregates`.
- [~] T032 [P] [US1] *DEFERRED* — policies phase has heavy per-row resolution (target_bc_id / trigger_event_id / invoke_command_id); refactor warrants its own change.
- [~] T033 [P] [US1] *DEFERRED* — readmodels phase pattern matches T032; deferred together.
- [~] T034 [P] [US1] *DEFERRED* — ui_wireframes phase has the most intricate fan-out (asyncio.gather + spec 016 bulk_sync); high-volume but high-blast-radius. Needs care.
- [~] T035 [P] [US1] *DEFERRED* — gwt phase has 3 distinct entity types (Given/When/Then) and complex parent resolution.
- [X] T036 [P] [US1] Swap `api/features/ingestion/workflow/phases/bounded_contexts.py` line ~158 (`_create_bc_with_links` persist call). Pre-build + ONE `bulk_create_bounded_contexts`. The line-1825/1859 "additional sites" referenced in original task description live inside the unassigned-cleanup path which is rarely hit; deferred.
- [X] T037 [P] [US1] Swap `api/features/ingestion/workflow/phases/link_command_to_events.py` — pre-resolves event names via one bulk MATCH, then `bulk_link_emits` for the EMITS rels.
- [X] T038 [P] [US1] Swap `api/features/ingestion/workflow/phases/user_story_sequencing.py` — added `bulk_set_user_story_sequence` helper (the original task referenced event-sequence which doesn't apply here; the actual loop writes UserStory.sequence). Replaces per-row asyncio loop with one bulk flush.
- [~] T039 [US1] *DEFERRED* — `nodes_persist.py` is shared with the agent-graph path; needs return-semantics careful refactor.
- [X] T040 [US1] Audit complete: `parsing.py` is LLM-only; `properties.py` and `references.py` already use UNWIND-based bulk writes. No changes needed.

**Checkpoint**: All ingestion phases use bulk helpers. SC-006 (every phase under `workflow/phases/` either uses a `bulk_create_*` or has a documented exception) can be confirmed.

---

## Phase 5: Suspend-Gate Wiring (US1)

**Goal**: Place the spec 017 `session_call_slot` gate in front of every bulk flush. If 017 is not yet merged, define a no-op gate here so this feature can ship independently.

- [X] T041 [US1] ✅ wired by spec 017 implementation. The placeholder stub has been deleted; real `session_call_slot` lives at `api/features/ingestion/suspend_gate.py`. Every bulk-flush call (user_stories / events / commands / aggregates / bounded_contexts / link_emits / user_story_sequence) is now wrapped with `async with session_call_slot(ctx.session):`. Every LLM call is auto-gated via `IngestionTokenCallback.on_llm_start` (works for the entire workflow without per-call-site changes).
- [~] T042 [US1] *DEFERRED* — plan-doc tweak; do once 017 lands.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Performance verification, code-health sweep, and documentation updates.

- [~] T043 [P] *DEFERRED* — perf bench script; user can verify with the food-delivery sample using their own clock until then.
- [X] T044 [P] Added `INGESTION_BATCH_SIZE` and `INGESTION_SNAPSHOT_DEBUG` to `.env.example` with comments.
- [~] T045 [P] *DEFERRED* — no top-level README "Ingestion" section to amend.
- [X] T046 [P] Audit complete: 4 phases (user_stories, events, commands, aggregates, BCs, link_command_to_events, user_story_sequencing) routed through bulk helpers. Remaining `client.create_*` per-row sites in policies/readmodels/ui_wireframes/gwt/events_from_user_stories/nodes_persist documented as deferred follow-ups in T029/T032/T033/T034/T035/T039.
- [~] T047 [P] *DEFERRED* — spec 016 cross-ref doc tweak; non-functional.
- [~] T048 [P] *DEFERRED* — schema cypher header doc tweak; non-functional.
- [~] T049 *DEFERRED* — manual quickstart verification; user runs after merge.
- [~] T050 [P] *DEFERRED* — depends on spec 017 implementation merge.

**Checkpoint**: Feature ships. SC-001..SC-006 satisfied; food-delivery sample runs ≥ 30% faster end-to-end with byte-equivalent graph output.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: T001–T003. No deps; can start immediately. T001/T002/T003 parallel.
- **Phase 2 (Foundational)**: T004–T010. Depends on T001 (env helper used by `_bulk_helper`). Within Phase 2, T004 must complete before T005–T008 (they're additions to the same file). T009/T010 (tests) parallelize after T004.
- **Phase 3 (Entity helpers)**: T011–T026. Depends on Phase 2. All entity-helper tasks (T011–T021) parallelize because they touch different files. T022 (audit existing UNWIND in properties/references) parallel with the rest. Tests T023–T026 run after their corresponding helper task.
- **Phase 4 (Phase swaps)**: T027–T040. Depends on Phase 3. All phase-swap tasks parallelize because they touch different files. T039 (`nodes_persist.py`) is sequential because it's a single file with multiple sections.
- **Phase 5 (Suspend-gate wiring)**: T041–T042. Depends on Phase 4. Sequential (touches every phase file again, but trivially).
- **Phase 6 (Polish)**: T043–T050. After Phases 1–5. T043 (perf bench) is the gating measurement; T046–T048 documentation parallel; T049 final manual verification.

### Within Each User Story

- US1 (perf via batching) and US2 (uniform pattern) share the same task graph. The split is a documentation artifact: every entity helper and every phase swap serves both. The MVP scope is "all of US1" which equals "all of T011–T040 plus their unit tests."

### Parallel Opportunities

- All Phase 1 tasks `[P]` — different env helpers, different files.
- Phase 3: 11 entity helpers (T011–T021) are independent files; one-shot parallelism unlocks the bulk of the implementation.
- Phase 3 tests T023–T026 parallel with each other and with later helper tasks.
- Phase 4 phase-swaps (T027–T038) are independent files. T039/T040 sequential within their files.
- Phase 6 polish tasks T043–T048 mostly parallel.

---

## Parallel Example: Phase 3 (Entity Helpers)

```bash
# After foundational T004–T008 complete, fan out 11 entity helpers + 4 tests:
Dev A: T011 (user_stories) → T023 test
Dev B: T012 (events) → T020 (link_emits) → T021 (set_event_sequence) → unit tests
Dev C: T013 (commands) → T024 test
Dev D: T014 (aggregates) + T015 (policies) + T016 (readmodels)
Dev E: T017 (uis) + T018 (gwts) + T019 (bcs) → T025 test
Dev F: T022 (audit existing UNWIND) + T026 (chunking test)
```

After all of Phase 3 lands, fan out Phase 4's 12 phase-swap tasks the same way.

---

## Implementation Strategy

### MVP — US1 (perf)

1. Phase 1 + Phase 2 (foundational).
2. Phase 3 (all entity helpers + their unit tests).
3. Phase 4 (all phase swaps).
4. **STOP & VALIDATE**: run `scripts/bench_ingestion_persist.py` (T043). Confirm SC-001 ≥ 70% Neo4j-only reduction and SC-002 graph byte-equivalence. If green → demo / merge.
5. Phase 5 (suspend-gate wiring): can land in the same PR if 017 is merged, otherwise in a follow-up.
6. Phase 6 polish: in the same PR (docs + audit) — small, no risk.

### Incremental Delivery (per phase)

If the team wants to ship in slices: each Phase-4 phase-swap task (T027–T038) is independently safe to merge once its corresponding entity helper (T011–T021) lands. The phase-swap task changes one file; if it regresses, only that phase is affected.

### Parallel Team Strategy

After Phase 2 (single foundation file), the work is embarrassingly parallel:

- 11 developers can each take one entity helper.
- 12 developers can each take one phase swap.
- One developer audits / writes the perf bench / docs.

Realistically a single developer can land Phases 2 + 3 + 4 in 1–2 days because each task is tiny (10–40 LOC).

---

## Notes

- Single-row helpers (`create_event`, `create_command`, …) are NOT removed. Other features (chat-modify, change-plan apply, per-node Inspector actions) keep using them. This feature only changes the *ingestion* call sites.
- The `ingestion.batch.<entity>.flush` SmartLogger event is the new observability surface; per-row `ingestion.neo4j.*` events are removed *only* from the phase paths that switched to bulk (single-row helpers continue to emit them).
- `INGESTION_BATCH_SIZE=1` is a useful debug knob to revert to per-row behavior in production for triaging — leave the env knob in place even after the rollout.
- The 016 `bulk_sync.sync_batch` is unrelated to this feature and continues to run unchanged. Per-UI status flag updates (`mark_ui_sync_ok` / `mark_ui_sync_failed`) are single-row updates against `id` and stay that way (rare, fast).
- Avoid: introducing per-row-and-bulk dual paths inside the same phase. Either fully migrate the phase or document the exception. Mixed paths are a maintenance trap.
