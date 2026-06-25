# Phase 0 Research: Constitution-driven Plan Stage

All Technical Context unknowns are resolved below. There were no remaining `NEEDS CLARIFICATION` markers from the spec (both were answered in the spec's Clarifications session); the items here resolve *design* decisions needed before Phase 1.

## R1. Where the new "Plan" stage AI reasoning lives (skill vs. backend)

- **Decision**: New Claude skill `skills/robo-proposals/robo-proposal-plan/SKILL.md` with `extends: robo-proposal-intent`. It declares Overrides that (a) drop the strategic-decomposition steps (now owned by intent), (b) keep/own the tactical decomposition (Aggregate/Command/Event/ReadModel/Policy), and (c) add an architecture-plan step grounded in the supplied Constitution.
- **Rationale**: Constitution Principle X (NON-NEGOTIABLE) requires AI workflows to be skill files, not LangChain code; the `extends:` pattern avoids duplicating the deep decomposition rules already encoded in `robo-proposal-intent/references/*`.
- **Alternatives considered**: (a) One skill emitting everything with a "stage" flag — rejected: muddies the strategic/tactical review seam and the spec requires intent output to contain *zero* tactical detail. (b) Backend Python that calls the LLM directly — rejected: violates Principle X.

## R2. Naming collision with the existing `robo-plan` skill

- **Decision**: Name the proposal-lifecycle plan skill **`robo-proposal-plan`** (not `robo-plan`).
- **Rationale**: A `robo-plan` skill already exists for the speckit/feature-graph flow (drafts `plan.md` for graph-modeled domain features and deliberately suppresses spec.md/data-model.md). The proposal-lifecycle plan stage is a different concern; reusing the name would shadow it. The `robo-proposal-*` prefix matches the sibling skills (`robo-proposal-intent/tasks/implement/test/context`).
- **Alternatives considered**: Reuse `robo-plan` via `extends` — rejected: the two operate on different inputs (graph feature-id vs. a Proposal's strategic diff) and different outputs.

## R3. Constitution persistence, hierarchy & UI placement (REVISED 2026-06-11)

- **Decision**: Store the Constitution as **Neo4j node(s)** — a singleton `Constitution{scope:'PROJECT'}` plus optional per-BC `Constitution{scope:'BOUNDED_CONTEXT'}` via `(:BoundedContext)-[:HAS_CONSTITUTION]->(:Constitution)`. The **effective** constitution for a BC = project-root merged with that BC's overrides. **Management UI lives on the Design side** ("헌장" entry at the Design root + each BC root). The **Proposals tab only runs the interview when the project-root constitution is absent** (one-time gate creating the project-root node); it never shows a view/edit surface and never creates a per-Proposal constitution.
- **Rationale**: The user revised the earlier "repo file" decision. The graph being the source of truth (Principle I) is cleaner — staleness, traceability, and per-BC overrides all live in one ontology; the design surface (where BCs already live) is the natural home for amending. A SHA snapshot of the effective project-root constitution is stamped onto the confirmed plan for staleness only.
- **Alternatives considered**: repo file (rejected on revision — second source of truth, no per-BC overrides, wrong UI home); per-proposal snapshot (explicitly forbidden — must never create proposal-scoped constitutions). The `robo-project-constitution` skill still `extends: speckit-constitution` for the interview text shape; only the *sink* changes from file to graph node.

## R4. Interview UX mechanism

- **Decision**: Reuse the existing sequential clarification-question pattern already used by intent (`clarificationLog`, selectable answers) and stream interview turns over SSE (`stream_constitution`). The `robo-project-constitution` skill emits questions until it has all four decision areas, then emits the constitution body.
- **Rationale**: Principle III (Streaming-First) and consistency with the intent/clarify UX the user already knows. No new interaction primitive needed.
- **Alternatives considered**: A static form — rejected: cannot adapt follow-ups (e.g. repo-strategy follow-up only when "microservices" chosen) and bypasses the skill-first agent.

## R5. Impact analysis placement

- **Decision**: Move impact analysis from the (former) combined intent step into the **Plan** stage, reusing the existing `services/impact_builder.py` (038 EFFECT/SemanticDiff). `plan_runner` invokes it after the tactical diff is produced.
- **Rationale**: The spec requires the Plan stage to produce the impact analysis; `impact_builder` already computes graph-traversal impact and is feature-local. No duplication.
- **Alternatives considered**: Keep impact in intent — rejected: contradicts FR-006 (intent = strategic only) and FR-009 (plan produces impact).

## R6. State machine & submit gate

- **Decision**: Keep the existing statuses (`DRAFT→SUBMITTED→IMPLEMENTING→…`). The Plan stage runs while `DRAFT` (after intent). Add a **submit precondition**: `SUBMITTED` requires a confirmed `implementationPlan` (in addition to the existing "diff present" check in `proposals_crud.py`). Re-running intent or amending the constitution sets a derived `planStale` flag (computed from `constitutionHash` mismatch / strategic-diff version) that blocks submit until re-planned.
- **Rationale**: Avoids a schema/status migration (Principle I, minimal change) while enforcing FR-010/FR-018. Staleness is derived, not a new persisted status.
- **Alternatives considered**: Add a `PLANNED` status — rejected: extra migration and UI states for little gain; the DRAFT phase already represents "not yet submitted."

## R7. Propagation into tasks & implementation

- **Decision**: `tasks_runner` includes the constitution body + implementation plan in the human prompt to `robo-proposal-tasks`, whose SKILL.md gains a "review against constitution/plan" step (FR-015/016). `implement_runner._context_doc` appends the constitution + plan sections to the context doc already passed to `robo-proposal-implement` (FR-017).
- **Rationale**: Both runners already assemble a prompt/context doc from `strategicDiff`/`tacticalDiff`; this is an additive field, not a new mechanism.
- **Alternatives considered**: A separate "constitution check" pass after tasks — rejected: an extra round-trip; the review belongs inside task generation where conflicts can be surfaced inline.

## Open items deferred to /speckit-tasks

- Exact target-repo filename/path for the constitution file (default: spec-kit path).
- Whether `planStale` is surfaced as a banner vs. a blocking modal (UX detail).
