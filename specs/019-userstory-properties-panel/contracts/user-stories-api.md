# Contract: User Stories API extensions

**Feature**: `019-userstory-properties-panel`
**Date**: 2026-05-08

This contract documents the additions and modifications to the user-stories HTTP surface and the GWT generation prompt input. The output schema of GWT generation is unchanged.

---

## 1. `PATCH /api/user-story/{id}` — NEW

Single-row partial update for the InspectorPanel save action.

### Request

- **Path param**: `id` — UserStory node `id`. 404 if not found.
- **Body** (JSON, all fields optional; at least one mutable field required):

```json
{
  "role": "string (non-empty if present)",
  "action": "string (non-empty if present)",
  "benefit": "string (non-empty if present)",
  "priority": "low | medium | high",
  "status": "new | in-progress | done | <existing values>",
  "acceptance_criteria": ["string", "..."]
}
```

### Behaviour

- For every present field, MERGE its value onto the matching property on the `UserStory` node.
- When `acceptance_criteria` is present (including empty list): also set `criteriaUserEdited = true` and `criteriaEditedAt = datetime()`.
- When `acceptance_criteria` is absent: do not touch `acceptanceCriteria`, `criteriaUserEdited`, or `criteriaEditedAt`.
- Strip empty-after-trim entries from `acceptance_criteria` before write. Cap at 100 entries; reject 400 if exceeded.
- Validate `priority`/`status` against the same enum used by `/user-story/apply` today. Reject 400 with `{"detail": "<field>: invalid value"}` on mismatch.
- Empty body or no recognised fields → 400 `{"detail": "no fields to update"}`.
- Emit a `SmartLogger` JSONL event at start and on success/error, with `correlation_id`, `user_story_id`, the set of fields changed (names only — never criteria text — for log hygiene), and whether `criteriaUserEdited` was flipped.

### Response

- **200** — body is the same shape as the `GET /api/user-stories/{id}` response (see §3).
- **400** — validation error: `{"detail": "<message>"}`.
- **404** — UserStory not found: `{"detail": "user story not found"}`.

---

## 2. `POST /api/user-story/apply` — EXTENSION

The existing `apply` endpoint (`api/features/user_stories/authoring_router.py:106`) is extended to accept an optional `acceptance_criteria` field on its request body. Other fields and behaviour are unchanged.

### Behaviour delta

- If `acceptance_criteria` is provided: persist as `acceptanceCriteria` on the new node.
- `criteriaUserEdited` is **not** set by `apply` (default stays `false`). Initial criteria — whether from the planning agent or user-typed at creation — are treated as freshly seeded; only post-creation edits via PATCH constitute "user has curated this."
- All other inputs and validations remain as today.

---

## 3. UserStory READ responses — EXTENSION

All endpoints that return UserStory objects MUST include the criteria-related fields. Specifically:

- `GET /api/user-stories` (`catalog_router.py:15`)
- `GET /api/user-stories/unassigned` (`catalog_router.py:54` and `authoring_router.py:454`)
- The 200 response body of the new PATCH and existing apply.

### Response shape

```json
{
  "id": "string",
  "role": "string",
  "action": "string",
  "benefit": "string",
  "priority": "low | medium | high",
  "status": "string",
  "bcId": "string | null",          // only on the catalog GET that already returns it
  "bcName": "string | null",        // only on the catalog GET that already returns it
  "acceptanceCriteria": ["string", "..."],
  "criteriaUserEdited": false,
  "criteriaEditedAt": "ISO8601 string | null"
}
```

Existing fields that endpoints already return (e.g., `bcId`, `bcName`) are preserved as-is per endpoint. The three new fields (`acceptanceCriteria`, `criteriaUserEdited`, `criteriaEditedAt`) are added to every UserStory-returning endpoint.

Field naming note: API responses use the camelCase property name `acceptanceCriteria` (matching the Neo4j property and the schema doc). Request bodies (PATCH, apply) use `acceptance_criteria` (matching existing snake_case convention on the Pydantic side and `GeneratedUserStory` in `ingestion_contracts.py:85`). The router maps between them.

---

## 4. GWT generation prompt input — EXTENSION

`api/features/ingestion/event_storming/nodes_gwt.py` is extended to enrich the prompt fed to the LLM for each Command and Policy under generation.

### New prompt section (inserted before existing Aggregate/Event context)

```
Acceptance Criteria from linked user stories:
  - From UserStory "<role>: <action> (so that <benefit>)":
    1. <criterion-1>
    2. <criterion-2>
    ...
  - From UserStory "<role>: <action> (so that <benefit>)":
    1. <criterion-1>
    ...
```

### Inclusion rules

- Iterate every `UserStory` linked (existing relationship — same edges the user-story planning agent and navigator already use) to the Command/Policy under generation.
- Skip a UserStory whose `acceptanceCriteria` is empty/null.
- If, after filtering, no UserStory contributes any criteria: omit the section entirely (no header). Generation falls back to the existing prompt content unchanged. (Satisfies FR-008.)
- Criteria are listed in their stored order. Criteria text is inserted verbatim — no rewording, no truncation up to a soft cap of 200 criteria total per prompt (well above realistic counts; protects against pathological inputs only).

### Output schema

**Unchanged.** The GWT generator continues to produce the same scenario shape it produces today; the prompt enrichment biases content, not structure.

---

## 5. Frontend contract: InspectorPanel UserStory branch

Not a network contract, but a UI contract worth nailing down so frontend and backend stay aligned.

- The InspectorPanel renders a UserStory branch when `nodeLabel === 'UserStory'`.
- Editable fields in this branch: `role`, `action`, `benefit`, `priority`, `status`, plus an Acceptance Criteria list editor (add / edit / remove / reorder).
- Save action calls `PATCH /api/user-story/{id}` with only the fields that changed (delta-PATCH). If criteria were touched at all, `acceptance_criteria` is included in the body.
- After a successful save, the panel updates its local node data from the response (so `criteriaUserEdited` / `criteriaEditedAt` become visible to any future render that wants to use them).
- The InspectorPanel does not present a separate confirm modal; saves are explicit (button) but in-panel.
- The legacy `userStoryEditor` Pinia store and `UserStoryEditModal.vue` are removed; no UI surface other than this panel edits UserStory data after this feature ships.

---

## 6. What is *not* in this contract

- No batch PATCH; updates are per-UserStory.
- No "regenerate criteria" endpoint. (Out of scope; can be added later as the explicit reset for `criteriaUserEdited`.)
- No streaming on the PATCH — these are millisecond-grain graph mutations and Principle III explicitly reserves request/response for instant graph queries.
- No GWT auto-trigger. Editing criteria does **not** automatically regenerate GWT for linked Commands/Policies; users still trigger GWT regeneration explicitly through the existing flow.
