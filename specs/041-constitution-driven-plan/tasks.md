---
description: "Task list for 041 Constitution-driven Plan Stage"
---

# Tasks: Constitution-driven Plan Stage for the Proposal Lifecycle

**Input**: Design documents from `specs/041-constitution-driven-plan/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included (spec quickstart calls out a Playwright flow + backend pytest). Test tasks are marked and may be skipped for a fast MVP.

**Organization**: Grouped by user story (US1–US4) for independent implementation/testing. This is an additive evolution of the existing `api/features/proposal_lifecycle/` backend and `frontend/src/features/proposals/` frontend, driven by skills under `skills/robo-proposals/`. **No new Neo4j label/relationship.**

## Path Conventions

Web app: backend `api/features/proposal_lifecycle/`, frontend `frontend/src/features/proposals/`, skills `skills/robo-proposals/`, frontend tests `frontend/tests/`, backend tests `api/features/proposal_lifecycle/tests/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffolding for new skills and contract models.

- [x] T001 [P] Create skill scaffold dir `skills/robo-proposals/robo-project-constitution/` with empty `SKILL.md` and `references/interview-questions.md`
- [x] T002 [P] Create skill scaffold dir `skills/robo-proposals/robo-proposal-plan/` with empty `SKILL.md` and `references/architecture-plan.md`
- [x] T003 [P] Create backend test dir marker `api/features/proposal_lifecycle/tests/__init__.py` (if missing) for new pytest modules

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pydantic models + persistence helpers every story depends on. MUST complete before US1–US4.

- [x] T004 Add `ArchitectureStyle`, `RepoStrategy`, `RepoMode` enums and `ConstitutionRef`/`ConstitutionFields` models to `api/features/proposal_lifecycle/proposal_contracts.py` per data-model.md
- [x] T005 Add `ArchitectureDecision` and `ImplementationPlan` Pydantic models to `api/features/proposal_lifecycle/proposal_contracts.py` (with `version`, `architectureDecisions`, `constitutionGaps`, `tacticalSummary`, `constitutionHash`, `strategicVersion`)
- [x] T006 Extend `ProposalResponse` in `api/features/proposal_lifecycle/proposal_contracts.py` with `implementationPlan`, `constitutionHash`, derived `planStale`; parse them in `from_neo4j`
- [x] T007 Add a `constitution_hash(raw: str) -> str` helper (SHA-256) and a `compute_plan_stale(node)` helper to `proposal_contracts.py` per data-model.md staleness rule
- [x] T008 [P] Add request models `UpdateConstitutionRequest`, `ConfirmPlanRequest`, `ConstitutionAnswerRequest` to `proposal_contracts.py`

**Checkpoint**: Models import cleanly; `python -c "import api.features.proposal_lifecycle.proposal_contracts"` succeeds.

---

## Phase 3: User Story 1 — Establish a Project Constitution via Interview (Priority: P1) 🎯 MVP

**Goal**: Detect missing constitution; run a seeded, recommendation-driven interview; persist the constitution file to the target repo; allow view/amend.

**Independent Test**: Start a Proposal with no constitution → interview runs (pre-filled from prompt, recommends defaults) → constitution file written to `projectRoot`, viewable/editable.

### Skill

- [x] T009 [P] [US1] Author `skills/robo-proposals/robo-project-constitution/SKILL.md` with `extends: speckit-constitution` frontmatter and the I/O contract from `contracts/constitution-skill-io.md` (seed-from-prompt FR-002a, recommend-fit FR-002b, four decision areas, spec-kit constitution output format)
- [x] T010 [P] [US1] Write `skills/robo-proposals/robo-project-constitution/references/interview-questions.md` (the four areas, conditional repo-mode follow-up, generation-language policy note)

### Backend

- [x] T011 [US1] Create `api/features/proposal_lifecycle/services/constitution_runner.py`: locate/read the constitution file under `projectRoot` (default `.specify/memory/constitution.md`), detect existence, build the seed prompt from `Proposal.originalPrompt` + strategic summary, invoke skill via `skill_runner.run_skill_lines("robo-proposals","robo-project-constitution",...)`, stream SSE events (`question`/`draft`/`done`), parse fields + compute hash
- [x] T012 [US1] Add `write_constitution(project_root, raw)` + `read_constitution(project_root)` file I/O in `constitution_runner.py`; on write, recompute hash and mark dependent proposals stale
- [x] T013 [US1] Create routes `api/features/proposal_lifecycle/routes/proposals_constitution.py`: `GET /{pid}/constitution`, `GET /{pid}/stream/constitution` (SSE), `POST /{pid}/constitution/answer`, `PUT /{pid}/constitution` per `contracts/http-endpoints.md`
- [x] T014 [US1] Register the constitution router in `api/features/proposal_lifecycle/routes/__init__.py` (and `api/main.py` if routers are wired there) so it appears in Swagger

### Frontend

- [x] T015 [P] [US1] Create `frontend/src/features/proposals/ui/ConstitutionInterview.vue`: question stream, pre-filled/recommended answers visibly marked, view/amend mode
- [x] T016 [US1] Wire constitution state + SSE + `getConstitution`/`answer`/`saveConstitution` actions into `frontend/src/features/proposals/proposals.store.js`
- [x] T017 [US1] In `frontend/src/features/proposals/ui/ProposalDetail.vue`, surface the interview when no constitution exists and an "Amend constitution" entry point when it does

**Checkpoint**: US1 fully testable on its own — constitution created/viewed/amended without running plan/implement.

---

## Phase 4: User Story 2 — Split Intent (Strategic) from Plan (Architecture & Impact) (Priority: P1)

**Goal**: Intent emits Strategic Diff only; new Plan stage consumes Strategic Diff + Constitution to produce Tactical Diff + impact + plan.

**Independent Test**: Intent output has zero tactical/architecture items; Plan stage adds them and consumed the constitution.

**Depends on**: Phase 2; the Plan sub-flow depends on US1 (constitution). The intent-narrowing sub-flow is independent.

### Skills

- [x] T018 [US2] Modify `skills/robo-proposals/robo-proposal-intent/SKILL.md`: remove Tactical Diff (Aggregate/Command/Event/VO) and architecture from the output contract; output = Strategic Diff only (Epic/Feature/UserStory/Process) per FR-006
- [x] T019 [US2] Author `skills/robo-proposals/robo-proposal-plan/SKILL.md` with `extends: robo-proposal-intent` and Overrides per `contracts/plan-skill-io.md` (drop strategic steps, keep tactical, add architecture-plan step)

### Backend

- [x] T020 [US2] Modify `api/features/proposal_lifecycle/services/intent_runner.py`: `_build_intent_prompt` and parsing emit Strategic Diff only; stop persisting `tacticalDiff` from intent; re-running sets `planStale`
- [x] T021 [US2] Create `api/features/proposal_lifecycle/services/plan_runner.py`: precondition checks (approved strategicDiff + constitution else 409 `constitution_required`), build prompt from strategicDiff + constitution + domain nodes, invoke `robo-proposal-plan`, stream `tactical`/`architecture` events, then call `impact_builder` and stream `impact`, assemble `ImplementationPlan`
- [x] T022 [US2] Create routes `api/features/proposal_lifecycle/routes/proposals_plan.py`: `GET /{pid}/stream/plan` (SSE), `POST /{pid}/plan/confirm` (persist plan + tacticalDiff + impactMap + stamp constitutionHash/strategicVersion), `GET /{pid}/plan`; register router (T014 pattern)

### Frontend

- [x] T023 [US2] Modify `frontend/src/features/proposals/ui/IntentDecompositionView.vue` to render Strategic Diff only (remove tactical sections)
- [x] T024 [P] [US2] Create `frontend/src/features/proposals/ui/PlanView.vue`: stream tactical + impact + (architecture placeholder until US3), Confirm-plan action
- [x] T025 [US2] Update `frontend/src/features/proposals/proposals.store.js` with plan SSE + `runPlan`/`confirmPlan` actions, and `ProposalDetail.vue` stage ordering Intent → Constitution → Plan → Submit

**Checkpoint**: Intent strategic-only and Plan stage produce tactical + impact; constitution consumed.

---

## Phase 5: User Story 3 — Constitution-grounded Microservice Architecture Plan (Priority: P2)

**Goal**: Plan enumerates deployment env, ingress, mesh/framework, frontend, repo mapping — consistent with constitution; gaps surfaced; monolith handled.

**Independent Test**: With a microservices constitution, plan lists all five aspects (or explicit gaps), each traceable to a constitution section; with a monolith, no fabricated infra.

**Depends on**: Phase 4 (Plan stage + skill).

- [x] T026 [P] [US3] Write `skills/robo-proposals/robo-proposal-plan/references/architecture-plan.md`: the five required aspects, traceability rule (FR-014), monolith rule (FR-012 → "N/A (monolith)"), repo-mapping honoring repoStrategy/repoMode
- [x] T027 [US3] In `plan_runner.py`, enforce completeness: every required aspect present in `architectureDecisions` OR `constitutionGaps` (SC-003); fail/flag otherwise
- [x] T028 [US3] Render `ArchitectureDecision[]` + a "Constitution gaps" callout in `frontend/src/features/proposals/ui/PlanView.vue`; show `constitutionRef` per decision
- [x] T029 [US3] Handle `architectureStyle = MONOLITH` in PlanView (mark ingress/mesh aspects "N/A (monolith)" rather than empty)

**Checkpoint**: Architecture plan is complete, gap-aware, and monolith-safe.

---

## Phase 6: User Story 4 — Carry Constitution & Plan into Tasks and Implementation (Priority: P2)

**Goal**: Task generation reviews constitution+plan (surfaces conflicts); implementation receives both; submit gate + staleness enforced.

**Independent Test**: Tasks reflect plan architecture + reference constitution; conflicts surfaced; implement receives constitution+plan; submit blocked without a confirmed, non-stale plan.

**Depends on**: Phases 3–5.

### Skills

- [x] T030 [P] [US4] Modify `skills/robo-proposals/robo-proposal-tasks/SKILL.md`: add a step that reviews generated tasks against the supplied Constitution + ImplementationPlan and flags conflicts (FR-015/FR-016)
- [x] T031 [P] [US4] Modify `skills/robo-proposals/robo-proposal-implement/SKILL.md`: honor the Constitution (repo strategy, stack, topology) + ImplementationPlan during implementation (FR-017)

### Backend

- [x] T032 [US4] Modify `api/features/proposal_lifecycle/services/tasks_runner.py`: include constitution body + `implementationPlan` in the human prompt to `robo-proposal-tasks`
- [x] T033 [US4] Modify `api/features/proposal_lifecycle/services/implement_runner.py` `_get_proposal_context`/`_context_doc` to load + append constitution + implementation plan sections
- [x] T034 [US4] Modify `api/features/proposal_lifecycle/routes/proposals_crud.py` submit handler: require `implementationPlan` present and `planStale = false`; return 400 `{reason: plan_required|plan_stale}` otherwise (FR-010/FR-018)
- [x] T035 [US4] Ensure intent re-run and constitution PUT set/clear `planStale` consistently (cross-check T012/T020); expose `planStale` in `ProposalResponse`

### Frontend

- [x] T036 [US4] Surface `planStale` (banner) + disable Submit until re-planned in `frontend/src/features/proposals/ui/ProposalDetail.vue`; show task/constitution conflict flags in the tasks view

**Checkpoint**: Full loop — constitution+plan propagate to tasks/implement; submit gated; staleness enforced.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T037 [P] Add `SmartLogger` phase logs (start/decision/error + correlation id) to `constitution_runner.py` and `plan_runner.py` (Principle VII)
- [x] T038 [P] [TEST] Backend pytest `api/features/proposal_lifecycle/tests/test_plan_and_constitution.py`: constitution detect/seed/hash, plan completeness (SC-003), submit gate + staleness (SC-005)
- [ ] T039 [P] [TEST] Playwright `frontend/tests/verify-proposal-constitution-plan.spec.ts`: create → intent (strategic-only) → interview → plan → submit-gate (maps quickstart smoke)
- [x] T040 Verify all new endpoints appear in Swagger `/docs` with correct request/response models; update README API summary if a new prefix was added
- [ ] T041 Run `quickstart.md` end-to-end against a local backend (`uvicorn ... --reload`) and confirm SC-001/SC-002/SC-003/SC-005

---

## Dependencies & Execution Order

- **Setup (P1)** → **Foundational (P2)** block everything.
- **US1 (P1)** is the MVP and is independently shippable.
- **US2 (P1)** intent-narrowing is independent; its Plan sub-flow needs US1.
- **US3 (P2)** needs US2. **US4 (P2)** needs US3 (and US1).
- **Polish (P7)** last.

## Parallel Opportunities

- Setup: T001/T002/T003 in parallel.
- Foundational: T008 parallel with T004–T007 review.
- US1: T009/T010 (skill) ∥ T015 (Vue) while backend T011–T014 proceed.
- US4: T030 ∥ T031 (two skills, different files).
- Polish: T037/T038/T039 in parallel.

## Implementation Strategy

**MVP = Phase 1 + 2 + US1** (a recorded, seeded, recommendation-driven project constitution). Then layer US2 (the intent/plan split), US3 (architecture detail), US4 (propagation), and finish with Polish. Each user story is a demoable increment.

**Total tasks**: 41 — Setup 3, Foundational 5, US1 9, US2 8, US3 4, US4 7, Polish 5.

---

## Phase 8: Revision (2026-06-11) — Constitution in Neo4j + Design-side UI

**Why**: Per architect direction, the Constitution is NOT a repo file. It lives in Neo4j (project-root node + per-BC overrides), management UI moves to the **Design side**, and the Proposals flow only runs the **interview when absent** (never per-proposal, no view/edit tab). Supersedes the file-storage parts of T011–T017.

- [x] T042 Add `Constitution` node + `HAS_CONSTITUTION` relationship to `docs/cypher/schema/03_node_types.cypher` / `04_relationships.cypher`
- [x] T043 New feature `api/features/constitution/services/constitution_store.py`: project-root + per-BC CRUD, effective(project+BC) merge, hash, proposal-staleness propagation
- [x] T044 New `api/features/constitution/router.py`: `GET/PUT /api/constitution`, `GET/PUT/DELETE /api/bounded-contexts/{bcId}/constitution`; register in `api/main.py`
- [x] T045 Refactor `proposal_lifecycle/services/constitution_runner.py` → interview gate only; writes project-root node via store (no file). `read_constitution()` now reads the graph node
- [x] T046 Trim `routes/proposals_constitution.py`: remove view/edit PUT; keep thin `{exists}` GET + interview SSE/answer
- [x] T047 [Frontend] Remove Constitution tab/button from `ProposalDetail.vue`; make `ConstitutionInterview.vue` interview-only; render it inline in `PlanView.vue` when constitution required
- [x] T048 [Frontend] New `features/constitution/` — `constitution.store.js` + `ui/ConstitutionEditor.vue` (project + per-BC, effective + override delete)
- [x] T049 [Frontend] Design-side "헌장" entry points: 📜 in canvas toolbar (PROJECT) + per-BC node header (BOUNDED_CONTEXT) via `robo:open-constitution` app event + App.vue modal
- [x] T050 Verify: backend full-app import OK, `vite build` exit 0, staleness pytest green

**Superseded** (file-based bits of original tasks): T011/T012 file I/O → graph store; T013 proposal PUT removed; T015/T016/T017 constitution view/amend in Proposals → Design side.
