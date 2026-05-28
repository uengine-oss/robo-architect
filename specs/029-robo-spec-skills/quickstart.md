# Quickstart: Robo Spec Skills & MCP Bridge — Manual Smoke Plan

**Feature**: 029-robo-spec-skills

**Audience**: Whoever is reviewing the implementation PR or trying the feature end-to-end for the first time.

**Pre-reqs**:

- Robo Architect backend running locally: `uvicorn api.main:app --reload --host 127.0.0.1 --port 8000` (Constitution Principle IX — uvicorn without `--reload` will *not* pick up the new routes).
- Frontend running.
- One existing Robo Architect project with at least one `BoundedContext` that has at least one `Aggregate`, one `Command`, and one `Event`.
- A scratch Claude Code workspace directory you don't mind writing into.

---

## S1. Link a workspace and verify verbatim install (FR-012, SC-006)

1. From the Robo Architect UI for your test project, link the scratch workspace via the existing setup-project flow.
2. Confirm `<workspace>/.claude/skills/` now contains `robo-plan/`, `robo-tasks/`, `robo-implement/`, `robo-sync/`.
3. Confirm `<workspace>/.claude/robo-project.json` exists with a non-empty `projectId` and a `mcpEndpoint` pointing at the running backend.
4. Run `diff -r skills/robo-spec/ <workspace>/.claude/skills/` from the Robo Architect repo root — there should be **zero** differences.
5. Run `grep -r '{{' <workspace>/.claude/skills/` and `grep -r '{%' <workspace>/.claude/skills/` — both must return nothing. (SC-006 + FR-012 — no Jinja markers leak.)

## S2. `/robo-plan` for a core BC produces clean-architecture plan, no spec.md/data-model.md/contracts (US1, FR-004, FR-005)

1. In Robo Architect's UI, set the test BC's classification to `core` (or via `PATCH /api/contexts/{bc_id}/classification` — E3).
2. Open the workspace in Claude Code. Run `/robo-plan <BC-name>`.
3. Wait for completion.
4. Verify:
   - `<workspace>/specs/<NNN>-<slug>/plan.md` exists.
   - **No** `spec.md`, `data-model.md`, `contracts/`, **and no `.robo-link.json`** were created in that directory (source mapping lives only in the graph — R5).
   - The architecture section of `plan.md` mentions clean-architecture layers (entities / use cases / interface adapters / frameworks).
   - `GET /api/robo-spec/projects/{project_id}/implementation-map?bcId=<bc>` returns an entry for every aggregate/command/event of the BC with `files: []` (nothing implemented yet).

## S3. `/robo-plan` for a supporting BC produces default-speckit plan (US1)

1. Set another BC's classification to `supporting`.
2. Run `/robo-plan <other-BC-name>`.
3. Verify the produced `plan.md`'s architecture section follows the default speckit-plan layout (no four-layer clean-architecture split).

## S4. `/robo-plan` asks for classification when missing and persists the answer (US1 scenario 4)

1. Create a third BC with no `classification` set (via the API, or by ensuring you do not touch it through the UI's classification toggle).
2. Run `/robo-plan <BC-name>`.
3. The skill should ask which architecture style to use. Pick `core`.
4. After completion, `GET /api/contexts/{bc_id}/classification` should return `"core"`. The next `/robo-plan` on the same BC must NOT re-ask.

## S5. `/robo-tasks` produces element-marked tasks and progress flows to Design tab (US2, FR-007, FR-008, SC-003)

1. With `plan.md` in place from S2, run `/robo-tasks`.
2. Verify `<workspace>/specs/<NNN>-<slug>/tasks.md` exists. Every checkbox item has an HTML comment `<!-- @robo elementId="..." kind="..." -->`.
3. Open the Robo Architect Design tab for the test BC. Confirm each aggregate/command/event/read-model in the canvas shows a progress badge in `todo` state.
4. Manually tick one checkbox from `[ ]` to `[x]` in `tasks.md`. Save.
5. Within 5 seconds, the corresponding node in the Design tab updates its badge to `done`. (SC-003)

## S6. Click-to-open from Design tab — happy path (US3, FR-009, SC-004)

1. Run `/robo-implement` to scaffold at least one file (e.g., the primary `Order.ts` for an aggregate).
2. In the Design tab, click the corresponding Aggregate node.
3. Within 2 seconds the editor opens the file. (SC-004)

## S7. Click-to-open from Design tab — file does not yet exist (US3 scenario 2)

1. Pick a Command node that has no corresponding file yet (`.robo-link.json` has `files: []` for it).
2. Click it on the Design tab.
3. The UI shows a "not implemented yet" affordance and surfaces the related `tasks.md` task as the next action — not a generic editor error.

## S8. `/robo-implement` ticks checkboxes and registers source mapping (US4, FR-010)

1. With unticked tasks in `tasks.md`, run `/robo-implement`.
2. Watch the Design tab: nodes whose tasks complete flip from `todo` → `in-progress` → `done`.
3. After the run, `tasks.md` checkboxes for completed items are `[x]`. Files referenced live under clean-architecture-aligned directories when the BC is `core`.
4. **Source mapping in the graph**: `GET /api/robo-spec/projects/{project_id}/implementation-map?bcId=<bc>` now lists the scaffolded files under each touched element's `files[]`. Verify no `.robo-link.json` exists in the feature directory (mapping lives only in the graph — R5).
5. **No codegen markers in source**: `grep -RIn '@robo' src/` returns nothing. `/robo-implement` does not write marker comments into developer source files (R7).

## S9. `/robo-sync` round trip — additive change (US5, FR-011)

1. In a source file scaffolded by `/robo-implement` (e.g., `src/order/domain/Order.ts`), manually add a new property to the aggregate, **without** any `@robo` marker — just normal idiomatic TypeScript:
   ```ts
   loyaltyTier: string
   ```
2. Run `/robo-sync`.
3. The skill runs the TS AST extractor over the linked file, normalizes the extract, and calls `propose_sync`. It prints a proposal showing the added field. No `requiresConfirmation` entries appear (additions are non-destructive).
4. Confirm the apply step.
5. In Robo Architect's UI, the aggregate now shows `loyaltyTier` as a property.

## S10. `/robo-sync` round trip — rename requires confirmation (US5 scenario 2)

1. Rename an existing property in source (e.g., `customerEmail` → `customerContact`). Again, no markers — just the rename.
2. Run `/robo-sync`. The AST extractor sees one removed field and one added field of the same type; the server's diff puts them under `renameCandidates` and adds an entry to `requiresConfirmation`.
3. Decline. Robo Architect is **not** modified.
4. Re-run, confirm the rename. Robo Architect now reflects the rename (the property keeps its original element id; only its `name` changed).

## S11. `/robo-sync` no-op when nothing changed (US5 scenario 3)

1. Run `/robo-sync` twice in a row without changing anything in between.
2. The second run reports "no changes" — the AST extract matches the graph exactly — and does not modify Robo Architect.

## S12. Drift detection (FR-013)

1. After running `/robo-plan` and `/robo-tasks` against a BC, rename one of its aggregates in Robo Architect's UI.
2. Run `/robo-tasks` again. The skill calls `compute_drift` with the element IDs + `nameSeen` values from the local `tasks.md`; the server compares against live names and returns `status: "drift"` with the renamed aggregate listed. The skill stops and reports the drift (e.g., "Aggregate Order was renamed to OrderV2") before writing any files. No local fingerprint file is consulted — drift is computed statelessly at request time (R8).

## S13. Code link offline fallback (FR-008, edge case)

1. With the Design tab showing live progress badges, stop the linked workspace (e.g., shut down the developer's laptop or block the path).
2. Within ~10 seconds the Design tab badges visibly switch to "code link offline" rather than freezing on stale values.

## S14. Skill inheritance survives a speckit upgrade (R11, FR-002)

1. Note the currently installed speckit version (e.g., `0.8.13`) and confirm it sits inside the `requires-speckit` range declared in `skills/robo-spec/robo-plan/SKILL.md`'s frontmatter.
2. Upgrade speckit in the workspace to the next minor release (e.g., `0.9.x`) without changing anything under `<workspace>/.claude/skills/robo-*/`.
3. Re-run `/robo-plan <BC-name>` on a `core` BC and `/robo-tasks` after it.
4. Expected behaviors:
   - If the upgraded speckit version is **inside** the `requires-speckit` range, both commands produce the same artifacts they produced on the pinned version (re-run S2 + S5 verification steps). Inheritance still holds.
   - If the upgraded version is **outside** the range, the robo-* skill MUST visibly warn the developer (in its first output) that the upstream speckit is untested with these overrides and ask for confirmation before continuing. It does not silently produce wrong output.
5. After this scenario, revert speckit to the original pinned version so subsequent smoke runs are reproducible.

---

## Pass criteria summary

| Scenario | Verifies                                                       |
|----------|----------------------------------------------------------------|
| S1       | FR-012, SC-006 (verbatim install)                              |
| S2/S3/S4 | US1, FR-004, FR-005                                            |
| S5       | US2, FR-007, FR-008, SC-003                                    |
| S6/S7    | US3, FR-009, SC-004                                            |
| S8       | US4, FR-010                                                    |
| S9/S10/S11 | US5, FR-011, SC-005                                          |
| S12      | FR-013, edge case (rename drift)                               |
| S13      | FR-008 fallback, edge case (workspace offline)                 |
| S14      | R11, FR-002 (inheritance after speckit upgrade)                |

The feature is ready to merge when every scenario above passes once on a fresh checkout with `uvicorn --reload` running and a freshly linked scratch workspace.
