# Phase 0 Research: Unified UserStory Editing in Properties Panel

**Feature**: `019-userstory-properties-panel`
**Date**: 2026-05-08

This document resolves the open questions raised in `spec.md` (notably FR-012's `[NEEDS CLARIFICATION]`) and locks in the integration decisions needed before Phase 1 design.

---

## D1. Where the unified Properties panel lives

**Decision**: Reuse `frontend/src/features/canvas/ui/InspectorPanel.vue`. Add a new branch in its existing per-type rendering (the `nodeLabel` computed at line 179 already normalizes `"UserStory"` even though no UI currently renders for it). All UserStory editing entry points are migrated to call the existing `openInspector` injection (`provide('openInspector', ...)` at `CanvasWorkspace.vue:397–401`) — same as Events/Commands/Aggregates.

**Rationale**: The user's stated complaint is that UserStory diverges from "every other object." The existing InspectorPanel is precisely the surface they mean by "속성창" — Events/Commands/Aggregates/ReadModels/UI/Policies all already render there. Mirroring that pattern is the smallest change that satisfies P1 and gives Story 2 a natural home (the Acceptance Criteria editor is just another section in the UserStory branch). The alternative — building a dedicated UserStory inspector — would re-introduce exactly the asymmetry the user wants removed.

**Alternatives considered**:
- *Keep the modal but enrich it with criteria editing.* Rejected — does not satisfy FR-001/FR-009 (must remove the popup) and re-entrenches the asymmetry.
- *Build a third "Story panel" surface alongside InspectorPanel.* Rejected — yet another asymmetry; multiplies maintenance.

---

## D2. Reconciliation of regenerated criteria vs. user-edited criteria (resolves FR-012)

**Decision**: User edits win. When ingestion (or any future regenerator) runs against a UserStory whose `acceptanceCriteria` has been edited in the Properties panel since the last ingestion, the regenerator MUST NOT overwrite that field. Detection mechanism: a boolean flag `criteriaUserEdited` (default `false`) on the `UserStory` node, plus a timestamp `criteriaEditedAt`. The InspectorPanel's PATCH sets both. The bulk-write phase in `api/features/ingestion/workflow/phases/user_stories.py` skips writing `acceptanceCriteria` for any UserStory whose `criteriaUserEdited == true`, while still updating other fields.

**Rationale**: This is the only policy that does not silently destroy user work. "Overwrite" punishes the analyst for editing; "merge" is impossible to do well without semantic alignment between two natural-language criteria lists; "skip" with a flag is deterministic, observable, and trivially reversible (the user can clear the flag by manually deleting all criteria, or we expose a "regenerate from scratch" action later). The flag also gives us a clean signal for telemetry — how often does ingestion actually find user edits in the wild?

**Alternatives considered**:
- *Always overwrite.* Rejected — silently loses curated criteria; violates Principle IV (human in the loop) for the criteria field specifically.
- *Always skip if criteria are non-empty.* Rejected — too aggressive; a fresh story with its initial ingestion-generated criteria would never get re-generated even if the underlying requirement changes substantially.
- *Merge via LLM diff.* Rejected — non-deterministic, expensive per ingestion, and would itself need user review, recursing the original problem.

**Operational note**: `criteriaUserEdited` is also exposed in the GET response so the frontend can render a small "edited" badge if useful (out of scope for this spec but cheap to keep open).

---

## D3. How GWT generation consumes Acceptance Criteria

**Decision**: At GWT generation time for a Command or Policy, fetch the `acceptanceCriteria` of every `UserStory` linked to that element (existing relationship — already used by the navigator and by the user-story planning agent). Inject the criteria, grouped by source UserStory, into the existing prompt template in `api/features/ingestion/event_storming/nodes_gwt.py:27–71` as a new "Acceptance Criteria from linked user stories" section, ahead of the Aggregate/Event context that the prompt already provides. The output schema is unchanged.

If a Command has no linked UserStory, or all linked UserStories have empty criteria, the prompt-builder omits the section entirely — the LLM falls back to the current Command/Aggregate/Event-driven generation. This satisfies FR-008 (graceful empty-criteria fallback).

**Rationale**: This is additive, not invasive. The existing prompt structure, the existing GWT output schema, the existing `/gwt/upsert` endpoint — none change. We are giving the generator more authoritative context, not changing what it produces. Grouping criteria *by source UserStory* (rather than flattening into a single bullet list) lets the LLM attribute scenarios back to the right story and respects FR-007 ("each criterion is reflected in at least one scenario or explicitly accounted for"), while not constraining it to a 1:1 criterion→scenario mapping (which would over-fit and force trivial scenarios for trivial criteria).

**Alternatives considered**:
- *Generate one GWT scenario per criterion, deterministically (no LLM).* Rejected — criteria are natural language; deterministic templating produces brittle GWTs ("Given criterion is true…") and ignores the surrounding domain context that GWT generation rightly leverages.
- *Run a separate, criteria-only GWT pass and merge with the domain-driven pass.* Rejected — two LLM calls, two output schemas to reconcile, and merge ambiguity. Single enriched prompt is simpler and proven by the same pattern used elsewhere in this repo (cf. how user-story metadata is already injected into other prompts).
- *Trigger automatic GWT regeneration on every criteria edit.* Rejected — violates Principle IV (changes propose-then-confirm); also would burn LLM cost on every keystroke-grain save. Regeneration stays an explicit user action, exactly like today.

---

## D4. Single-row UserStory write path (PATCH endpoint)

**Decision**: Add `PATCH /api/user-story/{id}` to `api/features/user_stories/authoring_router.py`. Body is a partial-update Pydantic model with optional `role`, `action`, `benefit`, `priority`, `status`, and `acceptance_criteria: list[str] | None`. When `acceptance_criteria` is present (even as an empty list), the handler MERGEs `acceptanceCriteria`, `criteriaUserEdited = true`, and `criteriaEditedAt = datetime()`. When it is absent, those three fields are not touched. The existing `POST /user-story/apply` endpoint is also extended to accept (optional) `acceptance_criteria` so a user can author criteria at creation time, but `apply` does NOT set `criteriaUserEdited` (initial authoring is treated like ingestion — regeneration is still allowed until the user explicitly edits afterward).

**Rationale**: The current authoring router has no per-row update endpoint at all (only `/add` and `/apply`); the InspectorPanel needs one. PATCH semantics fit the partial-edit nature of the panel (a user can edit just the priority, or just one criterion). Reusing the same handler for both field edits and criteria edits keeps the surface small. The flag-set distinction between PATCH (sets flag) and apply (does not) reflects the lifecycle: at creation, the LLM-generated or user-typed criteria are equally "fresh"; only post-creation manual edits constitute the "user has curated this" signal that should block regeneration.

**Alternatives considered**:
- *Two endpoints — PATCH for fields, PATCH-criteria for criteria.* Rejected — the InspectorPanel commonly saves both at once (e.g., user fixes the action wording and adds a criterion in the same edit). Single endpoint avoids transactional spread.
- *Reuse the bulk-write helper for single-row updates.* Rejected — that helper is built around the ingestion contract shape and would couple authoring to ingestion semantics, including unintended ingestion-only side effects.

---

## D5. Removing the legacy modal cleanly

**Decision**: Delete `frontend/src/features/userStories/ui/UserStoryEditModal.vue` and `frontend/src/features/userStories/userStoryEditor.store.js` outright. Migrate the only known caller — `frontend/src/features/navigator/ui/TreeNode.vue:279–288` — to call the injected `openInspector.openInspectorForNodeData({ id: node.id, type: 'UserStory', ... })` (the same shape used by EventModelingPanel at `EventModelingPanel.vue:829`). Remove the modal mount from `frontend/App.vue`. Search for any residual import of the deleted files and fail the build if any remains.

**Rationale**: The constitution disallows half-finished migrations (no parallel surfaces). FR-009 makes complete removal a hard requirement. Deleting the files (rather than leaving them behind a flag) makes the migration provably complete — if anything still imports them, the build breaks loudly; that is the desired failure mode.

**Alternatives considered**:
- *Soft-deprecate behind a feature flag.* Rejected — flag-gated UI duality is exactly the asymmetry the spec asks us to eliminate, and tends to live forever.
- *Keep the modal as a "fullscreen edit" alternative.* Rejected — same reason; also doubles the test surface.

---

## Summary of resolved questions

| Question | Origin | Resolution |
|---|---|---|
| Where does UserStory editing render? | Spec User Story 1 / FR-001 | InspectorPanel.vue, new UserStory branch (D1) |
| What if regeneration meets manual edits? | spec.md FR-012 `[NEEDS CLARIFICATION]` | User edits win; tracked via `criteriaUserEdited` flag (D2) |
| How do criteria reach GWT? | Spec User Story 3 / FR-007 | Injected as a new section in the existing GWT prompt, grouped by source UserStory; omitted on empty (D3) |
| How does the panel save changes? | Implicit in FR-006 | New `PATCH /api/user-story/{id}`; flag-setting on criteria edit (D4) |
| What happens to the modal? | FR-009 | Files deleted; only entry point (TreeNode dblclick) re-routed (D5) |

All `[NEEDS CLARIFICATION]` markers are resolved. No remaining unknowns block Phase 1.
