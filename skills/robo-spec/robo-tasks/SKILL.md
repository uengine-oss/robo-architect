---
name: robo-tasks
description: Robo Architect-aware task generation. Inherits speckit-tasks; every checkbox item carries an HTML-comment marker mapping it to a Robo Architect design element so checkbox state can be reflected on the Design tab.
extends: speckit-tasks
requires-speckit: ">=0.8.13, <0.9.0"
user-invocable: true
---

## Inheritance

This skill inherits the workflow of `/speckit-tasks`. Read
`.claude/skills/speckit-tasks/SKILL.md` first for the default outline,
then apply the Overrides below verbatim on top.

If the installed speckit version is outside `requires-speckit`, warn
the developer in your first reply and ask for confirmation.

## Overrides

### Override 1 — locate the feature directory

Upstream looks at `.specify/feature.json` to find `feature_directory`.
We don't write that file. Instead:

1. Find the most recent `specs/<NNN>-<slug>/plan.md` in the workspace
   (highest `NNN`). If `$ARGUMENTS` names a BC and a matching
   `specs/<NNN>-<BC-slug>/plan.md` exists, prefer that.
2. If multiple `plan.md` files exist and `$ARGUMENTS` is empty,
   present a numbered picker of all `specs/<NNN>-<slug>/` directories
   and ask the developer which one to work on. (You may also call MCP
   `list_design_elements()` to cross-reference which BCs have
   `plan.md` on disk.)
3. If there are NO `plan.md` files at all, stop and tell the developer
   to run `/robo-plan <BC-name>` first — `/robo-tasks` needs a plan to
   convert into tasks.
4. Read the selected `plan.md` and identify the BC by its UUID (the
   Summary section names it explicitly).

### Override 2 — re-fetch the design from MCP

Upstream reads `spec.md`. We don't have one. Instead:

1. Call MCP `get_bc_design(bcId=<BC UUID from plan.md>)` to get the
   current design.
2. Use the returned aggregates / commands / events / read models as
   the **source of truth** for what tasks to generate. Do **not** rely
   on `plan.md`'s "Design Slice" section being current — the design
   may have changed since the plan was written.

### Override 3 — every checkbox carries an @robo marker

Upstream produces lines like:

```markdown
- [ ] T001 Implement OrderAggregate in src/order/Order.ts
```

We add an HTML-comment marker mapping the task to its design element:

```markdown
- [ ] T001 Implement OrderAggregate <!-- @robo elementId="<aggregate-uuid>" kind="Aggregate" -->
```

Rules:

- Every checkbox MUST carry exactly one `<!-- @robo elementId="..."
  kind="Aggregate|Command|Event|ReadModel" -->` marker.
- The marker is placed at the end of the line, after the task text.
- The `kind` matches what `get_bc_design` returned for that element.
- Tasks that aren't tied to a specific design element (setup,
  foundational, polish) get NO marker — only element-bound tasks do.

Write `tasks.md` to the same `specs/<NNN>-<slug>/` directory as
`plan.md`.

### Override 4 — file paths come from plan.md's File Layout section

Each task that scaffolds code references the predicted file path from
`plan.md`'s "File Layout" section. Do not invent paths.

## What this skill does NOT do

- Does NOT write marker comments into developer source code at any
  point. Markers go in `tasks.md` only (research R7).
- Does NOT regenerate `plan.md`. If the design has drifted from
  `plan.md`, surface that and ask the developer to re-run
  `/robo-plan`.
- Does NOT call `register_implementation_files` — that's
  `/robo-implement`'s job.
