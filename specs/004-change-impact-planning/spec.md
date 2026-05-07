# Feature Specification: Change Impact Analysis & LLM-Assisted Change Planning

**Feature Branch**: `004-change-impact-planning`
**Created**: 2026-05-06
**Status**: Backfilled (reverse-engineered from existing implementation)
**Input**: Backfill from existing code at `api/features/change_management/routes/impact_analysis.py`, `api/features/change_management/routes/change_planning.py`, `api/features/change_management/routes/change_apply.py`, `api/features/change_management/change_api_contracts.py`, `frontend/src/features/changeManagement/ui/ImpactAnalysisPanel.vue`

## User Scenarios & Testing

### User Story 1 - See what an existing user story affects (Priority: P1)

A product owner is about to revise a user story (role/action/benefit). Before changing wording, they want to see every other piece of the domain model that touches that story so they can plan a coherent edit instead of breaking downstream behavior.

**Why this priority**: Impact visibility is the foundational capability — without it, users have no objective basis for editing stories or estimating risk, and every later step (planning, applying) becomes unsafe.

**Independent Test**: Load any existing user story by id, request its impact, and verify the response lists the parent BoundedContext plus every Aggregate, Command, and Event reachable through `IMPLEMENTS`/`HAS_AGGREGATE`/`HAS_COMMAND`/`EMITS` paths, deduplicated by id.

**Acceptance Scenarios**:

1. **Given** a user story that `IMPLEMENTS` a BoundedContext with two Aggregates, each with Commands that EMIT Events, **When** the user requests impact analysis, **Then** the response returns the user story, its bounded context, and all reachable aggregates/commands/events as a single deduplicated `impactedNodes` list with each node carrying `id`, `name`, and `type`.
2. **Given** a user story that `IMPLEMENTS` a Command directly (not a BC), **When** impact is requested, **Then** the parent Aggregate of that Command and every Event the Command emits are still included.
3. **Given** a `user_story_id` that does not exist in Neo4j, **When** impact is requested, **Then** the API returns HTTP 404 with a clear "user story not found" message.

### User Story 2 - Get an LLM-proposed change plan after editing (Priority: P1)

After editing the user story text, the user submits the original + edited story together with the impacted nodes. They want an ordered, reasoned list of concrete changes (rename, update, create, delete, connect) — not just free-text advice.

**Why this priority**: Without a structured plan, users would have to translate impact data into model edits manually for every story, defeating the purpose of the agent.

**Independent Test**: POST a request with `userStoryId`, `originalUserStory`, `editedUserStory`, and `impactedNodes` to the planning endpoint and verify the response contains a `scope` value, `scopeReasoning`, `keywords`, `relatedObjects`, an array of `changes`, and a `summary`.

**Acceptance Scenarios**:

1. **Given** a meaningful edit (e.g. renaming the actor in a story), **When** the user requests a plan, **Then** the response returns a non-empty `changes` array where each item has `action`, `targetType`, `targetId`, `targetName`, optional `from`/`to`, `description`, and `reason`.
2. **Given** a user has already received a plan and provides `feedback` plus `previousPlan`, **When** the user requests a plan again, **Then** the agent revises the previous plan rather than generating from scratch and returns the revised plan with the same shape.
3. **Given** the agent expanded impact through propagation, **When** the plan is returned, **Then** a `propagation` block reports `enabled`, `rounds`, `stopReason`, plus `confirmed` and `review` change lists.

### User Story 3 - Approve and apply changes back to the model (Priority: P2)

After reviewing the plan, the user approves it and asks the system to apply each change to the Neo4j model atomically per item, plus persist the edited user story text.

**Why this priority**: Visualization and planning are useless if changes cannot be persisted; this closes the loop. Marked P2 because P1 stories can be tested end-to-end without applying.

**Independent Test**: Submit `userStoryId` + `editedUserStory` + a `changePlan` containing one of each supported action and verify the user story node is updated and each change item is reflected in the graph (or recorded as a per-item failure with `success: false`).

**Acceptance Scenarios**:

1. **Given** a plan with a `rename` action on an Aggregate, **When** the plan is applied, **Then** that node's `name` is updated and `updatedAt` is set.
2. **Given** a plan with a `create` action of `targetType=Policy` and a `targetBcId`, **When** applied, **Then** a Policy node is merged and a `HAS_POLICY` relationship from the BC is established.
3. **Given** a plan with a `connect` action of `connectionType=TRIGGERS` between an Event and a Policy, **When** applied, **Then** an `Event-[:TRIGGERS]->Policy` edge is created with `priority`, `isEnabled`, and `createdAt` properties.
4. **Given** one change in the plan errors mid-apply, **When** the request completes, **Then** the response still returns `success=false`, the failing item with `success: false` and an `error`, and all other items in `appliedChanges`.

### Edge Cases

- A user story implements only a Command (no BC); BC is reported as `null` but commands/events are still resolved.
- The same node is reachable via multiple paths (e.g. via BC and via direct IMPLEMENTS) — it MUST appear only once in `impactedNodes`.
- A `create` change has an unsupported `targetType` (anything other than Policy/Command/Event) — the apply step skips it and logs a warning, no node is created.
- A `connect` change uses a `connectionType` outside `TRIGGERS|INVOKES|IMPLEMENTS` — the relationship is not created.
- Plan revision is requested with `feedback` but without `previousPlan` — the system treats it as an initial plan generation.
- Delete action is "soft": node remains in graph with `deleted=true` and `deletedAt` timestamp instead of being removed.

## Requirements

### Functional Requirements

- **FR-001**: System MUST expose `GET /api/change/impact/{user_story_id}` that returns the user story, its bounded context (or `null`), and a deduplicated list of impacted nodes (Aggregates, Commands, Events).
- **FR-002**: Impact analysis MUST traverse four Cypher paths from the user story: direct `IMPLEMENTS`; via BoundedContext → Aggregate → Command → Event; via Aggregate → Command → Event; via Command → Event plus the Command's parent Aggregate.
- **FR-003**: System MUST return HTTP 404 when the requested `user_story_id` does not exist.
- **FR-004**: System MUST expose `POST /api/change/plan` accepting `userStoryId`, `originalUserStory` (optional), `editedUserStory`, `impactedNodes`, optional `feedback`, and optional `previousPlan`.
- **FR-005**: The plan response MUST include `scope`, `scopeReasoning`, `keywords`, `relatedObjects`, `changes`, and `summary` so the user can both judge the plan's reach and review each individual change.
- **FR-006**: When `feedback` and `previousPlan` are both supplied, the system MUST treat the request as a revision of the prior plan rather than a fresh generation.
- **FR-007**: When the planning agent ran impact propagation, the response MUST include a `propagation` object reporting `enabled`, `rounds`, `stopReason`, `confirmed`, and `review`.
- **FR-008**: System MUST expose `POST /api/change/apply` accepting `userStoryId`, `editedUserStory`, and `changePlan`, returning `success`, `appliedChanges`, and `errors`.
- **FR-009**: Apply MUST persist `role`, `action`, `benefit`, and `updatedAt` on the user story node before processing the plan.
- **FR-010**: Apply MUST support per-item actions `rename` (set name), `update` (set description), `create` (Policy/Command/Event), `connect` (`TRIGGERS`/`INVOKES`/`IMPLEMENTS`), and `delete` (soft via `deleted=true`).
- **FR-011**: A failure on a single change item MUST NOT abort the entire apply call; the item MUST be recorded with `success: false` and an `error` string while remaining items continue to process.
- **FR-012**: Every step (impact, plan, apply, per-item) MUST emit structured logs via `SmartLogger` with categories `change.impact.*`, `change.plan*`, and `change.apply.*` carrying `http_context` and the relevant identifiers for traceability.

### Key Entities

- **UserStory** (Neo4j label `UserStory`): the editable narrative; `id`, `role`, `action`, `benefit`, `priority`, `status`, `updatedAt`. Anchor for impact + apply.
- **BoundedContext** (label `BoundedContext`): scope container reached via `IMPLEMENTS`; reported as `boundedContext` in impact response.
- **Aggregate / Command / Event** (labels `Aggregate`, `Command`, `Event`): impacted nodes; carry `id`, `name`, plus type-specific attributes (`rootEntity` for Aggregate, `actor` for Command, `version` for Event) and a synthetic `type` field in the response.
- **Policy** (label `Policy`): may be created by the plan; linked to a BC via `HAS_POLICY` and addressable as `TRIGGERS`/`INVOKES` endpoints.
- **ChangeItem**: API contract object with `action`, `targetType`, `targetId`, `targetName`, optional `from`/`to`, `description`, `reason`; for `connect` adds `sourceId` and `connectionType`.
- **Propagation report**: per-plan diagnostic object summarizing iterative impact expansion (`rounds`, `stopReason`, `confirmed`, `review`).

## Success Criteria

### Measurable Outcomes

- **SC-001**: For any user story with a non-trivial graph footprint (≥3 connected aggregates/commands/events), impact analysis returns the complete deduplicated set in a single request without the user manually traversing the graph.
- **SC-002**: A user can go from "I want to edit this story" to a reviewable structured change plan in one click after editing the text — no hand-authoring of change items.
- **SC-003**: Plan revisions reflect user feedback without losing already-acceptable items from the previous plan, so users converge on an approved plan in fewer iterations than restarting from scratch.
- **SC-004**: Approved plans persist to the model with per-item success reporting, so partial failures are visible and recoverable instead of silently rolling back the whole change.
- **SC-005**: Every impact, plan, and apply call produces structured logs sufficient to reconstruct what was requested, what the agent decided, and what was written to Neo4j without re-running the request.

## Assumptions

- The Neo4j graph already contains the relationship types `IMPLEMENTS`, `HAS_AGGREGATE`, `HAS_COMMAND`, `EMITS`, `HAS_POLICY`, `TRIGGERS`, `INVOKES` with the semantics encoded in the queries.
- Soft-delete semantics (`deleted=true` instead of physical removal) are acceptable for downstream consumers.
- The LLM-backed `run_change_planning` workflow handles its own scoping, related-object retrieval, propagation, and revision logic; this spec covers the contract surface only.
- "Apply" is per-item best-effort, not a transactional all-or-nothing operation; consumers reading `appliedChanges` must check `success` per item.
- The frontend `ImpactAnalysisPanel.vue` is the primary user surface; other entry points (e.g. CLI) MAY exist but are not required.
