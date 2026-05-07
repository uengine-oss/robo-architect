# Feature Specification: New User Story Authoring with LangGraph Planning Agent

**Feature Branch**: `008-user-story-planning-agent`
**Created**: 2026-05-06
**Status**: Backfilled (reverse-engineered from existing implementation)
**Input**: Backfill from existing code at `api/features/user_stories/authoring_router.py`, `api/features/user_stories/catalog_router.py`, `api/features/user_stories/planning_agent/user_story_graph.py`, `api/features/user_stories/planning_agent/user_story_planning_graph.py`, `api/features/user_stories/planning_agent/user_story_planning_contracts.py`, `frontend/src/features/userStories/ui/UserStoryEditModal.vue`

## User Scenarios & Testing

### User Story 1 - Add a new user story and get an agent-generated plan (Priority: P1)

A product owner writes a new requirement in Given/When/Then style — supplying `role`, `action`, and optional `benefit` — and optionally points it at a target Bounded Context. They want the system to immediately produce an actionable plan: scope decision (existing BC vs. new BC vs. cross-BC), extracted keywords, related existing model objects, and the concrete list of nodes/edges to create.

**Why this priority**: This is the primary new-authoring flow; without it, every new story would require the user to manually decide which BC to attach to and to hand-author every aggregate/command/event from scratch.

**Independent Test**: POST a new story to `/api/user-story/add` and verify the response contains `scope`, `scopeReasoning`, `keywords`, `relatedObjects`, `changes`, and `summary`, where `changes` are concrete `ProposedObject` records (not free text).

**Acceptance Scenarios**:

1. **Given** a new story whose action obviously matches an existing BC's domain language, **When** add is called, **Then** `scope` is `existing_bc`, `scopeReasoning` explains the match, and `changes` propose objects under that BC.
2. **Given** a new story whose domain has no match in the current model, **When** add is called, **Then** `scope` is `new_bc` and `changes` include creating a new `BoundedContext` plus its initial Aggregates/Commands/Events.
3. **Given** a story that spans multiple BCs (e.g. requires Events from one and Commands from another), **When** add is called, **Then** `scope` is `cross_bc` and `relatedObjects` reference nodes in more than one BC.
4. **Given** the caller passes `targetBcId`, **When** add is called, **Then** the plan respects that BC as the anchor regardless of keyword matching.
5. **Given** the agent fails internally, **When** add is called, **Then** the API returns HTTP 500 with `Failed to generate plan: <message>` and the error is logged at category `api.user_story.add.error`.

### User Story 2 - Approve the plan and persist the new story to the model (Priority: P1)

After reviewing the generated plan, the user approves it. The system creates a `UserStory` node, optionally links it to a target BC via `IMPLEMENTS`, and applies every `ProposedObject` (Aggregate / Command / Event / Policy / BoundedContext create + connect actions) to Neo4j.

**Why this priority**: Without persistence, planning is throwaway. Marked P1 because the value of US1 only materializes when the model actually changes.

**Independent Test**: POST `/api/user-story/apply` with a `userStory` payload, optional `targetBcId`, and a `changePlan`; verify a `UserStory` node is created with a generated `US-XXXXXXXX` id, that the response carries `userStoryId`, `appliedChanges` with per-item success and `duration_ms`, and `errors`.

**Acceptance Scenarios**:

1. **Given** a plan that creates an Aggregate and a Command on it, **When** apply runs, **Then** an `Aggregate` node is merged with `rootEntity` set to the name, a `Command` is merged, an `Aggregate-[:HAS_COMMAND]->Command` edge is created, and the user story is linked via `IMPLEMENTS` to the Aggregate.
2. **Given** `targetBcId` is provided, **When** apply runs, **Then** a `UserStory-[:IMPLEMENTS]->BoundedContext` edge is created before processing the change plan.
3. **Given** a plan with a `connect` action `connectionType=TRIGGERS` (Event→Policy), **When** apply runs, **Then** the `TRIGGERS` edge is merged with `priority=1` and `isEnabled=true`.
4. **Given** one item in the plan errors, **When** apply runs, **Then** the response still returns `success=false`, that item is recorded with `success: false` and an `error` string, and other items continue to apply.
5. **Given** any successful apply, **When** the response is returned, **Then** the slowest 10 change timings are summarized in `api.user_story.apply.done` logs for performance triage.

### User Story 3 - List existing user stories for review (Priority: P2)

A user (or an automated dashboard) wants to enumerate all user stories in the model, including which BC each is currently bound to, so they can spot unbound stories and review status.

**Why this priority**: Read-only browsing is supportive — useful for editing flows and dashboards but not blocking the core authoring/planning loop.

**Independent Test**: GET `/api/user-stories` and verify a JSON array where each entry carries `id`, `role`, `action`, `benefit`, `priority`, `status`, `bcId`, `bcName`, ordered by `id`.

**Acceptance Scenarios**:

1. **Given** the model has both BC-bound and unbound user stories, **When** the catalog endpoint is called, **Then** all are returned, with `bcId`/`bcName` populated only when an `IMPLEMENTS` edge to a `BoundedContext` exists.
2. **Given** the caller wants only unbound stories, **When** `GET /api/user-stories/unassigned` (or `GET /api/user-story/unassigned`) is called, **Then** only stories without any `IMPLEMENTS` edge to a `BoundedContext` are returned.

### Edge Cases

- The user passes `autoGenerate=false` — the agent runs through analyze/match-BC nodes but skips object generation; `changes` may be empty (frontend may use this for a quick scope-only preview).
- Two stories share identical role/action — apply still produces distinct nodes because each gets a fresh `US-XXXXXXXX` id.
- A `create` action with `targetType=Aggregate` references a BC id that doesn't exist — the BC link is skipped (OPTIONAL MATCH) but the Aggregate and the user-story IMPLEMENTS edge are still created.
- A `connect` action references a `sourceId` or `targetId` that doesn't exist — the MERGE silently fails to create the relationship, and the item is marked failed only if the Cypher errors.
- The user supplies a benefit field but the agent decides it doesn't change scope/related objects — the benefit is still persisted on the `UserStory` node.
- Apply receives an action other than `create`/`connect`/`update` — it is silently skipped (no error, no log entry beyond completion summary).

## Requirements

### Functional Requirements

- **FR-001**: System MUST expose `POST /api/user-story/add` accepting `role`, `action`, optional `benefit`, optional `targetBcId`, and `autoGenerate` (default `true`).
- **FR-002**: `/add` MUST return `scope` (`existing_bc` | `new_bc` | `cross_bc`), `scopeReasoning`, `keywords`, `relatedObjects`, `changes`, and `summary`.
- **FR-003**: The planning workflow MUST be implemented as a LangGraph state graph with at least three nodes: `analyze_story` (extract intent/keywords/verbs), `find_matching_bc` (decide scope, possibly match an existing BC), `generate_objects` (produce `ProposedObject` records).
- **FR-004**: Each `ProposedObject` MUST carry `action` (`create`/`update`/`connect`), `targetType`, `targetId`, `targetName`, optional `targetBcId`/`targetBcName`, `description`, `reason`, and connection fields (`connectionType`, `sourceId`, plus optional `actor`, `aggregateId`, `commandId`).
- **FR-005**: `/add` MUST log inputs at `api.user_story.add.request`, success at `api.user_story.add.done` with the full result, and failure at `api.user_story.add.error` with exception type and message.
- **FR-006**: System MUST expose `POST /api/user-story/apply` accepting `userStory`, optional `targetBcId`, and `changePlan`, returning `success`, `userStoryId`, `appliedChanges`, and `errors`.
- **FR-007**: Apply MUST generate a new user story id of the form `US-XXXXXXXX` (8-char uppercase UUID prefix) and CREATE a `UserStory` node with `role`, `action`, `benefit`, `priority='medium'`, `status='new'`, and `createdAt=datetime()`.
- **FR-008**: When `targetBcId` is provided, apply MUST `MERGE (us)-[:IMPLEMENTS]->(bc)` to the target BoundedContext before iterating the change plan.
- **FR-009**: Apply MUST support `create` for `Aggregate` (sets `rootEntity` = name, links via `HAS_AGGREGATE` and `IMPLEMENTS` from the user story), `Command` (links via `HAS_COMMAND` from a parent Aggregate), `Event` (links via `EMITS` from a parent Command), `Policy` (links via `HAS_POLICY` from a BC), and `BoundedContext` (links via `IMPLEMENTS` from the user story and updates `target_bc_id`).
- **FR-010**: Apply MUST support `connect` actions for `TRIGGERS` (Event→Policy with `priority=1`, `isEnabled=true`), `INVOKES` (Policy→Command with `isAsync=true`), and `IMPLEMENTS` (UserStory→any node).
- **FR-011**: Apply MUST support `update` actions that set `name` and `updatedAt` on the target node.
- **FR-012**: A failure on a single change item MUST NOT abort the apply call; the item MUST be recorded with `success: false`, an `error` string, and `duration_ms`, while remaining items continue.
- **FR-013**: Apply MUST capture per-item `duration_ms` and emit a completion log including `slowest_changes_top10` for performance visibility.
- **FR-014**: System MUST expose `GET /api/user-stories` returning all user stories with their BC assignment, ordered by `id`.
- **FR-015**: System MUST expose `GET /api/user-stories/unassigned` (and equivalent `GET /api/user-story/unassigned`) returning only user stories with no `IMPLEMENTS` edge to a `BoundedContext`.

### Key Entities

- **UserStory** (Neo4j label `UserStory`): authored requirement; `id` shaped `US-XXXXXXXX`, `role`, `action`, `benefit`, `priority`, `status`, `createdAt`, `updatedAt`. Linked to context via `IMPLEMENTS` edges.
- **BoundedContext** (label `BoundedContext`): scope anchor; user stories implement BCs; created lazily via `BoundedContext` `create` actions in the plan.
- **Aggregate / Command / Event / Policy** (labels `Aggregate`, `Command`, `Event`, `Policy`): primary domain objects the plan can create or connect.
- **ProposedObject** (Pydantic `ProposedObject`): single change item in a plan; canonical contract between the planning agent and the apply endpoint.
- **UserStoryPlanningState** (Pydantic `UserStoryPlanningState`): in-memory LangGraph state carrying inputs, analysis outputs (`story_intent`, `domain_keywords`, `action_verbs`), BC matching (`scope`, `scope_reasoning`, `matched_bc_id`, `matched_bc_name`), `related_objects`, and `proposed_objects`.
- **PlanningScope** (enum): `existing_bc` | `new_bc` | `cross_bc`; drives downstream object generation strategy.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A user can go from "I have a new requirement" to a structured, reviewable plan with explicit scope reasoning in a single API call — without manually picking a BC or hand-authoring object lists.
- **SC-002**: The plan distinguishes the three scope cases (`existing_bc`, `new_bc`, `cross_bc`) clearly enough that the user can decide whether to approve, refine, or escalate before applying.
- **SC-003**: Applying an approved plan persists the user story plus all proposed objects in one call, with per-item success/failure and timing visible in the response — no silent half-states.
- **SC-004**: Catalog endpoints surface unbound stories so users can find and assign work-in-progress without ad-hoc Cypher queries.
- **SC-005**: All add/apply calls produce structured logs (`api.user_story.add.*`, `api.user_story.apply.*`) sufficient to reconstruct what was requested, what the agent decided, and what was written to Neo4j.

## Assumptions

- `run_user_story_planning` is a deterministic-on-success function that returns either a Pydantic `UserStoryPlanningState`-like object or a plain dict; the router handles both shapes.
- The graph already supports the relationship types `IMPLEMENTS`, `HAS_AGGREGATE`, `HAS_COMMAND`, `EMITS`, `HAS_POLICY`, `TRIGGERS`, `INVOKES` with the semantics encoded in the Cypher.
- The frontend `UserStoryEditModal.vue` and the `userStoryEditor.store.js` / `userStoryChangeWorkflow.store.js` stores are the primary surfaces driving these endpoints; other clients MAY exist.
- "Soft" defaults (`priority='medium'`, `status='new'`) are acceptable starting values for a freshly authored story; later workflows can update them.
- Apply is per-item best-effort, not transactional across items; consumers must inspect `appliedChanges[i].success` rather than relying on the top-level `success` alone.
- The two `unassigned` endpoints under different prefixes (`/api/user-story/unassigned` and `/api/user-stories/unassigned`) coexist for backward compatibility; new clients should prefer the catalog router.
