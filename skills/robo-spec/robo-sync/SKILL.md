---
name: robo-sync
description: Reverse sync — propagates developer-made edits to aggregate / event / command properties in source code back into the Robo Architect graph via AST extraction (no marker comments). Propose→confirm→apply (Principle IV); destructive changes (renames, deletions) require explicit confirmation.
requires-speckit: ">=0.8.13, <0.9.0"
user-invocable: true
---

## No upstream inheritance

`/robo-sync` has no `/speckit-*` counterpart and is fully self-contained
(research R11). The frontmatter intentionally omits `extends:`.

## What this skill does

Given a project home that's already been set up (via the SPA's
**프로젝트 홈 생성** flow) and has source files that `/robo-implement`
scaffolded — and that the developer has since edited — push the
structural deltas back into the Robo Architect graph so the Aggregate
viewer / Design tab reflect them.

**Source code stays the source of truth for in-flight code.** The
graph stays the source of truth for the canonical design. `/robo-sync`
is the path that lets a developer make a structural change in code
(add / rename / remove an aggregate property, event payload field, or
command parameter), have the graph catch up, and then continue working
with the graph as the design oracle.

## Flow

1. **Read project context.** Open
   `<workspace>/.claude/robo-project.json` and remember `projectId`,
   `backendUrl`, `mcpEndpoint`. If the file is missing, stop and tell
   the developer to run the SPA's **프로젝트 홈 생성** flow first.

2. **Locate the BC.** If the developer passed an argument
   (`/robo-sync <BC-name>` or a BC id), use it. Otherwise find the
   most recent `specs/<NNN>-<slug>/plan.md` in the workspace and pull
   the BC id from its Summary section.

3. **Fetch the current design via MCP `get_bc_design(bcId=…)`.** The
   response carries every Aggregate / Command / Event / ReadModel
   with its current `implementationFiles[]` linkages and the
   per-element `version` you'll need for optimistic-concurrency on
   apply.

4. **Extract source structure.** For each file in any element's
   `implementationFiles[]`:

   ```bash
   # TypeScript file
   node .claude/skills/robo-sync/extractors/ts_extract.mjs <abs-path>
   ```

   ```bash
   # Python file
   python .claude/skills/robo-sync/extractors/python_extract.py <abs-path>
   ```

   Each extractor emits a single JSON document with `{kind, name, fields}`
   on stdout. Collect one entry per element.

5. **Call MCP `propose_sync(projectId, bcId, extracts)`.** The
   response carries:

   ```json
   {
     "proposalId": "prop-abc123",
     "diff": { "elements": [{ "elementId": "...", "added": [...], "modified": [...], "removed": [...] }] },
     "renameCandidates": [{ "elementId": "...", "from": {...}, "to": {...}, "confidence": 0.5, "rationale": "..." }],
     "requiresConfirmation": ["<elementId>:remove:<fieldName>", "<elementId>:rename:<old>-><new>", ...]
   }
   ```

6. **Render the diff to the developer in plain language.** For each
   element show:
   - **+ added** fields (safe; not in `requiresConfirmation`)
   - **~ modified** field types (safe; not in `requiresConfirmation`)
   - **- removed** fields (destructive; each entry IS in `requiresConfirmation`)
   - **↻ rename candidates** with the type-matched pair + confidence
     (each entry IS in `requiresConfirmation`)

7. **Ask the developer to confirm** every entry in
   `requiresConfirmation` individually. Default to NOT applying.
   Build the `confirmed` array out of the entries the developer
   explicitly approved.

8. **Call MCP `apply_proposal(projectId, proposalId, confirmed)`.**
   - On `status: "applied"` print a summary of `applied[]` (each
     element's new version + counts of added/modified/removed).
   - On `status: "conflict"` print which elements had their version
     bumped underneath, and offer to re-fetch the design + re-propose
     (the graph changed since step 5).
   - On `status: "unknown-proposal"` (TTL expired — 10 minutes) tell
     the developer to re-run `/robo-sync`.

## What this skill does NOT do

- Does NOT write `@robo` marker comments into source code at any
  phase (research R7 explicitly forbids this).
- Does NOT create new aggregates / commands / events from source. If
  the developer added a brand-new class in code that doesn't map to
  any element in the graph, `/robo-sync` reports it as "skipped —
  element not found in BC slice" and the developer is expected to
  add the element through Robo Architect first.
- Does NOT touch source code. The MCP write side only mutates the
  graph; source files are read-only from `/robo-sync`'s perspective.
- Does NOT silently apply destructive changes. Every entry in
  `requiresConfirmation` must be explicitly approved.
