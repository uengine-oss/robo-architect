# Implementation Plan: Aggregate Tab Drill-Down & Canvas UX

**Branch**: `028-aggregate-tab-drilldown` (working branch: `figma-integration`) | **Date**: 2026-05-18 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/028-aggregate-tab-drilldown/spec.md`

## Summary

Connect the **Design** tab and the **Aggregate** tab so a user can drill from a selected aggregate into its detailed view, carry that selection across a manual tab switch, drop an aggregate (not just a Bounded Context) directly onto the Aggregate canvas, and recognize the aggregate boundary visually (yellow tint + `«Aggregate»` stereotype).

**Technical approach**: Frontend-only. No backend, no graph schema changes. Reuses the existing read endpoint `GET /api/contexts/{bcId}/full-tree` and the existing `GET /api/graph/expand-with-bc/{aggregateId}` (only as a bcId-resolution fallback). The cross-tab "current aggregate" intent is carried through a small piece of new state on the existing `aggregateViewer` Pinia store; tab switching uses the existing `provide('activeTab')` ref in `App.vue`. Single-aggregate display is achieved by adding an aggregate-level visibility filter to the store (today the store only filters at Bounded-Context granularity).

## Technical Context

**Language/Version**: JavaScript (ES2022) + Vue 3 SFCs (`<script setup>`)
**Primary Dependencies**: Vue 3, Pinia, Vue Flow (`@vue-flow/core`, canvas rendering + `fitView`), Vite
**Storage**: N/A (Neo4j is read via existing endpoints; no new persistence; `localStorage` reused only for existing canvas position memory)
**Testing**: Manual smoke testing via `quickstart.md` (the repo has no frontend unit-test harness for canvas features; consistent with prior specs 024–027)
**Target Platform**: Modern desktop browser (Vue 3 SPA served by Vite)
**Project Type**: Web application — frontend feature only (`frontend/src/features/canvas/`)
**Performance Goals**: Drill-down → focused detail visible within one render cycle after tab switch; no perceptible regression in Aggregate-tab layout time
**Constraints**: No backend changes; no new endpoints; no Neo4j schema changes; preserve existing Bounded-Context drop behavior (no regression)
**Scale/Scope**: 4 frontend files touched, 1 Pinia store extended, ~1 new store action + 1 visibility filter; ≤ ~50 aggregates expected on a canvas

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Graph-as-Source-of-Truth | PASS | Read-only feature. No parallel store of model state — only transient UI focus/visibility state (which aggregates are shown, which one to focus). |
| II. Event Storming Vocabulary | PASS | Uses `Aggregate`, `BoundedContext`, `«Aggregate»` stereotype — DDD terms throughout. |
| III. Streaming-First UX | PASS | No long-running operation introduced. `full-tree` is an instant graph query (request/response is the established pattern for it). |
| IV. Human-in-the-Loop | PASS | No mutations. Drill-down/drop/focus are navigation + display only. |
| V. Feature-Modular Architecture | PASS | All changes within `frontend/src/features/canvas/`. InspectorPanel reads the existing `aggregateViewer` store and the `provide`d `activeTab` — no cross-feature imports. |
| VI. Provider-Agnostic LLM Runtime | PASS | No LLM involved. |
| VII. Observable by Default | PASS | No new backend endpoints; no correlation-ID surface to extend. |
| VIII. Figma SceneGraph Pipeline | N/A | Feature does not produce a SerializedSceneGraph. |
| IX. Plugin ↔ Backend Dev-Loop | N/A | Feature does not touch the Figma plugin. |
| Graph Schema Changes | PASS | None — no new node labels or relationship types. `docs/cypher/schema/` untouched. |
| API Documentation | PASS | No new endpoints — `/docs` unchanged. |
| Frontend ↔ Backend Mirror | PASS | Frontend-only feature; no backend folder to mirror. |

**Result**: No violations. Complexity Tracking section omitted (nothing to justify).

## Project Structure

### Documentation (this feature)

```text
specs/028-aggregate-tab-drilldown/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (UI state model — no DB entities)
├── quickstart.md        # Phase 1 output (manual smoke scenarios)
├── contracts/
│   └── ui-contract.md   # Phase 1 output (cross-tab focus contract + reused endpoints)
└── checklists/
    └── requirements.md  # Spec quality checklist (from /speckit-specify)
```

### Source Code (repository root)

```text
frontend/src/features/canvas/
├── aggregateViewer.store.js              # MODIFY — add aggregate-level visibility filter +
│                                         #          pending-focus state + fetchAggregate action
├── ui/
│   ├── AggregatePanel.vue                # MODIFY — handle Aggregate drop; onMounted auto-focus;
│   │                                     #          watch pending-focus → fitView on container
│   ├── InspectorPanel.vue                # MODIFY — "View Detail" button for Aggregate nodes;
│   │                                     #          inject activeTab; resolve bcId; trigger focus
│   └── nodes/
│       └── AggregateContainerNode.vue    # MODIFY — yellow tint background + «Aggregate» stereotype
```

No new files. No backend (`api/`) changes. No `docs/cypher/` changes.

**Structure Decision**: Web application, frontend-only slice. All work lives in the existing `canvas` feature module (`frontend/src/features/canvas/`), consistent with Principle V. The Aggregate tab (`AggregatePanel.vue`) and Design tab inspector (`InspectorPanel.vue`) already coexist in this module; the feature wires them together through the module's existing `aggregateViewer` store and the app-level `activeTab` injection.
