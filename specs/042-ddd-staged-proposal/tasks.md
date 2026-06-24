---
description: "Task list for 042 Staged DDD Decomposition Mode for Proposals"
---

# Tasks: Staged DDD Decomposition Mode for Proposals

**Input**: Design documents from `/specs/042-ddd-staged-proposal/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/staged-ddd-api.md](contracts/staged-ddd-api.md), [quickstart.md](quickstart.md)

**Tests**: INCLUDED — the spec defines an explicit Test Plan (TP-A…F) and quickstart test entry points, so per-story test tasks are generated.

**Organization**: Tasks are grouped by user story. P1 stories are sequenced by real execution dependency (US1 mode → US3 stage-plan → US2 stages → US4 memory), since the staged walkthrough consumes the stage plan and the stage skills.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1…US6 per spec.md
- All paths are repo-relative from `/Users/uengine/main-robo-arch/robo-architect/`

## Path Conventions

Web app (Principle V): backend `api/features/<feature>/`, frontend `frontend/src/features/<feature>/`, skills `skills/robo-proposals/`, schema docs `docs/cypher/schema/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Schema documentation + scaffolds that precede code (Development Workflow rule).

- [X] T001 Add comment-only documentation for the new `Proposal` properties (`decompositionMode`, `stagePlan`, `stageArtifacts`, `currentStage`, `memoryConflicts`) and the new `Constitution.strategicMemory` property to docs/cypher/schema/03_node_types.cypher (no new labels)
- [X] T002 Add a comment in docs/cypher/schema/04_relationships.cypher noting no new relationships — `strategicMemory` rides the existing `HAS_CONSTITUTION` / `CON-ROOT` nodes
- [X] T003 [P] Create empty skill folder scaffolds under skills/robo-proposals/ for robo-proposal-scope, -discover, -decompose, -strategize, -connect, -define, -tactical (each with a placeholder SKILL.md frontmatter + `extends:` line)
- [X] T004 [P] Create the package scaffold api/features/proposal_lifecycle/services/stage_runners/__init__.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pydantic contracts, Constitution `strategicMemory` store read, orchestrator skeleton, and route wiring that every staged user story depends on.

**⚠️ CRITICAL**: No staged-flow user story (US2/US3/US4) can begin until this phase is complete.

- [X] T005 Add `DecompositionMode` enum (`SIMPLIFIED`|`DETAILED_DDD`) and the staged models — `StagePlan`, `StagePlanItem`, the six `*Artifact` shapes, `StageArtifact` union, `MemoryConflict` — to api/features/proposal_lifecycle/proposal_contracts.py per data-model.md §1
- [X] T006 Add `StrategicMemory` + `ContextStrategy` models (differentiation/couplingPosture/contexts) to api/features/proposal_lifecycle/proposal_contracts.py per data-model.md §2
- [X] T007 Extend `CreateProposalRequest` with `decompositionMode: DecompositionMode = SIMPLIFIED` and add the five new fields to `ProposalResponse` (+ parse them in `from_neo4j`) in api/features/proposal_lifecycle/proposal_contracts.py
- [X] T008 Extend api/features/constitution/services/constitution_store.py: read/write a `strategicMemory` JSON property on project-root and per-BC `Constitution` nodes; include `strategicMemory` in `_node_to_dict`
- [X] T009 Extend `effective_for_bc()` in api/features/constitution/services/constitution_store.py to merge `strategicMemory` section-by-section (BC overrides project-root; `differentiation`/`couplingPosture` from project-root only) per data-model.md §2
- [X] T010 Update `constitution_hash` input in api/features/constitution/services/constitution_store.py to cover `strategicMemory` so amendments bump the hash and `_mark_proposals_stale` flags dependent proposal plans (foundation for FR-021)
- [X] T011 Create the orchestrator skeleton api/features/proposal_lifecycle/services/staged_runner.py: load `stagePlan`/`stageArtifacts`/`currentStage` off the Proposal, compute the next non-skipped stage, persist artifacts, expose `resume_point()` (resumable per FR-027) — stage bodies stubbed
- [X] T012 Create api/features/proposal_lifecycle/routes/proposals_staged.py with an empty `APIRouter()` and register it in api/features/proposal_lifecycle/router.py (`include_router(staged_router)`)
- [X] T013 [P] Create a shared stage-runner base in api/features/proposal_lifecycle/services/stage_runners/base.py wrapping `run_skill_lines` + SSE event emission + `extract_json` (mirrors plan_runner.stream_plan) for reuse by all six stages

**Checkpoint**: Models, memory store read/merge, orchestrator skeleton, and route module exist. User stories can begin.

---

## Phase 3: User Story 1 - Choose decomposition mode at creation (Priority: P1) 🎯 MVP

**Goal**: A switch in the new-proposal dialog selects Simplified vs Detailed DDD; the choice is recorded and governs the flow; a not-yet-confirmed Simplified proposal can be upgraded to Detailed.

**Independent Test**: Create a proposal in each mode; confirm the switch renders with a default, the mode is persisted, Simplified runs today's intent flow, Detailed routes to scope; upgrade a Simplified draft and confirm it seeds from the existing Strategic Diff.

### Tests for User Story 1 (TP-A)

- [X] T014 [P] [US1] Backend test: creating a proposal persists `decompositionMode`; default is `SIMPLIFIED`; mode appears in `ProposalResponse` — in api/features/proposal_lifecycle/tests/test_staged_ddd.py
- [X] T015 [P] [US1] Backend test: `POST /{id}/mode` upgrades a not-confirmed Simplified proposal to `DETAILED_DDD` and 409s when the plan is already confirmed — in api/features/proposal_lifecycle/tests/test_staged_ddd.py

### Implementation for User Story 1

- [X] T016 [US1] Write `decompositionMode` on `CREATE (p:Proposal …)` in api/features/proposal_lifecycle/routes/proposals_crud.py (from `body.decompositionMode`, default `SIMPLIFIED`)
- [X] T017 [US1] Add `POST /{proposal_id}/mode` to api/features/proposal_lifecycle/routes/proposals_staged.py — set `DETAILED_DDD`, seed `currentStage=SCOPE` from existing `strategicDiff`, 409 `plan_confirmed` if confirmed (FR-003)
- [X] T018 [US1] Add the Simplified/Detailed mode switch (i18n labels + one-line descriptions, default Simplified) above the prompt textarea in frontend/src/features/proposals/ui/ProposalCreate.vue
- [X] T019 [US1] Add i18n keys for the mode switch labels/descriptions in frontend/src/app/i18n.js
- [X] T020 [US1] In frontend/src/features/proposals/proposals.store.js: pass `decompositionMode` through `createProposal`, and branch on submit — Simplified → existing intent subscription; Detailed → new scope flow (US3)
- [X] T021 [US1] Add an `upgradeMode(id)` action in frontend/src/features/proposals/proposals.store.js calling `POST /{id}/mode` and surface an "Upgrade to Detailed DDD" affordance in frontend/src/features/proposals/ui/ProposalDetail.vue for unconfirmed Simplified proposals

**Checkpoint**: Mode selection works end-to-end; Detailed routes into the (US3) scope flow.

---

## Phase 4: User Story 3 - Scope-aware stage plan with skip prompts (Priority: P1)

**Goal**: Before the walkthrough, classify the proposal's reach and propose which stages apply / are skipped (with reasons); the architect confirms/overrides; the confirmed plan is recorded. Discover is never fully omittable for behavior-changing proposals.

**Independent Test**: Run single-BC, strategic-only, and micro/local proposals; confirm each gets a reduced stage plan with reasons, no silent skips, and the recorded plan reflects ran/skipped + reason.

### Tests for User Story 3 (TP-C)

- [X] T022 [P] [US3] Backend test: stage-plan confirm rejects skipping DISCOVER on a behavior-changing proposal (422 `discover_not_skippable`); persists `stagePlan` with per-item reason — in api/features/proposal_lifecycle/tests/test_staged_ddd.py
- [X] T023 [P] [US3] Backend test: single-BC scope recommends skipping cross-context Connect/Decompose; strategic-only recommends skipping Tactical — in api/features/proposal_lifecycle/tests/test_staged_ddd.py

### Implementation for User Story 3

- [X] T024 [P] [US3] Author skills/robo-proposals/robo-proposal-scope/SKILL.md (`extends: ddd-starter` orientation) — input: prompt + domain nodes + existing strategic memory; output JSON `stagePlan` with `{stage, applies, recommendSkip, reason}` per FR-009 and the skip decision tree (single-BC→skip Connect; strategic-only→skip Tactical; micro→collapse; Discover never fully omitted)
- [X] T025 [US3] Implement api/features/proposal_lifecycle/services/stage_runners/scope.py — stream `robo-proposal-scope`, parse the stage plan, emit `stage_plan` SSE (uses base.py)
- [X] T026 [US3] Add `GET /{id}/stream/scope` (SSE) and `POST /{id}/stage-plan/confirm` to api/features/proposal_lifecycle/routes/proposals_staged.py — persist `stagePlan`, set `currentStage` to first non-skipped stage, enforce 422 `discover_not_skippable` (FR-010/FR-014/FR-015)
- [X] T027 [P] [US3] Create frontend/src/features/proposals/ui/StagePlanReview.vue — render proposed stages with reasons, toggles to re-enable/skip, confirm button
- [X] T028 [US3] Wire scope SSE + stage-plan confirm actions in frontend/src/features/proposals/proposals.store.js and show StagePlanReview after the Detailed-mode submit

**Checkpoint**: Detailed proposals produce an architect-confirmed stage plan that drives the walkthrough.

---

## Phase 5: User Story 2 - Staged DDD walkthrough with real per-stage decisions (Priority: P1)

**Goal**: Each non-skipped ddd-starter stage asks its characteristic decision questions, produces a reviewable artifact, and gates on confirm/skip; corrections carry forward; output consolidates into Strategic/Tactical Diff. Resumable mid-stage.

**Independent Test**: Run a multi-context proposal; assert each stage's artifact carries its characteristic decisions (TP-B), no stage auto-advances, a stage-N correction feeds stage N+1, and the final consolidation yields standard diffs; abandon mid-stage and resume.

### Tests for User Story 2 (TP-B, TP-F)

- [X] T029 [P] [US2] Backend test: per-stage artifact validation — Strategize requires `kind`, Define requires ≥5 ubiquitous-language terms, Tactical requires ≥2 invariants; Connect labels Event/Command/Query and raises a coupling warning on injected bidirectional-sync — in api/features/proposal_lifecycle/tests/test_staged_ddd.py
- [X] T030 [P] [US2] Backend test: orchestrator resumes at the first non-skipped stage with no artifact (TP-F) and refuses a stage whose prior stage is incomplete (409 `prior_stage_incomplete`) — in api/features/proposal_lifecycle/tests/test_staged_ddd.py

### Stage skills (parallel — different files) — author per ddd-starter reference

- [X] T031 [P] [US2] Author skills/robo-proposals/robo-proposal-discover/SKILL.md (`extends:` 02-discover) — emit `DiscoverArtifact` (events past-tense, pivotal, hotspots resolve-now/defer, external systems) per FR-005a
- [X] T032 [P] [US2] Author skills/robo-proposals/robo-proposal-decompose/SKILL.md (`extends:` 03-decompose) — emit `DecomposeArtifact` (domain-named sub-domains, one-line responsibility, adjacency, loose-coupling notes) per FR-005b
- [X] T033 [P] [US2] Author skills/robo-proposals/robo-proposal-strategize/SKILL.md (`extends:` 04-strategize) — emit `StrategizeArtifact` (Core/Supporting/Generic via differentiator + market-maturity questions, build-vs-buy for Generic); accept current strategic memory as input per FR-005c
- [X] T034 [P] [US2] Author skills/robo-proposals/robo-proposal-connect/SKILL.md (`extends:` 05-connect) — emit `ConnectArtifact` (Event/Command/Query, pub/sub default, coupling checks, messaging channel) per FR-005d
- [X] T035 [P] [US2] Author skills/robo-proposals/robo-proposal-define/SKILL.md (`extends:` 07-define) — emit `DefineArtifact` (BC canvas: purpose/roles/inbound/outbound/≥5 ubiquitous terms/business decisions/assumptions, language clashes) per FR-005e
- [X] T036 [P] [US2] Author skills/robo-proposals/robo-proposal-tactical/SKILL.md (`extends:` 08-code + robo-proposal-plan tactical refs) — emit `TacticalArtifact` (aggregate boundary, ≥2 invariants, state transitions, commands/events, throughput; VO≠Aggregate) per FR-005f

### Stage runners (parallel — different files)

- [X] T037 [P] [US2] Implement api/features/proposal_lifecycle/services/stage_runners/discover.py (uses base.py; seeds from prior artifacts)
- [X] T038 [P] [US2] Implement api/features/proposal_lifecycle/services/stage_runners/decompose.py
- [X] T039 [P] [US2] Implement api/features/proposal_lifecycle/services/stage_runners/strategize.py (inject existing strategic memory into prompt)
- [X] T040 [P] [US2] Implement api/features/proposal_lifecycle/services/stage_runners/connect.py (inject coupling posture memory)
- [X] T041 [P] [US2] Implement api/features/proposal_lifecycle/services/stage_runners/define.py (inject per-BC ubiquitous language memory)
- [X] T042 [P] [US2] Implement api/features/proposal_lifecycle/services/stage_runners/tactical.py

### Orchestration, routes, consolidation, UI

- [X] T043 [US2] Flesh out api/features/proposal_lifecycle/services/staged_runner.py to dispatch each `currentStage` to its runner, store the returned artifact in `stageArtifacts`, advance `currentStage`, and skip skipped stages (depends on T037–T042)
- [X] T044 [US2] Add `GET /{id}/stream/stage/{stage}` (SSE), `POST /{id}/stage/{stage}/confirm`, `POST /{id}/stage/{stage}/skip` to api/features/proposal_lifecycle/routes/proposals_staged.py — emit `artifact`/`done`, persist edited artifact (FR-006), enforce `prior_stage_incomplete`/`discover_not_skippable`
- [X] T045 [US2] Create api/features/proposal_lifecycle/services/staged_consolidate.py — fold completed stage artifacts into the standard `strategicDiff` (+ `tacticalDiff` if Tactical ran) shapes (FR-007)
- [X] T046 [US2] Add `POST /{id}/staged/consolidate` to api/features/proposal_lifecycle/routes/proposals_staged.py writing the consolidated diffs to the Proposal
- [X] T047 [US2] Create frontend/src/features/proposals/ui/StagedDddWalkthrough.vue — stage stepper, per-stage SSE log, editable artifact review, confirm/skip buttons, and resume from `currentStage`
- [X] T048 [US2] Add staged stage SSE + confirm/skip + consolidate actions to frontend/src/features/proposals/proposals.store.js and mount StagedDddWalkthrough after StagePlanReview in the Detailed flow
- [X] T049 [US2] Ensure the Constitution gate (041) runs once before planning in the Detailed flow exactly as in Simplified — reuse the existing `PlanView`/constitution interview routing (FR-008), no duplication

**Checkpoint**: Full Detailed walkthrough runs, gates per stage, resumes, and consolidates into standard diffs.

---

## Phase 6: User Story 4 - Capture durable strategic decisions into memory & reuse (Priority: P1)

**Goal**: Durable conclusions (differentiator, per-BC Core/Supporting/Generic, coupling posture, per-BC ubiquitous language) are written once to the Constitution `strategicMemory`; later proposals load/confirm/amend instead of re-asking; conflicts force amend-or-justify; amendments mark plans stale; per-change tactical detail is not promoted.

**Independent Test**: First proposal seeds memory; second proposal on the same BC reuses it (zero from-scratch re-asks); a conflicting local decision is surfaced; amending memory flags dependent plans stale.

### Tests for User Story 4 (TP-D)

- [X] T050 [P] [US4] Backend test: confirming strategize/connect/define promotes durable sections to project-root + per-BC `strategicMemory`; per-change tactical detail stays only on the Proposal (FR-016/FR-020) — in api/features/proposal_lifecycle/tests/test_staged_ddd.py
- [X] T051 [P] [US4] Backend test: second proposal loads recorded memory as stage starting point (no re-ask); conflict yields `409 unresolved_conflicts` until amend/justify; memory amendment marks dependent plans `planStale` (FR-018/FR-019/FR-021, SC-004/SC-008) — in api/features/proposal_lifecycle/tests/test_staged_ddd.py
- [X] T052 [P] [US4] Constitution test: `effective_for_bc` merges `strategicMemory` (project-root + BC override) section-by-section — in api/features/constitution/ (new test_strategic_memory.py)

### Implementation for User Story 4

- [X] T053 [US4] Create api/features/proposal_lifecycle/services/strategic_memory.py — `promote(stage, artifact)` writing durable sections to the correct Constitution level (project-root vs per-BC) via constitution_store, excluding per-change tactical detail (FR-016/FR-017/FR-020)
- [X] T054 [US4] Add conflict detection in api/features/proposal_lifecycle/services/strategic_memory.py — compare stage decisions vs recorded memory, return `MemoryConflict[]`; called by strategize/connect/define runners to emit the `conflicts` SSE event (FR-019)
- [X] T055 [US4] In api/features/proposal_lifecycle/routes/proposals_staged.py stage-confirm handler: accept `conflictResolutions`, block advance on `UNRESOLVED` (409 `unresolved_conflicts`), apply AMEND_MEMORY → promote, JUSTIFY_LOCAL → record justification on the Proposal (FR-019)
- [X] T056 [US4] Hook promotion into T044's confirm path for strategize/connect/define so durable conclusions persist on confirm (depends on T053)
- [X] T057 [P] [US4] Surface `strategicMemory` view/edit on the Design side in frontend/src/features/constitution/ui/ConstitutionEditor.vue + frontend/src/features/constitution/constitution.store.js (FR-022)
- [X] T058 [US4] Extend api/features/constitution/router.py project + per-BC GET/PUT payloads to include/accept `strategicMemory`; PUT triggers staleness via the extended hash (T010)
- [X] T059 [US4] Render conflict prompts (amend-memory vs justify-local) in frontend/src/features/proposals/ui/StagedDddWalkthrough.vue from the `conflicts` SSE event

**Checkpoint**: Strategic memory seeds once, reuses thereafter, blocks silent overrides, and drives staleness.

---

## Phase 7: User Story 5 - Simplified mode stays fast and unchanged (Priority: P2)

**Goal**: Simplified mode adds zero steps; it still reads strategic memory as input but does not run the staged interview.

**Independent Test**: A Simplified proposal has the exact pre-feature step count; a Simplified plan in a project with memory honors that memory as input.

### Tests for User Story 5 (TP-E)

- [X] T060 [P] [US5] Backend test: a `SIMPLIFIED` proposal exercises only the existing intent→plan endpoints (no scope/stage endpoints invoked) and the Constitution gate fires exactly once — in api/features/proposal_lifecycle/tests/test_staged_ddd.py

### Implementation for User Story 5

- [X] T061 [US5] In api/features/proposal_lifecycle/services/plan_runner.py `_build_plan_prompt`, include the project/BC `strategicMemory` (when present) as read-only input so Simplified plans honor recorded strategy without running stages (FR-025)
- [X] T062 [US5] Guard the frontend Detailed-only UI (StagePlanReview/StagedDddWalkthrough) behind `decompositionMode === 'DETAILED_DDD'` in frontend/src/features/proposals/ui/ProposalDetail.vue so Simplified renders the existing flow unchanged

**Checkpoint**: Simplified path verified unchanged and memory-aware.

---

## Phase 8: User Story 6 - Mode-agnostic downstream convergence (Priority: P2)

**Goal**: Both modes hand the same Strategic/Tactical Diff + Plan to Impact Preview, Tasks, and Implementation; 041 plan-confirmation/Submit gates apply unchanged.

**Independent Test**: Decompose one requirement in each mode; confirm Impact/Tasks/Implement run with no mode-specific branching and the 041 gates hold.

### Tests for User Story 6 (TP-E)

- [X] T063 [P] [US6] Backend test: after `consolidate`, a Detailed proposal feeds the existing `/{id}/stream/plan` + `/{id}/plan/confirm` and reaches `planStale=false`/Submit-eligible identically to a Simplified proposal — in api/features/proposal_lifecycle/tests/test_staged_ddd.py

### Implementation for User Story 6

- [X] T064 [US6] Verify/adjust that staged consolidation output passes unchanged into impact_builder + confirm_plan (no new branches in api/features/proposal_lifecycle/services/plan_runner.py or tasks_runner.py / implement_runner.py) — add a thin assertion/shape check in staged_consolidate.py (FR-023/FR-024)

**Checkpoint**: Downstream is mode-agnostic; gates intact.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T065 [P] Finalize schema doc comments in docs/cypher/schema/03_node_types.cypher / 04_relationships.cypher to match the shipped property names
- [X] T066 [P] Add SmartLogger phase-boundary logs (start/decision/done with correlation id) to staged_runner.py and each stage runner (Principle VII), matching plan_runner
- [X] T067 [P] Create frontend/tests/manual-042-capture.spec.ts (Playwright) driving quickstart Scenarios A–F for the user manual capture
- [X] T068 Run the playwright-docx-manual / test-and-create-manual skill to produce the Korean user manual for the staged-DDD flow
- [X] T069 [P] Update README API summary if a new route prefix surfaced (here routes stay under `/api/proposals` and `/api/constitution`) and confirm all new endpoints appear in Swagger `/docs`
- [X] T070 Execute quickstart.md Scenarios A–F end-to-end against a running backend + Neo4j Desktop and record results

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (P1)**: no dependencies.
- **Foundational (P2)**: depends on Setup; **blocks US2/US3/US4**.
- **US1 (Phase 3)**: depends on Foundational (T005–T007, T012). Independently testable MVP.
- **US3 (Phase 4)**: depends on Foundational + US1 routing; produces the stage plan US2 consumes.
- **US2 (Phase 5)**: depends on Foundational + US3 (stage plan). Stage skills/runners (T031–T042) are parallel; orchestrator/routes/UI (T043–T049) are sequential.
- **US4 (Phase 6)**: depends on US2 stage confirm path (T044) + Foundational memory store (T008–T010).
- **US5 (Phase 7)** / **US6 (Phase 8)**: depend on US2 consolidation; mostly verification + small guards.
- **Polish (Phase 9)**: after all desired stories.

### Within stories

- Tests (TP) before/with implementation; models before services before endpoints before UI.
- US2 stage skill (T03x) pairs with its runner (T03x) before the orchestrator (T043) can dispatch it.

### Parallel Opportunities

- T003/T004 setup scaffolds.
- T013 base runner alongside T005–T010 (different files).
- **US2 stage skills T031–T036 all parallel; stage runners T037–T042 all parallel** (six different files each).
- All `[P]` test tasks within a story run together.
- Frontend StagePlanReview (T027) and ConstitutionEditor memory surface (T057) are independent of most backend tasks.

---

## Parallel Example: User Story 2 stage authoring

```bash
# Author all six stage skills together (different files):
Task: "robo-proposal-discover/SKILL.md"   (T031)
Task: "robo-proposal-decompose/SKILL.md"  (T032)
Task: "robo-proposal-strategize/SKILL.md" (T033)
Task: "robo-proposal-connect/SKILL.md"    (T034)
Task: "robo-proposal-define/SKILL.md"     (T035)
Task: "robo-proposal-tactical/SKILL.md"   (T036)

# Then implement all six runners together (different files): T037–T042
```

---

## Implementation Strategy

### MVP (US1 only)

1. Phase 1 Setup → Phase 2 Foundational → Phase 3 US1.
2. STOP & VALIDATE: mode switch persists and routes; Simplified path unchanged. Demo.

### Incremental delivery

1. + US3 → stage plan with skip prompts (demo scope classification).
2. + US2 → full staged walkthrough consolidating to standard diffs (the core feature).
3. + US4 → strategic memory seed/reuse/conflict/staleness (the durability payoff).
4. + US5/US6 → verify Simplified untouched and downstream mode-agnostic.
5. Polish → manual, schema docs, quickstart validation.

### Notes

- `[P]` = different files, no incomplete-task dependency.
- No new Neo4j labels/relationships — only properties (Principle I respected).
- All AI is skill-first (Principle X); backend orchestrates + parses only.
- Every stage/skip/memory-write is human-gated (Principle IV); every long op streams (Principle III).
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
