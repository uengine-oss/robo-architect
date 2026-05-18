# Implementation Plan: UI Sticker Flow Edges with Conditional Gateways

**Branch**: `025-ui-flow-edges` | **Date**: 2026-05-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/025-ui-flow-edges/spec.md`

## Summary

Add a new "user-journey" layer to the Event Storming graph by introducing a `:Gateway` node (XOR diamond) and a `[:NEXT_UI]` relationship between UI stickers (and Gateways). LLM-derive these from uploaded source documents during a new ingestion phase that runs after the existing `ui_wireframes` phase; render them on the event-modeling canvas as visually distinct arrows + diamonds; expose Inspector edit + manual draw with `source='manual'` preservation across re-ingest. Layer is independent of the existing `UI → Command → Event → ReadModel → UI` data-flow chain.

## Technical Context

**Language/Version**: Python 3.11+ (backend), Vue 3 + Vite (frontend)
**Primary Dependencies**: FastAPI, LangChain + LangGraph (ingestion pipeline), Neo4j Python driver (`api/platform/neo4j.py`), Vue Flow (canvas rendering), Pydantic v2
**Storage**: Neo4j (single source of truth per Constitution I) — adds `:Gateway` label, `[:NEXT_UI]` and `[:HAS_GATEWAY]` relationships; schema in `docs/cypher/schema/03_node_types.cypher` + `04_relationships.cypher`
**Testing**: pytest (backend, unit + workflow), Vitest/Playwright (frontend existing patterns), manual smoke per `quickstart.md`
**Target Platform**: Linux server (uvicorn behind reverse proxy), modern browser frontend
**Project Type**: Web application — `api/features/<feature>/` backend + `frontend/src/features/<feature>/` mirror per Constitution V
**Performance Goals**: Canvas renders ≤50 UIs + 80 `NEXT_UI` edges in <2s (SC-005); idempotent re-ingest produces zero net changes (SC-003); upsert/delete graph endpoints <300ms p95 under nominal Neo4j load
**Constraints**: No second source of truth (graph-only state); LLM phase MUST stream progress via existing SSE channel; manual edits MUST survive re-ingest 100% (SC-004); provider-agnostic LLM access via `get_llm_provider_model()`
**Scale/Scope**: Per-document scope — typical ingestion run has 10–30 UI nodes; aggressive ceiling 200 UIs; cross-BC edges allowed; v1 supports only `kind='exclusive'` gateways

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Graph-as-Source-of-Truth | ✅ Pass | All new state (`Gateway`, `NEXT_UI`) lives in Neo4j; no parallel store. Canvas reads via existing `/api/graph/event-modeling` query path; edits via new write endpoints |
| II. Event Storming Vocabulary | ✅ Pass | `Gateway` and `NEXT_UI` extend the DDD/Event-Storming vocabulary in a way the user explicitly asked for. Names are short and consistent with `HAS_AGGREGATE`/`HAS_POLICY`/`HAS_UI` conventions |
| III. Streaming-First UX | ✅ Pass | The new ingestion phase is an `AsyncGenerator[ProgressEvent, None]` exactly like `generate_ui_wireframes_phase`; it yields phase/progress/data events on the same SSE channel |
| IV. Human-in-the-Loop on Mutations | ✅ Pass | LLM proposes edges via ingestion (which is already a propose-then-persist flow through the existing UI confirmation gates); manual edits are an explicit user action; gateway delete requires a strategy choice (`stitch` vs `drop`) — no silent destructive default |
| V. Feature-Modular Architecture | ✅ Pass | Backend lives under `api/features/ingestion/event_storming/` (graph ops + LLM node) and `api/features/canvas_graph/routes/` (read/write endpoints); frontend under `frontend/src/features/eventModeling/`. No cross-feature imports |
| VI. Provider-Agnostic LLM | ✅ Pass | New LLM call uses `get_llm_provider_model()` per existing ingestion phases; no hardcoded provider/model |
| VII. Observable by Default | ✅ Pass | Logs at `agent.nodes.ui_flow.*` and `api.graph.ui_flow.*` with workflow_id + counts (FR-022); generation warning codes are first-class (FR-023) |
| VIII. Figma SceneGraph Pipeline | ✅ N/A | This feature does not emit `SerializedSceneGraph`. It consumes existing UI ids only |
| IX. Plugin ↔ Backend Dev-Loop | ✅ N/A | No plugin code changes |

**Result**: All gates pass. No entries required in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/025-ui-flow-edges/
├── plan.md              # This file
├── spec.md              # /speckit-specify output
├── research.md          # Phase 0 output (decisions D1–D6)
├── data-model.md        # Phase 1: Pydantic + Neo4j schema for Gateway / NEXT_UI
├── quickstart.md        # Phase 1: 6 manual smoke scenarios
├── contracts/
│   └── rest-api.md      # Phase 1: new /api/graph/ui-flow/* endpoints
├── checklists/
│   └── requirements.md  # /speckit-specify output
└── tasks.md             # /speckit-tasks output (not created here)
```

### Source Code (repository root)

```text
api/
├── features/
│   ├── ingestion/
│   │   ├── workflow/
│   │   │   └── phases/
│   │   │       └── ui_flow_edges.py            # NEW: phase 12 — LLM-derives NEXT_UI + Gateway after ui_wireframes
│   │   ├── event_storming/
│   │   │   ├── neo4j_ops/
│   │   │   │   └── ui_flow.py                  # NEW: UIFlowOps — upsert/delete Gateway + NEXT_UI, bulk variants
│   │   │   ├── structured_outputs.py           # EXTEND: UIFlowItem, GatewayItem Pydantic models for LLM JSON output
│   │   │   └── prompts.py                      # EXTEND: UI_FLOW_SYSTEM_PROMPT
│   │   └── ingestion_workflow_runner.py        # EDIT: invoke new phase after existing ui_wireframes step
│   ├── canvas_graph/
│   │   ├── router.py                           # EDIT: include new ui_flow_router
│   │   └── routes/
│   │       ├── ui_flow.py                      # NEW: /api/graph/ui-flow/{edge,gateway} CRUD endpoints
│   │       └── event_modeling.py               # EDIT: include NEXT_UI edges + Gateway nodes in /event-modeling response
│   └── platform/
│       └── keys.py                             # EDIT: add gateway_key() + ui_flow_edge_key() helpers
└── tests/
    ├── features/ingestion/event_storming/test_ui_flow_phase.py    # NEW
    └── features/canvas_graph/test_ui_flow_routes.py               # NEW

frontend/
└── src/
    └── features/
        └── eventModeling/
            ├── eventModeling.store.js          # EDIT: load NEXT_UI edges + Gateway nodes; manual-draw action
            └── ui/
                ├── EventModelingPanel.vue      # EDIT: render diamond + dashed/colored UI-flow arrows + condition labels
                └── GatewayInspector.vue        # NEW: Inspector form for Gateway label + per-edge condition list

docs/cypher/schema/
├── 03_node_types.cypher                        # EDIT: add Gateway node section
└── 04_relationships.cypher                     # EDIT: add NEXT_UI + HAS_GATEWAY sections
```

**Structure Decision**: Web-application split per Constitution V. Backend ingestion code lives under the existing `event_storming/` feature (this is an extension of the same workflow, not a new feature) plus a new `workflow/phases/ui_flow_edges.py` to mirror `ui_wireframes.py`. Canvas read/write endpoints follow the established `canvas_graph/routes/<topic>.py` pattern. Frontend mirrors backend under `eventModeling/`. No new top-level features are introduced.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*No constitution violations. Section intentionally empty.*
