# Implementation Plan: Robo Spec Skills & MCP Bridge

**Branch**: `029-robo-spec-skills` | **Date**: 2026-05-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/029-robo-spec-skills/spec.md`

## Summary

Ship four Claude Code skills (`/robo-plan`, `/robo-tasks`, `/robo-implement`, `/robo-sync`) and the MCP server that backs them, so a developer can go from a Robo Architect design (BC / Aggregate) to scaffolded, layered code — and back — without ever authoring a local `spec.md` / `data-model.md` / `contracts/`. The skill set lives **verbatim** under a new repo-root directory `skills/robo-spec/` and is copied byte-for-byte into the linked Claude Code workspace by the existing `setup-project` flow (no Jinja). The MCP server is mounted **in-process** in the existing FastAPI app over streamable-HTTP transport (Principles I, VI, VII). Architecture style in the generated `plan.md` is driven by a new optional `BoundedContext.classification ∈ {core, supporting}` property: `core` ⇒ clean architecture; `supporting` ⇒ default speckit-plan layout. Source mapping (which file backs which Aggregate/Command/Event/ReadModel) lives **only in the Neo4j ontology** as `(:Element)-[:IMPLEMENTED_IN]->(:ImplementationFile)`; there is no workspace-local mapping file, and no marker comments are written into the developer's source code at codegen time. `/robo-sync` discovers element changes via **full AST extraction** of the linked files (Python via stdlib `ast`, TypeScript via a small `@typescript-eslint/typescript-estree` Node helper shipped in `skills/robo-spec/`), normalizes the structural extract, and proposes a diff that the developer confirms before any destructive change reaches the graph (Principle IV). Progress is reflected on Robo Architect's Design tab in ≤5 s via a backend `watchfiles` watcher over `<workspace>/specs/**/tasks.md` and an SSE channel (Principle III). Click-to-open-file from the Design tab resolves through the same graph-only mapping plus the existing claude-code workspace file API.

## Technical Context

**Language/Version**: Python 3.11+ (backend MCP server + new FastAPI routes); TypeScript / Vue 3 (frontend Design-tab additions); plain Markdown (skill files under `robo-spec/`, copied verbatim).

**Primary Dependencies**:

- Backend: FastAPI, Pydantic, Neo4j driver (existing); new — `mcp` (official Anthropic Python SDK) for the in-process MCP server, `watchfiles` for the tasks.md filesystem watcher.
- Frontend: Vue 3 + Vue Flow + native `EventSource` (existing). No new framework dependencies.
- `/robo-sync` AST extractors (run client-side inside the workspace, shipped verbatim under `skills/robo-spec/robo-sync/extractors/`): Python stdlib `ast` (no extra deps); for TypeScript, a tiny Node helper using `@typescript-eslint/typescript-estree`. The helpers are invoked by Claude Code via Bash; no extractor code runs in the backend.
- Skill files: zero runtime dependencies — they are pure Markdown / YAML frontmatter consumed by Claude Code's skill loader.

**Storage**: Neo4j (existing) for the design **and the source mapping** — one new optional property (`BoundedContext.classification`), one new node label (`:ImplementationFile`), and one new relationship (`[:IMPLEMENTED_IN]`). On-disk workspace files under `<workspace>/.claude/` and `<workspace>/specs/<NNN>-<slug>/` for skill text, plan, and tasks **only** — no workspace-local source-mapping file. No new databases.

**Testing**: pytest for backend (`api/features/robo_spec/tests/`), with FastAPI `TestClient` for the HTTP contract and a mocked MCP harness for the tool contract. Vitest for any new frontend composable / component (`frontend/src/features/robo_spec/`). Manual smoke per `quickstart.md` for the end-to-end path.

**Target Platform**: macOS and Linux developer workstations running Claude Code (desktop / IDE / web), backed by the existing Robo Architect backend that already runs on Linux/macOS.

**Project Type**: Web application (FastAPI backend + Vue 3 frontend), with an additional **distribution artifact** — the verbatim-copyable `skills/robo-spec/` skill tree at the repo root.

**Performance Goals**:

- MCP read tools (`resolve_design_element`, `get_bc_design`, `compute_drift`) p95 < 500 ms for a BC with up to ~30 child elements.
- `tasks.md` change ⇒ Design-tab badge update median < 2 s, p95 < 5 s (SC-003).
- Click-to-open from Design tab median < 2 s, p90 < 2 s (SC-004).
- `setup-project` install (verbatim copy of `skills/robo-spec/`) < 1 s on local disk.

**Constraints**:

- The MCP server MUST be the sole channel skills use to read/write Robo Architect data (FR-006, Principle I).
- `/robo-plan` MUST NOT produce `spec.md`, `data-model.md`, or `contracts/` in the consumer workspace (FR-001, FR-004).
- Skill files under `skills/robo-spec/` MUST be byte-identical to what lands in `<workspace>/.claude/skills/` (FR-012, SC-006).
- Source mapping (element → implementation file) MUST live exclusively in the Neo4j ontology — there is no workspace-local mapping file, and no marker comments are written into developer source code at codegen time. Read/write goes through MCP T2 / T6b (Principle I).
- `/robo-sync` MUST propose before applying destructive (rename/delete) design changes (FR-011, Principle IV). The proposal is built from a full AST extract of the linked source files, not from in-source markers.
- All new HTTP routes MUST appear in `/docs` (Constitution Development Workflow rule).
- The schema additions (`BoundedContext.classification`, `:ImplementationFile`, `[:IMPLEMENTED_IN]`) MUST be reflected in `docs/cypher/schema/03_node_types.cypher` and `04_relationships.cypher` before any code emitting them ships (Principle I).

**Scale/Scope**: A typical Robo Architect project has a handful of BCs and dozens of aggregates / commands / events / read-models. The MCP server is single-tenant per backend process; multiple workspaces on different machines connect over streamable-HTTP. Frontend changes are localized to two existing components (`EventModelingPanel.vue`, `InspectorPanel.vue`) plus one new feature folder.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle                                       | Status   | Notes |
|-------------------------------------------------|----------|-------|
| I. Graph-as-Source-of-Truth (NON-NEGOTIABLE)    | ✅ Pass | The new `classification` field on `BoundedContext`, the new `:ImplementationFile` node, and the new `[:IMPLEMENTED_IN]` relationship are all added to the existing graph and documented in `docs/cypher/schema/`. **Source mapping is stored exclusively in the graph** — there is no workspace-local mapping file, and no marker comments are written into developer source code at codegen time. Progress state (parsed from `tasks.md` checkboxes at request time) is derivative and ephemeral. `/robo-sync` writes back to the graph through Robo Architect's existing mutation pathways. |
| II. Event Storming as Domain Vocabulary         | ✅ Pass | Every tool, route, marker, and skill argument speaks the existing vocabulary (BC, Aggregate, Command, Event, ReadModel, Policy, Invariant). No CRUD renames. |
| III. Streaming-First UX for Long-Running Work   | ✅ Pass | Progress reflection uses SSE (`GET /api/robo-spec/projects/{project_id}/progress/stream`). `/robo-implement` runs inside Claude Code, which streams natively. Short MCP calls (`resolve_design_element`, etc.) are intentionally request/response per the constitution's own carve-out for instant graph queries. |
| IV. Human-in-the-Loop on Mutations              | ✅ Pass | `/robo-sync` is split into `propose_sync` and `apply_proposal` MCP tools; destructive operations (rename/delete) require explicit confirmation in the `confirmed` array. `/robo-plan` asking the developer for missing BC classification is itself a human-in-the-loop step, with the answer persisted via `set_bc_classification`. |
| V. Feature-Modular Architecture                 | ✅ Pass | New backend feature at `api/features/robo_spec/`; mirrored frontend feature at `frontend/src/features/robo_spec/`. Cross-feature reads (BC/Aggregate data) go through existing platform/Neo4j layers, not through direct imports into `api/features/contexts/`. |
| VI. Provider-Agnostic LLM Runtime               | ✅ Pass / Not Applicable | The MCP server itself does not call any LLM provider; the LLM is Claude Code on the user's side. No provider/model is hardcoded anywhere in this feature. |
| VII. Observable by Default                      | ✅ Pass | Every MCP tool returns a `correlationId` threaded into `SmartLogger`; the in-process MCP mount inherits the existing correlation-ID middleware. SSE stream events carry timestamps. |
| VIII. Figma SceneGraph Generation Pipeline      | ✅ Not Applicable | No SceneGraph is produced; no Figma plugin touches this feature. |
| IX. Plugin ↔ Backend Dev-Loop Discipline        | ⚠️ Acknowledged | Not Figma-specific, but `quickstart.md` pre-reqs call out `uvicorn --reload`, which is the same footgun as Principle IX's uvicorn point — included to prevent the "endpoint not found" failure mode for the new `/api/robo-spec/*` routes during dev. |

**Result**: All gates pass. **No** entries in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/029-robo-spec-skills/
├── spec.md                       # Feature spec (already authored)
├── plan.md                       # This file
├── research.md                   # Phase 0 — decisions R1..R10
├── data-model.md                 # Phase 1 — Neo4j delta + on-disk artifacts + MCP in-process state
├── quickstart.md                 # Phase 1 — manual smoke plan (S1..S13)
├── contracts/
│   ├── mcp-tools.md              # MCP tool contract (T1..T8)
│   └── http-api.md               # New / extended FastAPI routes (E1..E6)
└── checklists/
    └── requirements.md           # Spec-quality checklist (from /speckit-specify)
```

### Source Code (repository root)

This is a multi-component layout that **extends** existing trees rather than introducing parallel ones:

```text
skills/                                     # NEW — verbatim source-of-truth for skill files (FR-012)
└── robo-spec/
    ├── robo-plan/SKILL.md                  # thin delegation+override on speckit-plan (R11)
    ├── robo-tasks/SKILL.md                 # thin delegation+override on speckit-tasks (R11)
    ├── robo-implement/SKILL.md             # thin delegation+override on speckit-implement (R11)
    └── robo-sync/                          # no speckit counterpart — self-contained
        ├── SKILL.md
        └── extractors/                     # client-side AST extractors (run via Bash in the workspace)
            ├── python_extract.py           # stdlib `ast` based
            └── ts_extract.mjs             # @typescript-eslint/typescript-estree based

api/
├── features/
│   ├── robo_spec/                          # NEW
│   │   ├── __init__.py
│   │   ├── router.py                       # E2..E6 + MCP mount at /mcp
│   │   ├── mcp_server.py                   # MCP tool implementations (T1..T8 + T6b)
│   │   ├── schemas.py                      # Pydantic models for HTTP + MCP I/O
│   │   ├── service.py                      # Pure business logic (resolve, drift, structural diff)
│   │   ├── implementation_files.py         # CRUD for :ImplementationFile + [:IMPLEMENTED_IN]
│   │   ├── tasks_watcher.py                # watchfiles-based watcher → SSE
│   │   └── tests/
│   │       ├── contract/                   # FastAPI TestClient + MCP harness
│   │       └── unit/
│   ├── claude_code/router.py               # EXTEND — verbatim-copy step in setup-project (E1)
│   └── contexts/router.py                  # EXTEND — expose classification + implementationFiles in tree responses
└── platform/
    └── neo4j.py                            # (used as-is; no new helpers required)

docs/
└── cypher/
    └── schema/
        ├── 03_node_types.cypher            # EXTEND — document BoundedContext.classification + :ImplementationFile
        └── 04_relationships.cypher         # EXTEND — document [:IMPLEMENTED_IN]

frontend/
└── src/
    └── features/
        ├── robo_spec/                      # NEW
        │   ├── components/ProgressBadge.vue
        │   ├── composables/useRoboProgressStream.ts
        │   ├── composables/useOpenImplFile.ts
        │   └── tests/
        ├── canvas/ui/InspectorPanel.vue    # EXTEND — Aggregate "View Detail" wiring continues to work; add no progress logic here unless required by US3
        └── eventModeling/ui/EventModelingPanel.vue  # EXTEND — render ProgressBadge per node, wire click-to-open
```

**Structure Decision**: Standard Robo Architect layout (Principle V: backend feature ↔ frontend feature mirror) plus a top-level `skills/robo-spec/` directory whose only job is to be a verbatim source for `setup-project` to copy. Putting it under `api/features/prd_generation/` would invite Jinja templating; putting it under `.claude/skills/` (the in-repo skills directory) would conflate the Robo Architect repo's own developer skills with the skills shipped to consumer workspaces. The `skills/` prefix makes the distribution intent explicit, and nesting under `robo-spec/` naturally groups future additional skill sets (one subdirectory per product). The AST extractors live under `skills/robo-spec/robo-sync/extractors/` so they ride the same verbatim-copy install path as the SKILL.md files and never touch the backend.

**Skill-inheritance shape** (R11): each of `robo-plan`, `robo-tasks`, `robo-implement` is a **thin delegation-and-override `SKILL.md`** that explicitly inherits the workspace-installed upstream `speckit-{plan,tasks,implement}/SKILL.md` and applies a numbered override list on top. No build step, no template engine — verbatim copy of the override file is sufficient. Frontmatter pins `requires-speckit:` to a tested range; quickstart S14 re-validates inheritance whenever speckit is upgraded. `/robo-sync` has no upstream counterpart and ships a self-contained SKILL.md.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No constitutional violations. Table intentionally empty.
