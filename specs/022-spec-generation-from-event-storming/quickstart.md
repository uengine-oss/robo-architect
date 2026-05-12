# Quickstart: DDD Artifact Generation from Event Storming

Manual smoke test for feature 022. Run after the implementation lands; verifies the spec's acceptance scenarios against a real Neo4j graph and an open-pencil wireframe service (running and, for one scenario, stopped). **No Figma access is involved in any scenario.**

## Prerequisites

- Backend running (`uv run uvicorn api.main:app --reload --port 8000`).
- Neo4j running and populated with at least one Bounded Context that has:
  - ≥ 1 Aggregate with attributes (and, ideally, an `invariants` array).
  - ≥ 1 Command on that Aggregate with one or more Given/When/Then criteria.
  - ≥ 1 Event, ≥ 1 Policy, ≥ 1 ReadModel on that Aggregate (so the Aggregate Spec tables are non-trivial).
  - ≥ 1 User Story attached to that Aggregate.
  - ≥ 1 User Story bound to a `UI` node that has a non-empty `sceneGraph`.
- Ideally a second Bounded Context with at least one cross-BC flow to the first (an Event of one consumed by a Policy of the other) — for the Context Map scenario.
- Optional: an Aggregate whose Commands have **no** GWT — for the degraded-path scenario.
- The open-pencil wireframe service reachable at `WIREFRAME_SERVICE_URL` (default `http://localhost:7610`) — and stoppable for S7.

## Scenarios

### S1 — Single Bounded Context, full artifact set (Story 1; FR-005 → FR-009)

1. Find a fully-populated Bounded Context id (Neo4j Browser or the canvas inspector).
2. `curl -X POST http://localhost:8000/api/ddd-spec/generate-bounded-context -H 'Content-Type: application/json' -d '{"bounded_context_id": "<bc-id>"}'`
3. **Expect**:
   - `200`; `created` lists `domain-terms.md`, `bc-<bc-slug>.md`, one `aggregates/aggregate-<slug>.md` per Aggregate, `requirements.md`, and one `requirements.assets/<userStoryId>-<ui-slug>.scene.json` per bound wireframe (plus `.svg` for each, since the service is up).
   - On disk under `specs/bounded-contexts/<bc-slug>/`: all of the above.
   - `domain-terms.md` has one `## Term:` block per Aggregate, Command, Event, ReadModel, and key Property, each with **Definition / Business Context / Related Terms / Aliases to AVOID** (the last "(suggested — confirm)" since `aliases_to_avoid` defaults to `"suggest"`).
   - `bc-<slug>.md` has Purpose / Strategic Classification / Inbound Communication / Outbound Communication / Ubiquitous Language summary / Business Decisions / Assumptions — any section the graph can't fill is marked "(not modeled — confirm)", not omitted.
   - Each `aggregate-<slug>.md` has all nine sections; "Enforced Invariants" lists numbered EARS lines (`WHEN…/IF…/THEN system SHALL…`); "Corrective Policies" is present; the "Commands" table has Preconditions / Postconditions / Events emitted; a Repository Interface stub references the identity type.
   - `requirements.md` lists User Stories grouped by Aggregate, each with narrative, EARS acceptance criteria, and (for bound stories) a wireframe section showing a textual element tree, an embedded SVG, and a link to the `.scene.json`.

✅ Pass when: every Aggregate / Command / Event / ReadModel / User Story in the graph for that BC appears in the right artifact, and the markdown renders cleanly (SVGs visible) in a viewer.

---

### S2 — EARS translation fidelity (Story 1, Scenario 2; FR-011)

1. Pick one Command in the BC from S1 whose GWT you can read in the graph.
2. Open the owning Aggregate's `aggregate-<slug>.md` → "Enforced Invariants", and `requirements.md` → that Command's User Story → "Acceptance Criteria".
3. **Expect**: for `Given X, When Y, Then Z` you see `WHEN Y IF X THEN system SHALL Z` in both places; for a no-Given criterion you see `WHEN Y THEN system SHALL Z`; for an Aggregate-level unconditional invariant you see `THE <Aggregate> SHALL <constraint>`. The numbered list in "Enforced Invariants" has one entry per criterion (plus one per unconditional invariant).
4. Re-run S1's command with `{"bounded_context_id": "<bc-id>", "overwrite": true, "smooth_ears": false}` and confirm the EARS lines are identical (no LLM smoothing applied) — establishes the deterministic baseline.

✅ Pass when: the GWT→EARS mapping is exactly as specified and `smooth_ears:false` output is stable.

---

### S3 — Wireframe rendered from the scene graph, no Figma call (Story 1, Scenario 4; FR-012)

1. Confirm (e.g. via tcpdump / proxy logs, or simply by code inspection) that handling S1's request made **no outbound request to `api.figma.com`**.
2. Open `requirements.md` for the BC and find a story bound to a UI node.
3. **Expect**: a "Wireframe: <ui name>" sub-section with (a) a nested bullet list of the scene-graph elements (containers, text with content, buttons/inputs with labels), (b) an embedded `<img src="./requirements.assets/<userStoryId>-<ui-slug>.svg">`, (c) a link to `./requirements.assets/<userStoryId>-<ui-slug>.scene.json`. The `.scene.json` file content equals the `UI.sceneGraph` value from Neo4j.

✅ Pass when: the wireframe is reproduced from the local scene graph, the `.scene.json` matches the graph, and nothing touched Figma.

---

### S4 — Context Map (Story 2; FR-010)

1. `curl -X POST http://localhost:8000/api/ddd-spec/generate-context-map -H 'Content-Type: application/json' -d '{}'`
2. **Expect**:
   - `200`; `created` contains the single `context_map` entry; `specs/context-map.md` exists.
   - It opens with a Mermaid ```` ```mermaid ```` `graph LR` listing every BC and one labeled edge per cross-BC flow.
   - A "## Relationships" section has one `### <Upstream> → <Downstream>` block per edge with **Pattern**, **Direction**, **Translation**/**Reason**, **Spec file**.
   - Any edge whose pattern wasn't read from the graph shows "(inferred — confirm)" and produced a `relationship_pattern_inferred` warning.
   - If only one BC exists, the Relationships section is empty with an explanatory note.
3. Paste the Mermaid block into a Mermaid renderer (e.g. the VS Code preview) — it parses without errors.

✅ Pass when: the diagram is valid Mermaid, every cross-BC flow has a Relationships block, and inferred patterns are clearly marked + warned.

---

### S5 — Single Aggregate refresh leaves siblings alone (Story 3; FR-003)

1. After S1, note the mtimes of every file in `specs/bounded-contexts/<bc-slug>/`.
2. Modify one Aggregate in the graph (e.g. add an invariant).
3. `curl -X POST http://localhost:8000/api/ddd-spec/generate-aggregate -H 'Content-Type: application/json' -d '{"aggregate_id": "<id>", "overwrite": true}'`
4. **Expect**: only `aggregates/aggregate-<slug>.md` has a newer mtime and reflects the new invariant; `domain-terms.md`, `bc-<slug>.md`, `requirements.md`, and the other aggregate specs are byte-unchanged.

✅ Pass when: exactly one file changed and it shows the new graph state.

---

### S6 — Whole-model bootstrap with SSE + conflict + degraded path (Story 4; FR-004, FR-013, FR-014)

1. `curl -N -X POST http://localhost:8000/api/ddd-spec/generate-all -H 'Content-Type: application/json' -d '{}'` — observe a stream: `phase: loading_model`, `phase: context_map`, then per-BC `bc_started` / `wireframe_rendered` / `bc_completed`, ending with `event: complete`.
2. **Expect**: one BC folder per Bounded Context, `specs/context-map.md`, and the final `complete` payload listing all of them. The BC from S1 is reported in `skipped` with `reason: "already_exists"` (since you didn't pass `overwrite`); the others are created.
3. Re-run with `{"overwrite": true}` — now every BC is regenerated; folders that existed are replaced; `requirements.assets/*` from prior runs that are no longer referenced come back as `stale_asset` warnings (and are still on disk).

✅ Pass when: the SSE trace is well-formed, the conflict is reported rather than clobbered, and overwrite regenerates everything while preserving (and flagging) stale assets.

---

### S7 — Wireframe service down: textual artifacts still produced (Edge Case; FR-012, FR-014; SC-007)

1. Stop the open-pencil service (or set `WIREFRAME_SERVICE_URL` to a dead port and restart the backend).
2. Re-run S1's command with `{"bounded_context_id": "<bc-id>", "overwrite": true}`.
3. **Expect**: `200`; `requirements.md` is fully produced; every bound wireframe still has its textual element tree and its `.scene.json`; no `.svg` files were written; `warnings` includes `wireframe_service_unavailable` (and/or `svg_render_failed` per wireframe). The `.md`/`.scene.json` files are otherwise identical to S1's output.
4. Restart the service, re-run with `overwrite:true` — the `.svg` files reappear and the warnings drop out.

✅ Pass when: artifact text and `.scene.json` are intact with the service down, only SVGs are missing, and the gap is reported.

---

### S8 — Frontend framework declaration is a precondition (Story 5, Scenario 1; FR-020)

1. Open the PRD-generation UI (or `curl -X POST http://localhost:8000/api/prd/generate -d '{"tech_stack":{"include_frontend":true,"spec_format":"ddd","ai_assistant":"claude"}}'` with `Content-Type: application/json`).
2. **Expect**: `400` with body `{"code":"frontend_framework_required", "detail":"Select a frontend framework before generation (vue / react / svelte / …)."}`. No `specs/frontend/` is written; no zip is built.
3. Re-issue with `"frontend_framework":"vue"` (or `"react"` / `"svelte"`) added under `tech_stack` — the call succeeds (200) and the `files_to_generate` list includes `specs/frontend/framework.md`, `specs/frontend/menu-structure.md`, `specs/frontend/ui-flow.md`, `.claude/agents/frontend-engineer.md`, `.claude/agents/ddd-specialist.md`, `.claude/commands/generate-frontend.md`.

✅ Pass when: the precondition refuses with the right code, and supplying any of the three named frameworks unblocks the call with the expected file plan.

---

### S9 — Full DDD + frontend package, with causal UI flow (Stories 5–7; FR-021, FR-022, FR-023, FR-024; SC-009, SC-010, SC-011)

1. With a graph that has ≥ 2 Bounded Contexts connected by at least one cross-BC Policy → Event chain whose downstream Event triggers a User Story bound to a UI, `curl -X POST http://localhost:8000/api/prd/download -d '{"tech_stack":{"spec_format":"ddd","ai_assistant":"claude","include_frontend":true,"frontend_framework":"vue"}}' -H 'Content-Type: application/json' -o pkg.zip`.
2. `unzip -l pkg.zip` and confirm:
   - `specs/frontend/framework.md` (first non-heading line reads `Framework: vue`).
   - `specs/frontend/menu-structure.md` (BC-grouped bullet tree, leaves name route + User Story id).
   - `specs/frontend/ui-flow.md` (numbered entries; the upstream BC's UI appears *before* the downstream BC's UI per the causal chain).
   - `.claude/agents/frontend-engineer.md` and `.claude/agents/ddd-specialist.md` — exactly one of each; bodies reference `.claude/skills/*.md` by relative path, not by restated body content.
   - `.claude/commands/generate-frontend.md` — its body opens `specs/frontend/{framework,menu-structure,ui-flow}.md` and walks each `ui-flow` entry's link.
   - **No** `.claude/agents/<bc_name>_agent.md` files (verify with `unzip -l pkg.zip | grep '\.claude/agents/' | grep -v -E '(frontend-engineer|ddd-specialist)\.md$'` returning empty).
3. `unzip -p pkg.zip PRD.md | grep -E -i '\b(MUST|SHALL|Before starting|🚨|CRITICAL)\b'` returns **empty** (FR-022 / SC-011 — PRD.md is compositional only).
4. `unzip -p pkg.zip CLAUDE.md | grep -E '## Technology Stack|## Bounded Contexts'` returns **empty** (CLAUDE.md must not restate the stack table or BC inventory).
5. Follow one `ui-flow.md` entry's link: `unzip -p pkg.zip <the .scene.json relative path>` and confirm the file exists with non-empty content (SC-010 — every link reachable).
6. Repeat steps 1–5 with `"frontend_framework":"react"` and `"frontend_framework":"svelte"` — each run produces a `framework.md` whose conventions match the chosen framework's catalog entry.

✅ Pass when: the zip carries the three frontend files + role-based agents + new command, PRD.md and CLAUDE.md content are disjoint per the lint, every `ui-flow.md` link resolves to a real asset, and the UI-flow ordering reflects the cross-BC causal chain.

---

### S10 — Degraded paths for the frontend perspective (Edge Cases for P5–P7)

1. **Single BC fallback** — run S9 against a graph with only one BC (or BCs that don't talk to each other). **Expect**: `specs/frontend/ui-flow.md` falls back to per-BC insertion order; the response `warnings` array contains `ui_flow_no_cross_bc_edges` with the message naming the fallback.
2. **Unsupported framework** — temporarily edit `prd_tech_stack_catalog` to remove the `svelte` conventions stub (or use a framework value the catalog has no entry for, if the API permits). Re-run with that framework. **Expect**: `specs/frontend/framework.md` carries `Framework: <name>` line 1 and the Conventions section reads "(no curated conventions for this framework — confirm)"; `warnings` contains `frontend_framework_unsupported`. Restore the catalog.
3. **Unreferenced UI** — confirm a BC has at least one bound UI whose User Story isn't reachable from any cross-BC flow (a UI that's "an island" in the DAG). Re-run S9. **Expect**: `specs/frontend/ui-flow.md` lists that UI at the tail with the label "(unreferenced flow — review)"; `warnings` contains `ui_unreferenced_flow` naming the UI.
4. **Deprecated per-BC agent** — manually drop a fake `.claude/agents/membership_agent.md` into your working copy (simulating a pre-amendment zip), then re-run S9. **Expect**: the new zip does **not** include that file; the response `skipped` array contains an entry with `reason: "deprecated_per_bc_agent"` and the file's path so the user knows to delete their local copy.
5. **PRD↔CLAUDE lint failure** — hand-edit the generator to (temporarily) emit a prescriptive imperative ("you MUST read CLAUDE.md before starting") inside PRD.md. **Expect**: the build aborts with HTTP 500 + body `{"code":"prd_split_lint_failed", "detail":"PRD.md contains prescriptive imperative 'MUST' at offset ...; move it to CLAUDE.md."}`. Revert the edit.

✅ Pass when: every degraded path produces a warning (or, for the lint failure, an abort) with the expected code and the artifact set remains internally consistent.

---

### Non-regression check — existing features untouched

Quickly confirm these behave exactly as before this PR:

- `POST /api/ingestion/...` — start an ingestion flow; SSE arrives, Neo4j populated.
- `WS /api/figma-binding/...` — open the Figma plugin; bindings sync as before (this feature added/changed nothing here).
- `GET /api/claude-code/tree` (feature 021) — the Claude Code workspace opens, tree loads.
- `/docs` (Swagger) — the new endpoints appear under "ddd-spec"; all existing endpoints unchanged; no new env var demanded at startup.
- `specs/NNN-*/` and `specs/constitution.md` — untouched on disk after any of the above runs.

If any of these regress, this PR has unintended side effects and must be triaged before merge.
