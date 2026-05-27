---

description: "Task list for Robo Spec Skills & MCP Bridge"
---

# Tasks: Robo Spec Skills & MCP Bridge

**Input**: Design documents from [`specs/029-robo-spec-skills/`](.)

**Prerequisites**: [plan.md](plan.md) (required), [spec.md](spec.md) (required for user stories), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/)

**Tests**: This feature does **not** request TDD. End-to-end validation is the manual smoke plan in [quickstart.md](quickstart.md) (S1..S14), executed in the Polish phase. Add unit/contract tests opportunistically inside the relevant user-story phase if you want them — they are not enumerated here.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1..US6)
- Include exact file paths in descriptions

## Path Conventions

This is a multi-component project (backend `api/`, frontend `frontend/`, plus the new verbatim-copy distribution root `robo-spec/` at the repo root). Paths below are repo-relative.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project scaffolding and dependency bootstrapping for everything downstream

- [x] T001 Create `robo-spec/` directory at repo root with subtree `robo-spec/.claude/skills/{robo-plan,robo-tasks,robo-implement,robo-sync}/` and `robo-spec/.claude/skills/robo-sync/extractors/` per [plan.md](plan.md) Project Structure
- [x] T002 Add `mcp` (official Anthropic Python SDK) and `watchfiles` to [pyproject.toml](pyproject.toml); run `uv pip compile` to refresh the lockfile (no breaking version bumps to existing pins)
- [x] T003 [P] Create [robo-spec/.claude/skills/robo-sync/extractors/package.json](robo-spec/.claude/skills/robo-sync/extractors/package.json) declaring `@typescript-eslint/typescript-estree` as the sole runtime dep for the TS AST helper
- [x] T004 Create backend feature scaffold [api/features/robo_spec/](api/features/robo_spec/) with empty `__init__.py`, `router.py`, `schemas.py`, `service.py`, `mcp_server.py`, `implementation_files.py`, `tasks_watcher.py`, and `tests/{contract,unit}/__init__.py`; register the new router in `api/main.py`
- [x] T005 [P] Create frontend feature scaffold [frontend/src/features/robo_spec/](frontend/src/features/robo_spec/) with empty `components/`, `composables/`, `tests/` subdirectories

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema + Pydantic + MCP transport + shared platform glue — every user story depends on these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T006 [P] Document `BoundedContext.classification` (optional string, `"core"|"supporting"`) in [docs/cypher/schema/03_node_types.cypher](docs/cypher/schema/03_node_types.cypher) per data-model §1.1 and Constitution Principle I
- [x] T007 [P] Document the new `:ImplementationFile { projectId, path, role, createdAt, lastSeenAt }` node and `(:Aggregate|Command|Event|ReadModel)-[:IMPLEMENTED_IN]->(:ImplementationFile)` relationship in [docs/cypher/schema/03_node_types.cypher](docs/cypher/schema/03_node_types.cypher) and [docs/cypher/schema/04_relationships.cypher](docs/cypher/schema/04_relationships.cypher); include the `CREATE CONSTRAINT` for unique `(projectId, path)`
- [x] T008 Write all Pydantic models for HTTP routes E1..E6 and MCP tools T1..T8 + T6b in [api/features/robo_spec/schemas.py](api/features/robo_spec/schemas.py) per [contracts/http-api.md](contracts/http-api.md) and [contracts/mcp-tools.md](contracts/mcp-tools.md) — these drive `/docs` Swagger discoverability (Constitution Development Workflow)
- [x] T009 Implement Neo4j CRUD for `:ImplementationFile` nodes and `[:IMPLEMENTED_IN]` relationships in [api/features/robo_spec/implementation_files.py](api/features/robo_spec/implementation_files.py): `register(elementId, files, mode="replace"|"merge")`, `lookup_by_element(elementId)`, `lookup_by_bc(bcId)`, path validation (POSIX, no `..`, no absolute) per data-model §1.2
- [x] T010 Mount the in-process MCP server at `/mcp` (streamable-HTTP transport) inside [api/features/robo_spec/router.py](api/features/robo_spec/router.py); ensure the existing `SmartLogger` correlation-ID middleware (Principle VII) wraps every MCP tool call by reusing the platform observability hook
- [x] T011 Implement HTTP E2 + E3 (`GET|PATCH /api/contexts/{bc_id}/classification`) in [api/features/contexts/router.py](api/features/contexts/router.py) with enum validation, optional `If-Match` version header, and a `SmartLogger` `bc.classification.changed` emission on write per [contracts/http-api.md](contracts/http-api.md)
- [x] T012 Extend `GET /api/contexts/{context_id}/tree` in [api/features/contexts/router.py](api/features/contexts/router.py) to include `classification` on the BC node, a per-element `version` integer, and `implementationFiles[]` on every Aggregate/Command/Event/ReadModel via a join into `[:IMPLEMENTED_IN]`; preserve existing field shape (additive only)

**Checkpoint**: Foundation ready — user story implementation can now begin in parallel.

---

## Phase 3: User Story 6 - Skills install by direct file copy, not Jinja templating (Priority: P1) 🎯 MVP enabler

**Goal**: `setup-project` lays down the verbatim-copied skill tree and the per-project MCP config so any downstream `/robo-*` invocation has the files it needs.

**Independent Test**: Wire any new project to a scratch workspace via `setup-project`; confirm `<workspace>/.claude/skills/` matches `robo-spec/.claude/skills/` byte-for-byte (no Jinja markers), and `<workspace>/.claude/{robo-project.json,mcp.json}` exist and point at the running backend. Run quickstart S1 to validate.

> **Sequencing note**: this story produces skeleton SKILL.md files (just frontmatter + a TODO body). The actual override content for each skill is authored in its respective user-story phase (US1 fills robo-plan, US2 fills robo-tasks, US4 fills robo-implement, US5 fills robo-sync + extractors). This keeps US6 honestly about *installation* and lets US1..US5 be authored in parallel.

### Implementation for User Story 6

- [x] T013 [US6] Extend `POST /api/claude-code/setup-project` in [api/features/claude_code/router.py](api/features/claude_code/router.py) to (a) `shutil.copytree(<repo>/robo-spec/.claude/skills/, <workspace>/.claude/skills/, dirs_exist_ok=True)`, (b) write `<workspace>/.claude/robo-project.json` per data-model §2.1, (c) write `<workspace>/.claude/mcp.json` with the project-specific `{backendUrl}/mcp` URL, (d) compute and return a sha256 `roboSpecChecksum` of the copied subtree, (e) reject `projectId` mismatch on re-run with HTTP 409 — all per [contracts/http-api.md](contracts/http-api.md) E1
- [x] T014 [P] [US6] Create skeleton [robo-spec/.claude/skills/robo-plan/SKILL.md](robo-spec/.claude/skills/robo-plan/SKILL.md): frontmatter only (`name: robo-plan`, `description`, `extends: speckit-plan`, `requires-speckit: ">=0.8.13, <0.9.0"`, `user-invocable: true`) + a `## Inheritance` header pointing at `.claude/skills/speckit-plan/SKILL.md` + a `## Overrides` heading with a TODO marker for US1 to flesh out — per research R11
- [x] T015 [P] [US6] Create skeleton [robo-spec/.claude/skills/robo-tasks/SKILL.md](robo-spec/.claude/skills/robo-tasks/SKILL.md) with the analogous frontmatter (`extends: speckit-tasks`) and inheritance header; `## Overrides` is a TODO for US2
- [x] T016 [P] [US6] Create skeleton [robo-spec/.claude/skills/robo-implement/SKILL.md](robo-spec/.claude/skills/robo-implement/SKILL.md) with analogous frontmatter (`extends: speckit-implement`); `## Overrides` is a TODO for US4
- [x] T017 [P] [US6] Create skeleton [robo-spec/.claude/skills/robo-sync/SKILL.md](robo-spec/.claude/skills/robo-sync/SKILL.md) — *no* `extends:` (self-contained per research R11) — with frontmatter (`name: robo-sync`, `requires-speckit: ">=0.8.13, <0.9.0"`, `user-invocable: true`) and a TODO body for US5
- [x] T018 [P] [US6] Create skeleton extractor stubs [robo-spec/.claude/skills/robo-sync/extractors/python_extract.py](robo-spec/.claude/skills/robo-sync/extractors/python_extract.py) and [robo-spec/.claude/skills/robo-sync/extractors/ts_extract.mjs](robo-spec/.claude/skills/robo-sync/extractors/ts_extract.mjs) (argument-parsing stubs that exit 1 with "TODO" — full implementation in US5)
- [x] T019 [US6] Add an install-integrity check script at [scripts/check_robo_spec_install.sh](scripts/check_robo_spec_install.sh) that (a) `diff -r robo-spec/.claude/skills/ <target>/.claude/skills/` returns no differences, (b) `grep -r -E '\{\{|\{%' robo-spec/.claude/skills/` returns nothing (no Jinja markers), and (c) the recorded `roboSpecChecksum` equals the recomputed sha256

**Checkpoint**: A linked workspace has the four skill skeletons installed, `mcp.json` + `robo-project.json` present, and quickstart S1 passes. Downstream user stories can now fill in the SKILL.md bodies and stand up the MCP tools.

---

## Phase 4: User Story 1 - Plan an implementation from a Robo Architect design (Priority: P1)

**Goal**: `/robo-plan <feature-id | BC-name | Aggregate-name>` resolves the argument via MCP, drafts `plan.md` with classification-driven architecture, never emits `spec.md` / `data-model.md` / `contracts/`, and seeds the implementation map in the graph.

**Independent Test**: Quickstart S2 (core → clean architecture, no `.robo-link.json`), S3 (supporting → default), S4 (missing classification → ask + write back).

### Implementation for User Story 1

- [ ] T020 [US1] Implement MCP tool `T1 resolve_design_element` (resolved | ambiguous) in [api/features/robo_spec/mcp_server.py](api/features/robo_spec/mcp_server.py): unions BC / Aggregate / feature-id resolution via Neo4j; returns disambiguation candidates when multiple matches per [contracts/mcp-tools.md](contracts/mcp-tools.md) T1
- [ ] T021 [US1] Implement MCP tool `T2 get_bc_design` in `mcp_server.py`: thin wrapper over the augmented `GET /api/contexts/{context_id}/tree` (T012), adds `INCOMPLETE_DESIGN` error path when the BC has zero aggregates per contract T2
- [ ] T022 [US1] Implement MCP tool `T3 set_bc_classification` in `mcp_server.py` (proxies to `PATCH /api/contexts/{bc_id}/classification` from T011); idempotent for the same value per contract T3
- [ ] T023 [US1] Implement MCP tool `T4 compute_drift` (stateless name compare) in `mcp_server.py`: input `references: [{id, kind, nameSeen}]` + `classificationSeen`; reports `renamed | deleted | added | reclassified` with `blocking: ["renamed","deleted","reclassified"]` per contract T4 and research R8
- [ ] T024 [US1] Replace the TODO in [robo-spec/.claude/skills/robo-plan/SKILL.md](robo-spec/.claude/skills/robo-plan/SKILL.md) `## Overrides` section with the numbered override list per research R11: (1) skip `setup-plan.sh` — resolve via T1 + T2 instead; (2) replace Phase 1 step 1 (data-model.md) with no-op; (3) replace Phase 1 step 2 (contracts/) with no-op; (4) classification-driven Phase 1 step 3 architecture template; (5) final `register_implementation_files(mode="merge", files=[])` for every element. Each override carries **both** the upstream step number **and** a verbatim phrase anchor (mitigation for speckit refactors per R11)
- [ ] T025 [US1] Add classification-driven architecture template snippets inline in [robo-spec/.claude/skills/robo-plan/SKILL.md](robo-spec/.claude/skills/robo-plan/SKILL.md) — a short clean-architecture template (entities / use cases / interface adapters / frameworks & drivers) and a short "use default speckit layout" pointer — so the LLM has explicit guidance per FR-005 / R4
- [ ] T026 [US1] Implement the "ask developer when classification is missing, then write back via T3" branch inside the robo-plan override list (T024); persist the answer via MCP `set_bc_classification` so the next run does not re-ask per FR-005 / S4

**Checkpoint**: `/robo-plan` end-to-end works against a real Robo Architect project (quickstart S2/S3/S4 pass).

---

## Phase 5: User Story 2 - Generate tasks and track checkbox progress in Design tab (Priority: P1)

**Goal**: `/robo-tasks` produces a `tasks.md` whose every checkbox carries an HTML-comment marker mapping it to a design element; checkbox state changes propagate to Robo Architect's Design tab within 5 s.

**Independent Test**: Quickstart S5 (tick checkbox → Design-tab badge update ≤ 5 s) + S13 (workspace-offline fallback). Implementation may proceed in parallel with US1 since the watcher + SSE path does not depend on US1's MCP tools.

### Implementation for User Story 2

- [ ] T027 [US2] Implement the tasks-marker parser in [api/features/robo_spec/tasks_watcher.py](api/features/robo_spec/tasks_watcher.py): regex over `tasks.md` extracting `(checkboxState, elementId, kind, item?)` for every `- [ ]` / `- [x]` line that carries a `<!-- @robo elementId="..." kind="..." item?="..." -->` marker; ignore lines without a marker per data-model §2.3
- [ ] T028 [US2] Implement the `watchfiles`-based watcher in `tasks_watcher.py`: per linked project, watch `<workspace>/specs/**/tasks.md`; debounce 200 ms; on change, reparse, diff against `WatchedTasksFile.lastCheckedState` (data-model §3.2), compute `todo|in-progress|done|blocked|orphaned` per element, publish a `progress` event onto the in-process SSE bus
- [ ] T029 [US2] Implement MCP tool `T5 report_progress` in [api/features/robo_spec/mcp_server.py](api/features/robo_spec/mcp_server.py): idempotent skill-side push; validates `elementId`, `featureDirectory`, `status`; fans out via the same SSE bus per contract T5
- [ ] T030 [US2] Implement MCP tool `T8 subscribe_progress` (SSE) in `mcp_server.py`: emits `progress` and `link-offline` events; on every fresh subscription, sends a synthetic `progress` event with the full current state for the project per contract T8 and research R6
- [ ] T031 [US2] Implement HTTP E5 `GET /api/robo-spec/projects/{project_id}/progress/stream` in [api/features/robo_spec/router.py](api/features/robo_spec/router.py) — a thin SSE wrapper around T8 so the frontend `EventSource` can subscribe without an MCP client; preserve the "full-state replay on reconnect" guarantee per [contracts/http-api.md](contracts/http-api.md) E5
- [ ] T032 [P] [US2] Implement frontend composable [frontend/src/features/robo_spec/composables/useRoboProgressStream.ts](frontend/src/features/robo_spec/composables/useRoboProgressStream.ts): subscribe to E5 with native `EventSource`; expose reactive `Map<elementId, status>`; auto-reconnect on network blips with full-state replay
- [ ] T033 [P] [US2] Implement frontend component [frontend/src/features/robo_spec/components/ProgressBadge.vue](frontend/src/features/robo_spec/components/ProgressBadge.vue): renders one of `todo | in-progress | done | blocked | orphaned | offline` with appropriate color + tooltip; consumes `status` as a prop
- [ ] T034 [US2] Wire `ProgressBadge.vue` into [frontend/src/features/eventModeling/ui/EventModelingPanel.vue](frontend/src/features/eventModeling/ui/EventModelingPanel.vue): inject `useRoboProgressStream` once at panel root; render one badge per Aggregate / Command / Event / ReadModel node using the reactive map; this is the **only** cross-feature edit `ProgressBadge.vue` requires (Principle V — through the composable, not via direct imports)
- [ ] T035 [US2] Replace the TODO in [robo-spec/.claude/skills/robo-tasks/SKILL.md](robo-spec/.claude/skills/robo-tasks/SKILL.md) `## Overrides` section with the directive that every produced checkbox item carry exactly one `<!-- @robo elementId="..." kind="..." item?="..." -->` marker keyed to the design element it implements per data-model §2.3 (these markers live **only** in `tasks.md`, never in source code — research R7)

**Checkpoint**: Tasks are produced with markers; checkbox toggles propagate to Design-tab badges within 5 s (quickstart S5 passes).

---

## Phase 6: User Story 3 - Open the implementation file from the design tab (Priority: P2)

**Goal**: Clicking an Aggregate / Command / Event / ReadModel on the Design tab opens its implementation file in the workspace editor; missing files show a "not implemented yet" affordance; an offline workspace shows "code link offline".

**Independent Test**: Quickstart S6 (happy path open in ≤ 2 s) + S7 (no file → affordance).

### Implementation for User Story 3

- [ ] T036 [US3] Implement MCP tool `T7 open_file_in_workspace` in [api/features/robo_spec/mcp_server.py](api/features/robo_spec/mcp_server.py): query `(:Element {id})-[:IMPLEMENTED_IN]->(:ImplementationFile)` via T009; resolve `preferredRole`; return one of `opened | not-implemented | ambiguous | offline` per contract T7
- [ ] T037 [US3] Implement HTTP E4 `POST /api/robo-spec/projects/{project_id}/open-file` in [api/features/robo_spec/router.py](api/features/robo_spec/router.py): proxies to T7; for the `opened` case, dispatches the actual open command through the existing `claude_code` workspace bridge in [api/features/claude_code/router.py](api/features/claude_code/router.py); returns 503 on bridge timeout
- [ ] T038 [US3] Implement HTTP E6 `GET /api/robo-spec/projects/{project_id}/implementation-map?bcId=` in [api/features/robo_spec/router.py](api/features/robo_spec/router.py): pure graph projection via T009's `lookup_by_bc(bcId)`; returns one `files[]` per element
- [ ] T039 [P] [US3] Implement frontend composable [frontend/src/features/robo_spec/composables/useOpenImplFile.ts](frontend/src/features/robo_spec/composables/useOpenImplFile.ts): calls E4; returns a tagged union of result variants; surfaces a "not-implemented" affordance with a hint pointing at the matching task in `tasks.md`, and an "ambiguous" picker
- [ ] T040 [P] [US3] On Design-tab BC change, fetch E6 once and merge `files[]` per element into a reactive store in [frontend/src/features/robo_spec/composables/useRoboProgressStream.ts](frontend/src/features/robo_spec/composables/useRoboProgressStream.ts) (or a sibling composable) so the badge UI can render `not-implemented` before any click
- [ ] T041 [US3] Wire click handlers on Aggregate / Command / Event / ReadModel nodes in [frontend/src/features/eventModeling/ui/EventModelingPanel.vue](frontend/src/features/eventModeling/ui/EventModelingPanel.vue) to `useOpenImplFile`; render the picker UI for `ambiguous` and the "not implemented yet" UI for `not-implemented`

**Checkpoint**: Click an existing file → editor opens (quickstart S6). Click a missing file → "not implemented yet" (quickstart S7).

---

## Phase 7: User Story 4 - Run the implementation loop via /robo-implement (Priority: P2)

**Goal**: `/robo-implement` writes code in the locations dictated by `plan.md`, registers each scaffolded file as an `:ImplementationFile` in the graph, and ticks `tasks.md` checkboxes as items complete — **without** writing any marker comments into source.

**Independent Test**: Quickstart S8 (`/robo-implement` ticks checkboxes + populates `:ImplementationFile` rows + `grep '@robo' src/` returns nothing).

### Implementation for User Story 4

- [ ] T042 [US4] Implement MCP tool `T6b register_implementation_files` in [api/features/robo_spec/mcp_server.py](api/features/robo_spec/mcp_server.py): wires to `implementation_files.py` (T009); supports `mode="replace"|"merge"`; rejects absolute / `..`-bearing paths with `INVALID_PATH` per contract T6b
- [ ] T043 [US4] Replace the TODO in [robo-spec/.claude/skills/robo-implement/SKILL.md](robo-spec/.claude/skills/robo-implement/SKILL.md) `## Overrides` section with: (a) constrain every produced file to the path layout dictated by the upstream `plan.md` (clean architecture for `core` BCs, default speckit layout for `supporting`); (b) after scaffolding each file, call `register_implementation_files(mode="merge")` with the new path + appropriate `role`; (c) after completing a task, atomically update its `tasks.md` checkbox to `[x]` via write-temp-then-rename (data-model §4); (d) on a blocked task, leave the checkbox unticked and append a brief reason annotation; (e) **never** write `@robo` marker comments into source files (research R7)

**Checkpoint**: `/robo-implement` runs end-to-end against a `core` BC; quickstart S8 passes including the `grep '@robo' src/` returning empty.

---

## Phase 8: User Story 5 - Reverse sync via /robo-sync (Priority: P2)

**Goal**: Developer edits to aggregate properties / event payloads / command parameters in source code are surfaced as a proposal via full AST extraction; the developer confirms (with explicit confirmation required for renames and deletions); the graph is updated through Robo Architect's existing mutation pathway.

**Independent Test**: Quickstart S9 (additive), S10 (rename with confirmation), S11 (no-op when nothing changed).

### Implementation for User Story 5

- [ ] T044 [US5] Implement [robo-spec/.claude/skills/robo-sync/extractors/python_extract.py](robo-spec/.claude/skills/robo-sync/extractors/python_extract.py) (stdlib `ast`): walk class definitions + dataclass fields + type annotations; emit one JSON document per element `{ kind, name, fields: [{name, type}] }` to stdout; the calling skill is responsible for resolving each name to an `elementId` via the design fetched from T2
- [ ] T045 [US5] Implement [robo-spec/.claude/skills/robo-sync/extractors/ts_extract.mjs](robo-spec/.claude/skills/robo-sync/extractors/ts_extract.mjs) using `@typescript-eslint/typescript-estree` (per T003): walk interfaces / type aliases / class members; emit the same JSON shape as T044; document the `node extractors/ts_extract.mjs <file.ts>` invocation
- [ ] T046 [US5] Implement the structural-diff service in [api/features/robo_spec/service.py](api/features/robo_spec/service.py): compare the incoming AST extract against the current graph; produce `added` / `modified` / `removed` per element; identify rename-candidate pairs by `(same type) AND (Levenshtein distance ≤ N OR substring overlap ≥ M)`; return both the raw diff and the candidate list per research R7
- [ ] T047 [P] [US5] (Optional) Add an LLM-ranking helper in `service.py` that uses the existing `api/features/ingestion/ingestion_llm_runtime.py` runtime (provider-agnostic per Principle VI) to score each rename-candidate pair and populate `confidence` + `rationale` fields per contract T6; if the runtime is not available, fall back to the deterministic ranker from T046 — the developer always makes the final call (Principle IV)
- [ ] T048 [US5] Implement MCP tool `T6 propose_sync` in [api/features/robo_spec/mcp_server.py](api/features/robo_spec/mcp_server.py): validate incoming `extracts[].version` against the current graph; call the diff service (T046) + optional ranker (T047); store the resulting proposal in `ProjectSession.pendingProposals[proposalId]` with a 10-minute TTL per data-model §3.1; return `proposalId`, `diff`, `renameCandidates`, `requiresConfirmation` per contract T6
- [ ] T049 [US5] Implement MCP tool `T6a apply_proposal` in `mcp_server.py`: look up the pending proposal; re-check `version` on every targeted element; if any version has been bumped since the proposal, return `status: "conflict"` and apply **nothing**; otherwise apply through Robo Architect's existing mutation pathway, bump versions, return `applied` / `rejected` arrays per contract T6a
- [ ] T050 [US5] Replace the TODO in [robo-spec/.claude/skills/robo-sync/SKILL.md](robo-spec/.claude/skills/robo-sync/SKILL.md) body with the end-to-end flow: (a) read `<workspace>/.claude/robo-project.json` for `projectId`; (b) call `T2 get_bc_design` to learn which files back which elements; (c) for each file, run the right extractor via Bash (`python extractors/python_extract.py <file>` or `node extractors/ts_extract.mjs <file>`); (d) call `T6 propose_sync` with the aggregated extracts; (e) render the diff to the developer, prompting explicitly for every entry in `requiresConfirmation`; (f) call `T6a apply_proposal` with the confirmed subset; (g) on `CONFLICT`, re-fetch via T2 and re-propose **once** before giving up

**Checkpoint**: `/robo-sync` round-trips additive changes (quickstart S9), forces confirmation on renames (S10), and is a true no-op when nothing changed (S11).

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Cross-story validation, documentation, and the manual smoke that proves the whole feature works.

- [ ] T051 Verify all new + extended HTTP routes (E1 extension, E2, E3, E4, E5, E6) appear in `/docs` Swagger with accurate Pydantic models grouped under the `robo-spec` tag (Constitution Development Workflow rule)
- [ ] T052 [P] Audit every `robo-*` SKILL.md frontmatter for the `requires-speckit: ">=0.8.13, <0.9.0"` version pin (T014/T015/T016/T017) and add an LLM-side check in each Overrides section instructing the skill to warn the developer when the installed speckit version is outside the declared range (research R11 mitigation 1)
- [ ] T053 [P] Update the repo [README.md](README.md) architecture section to document the new `robo-spec/` distribution root, the verbatim-copy install behavior, and the existence of the `/robo-*` skill suite
- [ ] T054 Wire the offline fallback in [frontend/src/features/robo_spec/composables/useRoboProgressStream.ts](frontend/src/features/robo_spec/composables/useRoboProgressStream.ts): on `link-offline` SSE event, flip every progress badge in the affected project to the "code link offline" affordance per FR-008 (quickstart S13)
- [ ] T055 Execute [quickstart.md](quickstart.md) S1..S14 manual smoke against a fresh workspace + a Robo Architect project containing at least one `core` BC, one `supporting` BC, and one unclassified BC; record results inline as checkboxes ticked under each S-scenario; fix any failures before merge

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. **Blocks all user stories.**
- **US6 (Phase 3, P1)**: Depends on Foundational. **Blocks every other user story end-to-end** (no skill files = nothing for the LLM to run), but other stories can author skeletons in parallel.
- **US1 (Phase 4, P1)**: Depends on US6 skeletons (T014, T024) for the robo-plan body; depends on Foundational for MCP transport and schemas. Implementation may proceed in parallel with US2.
- **US2 (Phase 5, P1)**: Depends on US6 skeleton (T015) for the robo-tasks body; depends on Foundational. Independent of US1 on the implementation side.
- **US3 (Phase 6, P2)**: Depends on US4's `register_implementation_files` (T042) for a non-empty Design-tab demo, but the click-to-open path itself only needs Foundational + US6.
- **US4 (Phase 7, P2)**: Depends on US6 skeleton (T016) for the robo-implement body; on US1 (so there is a `plan.md` to constrain layout); on US9's `T6b` (which is implemented inside US4 itself, T042).
- **US5 (Phase 8, P2)**: Depends on US6 skeletons (T017, T018) + US4 (so there are scaffolded files to AST-extract).
- **Polish (Phase 9)**: Depends on all desired user stories being complete. T055 is the gate.

### Within Each User Story

- Backend MCP tools and HTTP routes before SKILL.md overrides that call them.
- Composables before components that consume them.
- `ProgressBadge.vue` (US2) + `useOpenImplFile.ts` (US3) wiring into `EventModelingPanel.vue` happens after the respective backend endpoints are live.

### Parallel Opportunities

- **Phase 1**: T003 [P] (npm helper deps) and T005 [P] (frontend scaffold) run alongside T002/T004.
- **Phase 2**: T006 [P] and T007 [P] (Cypher schema docs) run in parallel with each other before T008/T011/T012.
- **Phase 3 (US6)**: T014, T015, T016, T017, T018 are all [P] — five independent skeleton files; T013 and T019 are the bookends.
- **Phase 4 (US1)**: T020, T021, T022, T023 are MCP-tool implementations in the same file (`mcp_server.py`) so they are **not** [P] with each other; T024–T026 are SKILL.md edits in a single file, also not [P].
- **Phase 5 (US2)**: T032 [P] and T033 [P] (frontend composable + component) run in parallel; backend tasks T027–T031 are mostly in the same files and are sequential.
- **Phase 6 (US3)**: T039 [P] and T040 [P] are parallelizable composables.
- **Phase 8 (US5)**: T044 and T045 touch different files (Python vs. Node extractors) and could be marked [P] if assigned to two contributors; T047 [P] (the optional LLM ranker) is independent of T046.
- **Cross-story parallelism**: After Phase 3 (US6) checkpoint, US1 and US2 can be implemented by two contributors in parallel; US3 / US4 / US5 can run in parallel after their respective dependencies clear.

---

## Parallel Example: User Story 6 skeleton creation

```bash
# Once T013 is in flight, kick off all five skill skeletons together (different files):
Task: "Create skeleton robo-spec/.claude/skills/robo-plan/SKILL.md (T014)"
Task: "Create skeleton robo-spec/.claude/skills/robo-tasks/SKILL.md (T015)"
Task: "Create skeleton robo-spec/.claude/skills/robo-implement/SKILL.md (T016)"
Task: "Create skeleton robo-spec/.claude/skills/robo-sync/SKILL.md (T017)"
Task: "Create skeleton extractors (python_extract.py + ts_extract.mjs) (T018)"
```

---

## Implementation Strategy

### MVP first (US6 + US1 only — the smallest end-to-end loop)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete Phase 3: US6 (install path + skeletons).
4. Complete Phase 4: US1 (`/robo-plan` end-to-end).
5. **STOP and VALIDATE**: run quickstart S1–S4. At this point a developer can already turn a Robo Architect BC into a `plan.md` with the right architecture style — no other surface required.

### Incremental delivery

1. MVP above → deploy / demo.
2. Add US2 → quickstart S5/S13 → deploy / demo (progress feedback loop visible to the designer).
3. Add US3 → quickstart S6/S7 → deploy / demo (design → code navigation).
4. Add US4 → quickstart S8 → deploy / demo (`/robo-implement` constrained by `plan.md`).
5. Add US5 → quickstart S9/S10/S11 → deploy / demo (reverse sync closes the loop).
6. Run S14 (skill-inheritance regression after a speckit upgrade) before any release that bumps the speckit dependency range.

### Parallel team strategy

After Phase 3 (US6) checkpoint:

- Developer A: US1 (`/robo-plan`) — backend MCP tools T1–T4 + robo-plan SKILL.md overrides.
- Developer B: US2 (`/robo-tasks` + progress badges) — backend watcher + SSE + frontend composable/component + robo-tasks SKILL.md.
- Developer C: US3 (click-to-open) once US4's `T6b register_implementation_files` is in flight, plus US4 itself.
- Developer D: US5 (`/robo-sync`) once US4's scaffolded files exist to AST-extract.

---

## Notes

- [P] tasks = different files, no dependencies on other in-flight work.
- [Story] label maps every Phase-3+ task back to a user story in `spec.md` for traceability.
- Each user story checkpoint is independently testable via the matching quickstart S-scenario(s).
- No marker comments are written into developer source code at codegen time (research R7) — the only `@robo` markers in this entire feature live inside `tasks.md` (data-model §2.3) and are written by `/robo-tasks` in T035.
- Source mapping is in Neo4j only (research R5) — there is **no** `.robo-link.json` in any workspace; do not introduce one.
- Skill inheritance is markdown-level only (research R11) — no build step, no Jinja, no template engine in any task above.
- Commit after each task or each logical group (the existing `speckit-git-commit` hook is wired as an optional after-tasks hook).
