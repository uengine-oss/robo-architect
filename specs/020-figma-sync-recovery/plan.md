# Implementation Plan: Figma Sync Recovery & Retroactive Push

**Branch**: `020-figma-sync-recovery` (current working branch: `figma-integration`) | **Date**: 2026-05-08 | **Spec**: [./spec.md](./spec.md)
**Input**: Feature specification from `/specs/020-figma-sync-recovery/spec.md`

## Summary

Extend the existing **Figma 다큐먼트 연동** modal (built by spec 016) into a project-level recovery hub for Figma sync. Two surfaces are added inside the same modal:

1. **연결 상태 (Connection Status) tab** gains a primary action **"전체 Figma 반영"** that runs a *retroactive full sync* of the project — for every storyboard ensure a Figma page exists (reuses 016 `service.sync_storyboards`), for every UI without a sceneGraph generate one in figma-mode (reuses ingestion's `_generate_jsx_scene_graph_for_figma_mode`), and for every UI push a Figma frame into its storyboard's page (reuses 016 `service.push_frame_for_ui`). The action streams progress over SSE per Constitution III. While running, it holds a **project-scoped advisory lock** so a second collaborator can only join the progress view, never dispatch a competing run.

2. **이력 (History) tab** is rewritten from a flat audit log into the canonical recovery view: a **failure list** at the top (rows from the existing `:UI {figmaSyncStatus:'failed'}` store, with per-row "다시 시도" + a "전체 다시 시도" header button — both calling the existing `POST /api/figma-binding/retry-sync`) and **summary rows** beneath it (one row per `:SyncRun` with counts). Entries from a previously replaced binding (different `figmaFileKey`) render under a separated "이전 바인딩" group with retry controls disabled.

The implementation is strictly **additive** to 016. No parallel failure store is introduced — the per-`:UI` `figmaSyncStatus`/`figmaSyncLastError`/`figmaSyncLastAttemptAt` fields shipped by 016 v1.2 remain the single source of truth, shared by ingestion floating panel + Inspector Design tab badge + this new History tab. The new entity is `:SyncRun` (Neo4j node) which records a one-line summary per dispatched full-sync — it does NOT duplicate per-item events; success roll-up is computed at run-end and frozen, failures continue to live on `:UI`.

In-flight retry deduplication is server-side: `figma_binding.service` keeps a process-level `set[str]` of UI ids whose retry is in-flight; concurrent retries on the same id no-op (the second caller subscribes to the in-flight result rather than re-dispatching). The project-scoped sync lock is a `:FigmaBinding {currentRunId, currentRunHolder}` advisory pair (mutated atomically with a Cypher `WHERE binding.currentRunId IS NULL` guard) — nothing more elaborate is needed because there is one binding singleton per deployment.

## Technical Context

**Language/Version**: Python 3.11+ backend (FastAPI, async); Vue 3 + Vite frontend.
**Primary Dependencies**:
- Backend: existing `api/features/figma_binding/` (service / repository / bulk_sync), existing `api/features/ingestion/workflow/phases/ui_wireframes._generate_jsx_scene_graph_for_figma_mode`, `SmartLogger`, Neo4j driver.
- Frontend: existing `frontend/src/features/figmaBinding/` (api.js, store, FigmaBindingModal.vue), Pinia, EventSource for SSE.
- Plugin: NO changes required. 016's `CREATE_PAGE` / `CREATE_FRAME_IN_PAGE` messages remain the only plugin write surface; this feature only orchestrates them differently.
**Storage**: Neo4j only (Constitution I). New label `:SyncRun` (singleton-ish — at most one `status:'running'` per binding); reuses `:UI` `figmaSync*` fields from 016 v1.2; reuses `:FigmaBinding`. Two new properties on `:FigmaBinding` for the advisory lock: `currentRunId` (string|null), `currentRunHolder` (string|null).
**Testing**: pytest for backend integration (full-sync orchestration, lock contention, retry deduplication, non-retryable classification); Playwright for the modal UX (전체 Figma 반영 happy path, history tab failure-list + retry, two-tab lock smoke).
**Target Platform**: Web app — backend on `localhost:8000`, frontend on `localhost:5173`. No new Figma plugin protocol changes.
**Project Type**: Web application (frontend + API backend), additive feature.
**Performance Goals**:
- Full retroactive sync of 5 storyboards × 19 UIs (food-delivery sample): completes within 120 s on a developer laptop with the wireframe service running locally (SC-001).
- Retry of N failed UIs via 전체 다시 시도: ≥95% clear on first click under nominal network (SC-002).
- Idempotent re-run on already-synced project: <10 s, zero new pages/frames (SC-006).
- Cross-surface clearing latency (modal retry → Inspector badge clears): <2 s (SC-004).
**Constraints**:
- Streaming-first (Constitution III): full-sync streams over SSE `/api/figma-binding/full-sync/{run_id}/stream`; reuses 016's already-streaming `retry-sync`.
- Reuses 016 concurrency caps — the LLM render Semaphore (cap 2 in `wireframe_agent._render_jsx`) and bulk batch size 10 (`ui_wireframes` gather) — full-sync MUST NOT bypass them. The full-sync orchestrator processes UIs in batches of 10 with the same back-pressure as 016 FR-019.
- Project-scoped lock blocks concurrent dispatches but allows multiple subscribers to join the in-flight stream (read-only progress).
- No cross-feature Python imports added; bridges via Neo4j (Constitution V). `figma_binding.service.full_sync` calls into `ingestion`'s figma-mode sceneGraph generator via a thin module-public function (same shape as 016 v1.2's bulk_sync ↔ ingestion bridge), not a private import.
**Scale/Scope**: One Event Modeling project per deployment (matches 016); typical retroactive sync covers 5–25 storyboards and 20–100 UIs.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Graph-as-Source-of-Truth | ✅ | New `:SyncRun` and the lock fields on `:FigmaBinding` live in Neo4j. The failure store remains the existing `:UI {figmaSync*}` properties from 016 — no parallel cache. |
| II. Event Storming as Domain Vocabulary | ✅ | Reuses Storyboard / Command / UI vocabulary. `:SyncRun` is a runtime audit object, not a domain concept; named to avoid colliding with Event Storming terms. |
| III. Streaming-First UX for Long-Running Work | ✅ | Full-sync is a multi-step LLM + plugin pipeline (often >30s for a fresh project) — streamed over SSE `/api/figma-binding/full-sync/{run_id}/stream`. Retry-sync already streamed since 016. |
| IV. Human-in-the-Loop on Mutations | ✅ | The architect must explicitly click 전체 Figma 반영 from the modal — that click is itself the human-in-the-loop gate, mirroring the bulk path's "기존 데이터 삭제하고 계속" pattern (016 Q5). The 016 FR-012 per-node prompt is intentionally bypassed for this bulk-retroactive path; the modal's banner makes the destructive intent explicit ("기존 sceneGraph 가 있으면 덮어씌워집니다"). |
| V. Feature-Modular Architecture | ✅ | All backend changes live in `api/features/figma_binding/`; all frontend changes in `frontend/src/features/figmaBinding/`. The bridge to ingestion's figma-mode generator goes through one module-public function (`ingestion.workflow.phases.ui_wireframes.generate_jsx_for_existing_ui`) — same shape as 016 v1.2's `bulk_sync.sync_batch` bridge in the opposite direction. No cross-feature imports of internal modules. |
| VI. Provider-Agnostic LLM Runtime | ✅ | Reuses the existing wireframe agent end-to-end. No model/provider hardcoded. |
| VII. Observable by Default | ✅ | New SmartLogger categories: `figma_binding.full_sync.{requested,run_started,page_ok,page_failed,ui_generated,ui_pushed,ui_failed,run_completed,run_cancelled,lock_contended}`, `figma_binding.retry.{deduped}`, `figma_binding.history.{viewed}`. All carry the inbound correlation ID. |

**Result**: All gates pass; no entries in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/020-figma-sync-recovery/
├── plan.md              # This file
├── research.md          # Phase 0 (D1–D5 decisions)
├── data-model.md        # Phase 1 (:SyncRun, :FigmaBinding lock fields)
├── quickstart.md        # Phase 1 (manual smoke: full-sync + retry + lock contention + idempotency)
├── contracts/
│   └── rest-api.md      # New endpoints + SSE event schema
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (NOT created by /speckit-plan)
```

### Source Code (repository root)

Web application — feature-modular layout per Constitution V. All changes are additive edits to the existing 016 surfaces.

```text
api/
├── features/
│   ├── figma_binding/                 # EXISTING (from 016)
│   │   ├── router.py                  # MINIMAL EDIT: + POST /full-sync, + GET /full-sync/{run_id}/stream,
│   │   │                              # + POST /full-sync/{run_id}/cancel, + GET /sync-runs,
│   │   │                              # + GET /failures (canonical project-scoped failure list)
│   │   ├── service.py                 # MINIMAL EDIT: + full_sync(), + full_sync_stream(),
│   │   │                              # + cancel_full_sync(), + list_sync_runs(),
│   │   │                              # + classify_failure_retryability(), + acquire_run_lock(),
│   │   │                              # + release_run_lock(), + dedupe-aware retry helper
│   │   ├── repository.py              # MINIMAL EDIT: + create_sync_run(), + finalize_sync_run(),
│   │   │                              # + list_sync_runs(), + atomic lock acquire/release Cypher,
│   │   │                              # + read previous-binding failures for "이전 바인딩" group
│   │   ├── full_sync.py               # NEW — orchestrator that ties together
│   │   │                              # service.sync_storyboards (pages) + ingestion's figma-mode
│   │   │                              # generator (missing sceneGraphs) + service.push_frame_for_ui
│   │   │                              # (frame push). Yields per-item progress events.
│   │   ├── retry_dedupe.py            # NEW — process-level set[str] of in-flight retry ui_ids
│   │   │                              # with asyncio.Event per-id so duplicate calls await the
│   │   │                              # same outcome instead of re-dispatching to the plugin.
│   │   ├── failure_classifier.py      # NEW — non-retryable detection (binding replaced,
│   │   │                              # storyboard archived locally, UI deleted, file unreachable
│   │   │                              # with confirmed permanent error)
│   │   ├── bulk_sync.py               # untouched
│   │   ├── storyboard_resolver.py     # untouched
│   │   ├── plugin_messages.py         # untouched
│   │   └── schemas.py                 # MINIMAL EDIT: + FullSyncStartResponse, SyncRunSummary,
│   │                                   # FailureRow (with retryability + reason)
│   └── ingestion/
│       └── workflow/
│           └── phases/
│               └── ui_wireframes.py   # MINIMAL EDIT: extract a module-public
│                                       # generate_jsx_for_existing_ui(ui_id, *, ctx_or_none)
│                                       # wrapper around the existing
│                                       # _generate_jsx_scene_graph_for_figma_mode so figma_binding's
│                                       # full_sync orchestrator can call it without reaching into
│                                       # private internals. Same bridge shape as 016 v1.2.
│
docs/cypher/schema/
├── 03_node_types.cypher                # ADD :SyncRun (id, kind, startedAt, finishedAt, status,
│                                        # summary{pagesCreated, framesPushed, failures}, bindingFileKey)
│                                        # ADD :FigmaBinding properties: currentRunId, currentRunHolder
└── 04_relationships.cypher              # ADD :RUN_OF (SyncRun → FigmaBinding) for project-scoped queries

frontend/
├── src/
│   └── features/
│       └── figmaBinding/                # EXISTING (from 016)
│           ├── api.js                   # MINIMAL EDIT: + startFullSync(), + cancelFullSync(),
│           │                            # + subscribeFullSyncStream(), + listSyncRuns(),
│           │                            # + listProjectFailures()
│           ├── figmaBinding.store.js    # MINIMAL EDIT: + fullSync state machine
│           │                            # ({state: 'idle'|'running'|'completed'|'cancelled'|'aborted',
│           │                            #   progress: {storyboardsTotal, storyboardsDone,
│           │                            #              uisTotal, uisDone, currentTarget}}),
│           │                            # + syncRuns array, + failures normalized
│           │                            # (extends existing syncFailedUis from 016 v1.2)
│           └── ui/
│               ├── FigmaBindingModal.vue # MINIMAL EDIT: 연결 상태 tab gets the primary action;
│               │                          # 이력 tab body rewritten to render failures + summaries
│               │                          # + 이전 바인딩 group; lock-busy state gives a read-only
│               │                          # progress view
│               ├── FullSyncSection.vue   # NEW — extracted component for the 전체 Figma 반영 button +
│               │                          # progress bar + cancel button + 변경 없음 / aborted banner
│               ├── HistoryFailureRow.vue # NEW — single failure row with last error (Korean) +
│               │                          # 다시 시도 button (or 재시도 불가 reason)
│               ├── HistorySyncRunRow.vue # NEW — single SyncRun summary row
│               └── PreviousBindingGroup.vue # NEW — collapsible group for "이전 바인딩" entries

tests/
└── integration/
    └── figma_binding/                   # EXISTING from 016 v1.2
        ├── test_full_sync_orchestration.py   # NEW: end-to-end full-sync over an empty Figma file
        ├── test_full_sync_idempotent.py      # NEW: re-run on synced project → zero writes
        ├── test_full_sync_lock_contention.py # NEW: two concurrent dispatches → second blocked
        ├── test_full_sync_cancel.py          # NEW: cancel mid-run → in-flight items complete,
        │                                     # not-yet-attempted UIs remain not-yet-synced
        ├── test_retry_dedupe.py              # NEW: two concurrent retries on same uiId →
        │                                     # only one plugin dispatch
        ├── test_failure_classifier.py        # NEW: non-retryable detection across the four cases
        └── test_history_endpoint.py          # NEW: failures + sync-runs + 이전 바인딩 grouping

frontend/tests/
├── figma-recovery-full-sync.spec.ts          # NEW: open modal → 전체 Figma 반영 → progress visible
│                                              #      → completion summary → re-run shows 변경 없음
├── figma-recovery-retry-from-modal.spec.ts   # NEW: seed 3 failures → open History tab → 전체 다시
│                                              #      시도 → all clear; Inspector badge clears too
└── figma-recovery-lock-busy.spec.ts          # NEW: simulate two browser contexts on same project,
                                                #      first starts, second sees read-only progress
```

**Structure Decision**: Keep all changes inside the existing 016 module surfaces. The new orchestrator (`full_sync.py`) lives next to `bulk_sync.py` because they share the same kind of orchestration responsibility (iterate storyboards, iterate UIs, dispatch plugin writes, collect per-item failures); making them siblings emphasizes that the *only* difference is the trigger (ingestion-bound vs modal-bound) and the input set (just-created UIs vs every UI in the project).

The bridge into ingestion's figma-mode generator goes through a single new module-public function `generate_jsx_for_existing_ui(ui_id, ...)` in `api/features/ingestion/workflow/phases/ui_wireframes.py`. This matches the established 016 v1.2 pattern where the `figma_binding.bulk_sync.sync_batch` is called from `ingestion`'s `ui_wireframes.py` — except in the opposite direction. Both directions cross the feature boundary at exactly one named function, never via internal imports.

The frontend modal extension extracts new logic into small dedicated components (`FullSyncSection.vue`, `HistoryFailureRow.vue`, `HistorySyncRunRow.vue`, `PreviousBindingGroup.vue`) so the existing `FigmaBindingModal.vue` body stays a thin layout file. The store gains a `fullSync` slice but keeps `syncFailedUis` exactly as 016 v1.2 wrote it — the History tab reads from the same field.

The `:SyncRun` node and the `currentRunId/currentRunHolder` lock fields are the only Neo4j additions. No new label is introduced for failures (they continue to live on `:UI`); no new label is introduced for the lock (it's two fields on the existing `:FigmaBinding` singleton).

## Complexity Tracking

> No constitution violations; no entries required.
