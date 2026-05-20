# Quickstart: Manual smoke test for `019-userstory-properties-panel`

**Feature**: `019-userstory-properties-panel`
**Date**: 2026-05-08

This is a hand-run smoke that exercises every acceptance scenario in `spec.md` end-to-end against a running stack. It is the gate I use locally before saying "this slice works."

## 0. Prerequisites

- Backend running (`uv run uvicorn api.main:app --reload`) against a local Neo4j with at least one ingested project that contains UserStories with non-empty `acceptanceCriteria`. If you don't have one handy, run the requirements ingestion against `specs/001-requirements-ingestion-sse/quickstart.md`'s sample input first.
- Frontend running (`cd frontend && npm run dev`).
- Browser open at the dev URL with the project loaded; the navigator tree visible on the left, the canvas in the middle.
- An open DevTools Network tab so you can watch the new PATCH request.

## 1. Story 1 — UserStory opens in the unified Properties panel

1. From the navigator tree, locate any UserStory node (any leaf under a UserStories grouping).
2. **Expected before this feature**: double-clicking it pops up a modal dialog (`UserStoryEditModal.vue`).
3. **Action**: double-click it now.
4. **Expected after this feature**: the InspectorPanel on the right opens (or focuses) and shows the UserStory's `role`, `action`, `benefit`, `priority`, `status` as editable inputs. **No modal** appears.
5. Now click on a Command in the canvas to swap the panel content. Then double-click the UserStory again.
6. **Expected**: the panel switches back to the UserStory view, replacing the Command content (Story 1 / scenario 2).

## 2. Story 2 — View and edit Acceptance Criteria inline

1. With the UserStory loaded in the InspectorPanel, scroll to the Acceptance Criteria section.
2. **Expected**: every criterion already on the node (from ingestion) is listed in order, each as an editable item.
3. Edit one criterion's text. Click Save.
4. **Network**: confirm a `PATCH /api/user-story/{id}` request with body containing only `acceptance_criteria` (delta-PATCH). Status 200. Response includes the updated list and `criteriaUserEdited: true`.
5. Add a new criterion at the bottom. Save.
6. **Expected**: the new entry appears in the list and the network confirms persistence.
7. Remove an existing criterion. Save.
8. **Expected**: the entry is gone from the list and the network confirms persistence.
9. Reorder two criteria via drag-handle (or up/down buttons, whichever the panel implements). Save.
10. **Expected**: order persists after reload (see step 11).
11. Hard-reload the page. Re-open the same UserStory.
12. **Expected**: every edit from steps 3–9 is still there, in the order saved (FR-006).

### Empty-criteria edge

13. Find a UserStory with zero criteria (or remove all criteria from one as a setup step) — the InspectorPanel should show the section as an empty editable list with an obvious "add first criterion" affordance (Story 2 / scenario 5).

## 3. Story 3 — Acceptance Criteria inform GWT generation

1. Pick a UserStory you just edited (so its `acceptanceCriteria` is now distinctive — e.g., contains a phrase like "rate-limit at 5 req/sec" that you typed yourself).
2. Find a Command linked to that UserStory (the navigator should make the link visible, or open the InspectorPanel for the Command and see its linked UserStories).
3. Trigger GWT generation for that Command via whatever the existing UI affordance is (the same way you'd trigger GWT today — this feature does not introduce a new trigger).
4. **Expected**: the resulting GWT scenarios contain language clearly traceable to the criteria you typed (e.g., a Then-clause referencing "rate-limit" or an explicit Given/When that operationalises one of your criteria).
5. Pick a UserStory with **zero** criteria, and a Command linked to it. Trigger GWT generation.
6. **Expected**: GWT generation completes successfully (no error) and produces output indistinguishable in shape from pre-feature output (FR-008 fallback).

## 4. Regeneration-vs-edit policy (D2)

This is the `[NEEDS CLARIFICATION]` resolution; worth verifying explicitly.

1. Take a UserStory you have edited via the InspectorPanel (`criteriaUserEdited` should now be `true` — verify in the GET response, or via Cypher `MATCH (u:UserStory {id: '...'}) RETURN u.criteriaUserEdited`).
2. Re-run requirements ingestion against the same source for the same UserStory (so the bulk-write phase touches it again).
3. **Expected**: the user-edited `acceptanceCriteria` value is preserved (not overwritten). Other fields the ingestion would normally update are still updated. `criteriaUserEdited` remains `true`.
4. Take a UserStory with `criteriaUserEdited == false` (one you have not manually edited). Re-run ingestion.
5. **Expected**: `acceptanceCriteria` may be overwritten by the new ingestion output, as before.

## 5. Modal removal (D5 / FR-009)

1. Search for any UI affordance that previously opened the modal — e.g., a "Edit Story" button, a context-menu item, a deep link.
2. **Expected**: every one routes to the InspectorPanel. Zero entry points still produce a modal.
3. In the codebase, run `rg -n "userStoryEditor|UserStoryEditModal" frontend/src`. **Expected**: zero matches outside this spec directory.

## 6. Failure modes

1. PATCH with `acceptance_criteria: []` (empty list) — should succeed and result in zero stored criteria with `criteriaUserEdited: true`.
2. PATCH with `acceptance_criteria` containing 101 entries — should fail with 400.
3. PATCH against a non-existent id — 404.
4. PATCH with no recognised mutable fields — 400 `{"detail": "no fields to update"}`.
5. Concurrent edit: open the same UserStory in two tabs, edit in both, save in both. The last save wins (no merge conflict UI). Confirm this matches the spec's edge case for concurrent edit — per the design we accept last-write-wins for now and rely on the `criteriaUserEdited` flag rather than optimistic concurrency control.

## 7. Done when

- All steps 1–5 pass on a clean run, on a project with at least three UserStories of varying criteria states.
- `rg "userStoryEditor"` and `rg "UserStoryEditModal"` in `frontend/src/` return zero matches.
- `git diff` shows no parallel new "Story panel" file — only `InspectorPanel.vue` carries the UserStory branch.
