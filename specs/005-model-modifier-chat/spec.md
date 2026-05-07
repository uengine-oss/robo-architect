# Feature Specification: Conversational Model Modifier (Streaming ReAct Chat)

**Feature Branch**: `005-model-modifier-chat`
**Created**: 2026-05-06
**Status**: Backfilled (reverse-engineered from existing implementation)
**Input**: Backfill from existing code at `api/features/model_modifier/routes/chat_modify.py`, `api/features/model_modifier/routes/chat_confirm.py`, `api/features/model_modifier/routes/node_details.py`, `api/features/model_modifier/routes/ui_wireframe_from_image.py`, `api/features/model_modifier/chat_contracts.py`, `api/features/model_modifier/react_prompt.py`, `frontend/src/features/modelModifier/ui/ChatPanel.vue`

## User Scenarios & Testing

### User Story 1 - Edit a selected node by chatting in natural language (Priority: P1)

A modeler selects one or more nodes (Aggregate, Command, Event, Policy, ReadModel, UI, Property) on the canvas or in an explorer, opens the chat panel, and types a natural-language request such as "rename this command to PlaceOrder and update the description." The system streams back the agent's reasoning and concrete proposed changes; nothing is persisted yet.

**Why this priority**: This is the core value proposition — replacing tedious form editing with a conversational, multi-node-aware agent that understands the Event Storming model.

**Independent Test**: Select a node, send a non-trivial prompt, observe an SSE stream, and verify the response includes ReAct-style sections (THOUGHT/ACTION/OBSERVATION) and at least one structured draft change with a stable `changeId` — and that no Neo4j write occurs until confirm is called.

**Acceptance Scenarios**:

1. **Given** the user has selected at least one node and entered a non-empty prompt, **When** the user submits, **Then** the server opens an SSE stream (`text/event-stream`) and emits draft change events plus a final `[DONE]` sentinel.
2. **Given** the user submits with no selected nodes, **When** the request is made, **Then** the API returns HTTP 400 with a message asking to select nodes from explorer or canvas.
3. **Given** the user submits with only whitespace as the prompt, **When** the request is made, **Then** the API returns HTTP 400 "Prompt is required".
4. **Given** the user wrote the prompt in Korean, **When** the agent responds, **Then** the agent's natural-language reasoning is in Korean (matching the user's language).
5. **Given** the agent proposes a `connect` action, **When** the draft is emitted, **Then** the draft includes `sourceId`, `targetId`, and `connectionType` from the allowed set (`TRIGGERS`, `INVOKES`, `EMITS`, `REFERENCES`).

### User Story 2 - Approve a subset of proposed changes and persist them (Priority: P1)

After reviewing streamed drafts, the user picks which ones to approve and confirms. Only the approved drafts are written to Neo4j, and the operation is all-or-nothing across the approved set.

**Why this priority**: Without confirmation, suggestions never become persistent model changes; without per-item approval, the user cannot trust the agent enough to use it on real models.

**Independent Test**: Submit a confirm request with a list of `drafts` and a subset of `approvedChangeIds`; verify only the approved drafts are applied and the response reports `success`, `appliedChanges`, and `errors`.

**Acceptance Scenarios**:

1. **Given** the user provides drafts and a non-empty `approvedChangeIds` matching some of them, **When** confirm is submitted, **Then** only the matching drafts are applied and unapproved drafts are ignored.
2. **Given** `drafts` is empty or no approved id matches a draft, **When** confirm is submitted, **Then** the response is `success: true` with empty `appliedChanges` and `errors`.
3. **Given** any approved draft fails validation or persistence, **When** the apply runs, **Then** `success` is `false`, `errors` is non-empty, and no approved draft is partially persisted (atomic semantics).

### User Story 3 - Regenerate a UI wireframe from an uploaded screenshot (Priority: P2)

The user has a UI node attached to a Command or ReadModel and uploads a screenshot of a real screen. The system asks a vision-capable LLM to faithfully reproduce the screenshot as a sandboxed wireframe HTML fragment, normalizes it, and applies it directly as the UI node's `template`.

**Why this priority**: This is a high-impact authoring shortcut that is independent from chat editing; users can adopt it without using the chat at all.

**Independent Test**: POST a multipart/form-data request with `ui_id` and an image file; verify the UI node's `template` is updated with normalized HTML (rooted under `.wf-root`) and the response contains `template` and `success: true`.

**Acceptance Scenarios**:

1. **Given** a valid PNG/JPEG/WebP under 4 MB and an existing UI node id, **When** the request is made, **Then** the server returns a normalized wireframe HTML fragment and writes it to the UI node's `template`.
2. **Given** an unsupported content type or a file larger than 4 MB, **When** the request is made, **Then** the API returns HTTP 400 explaining the constraint.
3. **Given** `ui_id` does not match a UI node, **When** the request is made, **Then** the API returns HTTP 404.
4. **Given** the vision LLM exceeds 120 seconds, **When** the request is made, **Then** the API returns HTTP 504 "Wireframe generation timed out".

### User Story 4 - Inspect a node's current state before editing (Priority: P3)

Before issuing a chat request, the user (or the chat UI) wants to fetch the node's current properties and incoming/outgoing relationships so the prompt and the confirm preview can show "before" state.

**Why this priority**: Helpful but not essential — useful for confirm UI and tooling.

**Independent Test**: GET `/api/chat/node/{node_id}` and verify the response contains the node's properties and labels, its parent BoundedContext (if any), and a list of relationships with direction.

**Acceptance Scenarios**:

1. **Given** an existing node, **When** node details are requested, **Then** the response returns `{node, boundedContext, relationships}`, with `relationships` carrying `id`, `name`, `type`, `relationship`, and `direction` (`incoming`/`outgoing`).
2. **Given** a non-existent node id, **When** node details are requested, **Then** the API returns HTTP 404.

### Edge Cases

- The agent proposes a Property change without `parentType`/`parentId` — the prompt forbids this; downstream apply should reject as invalid.
- A `update` action targeting a Property uses the existing name as the selector and `updates.name` as the new name (Property rename does NOT use `action="rename"`).
- A UI `update` template fails normalization (missing `.wf-root`, contains `<script>`, inline event handlers, or `javascript:` URLs) — must be rejected by `normalize_ui_template`.
- A `REFERENCES` connect targets a Property where `isKey != true` — must be rejected.
- The user cancels mid-stream — the server's async generator stops cleanly without leaving partial Neo4j state because no writes occur during streaming.
- Even while ingestion is paused, modify requests still require an explicit node selection to bound context size.

## Requirements

### Functional Requirements

- **FR-001**: System MUST expose `POST /api/chat/modify` returning a Server-Sent Events stream (`text/event-stream`) with cache disabled and a final `[DONE]` sentinel.
- **FR-002**: `/modify` MUST require at least one entry in `selectedNodes` (HTTP 400 otherwise) and a non-empty `prompt` (HTTP 400 otherwise).
- **FR-003**: The streaming agent MUST follow a ReAct pattern (THOUGHT / ACTION / OBSERVATION) with inline JSON action blocks producing zero or more `DraftChange` records per turn.
- **FR-004**: Each `DraftChange` MUST carry a unique `changeId`, an `action` from `{rename, update, create, delete, connect}`, and a `targetId`; for `connect` it MUST also carry `sourceId` and `connectionType`.
- **FR-005**: System MUST emit no Neo4j writes during `/modify`; all persistence MUST happen via `POST /api/chat/confirm`.
- **FR-006**: `/confirm` MUST accept `drafts` and `approvedChangeIds`, filter drafts by approved id, and apply the approved subset atomically (all-or-nothing).
- **FR-007**: `/confirm` MUST return `success`, `appliedChanges`, and `errors`; on validation/apply failure `success` MUST be `false` and no approved draft is left partially persisted.
- **FR-008**: The agent prompt MUST instruct: respond in the user's language; include `bcId` for new nodes when known; route Property rename through `update` (not `rename`); enforce Property parent metadata; restrict `REFERENCES` to key-bearing properties.
- **FR-009**: For UI node `update`/`create`, `updates.template` MUST be an HTML fragment rooted under `.wf-root` with no `<!doctype>`, `<html>`, `<head>`, `<body>`, `<script>`, inline event handlers, or `javascript:` URLs; `<style>` blocks MUST be scoped under `.wf-root` and MUST NOT use `@import` or `url(...)`.
- **FR-010**: System MUST expose `POST /api/chat/ui-wireframe-from-image` accepting `ui_id`, an image file (PNG/JPEG/WebP, ≤ 4 MB), and `display_language` (`ko` or `en`, default `ko`).
- **FR-011**: The vision-LLM call MUST time out at 120 seconds and surface HTTP 504 to the client; non-existent UI nodes MUST return HTTP 404.
- **FR-012**: The wireframe response MUST update the UI node's `template` via the same atomic apply path as confirm and return the final normalized template.
- **FR-013**: System MUST expose `GET /api/chat/node/{node_id}` returning the node (with all properties and labels), its parent BoundedContext (resolved across `HAS_AGGREGATE`/`HAS_POLICY`/`HAS_UI`/`HAS_READMODEL`/`HAS_EVENT`), and its relationships with direction.
- **FR-014**: When `AI_AUDIT_LOG_ENABLED` is true, every modify request MUST be logged with the prompt, selected nodes, and conversation history (summarized) under `api.chat.modify.request`.

### Key Entities

- **DraftChange** (Pydantic model): in-memory proposal carrying `changeId`, `action`, `targetId`, optional `targetName`/`targetType`/`bcId`/`bcName`, `rationale`, an `updates` field-patch map, optional `before`/`after` snapshots, and connect-only `sourceId`/`connectionType`.
- **ModifyRequest**: `prompt`, `selectedNodes`, `conversationHistory`.
- **ConfirmRequest / ConfirmResponse**: contract for the apply step; response includes `success`, `appliedChanges`, `errors`.
- **UI** (Neo4j label `UI`): node carrying `template` (HTML), `attachedToId`/`attachedToType`/`attachedToName`; primary target of `ui-wireframe-from-image`.
- **Property** (Neo4j label `Property`): embedded child of an Aggregate/Command/Event/ReadModel; never appears as a standalone canvas node; subject to special agent rules (rename via update, REFERENCES requires `isKey=true`).
- **BoundedContext** (label `BoundedContext`): resolved as the parent context for any node returned via `/node/{node_id}`.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A user can rename, update, create, delete, or connect any supported node type by typing a single natural-language instruction, instead of opening per-type forms.
- **SC-002**: No proposed change reaches Neo4j without an explicit user confirm action — verifiable by inspecting the stream phase only emitting drafts and the confirm phase being the sole writer.
- **SC-003**: A user can regenerate a UI wireframe from a screenshot in under two minutes end-to-end (under the 120 s vision-LLM timeout plus normalization), with the result safely sandboxed under `.wf-root`.
- **SC-004**: Streaming feedback (THOUGHT/ACTION/OBSERVATION) appears progressively rather than only at the end, so users can interrupt obviously wrong reasoning before approving.
- **SC-005**: All audit logs needed to reconstruct a chat session (prompt, selection, drafts, approved subset, applied changes) are present when `AI_AUDIT_LOG_ENABLED` is on.

## Assumptions

- The platform `get_llm()` resolves to a chat LLM that supports streaming and tool/JSON output; `LLM_VISION_MODEL` may override the model used for image input.
- `apply_confirmed_changes_atomic` enforces both validation (Property parent rules, REFERENCES isKey rule, UI template sanitization via `normalize_ui_template`) and atomicity.
- Users always select nodes before chatting (UI gates this; backend enforces 400). The system intentionally does NOT auto-discover context to keep token budgets bounded (`MODEL_MODIFIER_CONTEXT_CHARS_LIMIT`).
- "Atomic" in the confirm path refers to the approved subset being applied together; unapproved drafts are simply discarded.
- Frontend `ChatPanel.vue` and `ImpactDetailsModal.vue` are the primary user surfaces; the API surface is reusable by other clients.
