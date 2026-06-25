# Implementation Plan: Staged DDD Decomposition Mode for Proposals

**Branch**: `042-ddd-staged-proposal` | **Date**: 2026-06-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/042-ddd-staged-proposal/spec.md`

## Summary

Add a per-proposal **decomposition mode** (Simplified vs. Detailed DDD) to the 039/040/041 Proposal lifecycle. Simplified mode keeps today's `Intent → Plan` path untouched. Detailed mode walks the proposal through the six `ddd-starter` stages — Discover → Decompose → Strategize → Connect → Define → Tactical — each implemented as **its own skill** (Principle X), each gated by an architect confirm/skip (Principle IV), each streamed over SSE (Principle III). A scope-classification step proposes which stages apply (skipping cross-context stages for single-BC changes, the tactical stage for strategic-only changes, collapsing micro changes toward Simplified). Durable strategic conclusions (business differentiator, per-BC Core/Supporting/Generic, default coupling posture, per-BC ubiquitous language) are promoted **once** into a new `strategicMemory` block on the existing **Constitution** node hierarchy (project-root + per-BC, effective merge from 041) and reused/confirmed by later proposals; per-change tactical detail stays on the Proposal. The staged flow consolidates into the **same** Strategic/Tactical Diff + Implementation Plan shapes the existing downstream (Impact Preview, Tasks, Implement) already consumes — zero downstream branching.

## Technical Context

**Language/Version**: Python 3.11+ (backend), Vue 3 + Vite (frontend)

**Primary Dependencies**: FastAPI, Neo4j official driver (via `api/platform/neo4j.py`), Claude Code PTY skill runner (`api/platform/skill_runner.run_skill_lines`), EventSource/SSE; Vue Flow / Pinia on the frontend. AI work is **skill-first** (Principle X) — no new LangChain/LangGraph.

**Storage**: Neo4j. **No new node labels or relationships.** New JSON-string properties on existing `Proposal` and `Constitution` nodes (see data-model.md).

**Testing**: pytest (`api/features/proposal_lifecycle/tests/`, `api/features/constitution/`), Playwright (`frontend/tests/`).

**Target Platform**: Local/desktop (Electron) + web; backend on Linux/macOS dev hosts.

**Project Type**: Web application (FastAPI backend + Vue frontend), feature-modular (Principle V).

**Performance Goals**: Streaming-first; each stage emits phase/log lines before completion. No throughput target beyond responsive SSE.

**Constraints**: Graph-as-source-of-truth (Principle I); human-in-the-loop on every stage/skip/memory write (Principle IV); provider-agnostic LLM (Principle VI); observable via SmartLogger at phase boundaries (Principle VII).

**Scale/Scope**: 6 new stage skills + 1 scope skill; 1 new backend route module + 1 orchestration service + thin per-stage runners; Constitution `strategicMemory` extension; frontend dialog switch + staged walkthrough UI; 8 FR groups, 27 FRs.

## Constitution Check

*GATE: must pass before Phase 0 and re-checked after Phase 1.*

| Principle | Compliance |
|---|---|
| **I. Graph-as-Source-of-Truth** | PASS — no parallel store. Stage artifacts are Proposal-scoped JSON on the graph; durable strategy lives on Constitution nodes; the only domain-graph mutation remains the consolidated Strategic/Tactical Diff applied via the existing merge. |
| **II. Event Storming Vocabulary** | PASS — stages and outputs use DDD terms (Bounded Context, Aggregate, Command, Event, Core/Supporting/Generic, Ubiquitous Language). |
| **III. Streaming-First** | PASS — every stage runs over SSE with phase/log_line events, reusing the intent/plan runner pattern. |
| **IV. Human-in-the-Loop** | PASS — each stage has explicit confirm/skip; memory writes and conflict resolutions are architect-confirmed; nothing auto-applies. |
| **V. Feature-Modular** | PASS — backend additions stay under `api/features/proposal_lifecycle/` and `api/features/constitution/`; frontend mirrors under `frontend/src/features/proposals/` and `…/constitution/`. No cross-feature imports (strategic memory reached via the constitution service / graph). |
| **VI. Provider-Agnostic LLM** | PASS — all AI via skills over the existing runtime; no provider/model hardcoded. |
| **VII. Observable by Default** | PASS — each stage runner logs start/decision/done with correlation IDs via SmartLogger (matches `plan_runner`). |
| **X. Skill-First Deep Agent (NON-NEGOTIABLE)** | PASS — the six stages + scope classifier are SKILL.md files using `extends:` against the `ddd-starter` step references and the existing `robo-proposal-*` skills; the backend only orchestrates + parses. No LangChain/LangGraph added. |
| **VIII / IX (Figma)** | N/A — no Figma SceneGraph or plugin surface in this feature. |

**Initial gate: PASS.** No violations → Complexity Tracking left empty.

**Development-workflow obligations**: schema doc comments precede code (property-only additions to `03_node_types.cypher`/`04_relationships.cypher`); every new endpoint appears in Swagger `/docs`; frontend folder changes ship in the same PR; spec lives under `specs/042-…`.

## Project Structure

### Documentation (this feature)

```text
specs/042-ddd-staged-proposal/
├── plan.md              # This file
├── spec.md              # Feature spec (with Test Plan)
├── research.md          # Phase 0 — R1…R8 decisions
├── data-model.md        # Phase 1 — Proposal + Constitution property extensions
├── contracts/
│   └── staged-ddd-api.md# Phase 1 — SSE + JSON endpoints
├── quickstart.md        # Phase 1 — Scenarios A–F
├── checklists/
│   └── requirements.md  # Spec quality checklist (passing)
└── tasks.md             # Phase 2 — created by /speckit-tasks (NOT here)
```

### Source Code (repository root)

```text
skills/robo-proposals/                         # Principle X — one skill per stage (NEW)
├── robo-proposal-scope/SKILL.md               # extends ddd-starter/references/00-orientation.md → stage plan
├── robo-proposal-discover/SKILL.md            # extends ddd-starter/references/02-discover.md
├── robo-proposal-decompose/SKILL.md           # extends ddd-starter/references/03-decompose.md
├── robo-proposal-strategize/SKILL.md          # extends ddd-starter/references/04-strategize.md  (writes durable memory)
├── robo-proposal-connect/SKILL.md             # extends ddd-starter/references/05-connect.md      (coupling posture)
├── robo-proposal-define/SKILL.md              # extends ddd-starter/references/07-define.md        (ubiquitous language)
└── robo-proposal-tactical/SKILL.md            # extends ddd-starter/references/08-code.md + robo-proposal-plan tactical refs

api/features/proposal_lifecycle/
├── proposal_contracts.py                      # +DecompositionMode, StagePlan, StageArtifact(*), MemoryConflict; CreateProposalRequest.decompositionMode
├── routes/
│   ├── proposals_crud.py                      # write decompositionMode on CREATE
│   └── proposals_staged.py                    # NEW — mode upgrade, scope SSE, stage SSE, stage confirm/skip, consolidate
└── services/
    ├── staged_runner.py                       # NEW — orchestrates stage sequence, resumable, persists artifacts
    ├── stage_runners/                         # NEW — thin per-stage runners (call run_skill_lines, yield SSE)
    │   ├── scope.py  discover.py  decompose.py  strategize.py  connect.py  define.py  tactical.py
    ├── strategic_memory.py                    # NEW — promote durable sections → Constitution; conflict detection
    └── staged_consolidate.py                  # NEW — stage artifacts → standard strategicDiff/tacticalDiff

api/features/constitution/services/
└── constitution_store.py                      # extend: strategicMemory read/write; effective_for_bc merge; hash includes strategicMemory

frontend/src/features/proposals/
├── ui/ProposalCreate.vue                      # mode switch + branch to staged flow
├── ui/StrategicStages.vue                     # NEW — Intent-tab orchestrator: scope→Discover→Decompose→Strategize
├── ui/PlanStages.vue                          # NEW — Plan-tab orchestrator: Connect→Define→Tactical→consolidate
├── ui/StagePlanReview.vue                     # NEW — scope stage-plan confirm/override
├── ui/stages/StageRunner.vue                  # NEW — shared stage shell: SSE log, viz, choices, feedback regen, conflicts, confirm/skip
├── ui/stages/{Discover,Decompose,Strategize,Connect,Define,Tactical}Viz.vue  # NEW — per-stage interactive visualizations
├── ui/ProposalDetail.vue                      # Intent tab = StrategicStages; Plan tab = PlanStages → PlanView (Impact tab unchanged)
└── proposals.store.js                         # staged SSE subscriptions (+ per-stage feedback) + confirm/skip/consolidate actions

frontend/src/features/constitution/
└── ui/ConstitutionEditor.vue                  # +strategicMemory view/edit (Design-side, FR-022)

docs/cypher/schema/
├── 03_node_types.cypher                       # comment-only: new Proposal/Constitution properties
└── 04_relationships.cypher                    # comment-only: no new relationships (strategicMemory on existing HAS_CONSTITUTION)
```

**Structure Decision**: Web-application layout, extending the existing `proposal_lifecycle` and `constitution` features in place (Principle V). The staged flow is a new route module + orchestration service alongside the existing `intent_runner`/`plan_runner`; the six stage skills follow the `extends:` inheritance pattern (Principle X). No new top-level feature directory is introduced because the capability *is* an evolution of the proposal lifecycle.

**UX decision (2026-06-14, post-implementation revision)**: The Detailed-mode stages are **fused into the existing Proposal tabs** rather than run as a standalone wizard — the strategic stages (Discover · Decompose · Strategize) live in the **Intent tab** (`StrategicStages.vue`), the tactical stages (Connect · Define · Tactical) live in the **Plan tab** (`PlanStages.vue`), and the **Impact tab is unchanged**. After the Plan tab's Tactical stage, `consolidate` produces the standard `strategicDiff`/`tacticalDiff` and the tab falls through to the existing `PlanView` for architecture generation. Each stage is rendered by a shared `StageRunner.vue` that shows a **stage-appropriate interactive visualization** (Strategize = 2×2 Core Domain Chart with draggable subdomains; Connect = Bounded-Context message map with per-edge Event/Command/Query + sync controls; Discover = event timeline; Decompose/Define/Tactical = structured cards) plus multiple-choice controls, a **per-stage feedback box** (regenerates that stage via `?feedback=` on the stage SSE), and a raw-JSON advanced fallback. Backend stage endpoints are altitude-agnostic, so this is purely a frontend composition change.

## Phase 0 — Research

Complete. See [research.md](research.md). Eight decisions resolved (skill packaging, memory storage, orchestration, scope classification, mode field, convergence, conflict detection, staleness). No NEEDS CLARIFICATION remains — the existing stack dictates all technical choices.

## Phase 1 — Design & Contracts

Complete:
- [data-model.md](data-model.md) — `Proposal` gains `decompositionMode`/`stagePlan`/`stageArtifacts`/`currentStage`/`memoryConflicts`; `Constitution` gains `strategicMemory`; stage machine + effective-merge + staleness defined. No new labels/relationships.
- [contracts/staged-ddd-api.md](contracts/staged-ddd-api.md) — mode on create, mode upgrade, scope SSE + stage-plan confirm, per-stage SSE + confirm/skip, consolidate, and the extended constitution endpoints for `strategicMemory`.
- [quickstart.md](quickstart.md) — Scenarios A–F mapping to SC-001…008 and the spec Test Plan TP-A…F.
- Agent context: CLAUDE.md SPECKIT marker updated to point at this plan.

### Post-Design Constitution re-check

Re-evaluated after design: still **PASS**. The design adds no parallel store (I), keeps DDD vocabulary (II), streams every stage (III), gates every mutation (IV), stays feature-modular (V), routes all AI through skills (VI/X), and logs at phase boundaries (VII). No complexity deviations to track.

## Phase 2 — Task planning approach (preview only; tasks.md created by `/speckit-tasks`)

`/speckit-tasks` will derive dependency-ordered tasks roughly in this order:
1. **Schema + contracts** — Pydantic models (`proposal_contracts.py`), schema doc comments, `decompositionMode` on create.
2. **Constitution `strategicMemory`** — store read/write, effective merge, hash/staleness; tests (extends `test_plan_and_constitution.py`).
3. **Stage skills** — the six `robo-proposal-*` SKILL.md (+ scope), each `extends:` its ddd-starter reference with its decision-question Overrides and JSON output contract.
4. **Stage runners + orchestrator** — `stage_runners/*`, `staged_runner.py`, `strategic_memory.py` (promotion + conflict detection), `staged_consolidate.py`.
5. **Routes** — `proposals_staged.py` (SSE + confirm/skip/consolidate + mode upgrade), Swagger.
6. **Frontend** — mode switch, `StagePlanReview.vue`, `StagedDddWalkthrough.vue`, store actions; `ConstitutionEditor.vue` strategic-memory surface.
7. **Tests** — backend `test_staged_ddd.py` (TP-A…F), Playwright `manual-042-capture.spec.ts`, then user manual.

Each task will cite its FR(s)/SC(s). Stage skills and their runners pair up so a stage can be built and tested end-to-end before the next.

## Complexity Tracking

No constitution violations — table intentionally empty.
