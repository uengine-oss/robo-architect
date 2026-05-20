# Implementation Plan: Figma Document Binding for Event Modeling

**Branch**: `016-figma-document-binding` (current working branch: `figma-integration`) | **Date**: 2026-05-07 | **Spec**: [./spec.md](./spec.md)
**Input**: Feature specification from `/specs/016-figma-document-binding/spec.md`

## Summary

Add a project-level Figma binding so that one Event Modeling project links to one Figma document, with each **storyboard** (= one row in the left-panel `BUSINESS PROCESSES` list = one user-initiated entry `:Command` in Neo4j and the vertical slice that flows from it) mapped 1:1 to a Figma page. When the binding is active, the Design tab's UI generation (`Component로 생성` / `OpenPencil AI로 생성` / HTML→Design conversion) routes through a new feature-modular pipeline that creates a Figma frame in the matching page via the existing Figma plugin's WebSocket channel — instead of producing an HTML wireframe locally — and stores the resulting frame's identifiers on the UI node.

The implementation reuses 009's Figma plugin transport (`api/features/ingestion/figma_plugin_ws.py`), the existing wireframe rendering service used by `generate_component_wireframe`, and Neo4j as the single source of truth for the binding and per-storyboard page mapping. Generation streams progress via SSE per Constitution III. Storyboard membership of a UI node is computed at sync/generate time by mirroring the existing `_buildProcessChains` BFS in backend Cypher (no new stored relationship is introduced).

The bulk ingestion path's `Figma UI` toggle (FR-019) is *binding-independent for sceneGraph storage*, but when a binding is active at ingestion time it additionally drives the same storyboard-page-sync + frame-push flow used by per-node generation, with non-blocking failure handling (FR-020) and a cancel-respects-current-batch contract (FR-021). Korean text rendering inside the Design tab's CanvasKit canvas is guaranteed by a bundled-font preload (FR-018), with a single-shot non-blocking banner if the preload itself fails.

## Technical Context

**Language/Version**: Python 3.11+ (FastAPI, LangChain/LangGraph) backend; Vue 3 + Vite frontend.
**Primary Dependencies**:
- Backend: FastAPI, Neo4j Python driver, `httpx` for Figma REST validation, existing plugin transport in `api/features/ingestion/figma_plugin_ws.py`, existing wireframe render client, `SmartLogger` for observability.
- Frontend: Vue 3, Pinia (existing canvas / `eventModeling` stores pattern), Vue Flow (canvas), EventSource for SSE.
- Plugin: existing `figma-plugin/src/plugin.ts` — extend with two new message types.
**Storage**: Neo4j only. New labels: `:FigmaBinding` (singleton), `:StoryboardPageMapping`, `:BindingHistoryEvent`. Schema additions go in `docs/cypher/schema/03_node_types.cypher` and `04_relationships.cypher` per Development Workflow.
**Testing**: pytest for backend unit/integration; Playwright for the Design-tab generation routing (UI smoke).
**Target Platform**: Web app — backend on `localhost:8000`, frontend on `localhost:5173`, optional Figma plugin running inside Figma desktop.
**Project Type**: Web application (web frontend + API backend + external Figma plugin).
**Performance Goals**:
- Binding validation (Figma file metadata fetch): single REST call, < 2 s typical.
- Storyboard page sync after binding (≤ 25 storyboards): completes within 5 s end-to-end (SC-002).
- Generate-to-Figma: visible frame in Figma within 15 s p90 (SC-003).
- Bulk Figma-mode ingestion: 100% populated `sceneGraph` for 19-UI sample (SC-007).
- Korean text in any FrameEditor instance on a fresh, permission-less load (SC-008).
**Constraints**:
- Streaming-first for the generation flow (Constitution III): SSE from `/api/figma-binding/generate-frame/{session_id}/stream`.
- All persisted state in Neo4j (Constitution I). Token storage continues to follow 009's existing pattern.
- Plugin write surface only: `CREATE_PAGE`, `CREATE_FRAME_IN_PAGE` are new plugin protocol messages.
- No new stored UI→storyboard relationship: membership is computed via the same BFS the frontend already uses, expressed once in `figma_binding` service-layer Cypher to avoid cross-feature imports (Constitution V allows cross-feature data sharing only "through the platform layer or through Neo4j").
- Wireframe-service (Bun, `:7610`) is the bottleneck for bulk fan-out — concurrency capped at 2 in the agent's `_render_jsx`, with three independent retry layers (FR-017).
**Scale/Scope**: One active Event Modeling project per deployment; typical project has 5–25 storyboards (entry commands) and dozens of UI nodes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Graph-as-Source-of-Truth | ✅ | Binding (`:FigmaBinding`) and per-storyboard mapping (`:StoryboardPageMapping`) live in Neo4j; nothing duplicated client-side. The new per-UI Figma sync status (FR-020) lives on the `:UI` node itself, not in any client cache. |
| II. Event Storming as Domain Vocabulary | ✅ | API uses `Command` and the methodology term `Storyboard` (vertical slice rooted at an entry Command). The user-facing UI label `BUSINESS PROCESSES` is preserved as a display string only. |
| III. Streaming-First UX for Long-Running Work | ✅ | Generate-to-Figma is multi-step (LLM + render + plugin round-trip), routed through `/.../generate-frame/{session_id}/stream` SSE. Bulk-with-binding (FR-019b) reuses the existing `/api/ingest/stream/{session_id}` SSE stream, augmented with new event types `figma_sync.start`, `figma_sync.ok`, `figma_sync.failed`. |
| IV. Human-in-the-Loop on Mutations | ✅ | Binding connect/replace/disconnect are explicit user actions. The "overwrite vs import" prompt for nodes that already have a sceneGraph (FR-012) preserves the propose-confirm pattern in *per-node* flow; the bulk path (FR-019) consciously bypasses the prompt because the architect already confirmed "기존 데이터 삭제하고 계속" at the upload modal — that explicit consent is the human-in-the-loop gate for bulk. |
| V. Feature-Modular Architecture | ✅ | New backend feature: `api/features/figma_binding/` (router + services). Mirror frontend feature: `frontend/src/features/figmaBinding/`. The storyboard-resolver Cypher is duplicated (intentionally, per Constitution: "through Neo4j") to avoid importing logic from `canvas_graph`. The bulk path bridges via Neo4j: ingestion writes `:UI` nodes with status flags; `figma_binding.service` reads them on retry. |
| VI. Provider-Agnostic LLM Runtime | ✅ | Reuses existing wireframe generator that already goes through the LLM runtime; no new model/provider hardcoding. |
| VII. Observable by Default | ✅ | Every endpoint emits `SmartLogger` events at phase boundaries. New categories from v1.1: `ai_design.wireframe.render.retries_exhausted`, `ai_design.wireframe.final_fallback`, `ingestion.ui_wireframe.figma_mode.{success,retry,empty,error}`. New from v1.2: `figma_binding.bulk_sync.{start,ok,failed}`, `figma_binding.retry.{requested,ok,failed}`, `frontend.fonts.preload_failed` (frontend-emitted via `/api/observability/log`). |

**Result**: All gates pass; no entries in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/016-figma-document-binding/
├── plan.md              # This file
├── research.md          # Phase 0 (resolved decisions)
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1 (manual smoke test)
├── contracts/           # Phase 1 (REST + plugin messages)
│   ├── rest-api.md
│   └── plugin-protocol.md
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (with v1.1 + v1.2 addendum phases)
```

### Source Code (repository root)

Web application — feature-modular layout per Constitution V.

```text
api/
├── features/
│   ├── figma_binding/                # NEW (US1–US4)
│   │   ├── __init__.py
│   │   ├── router.py                 # FastAPI router, /api/figma-binding/...
│   │   ├── service.py                # Business logic: connect / sync_storyboards / generate / bulk_sync / retry
│   │   ├── repository.py             # Neo4j read/write for :FigmaBinding, :StoryboardPageMapping
│   │   ├── storyboard_resolver.py    # Cypher: list entry-command storyboards;
│   │   │                             # given a UI node, return its owning storyboard ID
│   │   ├── schemas.py                # Pydantic request/response models
│   │   ├── plugin_messages.py        # New plugin protocol message builders/handlers
│   │   ├── bulk_sync.py              # NEW (v1.2 / FR-019b): orchestrates page-sync + frame-push
│   │   │                             # for every newly-created :UI in an ingestion session.
│   │   │                             # Called inline from the ingestion phase via a thin
│   │   │                             # callback (not a Python import — wired through the
│   │   │                             # ingestion context).
│   │   └── retry.py                  # NEW (v1.2 / FR-020): retry endpoint handler;
│   │                                 # reads :UI {figmaSyncStatus:'failed'} and replays
│   │                                 # the bulk_sync push for the requested set.
│   ├── ingestion/                    # EXISTING (009 lives here)
│   │   ├── figma_sync.py             # untouched (per-node REST sync from 009)
│   │   ├── figma_plugin_ws.py        # MINIMAL EDIT: register handlers for CREATE_PAGE_ACK
│   │   │                             # and CREATE_FRAME_IN_PAGE_ACK; honor REGISTER's
│   │   │                             # supportedMessages field
│   │   ├── figma_api.py              # reused for read-only validation
│   │   └── workflow/phases/
│   │       └── ui_wireframes.py      # MINIMAL EDIT (v1.2 / FR-019b): after each batch,
│   │                                 # if a :FigmaBinding is active, hand the just-created
│   │                                 # UI ids to figma_binding.bulk_sync.sync_batch(...)
│   │                                 # and stream the resulting per-UI ok/failed events
│   │                                 # through the SSE.
│   └── canvas_graph/
│       └── routes/
│           ├── event_modeling.py     # untouched (frontend continues to compute processChains)
│           └── canvas_expansion.py   # MINIMAL EDIT: when binding active,
│                                     # generate_component_wireframe delegates to
│                                     # figma_binding.service.generate_frame_for_ui
└── platform/
    ├── neo4j.py                      # untouched
    └── observability/                 # untouched (use SmartLogger as-is)

docs/cypher/schema/
├── 03_node_types.cypher              # ADD :FigmaBinding, :StoryboardPageMapping, :BindingHistoryEvent
│                                     # ADD properties on :UI: figmaSyncStatus, figmaSyncLastError, figmaSyncLastAttemptAt (v1.2 / FR-020)
└── 04_relationships.cypher           # ADD :MAPS_STORYBOARD (FigmaBinding→StoryboardPageMapping),
                                      #     :MAPS (StoryboardPageMapping→Command),
                                      #     :LOGGED (BindingHistoryEvent→FigmaBinding)

frontend/
├── src/
│   ├── app/
│   │   └── layout/
│   │       └── TopBar.vue            # MINIMAL EDIT: insert <FigmaButton/> + modal mount
│   ├── features/
│   │   ├── figmaBinding/             # NEW
│   │   │   ├── figmaBinding.store.js     # Pinia store: binding state, last sync, storyboards-mapped count
│   │   │   ├── ui/
│   │   │   │   ├── FigmaButton.vue       # Top-bar button + status indicator
│   │   │   │   ├── FigmaBindingModal.vue # Connect/replace/disconnect/sync dialog
│   │   │   │   ├── DesignBindingBadge.vue# Inspector Design-tab badge: "Linked to <file>/<page>/<frame>"
│   │   │   │   └── DesignSyncFailedBadge.vue # NEW (v1.2 / FR-020): red badge on Inspector Design tab when figmaSyncStatus = 'failed'; per-node 다시 시도 button
│   │   │   ├── api.js                    # SSE + REST client for /api/figma-binding/...
│   │   │   └── retry.js                  # NEW (v1.2 / FR-020): client for POST /api/figma-binding/retry-sync
│   │   ├── aiDesign/
│   │   │   ├── bootstrap.js              # EXISTING (v1.1)
│   │   │   ├── fonts.js                  # MINIMAL EDIT (v1.2 / FR-018 banner): expose
│   │   │   │                             # preloadKoreanFont() result via a small reactive
│   │   │   │                             # ref so the FrameEditor can observe success/fail
│   │   │   └── fontStatus.store.js       # NEW (v1.2 / FR-018 banner): tiny Pinia store wrapping
│   │   │                                 # the fonts.js Promise as { state: 'pending'|'ok'|'failed' }
│   │   ├── canvas/
│   │   │   └── ui/
│   │   │       └── InspectorPanel.vue # MINIMAL EDIT: branch generateComponentWireframe / 
│   │   │                              # generateWithAI / startConvertToDesign on binding state;
│   │   │                              # mount <DesignSyncFailedBadge/> when applicable
│   │   └── requirementsIngestion/
│   │       └── ui/
│   │           ├── IngestionProgressPanel.vue # MINIMAL EDIT (v1.2 / FR-020): summary section
│   │           │                              # "Figma 동기화 실패 N건" with 전체 다시 시도 + 노드별
│   │           │                              # 다시 시도 buttons. Reads from figmaBinding.store
│   │           │                              # populated by SSE events.
│   │           └── RequirementsIngestionModal.vue # untouched in v1.2
│   └── ...
└── public/
    ├── Inter-Regular.ttf             # v1.1: open-pencil bundled-font fallback
    ├── NotoNaskhArabic-Regular.ttf   # v1.1: same
    └── Pretendard-Regular.otf        # v1.1: Korean primary + CJK fallback (1.5 MB)

figma-plugin/
└── src/
    └── plugin.ts                     # MINIMAL EDIT: handle CREATE_PAGE, CREATE_FRAME_IN_PAGE;
                                      # extend REGISTER with supportedMessages
```

**Structure Decision**: Follow Constitution V — backend feature `api/features/figma_binding/` mirrors a new frontend feature `frontend/src/features/figmaBinding/`. The storyboard resolver lives inside `figma_binding` (its own Cypher, not an import from `canvas_graph`) so that cross-feature dependence remains via Neo4j only. Touch points into `canvas_graph` (backend) and `canvas/ui/InspectorPanel.vue` + `app/layout/TopBar.vue` (frontend) are kept to one-line dispatches, not embedded logic. The Figma plugin gains two new message handlers but no architectural change.

For v1.2 cross-cutting (FR-019b, FR-020), the bulk-with-binding bridge between `ingestion` and `figma_binding` is intentionally one-way: `ingestion`'s `ui_wireframes.py` calls a public function on `figma_binding.bulk_sync` (a thin module-public surface, not a private import) and forwards the resulting events into its own SSE channel. `figma_binding` does not call back into `ingestion`. Retry (FR-020) is fully driven from `figma_binding` reading the `:UI` nodes it needs from Neo4j — no cross-feature import.

For v1.2 frontend banner (FR-018 latter half), `aiDesign/fontStatus.store.js` is a tiny Pinia store the FrameEditor's wrapping component reads on mount; the store stays a single source of truth so any other component (e.g. a non-Design canvas using CanvasKit later) can read the same status without duplicating the check.

## Complexity Tracking

> No constitution violations; no entries required.

---

## Reliability & Operability Addendum (v1.1, 2026-05-07)

Two operability problems were observed once US3-style generation was wired to the bulk ingestion path (the `Figma UI` toggle in the upload modal that fans out one generation per Command/ReadModel via `asyncio.gather`, batch 10). Both are now part of the spec (FR-017, FR-018).

### A. Wireframe-service fan-out reliability (FR-017)

**Architecture reminder**: "Backend generation" is two cooperating processes — FastAPI (Python, `:8000`) drives the LLM agent loop and orchestrates; the **wireframe service (Bun, `:7610`, source in `open-pencil/packages/cli/src/wireframe-service.ts`)** does the actual JSX → SceneGraph render. open-pencil's renderer is TypeScript so we can't run it in-process from Python.

**Failure mode observed**: 19-UI sample → 11 populated, 8 empty (42% loss). Root cause: 10 concurrent Bun renders saturate the service; some httpx calls hit `ReadTimeout` at 60s, others get `500 {"error":"Unexpected end of JSON input"}` (Bun's `await req.json()` failing because the request body read got cut). The agent treats the resulting `None` from the render tool as a soft error; the LLM follows up with a summary instead of retrying, so the loop ends with `final_scene_graph = None`.

**Decision**: Defense in depth — three independent retry layers, each absorbing a different failure mode. No change to BATCH_SIZE so ingestion latency is preserved.

| Layer | File | What it catches |
|---|---|---|
| Transport-level retry | `api/features/ai_design/wireframe_agent.py::_render_jsx` | Bun transient (timeout, 5xx, request-body cut). 3 attempts with 0.5s/1s/2s backoff. **Zero LLM round-trips per retry** — re-sends the same JSX. Concurrency capped at 2 via module-level `asyncio.Semaphore` (3 still produced sporadic flakes; 1 serializes too aggressively). |
| Agent-loop final fallback | `api/features/ai_design/wireframe_agent.py::run_render_agent` | LLM gives up after a render tool-error turn. The agent caches `last_jsx` for every render call; if the loop ends with `final_scene_graph is None` but `last_jsx is not None`, it issues one direct `_render_jsx(last_jsx)` outside the agent. |
| Wrapper retry | `api/features/ingestion/workflow/phases/ui_wireframes.py::_generate_jsx_scene_graph_for_figma_mode` | Anything the inner two layers couldn't recover (e.g. genuinely bad JSX). Up to 3 attempts of the *whole agent loop*, with `0.5s × attempt` jittered sleep before each retry to avoid thundering-herd into the wireframe service. |

Also: `httpx.post(/render)` timeout raised 60 → 120 s (`api/platform/open_pencil_client.py`). Each render is CPU-heavy (JSX parse + Yoga layout); the previous ceiling was the dominant cause of `ReadTimeout` under load.

**Verification**: 15 concurrent end-to-end agent invocations (above prod's 10) → 15/15 OK; full-flow ingestion of the food-delivery sample → 19/19 populated (vs 11/19 baseline). Tests at `frontend/tests/figma-ui-bulk-diag.spec.ts`.

### B. Korean text rendering in the Design-tab canvas (FR-018, basic preload)

**Architecture reminder**: The Design tab's `FrameEditor` (federation-loaded from `open-pencil/src/federation/FrameEditor.vue`) drives a CanvasKit (Skia) WebAssembly renderer that maintains its own `TypefaceFontProvider`. Browser CSS `@font-face` registrations are invisible to it; CanvasKit needs the raw TTF/OTF bytes registered explicitly.

**Failure modes observed**:

1. open-pencil's `BUNDLED_FONTS` map points at root-relative URLs `/Inter-Regular.ttf` and `/NotoNaskhArabic-Regular.ttf`. robo-architect's `frontend/public/` did not contain those files, so Vite served the SPA's `index.html` as a 200 response (744 bytes, starts with `<!DO`). CanvasKit fed that to OTS, producing `OTS parsing error: invalid sfntVersion: 1008813135` (`= '<!DO'`) and `Failed to load font "Inter"`. With Inter not registered, no Latin glyphs were drawn either.
2. The CJK fallback chain (`queryLocalFonts` → Google Fonts metadata API) is unreliable on a fresh load: the Permissions API requires a user gesture, and the upstream-bundled metadata API key returns 429 under shared use. So Korean glyphs missing from Inter rendered as tofu (□□□).

**Decision**: Stop relying on the runtime fallback chain. Bundle a Korean-capable static OTF as a first-class app asset and register it in open-pencil's font registry before any `FrameEditor` mounts.

| Concern | File | What changed |
|---|---|---|
| Bundled-font URLs resolve | `frontend/public/Inter-Regular.ttf`, `frontend/public/NotoNaskhArabic-Regular.ttf` | Copied from `open-pencil/public/`. Vite plugin `copy-open-pencil-fonts` keeps this idempotent across clean builds. |
| Korean fallback always available | `frontend/public/Pretendard-Regular.otf` (1.5 MB, jsdelivr) | A static Latin+Hangul OTF — chosen over Noto Sans KR because Pretendard has both writing systems in one file (so it can act as the *primary* font too if the LLM picks it) and is already in open-pencil's `FIGMA_FONT_MAP` for round-tripping. |
| Preload + register | `frontend/src/features/aiDesign/fonts.js` (new) + `frontend/src/main.js` (one call) | At app boot, fetch the Pretendard OTF, call `markFontLoaded('Pretendard', 'Regular', buf)` and `setCJKFallbackFamily('Pretendard')`. open-pencil's `loadedFamilies` cache survives `FrameEditor` re-creation: when a new `SkiaRenderer` calls `initFontService()`, it replays every cached buffer into the fresh provider, so the registration is one-shot per page load. |
| Vite plugin parity | `frontend/vite.config.js` | New `copy-open-pencil-fonts` plugin alongside the existing `copy-canvaskit-wasm`. Pretendard itself lives in `frontend/public/` directly (it's a robo-architect asset, not an open-pencil asset). |

**Verification**: `frontend/tests/font-loading-diag.spec.ts` probes the three font URLs from a real Vite dev server, captures CanvasKit console errors, and screenshots the canvas. Pre-fix: `Inter-Regular.ttf` returns 744 bytes (HTML), all Korean labels rendered as tofu. Post-fix: 342 408 bytes (real TTF), no OTS errors, Korean labels render.

### Tests added by v1.1

| Path | What it exercises |
|---|---|
| `frontend/tests/font-loading-diag.spec.ts` | Bundled font URLs serve real binaries; no `OTS parsing error` / `Failed to load font` in CanvasKit; Hangul renders in the Design canvas. |
| `frontend/tests/figma-ui-bulk-diag.spec.ts` | Full-flow ingestion of the food-delivery sample under `Figma UI` mode; relays SSE through `window.EventSource` instrumentation; reports per-UI `sceneGraph` length and exits when phase=`complete` / progress=100 (the backend never emits `done` over SSE for the ingestion stream). |

The existing `frontend/tests/design-tab-reopen.spec.ts` (open Design tab on two consecutive UI nodes) keeps the regression coverage for the CanvasKit "deleted object" crashes that were fixed earlier in this branch.

---

## Clarification-Driven Additions (v1.2, 2026-05-07)

The five Q1–Q5 clarifications (see `spec.md` § Clarifications) added FR-019, FR-020, FR-021, and a tightening of FR-018's failure UX. This section turns those resolutions into concrete plan items the corresponding tasks (Phase 9 in `tasks.md`) implement.

### C. Bulk-with-binding: storyboard sync + frame push during ingestion (FR-019b)

**Background**: pre-clarification, `ui_generation_mode='figma'` only filled `:UI.sceneGraph`. Post-clarification, when a binding is active at ingestion time, the same flow MUST additionally (a) ensure each storyboard's Figma page exists and (b) push every new UI frame into its storyboard's page.

**Decision**:

1. The bulk path stays inside the ingestion feature for sceneGraph generation (it already lives in `api/features/ingestion/workflow/phases/ui_wireframes.py`). Crossing into the figma_binding feature happens at exactly one bridge point per batch.
2. After each `asyncio.gather(...)` batch of 10 returns and the corresponding UIs are written to Neo4j, `ui_wireframes.py` checks whether a `:FigmaBinding` is active *via repository* (Neo4j read; no cross-feature Python import). If active, it calls `figma_binding.bulk_sync.sync_batch(session_id, ui_ids, on_event)` — a single public function — and forwards the per-UI `figma_sync.start` / `figma_sync.ok` / `figma_sync.failed` events through the existing ingestion SSE.
3. `bulk_sync.sync_batch` reuses `figma_binding.service.sync_storyboards_for_ids(...)` (a slimmer variant of FR-006's full sync that only ensures pages for the storyboards touched by this batch — avoids re-syncing untouched storyboards) and then `figma_binding.service.push_frame_for_ui(ui_id, ...)` for each UI.
4. Per-UI failures set `:UI {figmaSyncStatus: 'failed', figmaSyncLastError: '<korean>', figmaSyncLastAttemptAt: datetime()}` on the affected node; success sets `'ok'` and clears `figmaSyncLastError`. **Ingestion does NOT halt** on failure (FR-020 contract).
5. The "overwrite vs import-existing" prompt from FR-012 is *not* shown by the bulk path — clarification Q5 nailed this down: bulk always overwrites because the architect already confirmed "기존 데이터 삭제하고 계속" at the upload modal. Bulk path passes `onConflict='overwrite'` (the same enum US3 introduced) directly.

**Why this layout instead of moving the whole bulk loop into figma_binding?**: the LLM-driven sceneGraph generation is *not* a figma-binding concern — it produces the sceneGraph regardless of binding. Splitting "generate" (ingestion) from "publish to Figma" (figma_binding) is the same separation US3 already enforced for per-node generation; the bulk path now mirrors that boundary instead of fusing the two responsibilities.

**Cancel semantics (FR-021)**: the cancel handler at `api/features/ingestion/router.py::cancel` already sets a flag the ingestion workflow checks between batches. With this addition, the check moves to *after* the figma sync sub-step within a batch (the LLM gather + the figma_binding sync_batch are treated as one logical batch, both running to natural completion before the cancel check trips). No `CancelledError` is propagated into running coroutines — that is the explicit clarification Q2 contract.

### D. Failure list & retry UX (FR-020)

**Decision**: Two surfaces, one source of truth.

| Surface | Component | Source of truth |
|---|---|---|
| Ingestion floating panel summary section "Figma 동기화 실패 N건" | `frontend/src/features/requirementsIngestion/ui/IngestionProgressPanel.vue` (existing component, additive section) | `figmaBinding.store` array `syncFailedUis`, populated by SSE `figma_sync.failed` events captured during the run. |
| Per-UI Inspector Design-tab red badge "Figma 동기화 실패" with a "다시 시도" button | `frontend/src/features/figmaBinding/ui/DesignSyncFailedBadge.vue` (new), mounted from `InspectorPanel.vue` when `node.data.figmaSyncStatus === 'failed'` | The same `:UI.figmaSyncStatus` / `figmaSyncLastError` properties read from the canvas-graph store on Inspector open. |

Both surfaces call the same retry endpoint:

```http
POST /api/figma-binding/retry-sync
Content-Type: application/json

{ "uiIds": ["<id1>", "<id2>", ...] }   # empty/missing → retry every :UI {figmaSyncStatus:'failed'}
```

The endpoint returns 202 with a `session_id`, and per-UI progress streams through `/api/figma-binding/retry-sync/{session_id}/stream` (SSE — Constitution III). The same `figma_sync.ok` / `figma_sync.failed` event types as the bulk-with-binding flow are reused so the frontend has only one event handler.

**Observability**: `figma_binding.retry.requested` (start, with uiIds), `.ok` (per-UI success), `.failed` (per-UI failure, with error reason). All carry the inbound correlation ID.

### E. Font-preload failure banner (FR-018 latter half)

**Decision**: surface the existing silent warning as a single, non-blocking, in-canvas banner.

**Wiring**:

1. `frontend/src/features/aiDesign/fonts.js` already exposes a cached promise (`loadingPromise`). Extend it to expose a tiny `subscribeToFontStatus(cb)` API that resolves with `{ state: 'ok' | 'failed', error? }` once the load settles.
2. New `frontend/src/features/aiDesign/fontStatus.store.js` (Pinia): a one-state store `{ koreanFont: 'pending' | 'ok' | 'failed' }`. Subscribes to fonts.js on init.
3. `FrameEditor.vue` (the open-pencil federation component) is third-party and we should not modify it. Instead, robo-architect's wrapper at `frontend/src/features/canvas/ui/InspectorPanel.vue` § Design tab shows the banner ABOVE the FrameEditor mount when `fontStatusStore.koreanFont === 'failed'`. Because the banner sits in our wrapper, no FrameEditor changes are needed.
4. The banner is a simple Vue component using Tailwind utility classes already in the project; appears once per page load (a session-scoped flag on `fontStatusStore` flips after first display) and dismissable.
5. SmartLogger event from frontend: POST to a small `/api/observability/log` endpoint (or the existing one if there's already a frontend-log channel) so backend records `frontend.fonts.preload_failed` for ops dashboards.

**Why a Pinia store and not just a ref in `fonts.js`?**: clarification Q3 asked for the banner to fire on *first FrameEditor mount*, not on app boot. The store decouples the load (boot-time) from the display (mount-time, possibly minutes later) and gives any other CanvasKit-using surface the same status without re-running the check.

### Tests added by v1.2

| Path | What it exercises |
|---|---|
| `tests/integration/figma_binding/test_bulk_sync_with_binding.py` (new) | Full ingestion under `Figma UI` mode with an active `:FigmaBinding`; mock plugin layer; assert every UI ends with `figmaSyncStatus='ok'` AND has `figmaPageId/figmaNodeId`. |
| `tests/integration/figma_binding/test_bulk_sync_failures_dont_halt.py` (new) | Force the plugin mock to fail for half the UIs; assert ingestion still reaches `phase=complete`, the failed half has `figmaSyncStatus='failed'` and a Korean error string, and the SSE emitted one `figma_sync.failed` per affected UI. |
| `tests/integration/figma_binding/test_retry_endpoint.py` (new) | Seed Neo4j with 3 `:UI {figmaSyncStatus:'failed'}` nodes; POST `/retry-sync` with all 3 ids; have plugin mock succeed; assert all three flip to `'ok'` and clear `figmaSyncLastError`. |
| `tests/integration/figma_binding/test_cancel_during_bulk.py` (new) | Start ingestion, fire cancel after the first batch begins; assert the *current* batch's UIs all get processed (sceneGraph + sync attempt) and the next batch never starts; no `CancelledError` propagates into running coroutines. |
| `frontend/tests/figma-ui-bulk-with-binding.spec.ts` (new) | E2E variant of `figma-ui-bulk-diag.spec.ts` with binding stubbed active; asserts the summary panel renders the "Figma 동기화 실패 N건" section when failures occur (uses a request-route stub to force failures); clicking "전체 다시 시도" re-runs and clears the section. |
| `frontend/tests/font-preload-failure-banner.spec.ts` (new) | Block `/Pretendard-Regular.otf` via `page.route(...)` to simulate the failure; open Design tab on a UI; assert the canvas-overlay banner "한글 폰트 로드 실패 — 새로고침을 시도해 주세요" appears exactly once and the FrameEditor itself still mounts. |

---

## Phase 0 Output

See [./research.md](./research.md). All decisions resolved.

## Phase 1 Outputs

- [./data-model.md](./data-model.md) — `:FigmaBinding`, `:StoryboardPageMapping`, `:BindingHistoryEvent`, UI-node design-source fields, plugin message schemas. **v1.2 addition**: `:UI` node gains `figmaSyncStatus` (`'ok' | 'failed' | null`), `figmaSyncLastError` (string), `figmaSyncLastAttemptAt` (datetime).
- [./contracts/rest-api.md](./contracts/rest-api.md) — REST contract for `/api/figma-binding/*`. **v1.2 addition**: `POST /api/figma-binding/retry-sync` + SSE stream `/api/figma-binding/retry-sync/{session_id}/stream`.
- [./contracts/plugin-protocol.md](./contracts/plugin-protocol.md) — New plugin WebSocket message types and the request/response shape (unchanged in v1.2; bulk-with-binding reuses CREATE_PAGE / CREATE_FRAME_IN_PAGE).
- [./quickstart.md](./quickstart.md) — Manual end-to-end smoke test (connect → sync storyboards → generate frame), plus v1.1 Step 6 for reliability checks. v1.2 quickstart additions covered by the new pytest + Playwright tests above.
