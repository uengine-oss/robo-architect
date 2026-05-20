# Implementation Plan: Aggregate Invariants

**Branch**: `figma-integration` | **Date**: 2026-05-18 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/027-aggregate-invariants/spec.md`

## Summary

Introduce **Invariant** as a first-class modeling object attached under an Aggregate. Each
Invariant carries a declaration statement and a set of detailed Given-When-Then conditions. Those
conditions are expressed by reusing the existing `Given`/`When`/`Then` model: an Invariant either
**references** a Command (`VERIFIED_BY` edge → the Command's GWT acceptance criteria are the
shared, jointly-edited condition) or **owns** a standalone GWT triple
(`parentType="Invariant"`). Invariants live only in the navigator design tree and the inspector —
never as a canvas sticker. Legacy `Aggregate.invariants` text is lazily migrated to `Invariant`
nodes; the ingestion pipeline gains an `extract_invariants_phase`. The GWT editing form is
extracted into a shared `GwtEditor.vue` so Commands and Invariants edit GWT through one window.

## Technical Context

**Language/Version**: Python 3.11+ (backend), Vue 3 + Vite (frontend)
**Primary Dependencies**: FastAPI, Pydantic, Neo4j official driver, LangChain/LangGraph (ingestion
LLM), Vue Flow / Pinia (frontend)
**Storage**: Neo4j (single source of truth — constitution I)
**Testing**: pytest (backend), Playwright (`frontend/tests/`) for UI smoke
**Target Platform**: Linux server backend + browser SPA
**Project Type**: Web application (mirrored `api/features/` ↔ `frontend/src/features/`)
**Performance Goals**: Invariant CRUD and tree expansion are instant graph queries (<200ms p95);
ingestion invariant extraction streamed phase-by-phase
**Constraints**: No second source of truth; reuse the existing `Given`/`When`/`Then` model rather
than a new condition label; no canvas node for Invariants
**Scale/Scope**: ~5 backend files + 1 ingestion phase + schema updates; ~4 frontend files + 1
component extraction; tens of Invariants per Aggregate

## Constitution Check

*GATE: evaluated against constitution v1.1.0. Re-checked after Phase 1 design — still passing.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Graph-as-Source-of-Truth | PASS | `Invariant` node + relationships in Neo4j; legacy text migrated then cleared; no parallel store. |
| II. Event Storming Vocabulary | PASS | "Invariant" is a DDD aggregate-design term; label `Invariant`, relationships `HAS_INVARIANT` / `VERIFIED_BY`. |
| III. Streaming-First UX | PASS | CRUD are instant graph queries (plain req/resp allowed); ingestion extraction streams `EXTRACTING_INVARIANTS`. |
| IV. Human-in-the-Loop on Mutations | PASS | CRUD are direct user actions, not LLM edits to an existing graph; ingestion output is an inherently reviewable draft (research R7). No propose→apply needed. |
| V. Feature-Modular Architecture | PASS | New `api/features/invariants/` ↔ `frontend/src/features/invariants/`. GWT reuse goes through the existing `/api/graph/gwt/*` API surface, not cross-feature imports. See note below on `GwtEditor.vue`. |
| VI. Provider-Agnostic LLM | PASS | `extract_invariants_phase` uses `ctx.llm`; no hardcoded provider/model. |
| VII. Observable by Default | PASS | New phase emits `SmartLogger` events at phase boundaries with correlation ID; CRUD routes inherit platform observability. |
| VIII. Figma SceneGraph Pipeline | N/A | Feature produces no `SerializedSceneGraph`. |
| IX. Plugin ↔ Backend Dev-Loop | N/A | No Figma plugin surface. |

**Note on Principle V (`GwtEditor.vue`)**: extracting the GWT form from `InspectorPanel.vue` into
a reusable component is a refactor *within* the `canvas` feature. The new `invariants` feature
imports that component — a shared Vue UI component, not business logic or state. This is
acceptable presentation-layer reuse; no graph state or service crosses the feature boundary.
If a `frontend/src/shared/ui/` location exists it is preferred; otherwise the component stays in
`canvas/ui/GwtEditor.vue`. No constitution violation — recorded here for transparency.

**Gate result**: PASS — no violations, Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/027-aggregate-invariants/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 — 8 decisions (R1–R8)
├── data-model.md        # Phase 1 — Neo4j schema + Pydantic DTOs + ingestion phase
├── contracts/
│   └── rest-api.md       # Phase 1 — /api/invariants router + GWT reuse + SSE event
├── quickstart.md        # Phase 1 — 7 manual smoke scenarios (S1–S7)
└── tasks.md             # Phase 2 — created by /speckit-tasks (NOT this command)
```

### Source Code (repository root)

```text
api/
├── features/
│   ├── invariants/                         # NEW feature module
│   │   ├── __init__.py
│   │   ├── router.py                       # /api/invariants + /api/aggregates/{id}/invariants
│   │   ├── invariants_contracts.py         # Pydantic DTOs (data-model §2)
│   │   ├── invariants_service.py           # CRUD + lazy migration orchestration
│   │   └── neo4j_ops.py                    # Invariant node/edge Cypher ops
│   ├── canvas_graph/routes/gwt.py          # EDIT: parentType Literal += "Invariant"
│   ├── contexts/router.py                  # EDIT: full-tree Aggregate += invariants[]
│   └── ingestion/
│       ├── event_storming/
│       │   ├── neo4j_ops/invariants.py     # NEW: InvariantOps for ingestion
│       │   ├── structured_outputs.py       # EDIT: ExtractedInvariant(Set)
│       │   └── prompts.py                  # EDIT: invariant-extraction prompt
│       ├── workflow/phases/extract_invariants.py   # NEW ingestion phase
│       └── ingestion_workflow_runner.py    # EDIT: register phase after generate_gwt
├── main.py                                 # EDIT: include invariants router
docs/cypher/schema/
├── 01_constraints.cypher                    # EDIT: Invariant constraints
├── 02_indexes.cypher                        # EDIT: Invariant indexes
├── 03_node_types.cypher                     # EDIT: Invariant example + parentType note
└── 04_relationships.cypher                  # EDIT: HAS_INVARIANT, VERIFIED_BY

frontend/
├── src/features/
│   ├── invariants/                         # NEW feature module
│   │   ├── invariants.api.js               # REST client
│   │   ├── invariants.store.js             # Pinia store
│   │   └── ui/InvariantEditor.vue          # Declaration + conditions editor
│   ├── canvas/ui/
│   │   ├── GwtEditor.vue                   # NEW: GWT form extracted from InspectorPanel
│   │   └── InspectorPanel.vue              # EDIT: mount GwtEditor; host InvariantEditor
│   └── navigator/
│       ├── ui/TreeNode.vue                 # EDIT: Invariant node type + Invariants group
│       └── navigator.store.js              # EDIT: carry invariants[] per Aggregate
└── tests/
    └── aggregate-invariants.spec.ts        # NEW: Playwright smoke (quickstart S1–S7)
```

**Structure Decision**: Web-application layout with mirrored backend/frontend feature modules
(constitution V). A dedicated `invariants` feature module is added on both sides. GWT editing is
reused — not reimplemented — by extending the existing `/api/graph/gwt/*` endpoint's `parentType`
and by extracting a shared `GwtEditor.vue`. The navigator and contexts features receive small
edits to surface Invariants in the tree; the ingestion feature gains one phase.

## Phase 0 — Research

Complete. See [research.md](research.md): 8 decisions —
R1 `Invariant` label + `HAS_INVARIANT`; R2 idempotent key `<aggregate.key>.invariant.<slug>`;
R3 reuse `Given/When/Then` via `VERIFIED_BY` (referenced) + `parentType="Invariant"` (owned),
no duplicate-condition label; R4 extract shared `GwtEditor.vue`; R5 lazy migration guarded by
`invariantsMigratedAt`; R6 `extract_invariants_phase` after `generate_gwt`; R7 HITL not
applicable to direct CRUD; R8 no canvas node.

## Phase 1 — Design & Contracts

Complete. Artifacts: [data-model.md](data-model.md), [contracts/rest-api.md](contracts/rest-api.md),
[quickstart.md](quickstart.md). Agent context (`CLAUDE.md` SPECKIT block) updated to point here.

## Phase 2 — Next

Run `/speckit-tasks` to generate `tasks.md` (dependency-ordered implementation tasks). Suggested
ordering: schema files → backend `invariants` module + GWT `parentType` extension → contexts
full-tree extension → ingestion phase → frontend `GwtEditor.vue` extraction → `invariants`
frontend module + navigator tree integration → Playwright smoke.

## Complexity Tracking

No constitution violations — no entries.
