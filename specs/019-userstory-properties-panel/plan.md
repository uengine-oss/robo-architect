# Implementation Plan: Unified UserStory Editing in Properties Panel

**Branch**: `019-userstory-properties-panel` (logical) | **Date**: 2026-05-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/019-userstory-properties-panel/spec.md`

## Summary

Today UserStory editing is a separate modal opened from the navigator tree, while every other domain object (Event, Command, Aggregate, ReadModel, UI, Policy) is edited inside the unified `InspectorPanel.vue` Properties panel on the canvas. UserStory's generated `acceptanceCriteria` field exists on the Neo4j node (written by the bulk ingestion path) but is not exposed to any read endpoint, not editable from any UI surface, and not consumed by GWT generation.

This feature unifies UserStory editing into the existing `InspectorPanel` (adding a new branch in its type-discriminated rendering), adds an editable Acceptance Criteria list section, exposes the field through the user-stories API (catalog read + new authoring PATCH), removes the legacy `UserStoryEditModal` entirely, and feeds each UserStory's current criteria into GWT generation for the Commands/Policies linked to it. The implementation is a thin slice across existing layers — no new framework, no new storage, no new orchestration — riding on the InspectorPanel's existing per-type rendering pattern, the existing UserStory Neo4j node label, and the existing GWT generation prompt structure.

## Technical Context

**Language/Version**: Python 3.11 (backend), Node 20 / Vue 3.x (frontend)
**Primary Dependencies**: FastAPI, Pydantic, official Neo4j Python driver, LangChain + LangGraph (for GWT generation prompt assembly), Vue 3 + Vite, Pinia, Vue Flow (canvas)
**Storage**: Neo4j (existing `UserStory` node label; existing `acceptanceCriteria: List<String>` property documented in `docs/cypher/schema/03_node_types.cypher:48`)
**Testing**: pytest (backend, including a Neo4j-backed integration test for the new PATCH + GWT input wiring), Vitest + Playwright (frontend, for InspectorPanel UserStory branch and end-to-end navigator → panel → save → reload flow)
**Target Platform**: Web (Chromium-class browser) calling FastAPI service backed by Neo4j 5.x
**Project Type**: Web application (FastAPI backend under `api/`, Vue 3 frontend under `frontend/`)
**Performance Goals**: Inline edit save (PATCH `/user-stories/{id}`) p95 < 200 ms with the existing Neo4j connection pool. Panel open after dblclick must feel as fast as the existing object types — no perceptible regression vs. an Event/Command open.
**Constraints**: Must not regress the bulk-write ingestion path that already persists `acceptanceCriteria`. Must not break GWT generation when a Command's linked UserStory has zero criteria (fallback to current behavior). Must not introduce a parallel store for criteria — Neo4j stays the single source of truth.
**Scale/Scope**: A single project today carries on the order of 10²–10³ UserStories with a handful (typically 3–8) criteria each. Editing is a one-user-at-a-time interaction; no multi-writer concurrency is required at this stage beyond the regeneration-vs-edit policy decided in Phase 0 research.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Note |
|---|---|---|
| I. Graph-as-Source-of-Truth | **PASS** | Criteria continue to live on the `UserStory` Neo4j node (`acceptanceCriteria` property already in `docs/cypher/schema/03_node_types.cypher:48`). No new store. |
| II. Event Storming as Domain Vocabulary | **PASS** | UserStory, Acceptance Criteria, GWT — all native ES/DDD vocabulary. No CRUD-flavoured renames. |
| III. Streaming-First UX for Long-Running Work | **N/A** | Inline edit and PATCH are sub-second graph mutations. No long-running pipeline introduced. |
| IV. Human-in-the-Loop on Mutations | **PASS** | The user *is* the human in the loop — they edit and save explicitly via the panel. The downstream GWT generation that consumes criteria still goes through its existing propose-then-confirm path; this feature does not auto-trigger GWT regeneration on criteria edits (see research D2). |
| V. Feature-Modular Architecture | **PASS** | Backend changes live under `api/features/user_stories/` (existing feature module) and `api/features/ingestion/event_storming/nodes_gwt.py` (existing module). Frontend changes live in `frontend/src/features/canvas/ui/InspectorPanel.vue`, `frontend/src/features/userStories/`, and the navigator. The `userStoryEditor.store.js` + `UserStoryEditModal.vue` files are removed (not orphaned). |
| VI. Provider-Agnostic LLM Runtime | **PASS** | GWT prompt is enriched with criteria text; the runtime abstraction in `api/features/ingestion/ingestion_llm_runtime.py` is unchanged. |
| VII. Observable by Default | **PASS** | New PATCH endpoint emits structured logs with correlation ID at start/success/error, matching the pattern in the rest of `authoring_router.py`. |

**Result**: All gates PASS pre-Phase-0. No Complexity Tracking entries needed.

Re-check after Phase 1 design (see end of Phase 1 below): still PASS — design only adds a property to existing payloads, one new PATCH route, one new InspectorPanel branch, and a string list in the GWT prompt. No new principle to violate.

## Project Structure

### Documentation (this feature)

```text
specs/019-userstory-properties-panel/
├── plan.md              # This file (/speckit-plan output)
├── spec.md              # Already written
├── research.md          # Phase 0 output — D1..D4 decisions
├── data-model.md        # Phase 1 — UserStory deltas + criteria edit-tracking
├── quickstart.md        # Phase 1 — manual smoke (dblclick → panel → edit → save → reload → GWT regen)
├── contracts/
│   └── user-stories-api.md   # PATCH + extended GET shapes; GWT input addendum
├── checklists/
│   └── requirements.md  # Already written
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
api/
├── features/
│   ├── user_stories/
│   │   ├── authoring_router.py        # MODIFY: add PATCH /user-story/{id}; extend /apply to accept acceptance_criteria
│   │   └── catalog_router.py          # MODIFY: include acceptanceCriteria in GET responses
│   └── ingestion/
│       ├── event_storming/
│       │   ├── neo4j_ops/
│       │   │   └── user_stories.py    # MODIFY: extend create_user_story() to accept acceptance_criteria; add update fn
│       │   └── nodes_gwt.py           # MODIFY: pull linked UserStory.acceptanceCriteria into prompt context
│       └── workflow/
│           └── phases/
│               └── user_stories.py    # MODIFY: respect criteriaUserEdited flag on re-ingestion (D2 policy)

frontend/
└── src/
    └── features/
        ├── canvas/ui/
        │   └── InspectorPanel.vue                       # MODIFY: add UserStory branch — fields + criteria editor
        ├── userStories/
        │   ├── userStoryEditor.store.js                 # DELETE (after entry-point migration)
        │   └── ui/
        │       └── UserStoryEditModal.vue               # DELETE (after entry-point migration)
        ├── navigator/ui/
        │   └── TreeNode.vue                             # MODIFY: dblclick on UserStory routes to InspectorPanel
        └── App.vue                                      # MODIFY: remove UserStoryEditModal mount

tests/  (per existing repo convention — backend tests beside features, frontend tests under frontend/tests)
└── (see tasks.md once /speckit-tasks runs)
```

**Structure Decision**: Web-application layout — backend under `api/` and frontend under `frontend/`, each with its own feature-modular subtree. This feature does **not** introduce any new top-level directory; every change lands in an existing feature module per Principle V. The frontend `userStories/` feature folder shrinks (modal + store removed) while the canvas `InspectorPanel` absorbs UserStory rendering, mirroring how every other domain type is already handled there.

## Complexity Tracking

> No constitution violations. Section intentionally empty.
