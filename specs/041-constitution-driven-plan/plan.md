# Implementation Plan: Constitution-driven Plan Stage for the Proposal Lifecycle

**Branch**: `041-constitution-driven-plan` | **Date**: 2026-06-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/041-constitution-driven-plan/spec.md`

## Summary

Evolve the Proposal lifecycle (039/040) by (1) capturing a per-target-project **Constitution** (design principles, tech stack, monolith-vs-microservices posture, repo strategy) via a guided interview skill when one does not yet exist in the target project repo, and (2) splitting the current single `robo-proposal-intent` decomposition into two reviewable stages: **Intent** (Strategic Diff only) and a new **Plan** stage (`robo-proposal-plan`) that takes the approved Strategic Diff + Constitution and produces the Tactical Diff, an impact analysis, and a constitution-grounded **implementation plan** with concrete microservice architecture decisions (deployment environment, ingress, service mesh/framework, frontend stack, repository mapping). The Constitution and Plan are then carried into `robo-proposal-tasks` (reviewed against them) and `robo-proposal-implement` (passed as inputs).

Technical approach: evolution of `api/features/proposal_lifecycle/` (new `plan_runner`, new Plan SSE routes) plus a **new `api/features/constitution/`** feature that stores the Constitution as **Neo4j nodes** — a project-root `Constitution` node + per-Bounded-Context override nodes via `HAS_CONSTITUTION` — and computes the effective (merged) constitution. The Plan output is stored as JSON on the existing `Proposal` Neo4j node. Driven by two new Claude skills under `skills/robo-proposals/` (skill-first / `extends:`, Principle X).

**Revised (2026-06-11):** the Constitution is **not** a repo file. It lives in the graph (Principle I) and its **management UI is on the Design side** (a "헌장" entry at the Design root + each BC root), **not** in the Proposals tab. The Proposal flow only triggers the interview when no project-root Constitution exists (one-time gate) and never creates a per-Proposal constitution. This introduces **one new node label (`Constitution`) and one relationship (`HAS_CONSTITUTION`)** — added to `docs/cypher/schema/` per the dev workflow.

The constitution interview is **seeded from technical preferences already present in the Proposal's natural-language prompt** (shown as overridable pre-fills, FR-002a) and **recommends fit-for-purpose defaults** for unspecified decision areas (FR-002b); this behavior is inherited from spec-kit's `speckit-constitution` skill (which already derives values from user input / repo context) rather than reimplemented.

## Technical Context

**Language/Version**: Python 3.11+ (backend), Node/Vue 3 + Vite (frontend); skills authored as Markdown (SKILL.md) executed by Claude Code

**Primary Dependencies**: FastAPI, Neo4j official driver, Pydantic (backend); Vue 3, Vue Flow, EventSource/SSE (frontend); `api/platform/skill_runner.py` (Claude Code PTY skill invocation); existing 038 impact/SemanticDiff machinery

**Storage**: Neo4j. New `Constitution` node (scope `PROJECT`|`BOUNDED_CONTEXT`) + `(:BoundedContext)-[:HAS_CONSTITUTION]->(:Constitution)`. `Proposal` node extended with `implementationPlan` (JSON), `constitutionHash` (string snapshot for staleness). Effective (merged) constitution computed in backend

**Testing**: pytest (backend services/contracts); Playwright `frontend/tests/verify-*.spec.ts` for the Proposal flow (consistent with existing `verify-proposal-*` specs)

**Target Platform**: Linux/macOS dev server (uvicorn `--reload`), Electron/web frontend

**Project Type**: web application (FastAPI backend + Vue 3 frontend) — feature-modular per Constitution Principle V

**Performance Goals**: SSE first-token < 3 s; interview and plan stages stream incremental progress (Principle III) — no fixed throughput target

**Constraints**: Zero new Neo4j schema (reuse `Proposal` node); zero live-graph mutation during plan/interview (read-only until confirm, Principle IV); new AI workflows MUST be skills, not LangChain (Principle X); the target-project Constitution must live in the target repo, not robo-architect's graph

**Scale/Scope**: Per-proposal artifacts; tens of proposals per project; interview ≈ 4–6 questions; plan ≈ one document per proposal

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* Evaluated against `.specify/memory/constitution.md` v1.2.0.

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Graph-as-Source-of-Truth | ✅ PASS (strengthened) | The Constitution now lives **in the graph** as `Constitution` nodes (project-root + per-BC), making the graph the single source of truth for it too. Plan/tactical output is JSON on the `Proposal` node. Only a `constitutionHash` snapshot is stamped on the plan for staleness. No repo-file source of truth. |
| II. Event Storming Vocabulary | ✅ PASS | Strategic Diff (Epic/Feature/UserStory/Process) and Tactical Diff (Aggregate/Command/Event/ReadModel/Policy) terms are preserved; the new Plan stage adds architecture vocabulary, not CRUD renaming. |
| III. Streaming-First UX | ✅ PASS | Constitution interview and Plan stage are LLM-driven; both stream via SSE following the existing `stream_intent` pattern. |
| IV. Human-in-the-Loop | ✅ PASS | Constitution is reviewed/amended before use; Plan is reviewed before SUBMITTED; nothing auto-applies. Submit gate requires a confirmed plan. |
| V. Feature-Modular Architecture | ✅ PASS | All code under `api/features/proposal_lifecycle/` + `frontend/src/features/proposals/`; cross-feature reuse (038 impact) via platform/Neo4j, not sibling imports. |
| VI. Provider-Agnostic LLM Runtime | ✅ PASS | New skills run through `skill_runner` (Claude Code PTY); no provider/model hardcoded in backend. |
| VII. Observable by Default | ✅ PASS | New runners emit `SmartLogger` phase logs (start / key decision / error) with correlation IDs, matching `intent_runner`. |
| X. Skill-First Deep Agent Execution | ✅ PASS | Two new skills: `robo-proposal-plan` (carries the tactical+impact+architecture reasoning split out of intent) and `robo-project-constitution` (interview — seeds from the prompt's tech preferences FR-002a, recommends fit-for-purpose defaults FR-002b). Both use `extends:` — `robo-proposal-plan` extends `robo-proposal-intent`; `robo-project-constitution` extends `speckit-constitution` (reusing its derive-from-input/recommend behavior). No LangChain. |
| VIII / IX (Figma) | N/A | Feature does not touch the Figma plugin or SceneGraph pipeline. |
| Tech Constraints / Dev Workflow | ✅ PASS | Python/FastAPI/Neo4j + Vue 3; every new endpoint appears in Swagger; **new `Constitution` node + `HAS_CONSTITUTION` relationship MUST be added to `docs/cypher/schema/03_node_types.cypher` / `04_relationships.cypher`** before emitting code ships; frontend (Proposals + Design side) updated in the same change. |

**Result: PASS — no violations. Complexity Tracking not required.**

## Project Structure

### Documentation (this feature)

```text
specs/041-constitution-driven-plan/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (HTTP + skill I/O contracts)
│   ├── http-endpoints.md
│   ├── plan-skill-io.md
│   └── constitution-skill-io.md
├── checklists/
│   └── requirements.md  # from /speckit-specify
└── tasks.md             # /speckit-tasks output (NOT created here)
```

### Source Code (repository root)

```text
api/features/constitution/                # NEW feature (Principle V) — Neo4j-backed constitution
├── constitution_contracts.py            # Constitution node models, scope, effective-merge result
├── router.py                            # /api/constitution (project) + /api/bounded-contexts/{bcId}/constitution
└── services/
    ├── constitution_store.py            # CRUD on Constitution nodes; effective(project+BC) merge; hash
    └── constitution_runner.py           # invoke robo-project-constitution interview → write project-root node (SSE)

api/features/proposal_lifecycle/
├── proposal_contracts.py            # +ImplementationPlan, +ArchitectureDecision models; extend ProposalResponse
├── routes/
│   ├── proposals_intent.py          # MODIFY: intent emits Strategic Diff only
│   ├── proposals_plan.py            # NEW: SSE GET /stream/{id}/plan + plan CRUD/confirm
│   ├── proposals_constitution.py    # NEW (thin): interview gate only (no view/edit); delegates to constitution feature
│   ├── proposals_tasks.py           # MODIFY: pass effective constitution + plan into tasks skill
│   └── proposals_crud.py            # MODIFY: submit gate requires confirmed plan; staleness vs project Constitution node
└── services/
    ├── intent_runner.py             # MODIFY: strip tactical/arch; strategic-only prompt + parse
    ├── plan_runner.py               # NEW: read effective constitution from graph; invoke robo-proposal-plan; impact; persist
    ├── impact_builder.py            # REUSE: impact analysis now invoked from plan stage
    ├── tasks_runner.py              # MODIFY: include effective constitution + plan in human prompt
    └── implement_runner.py          # MODIFY: _context_doc includes effective constitution + implementation plan

docs/cypher/schema/
├── 03_node_types.cypher             # MODIFY: add Constitution node label + constraints
└── 04_relationships.cypher          # MODIFY: add HAS_CONSTITUTION (BoundedContext→Constitution)

skills/robo-proposals/
├── robo-proposal-intent/SKILL.md    # MODIFY: remove tactical/architecture; strategic-diff-only output contract
├── robo-proposal-plan/              # NEW (extends: robo-proposal-intent): tactical + impact + arch plan
│   ├── SKILL.md
│   └── references/architecture-plan.md   # deployment/ingress/mesh/framework/frontend/repo-mapping contract
├── robo-project-constitution/       # NEW (extends: speckit-constitution): 4-area interview
│   ├── SKILL.md
│   └── references/interview-questions.md
├── robo-proposal-tasks/SKILL.md     # MODIFY: review tasks against constitution + plan
└── robo-proposal-implement/SKILL.md # MODIFY: honor constitution + plan during implementation

frontend/src/features/proposals/
├── proposals.store.js               # MODIFY: plan state + SSE; constitution = interview-gate only (no view/edit)
└── ui/
    ├── IntentDecompositionView.vue  # MODIFY: strategic-only intent view
    ├── PlanView.vue                 # NEW: tactical + impact + architecture (+integration/devenv) review
    ├── ConstitutionInterview.vue    # NEW: interview ONLY (one-time gate); no persistent view/edit tab
    └── ProposalDetail.vue           # MODIFY: stage ordering Intent → Plan → Submit; NO constitution tab

frontend/src/features/constitution/   # NEW — Design-side constitution management
├── constitution.store.js            # project + per-BC constitution CRUD/effective
└── ui/
    └── ConstitutionEditor.vue        # 헌장 editor opened from Design root + each BC root ("헌장" icon)
# + wire a "헌장" icon entry point into the Design-side tree/canvas (contexts/aggregate viewer)

frontend/tests/
└── verify-proposal-constitution-plan.spec.ts   # NEW: Playwright flow
```

**Structure Decision**: Web-application layout (Option 2). The feature is a feature-modular evolution of an existing backend feature (`api/features/proposal_lifecycle/`) and its mirrored frontend (`frontend/src/features/proposals/`), with the AI reasoning expressed as skills under `skills/robo-proposals/`. No new top-level project or module is introduced.

## Complexity Tracking

> No Constitution violations — section intentionally empty.
