# Phase 0 Research: Staged DDD Decomposition Mode for Proposals

**Feature**: 042-ddd-staged-proposal · **Date**: 2026-06-14

This document resolves the open technical questions for the plan. All decisions are grounded in the existing 039/040/041 proposal-lifecycle code and the `ddd-starter` skill.

## R1 — Skill packaging for the six DDD stages

**Decision**: One skill per stage — six new skills under `skills/robo-proposals/`:
`robo-proposal-discover`, `robo-proposal-decompose`, `robo-proposal-strategize`, `robo-proposal-connect`, `robo-proposal-define`, `robo-proposal-tactical`. Each declares `extends:` the matching `ddd-starter` step reference and carries numbered Overrides (Principle X inheritance). A seventh orchestration skill is **not** introduced — orchestration lives in a backend `staged_runner` that sequences the per-stage runners (mirrors how `intent_runner`/`plan_runner` already drive single skills).

**Rationale**: User-confirmed. Per-stage skills are independently invokable and resumable (FR-027), let a single stage be re-run after an amendment without re-running the rest (FR-018/US4-AC2), and keep each skill small enough to faithfully carry that stage's decision questions from the ddd-starter reference. Matches Principle X (skill-first) and Principle V (feature-modular).

**Alternatives considered**:
- *One monolithic `robo-proposal-ddd` skill* — rejected: re-running a single stage forces re-running the whole walkthrough; the skill would be too large to carry all six stages' decision depth faithfully.
- *Extend only intent+plan* — rejected: cannot expose the per-stage gates (Discover→…→Tactical) the spec requires; collapses the very deliberation the feature exists to surface.

## R2 — Strategic Decision Memory storage

**Decision**: Extend the existing **Constitution** node hierarchy (`api/features/constitution/services/constitution_store.py`). The project-root `(:Constitution {scope:'PROJECT', id:'CON-ROOT'})` and per-BC `(:BoundedContext)-[:HAS_CONSTITUTION]->(:Constitution {scope:'BOUNDED_CONTEXT'})` nodes gain a new JSON property `strategicMemory` (a structured DDD-strategy block), kept *alongside* the existing `raw` Markdown + best-effort fields. `effective_for_bc()` is extended to merge `strategicMemory` (BC overrides project-root, section by section).

**Rationale**: User-confirmed. The Constitution already has the exact project-root + per-BC + effective-merge shape, is already propagated into Plan/Tasks/Implement, and already drives staleness via `_mark_proposals_stale` (FR-021 comes for free). Adding a property (not a new label) avoids schema churn and reuses the constitution Design-side UI (FR-022).

**Structure of `strategicMemory`** (project-root holds project-level sections; per-BC holds BC-level sections):
```
{
  "version": 1,
  "differentiation": { "valueProposition": "...", "personas": ["..."], "differentiator": "..." },   // project-root
  "couplingPosture": { "default": "PUBSUB" | "SYNC", "rationale": "...", "pairs": [ {from,to,kind,sync} ] }, // project-root
  "contexts": {                                                                                       // per-BC (also mergeable at root)
    "<bcId-or-name>": {
      "classification": "CORE" | "SUPPORTING" | "GENERIC",
      "rationale": "...",
      "buildVsBuy": "...",            // for GENERIC
      "ubiquitousLanguage": [ {term, definition} ],
      "businessDecisions": ["..."],
      "purpose": "...", "domainRoles": ["..."]
    }
  }
}
```

**Alternatives considered**:
- *Separate `StrategicMemory` node hierarchy* — rejected by user; would duplicate the project-root + per-BC plumbing and the staleness wiring.

## R3 — Per-stage orchestration & state

**Decision**: Add a backend `staged_runner.py` under `api/features/proposal_lifecycle/services/` that owns the stage sequence. Each stage has its own thin runner (`stage_runners/<stage>.py`) calling `run_skill_lines(_SKILL_ROOT, "robo-proposal-<stage>", prompt)` and yielding SSE events, exactly like `plan_runner.stream_plan`. The orchestrator reads the **stage plan** + completed **stage artifacts** off the Proposal, runs the next not-skipped stage, and stores the resulting artifact back on the Proposal. This is resumable: on reconnect the orchestrator resumes at the first incomplete, non-skipped stage.

**Rationale**: Reuses the established runner+SSE pattern (Principle III streaming). Keeping orchestration in Python (not a skill) respects "the skill IS the agent, the backend is the parser" (Principle X) and gives deterministic, resumable sequencing.

**Alternatives considered**: A single SSE stream that runs all stages back-to-back — rejected: each stage needs a human confirm/skip gate (Principle IV), so the stream must stop at each stage boundary.

## R4 — Scope classification & stage plan

**Decision**: A lightweight `robo-proposal-scope` skill (extends `ddd-starter` `references/00-orientation.md`) runs first in Detailed mode, taking the original prompt + current domain nodes + existing strategic memory, and emits a **stage plan**: for each of the six stages `{ stage, applies: bool, recommendSkip: bool, reason }`. The backend presents it; the architect confirms/overrides (FR-009/FR-010); the confirmed plan is stored on the Proposal as `stagePlan`.

**Rationale**: The ddd-starter orientation reference already encodes the skip decision tree (single-context → skip Connect; strategic-only → skip Tactical; micro → collapse; Discover never fully omitted). Reusing it as the classifier honors Principle X and keeps the heuristics in one auditable place.

**Alternatives considered**: Pure backend heuristic (count epics/contexts) — kept as a *fallback default* the skill can refine, but not the primary, because the qualitative "strategic-only vs tactical" and "micro/local" judgments need the LLM reading the prompt.

## R5 — Mode field & dialog switch

**Decision**: Add `decompositionMode` (`SIMPLIFIED` | `DETAILED_DDD`, default `SIMPLIFIED`) to the Proposal node and `CreateProposalRequest`. `ProposalCreate.vue` gains a two-option switch above the prompt textarea (i18n labels + one-line descriptions). On submit, the store passes the mode; Simplified routes to today's intent SSE, Detailed routes to the new scope→staged flow. Upgrade-in-place (FR-003): a `POST /{id}/mode` endpoint sets `DETAILED_DDD` when `planStale`/not-confirmed and seeds the scope skill from the existing `strategicDiff`.

**Rationale**: Minimal, mirrors how the dialog already branches on stream events. Default `SIMPLIFIED` guarantees SC-006 (no change to the common case).

## R6 — Convergence into existing artifacts

**Decision**: The staged flow's terminal stages write the **same** `strategicDiff` (after Strategize/Decompose/Discover/Define consolidation) and `tacticalDiff` (after Tactical) shapes the current intent/plan stages produce, then hand off to the **existing** `plan_runner` impact build + `confirm_plan`. Downstream (Impact Preview 040, tasks_runner, implement_runner) is untouched.

**Rationale**: FR-023/SC-005 require mode-agnostic downstream. Consolidating into the established `StrategicDiff`/`tacticalDiff`/`ImplementationPlan` Pydantic shapes means zero downstream branching.

**Alternatives considered**: A parallel downstream for Detailed proposals — rejected: violates convergence, doubles maintenance.

## R7 — Conflict detection vs. strategic memory

**Decision**: When the Strategize/Connect/Define stages run for a BC that already has `strategicMemory`, the stage runner injects the recorded values into the skill prompt as "current memory" and instructs the skill to (a) start from them and (b) emit a `conflicts[]` array when the proposal's local decision diverges (e.g. recorded GENERIC but proposal treats as CORE; recorded PUBSUB default but proposal couples synchronously). The backend surfaces conflicts and blocks silent override — the architect must choose *amend memory* or *justify local exception* (FR-019), recorded on the Proposal.

**Rationale**: Keeps the comparison in the LLM that already has domain context, while the backend enforces the human-in-the-loop gate (Principle IV).

## R8 — Staleness on memory amendment

**Decision**: Reuse `constitution_store._mark_proposals_stale`. Because `strategicMemory` lives on the Constitution node and the project Constitution hash already drives `planStale`, extend the hash input to include `strategicMemory` so amending strategy bumps the hash and marks dependent proposal plans stale (FR-021/SC-008). Per-BC override amendments mark proposals whose plan touched that BC stale.

**Rationale**: Single staleness mechanism, already wired and tested in 041's `test_plan_and_constitution.py`.

## Resolved unknowns

All Technical Context items are resolved by the existing stack — no NEEDS CLARIFICATION remains. Language/runtime, storage, streaming, and skill-invocation are dictated by the established proposal-lifecycle feature and the constitution's Technology Constraints.
