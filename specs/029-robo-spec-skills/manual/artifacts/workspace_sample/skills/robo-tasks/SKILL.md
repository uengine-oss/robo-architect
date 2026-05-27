---
name: robo-tasks
description: Robo Architect-aware task generation. Inherits speckit-tasks; every checkbox item carries an HTML-comment marker mapping it to a Robo Architect design element so checkbox state can be reflected on the Design tab.
extends: speckit-tasks
requires-speckit: ">=0.8.13, <0.9.0"
user-invocable: true
---

## Inheritance

This skill **inherits** the workflow of `/speckit-tasks`. Before executing
anything else, read `.claude/skills/speckit-tasks/SKILL.md` and treat its
Outline + Task Generation Rules as the **default behavior**. Then apply
the Overrides section below on top.

If the installed speckit version is outside the `requires-speckit` range
declared in the frontmatter above, **warn the developer explicitly** in
your first reply and ask for confirmation before continuing.

## Overrides

> TODO (US2 — T035): replace this section with the override list per
> research R11. Outline:
>
> 1. **Before generating any task**: call MCP `compute_drift` with the
>    element ids + `nameSeen` values referenced by the local `plan.md`.
>    If `status == "drift"` and any blocking category is non-empty,
>    stop and report; do not write tasks against stale names (FR-013).
> 2. **Task format**: every checkbox item MUST include exactly one
>    HTML-comment marker of the form
>    `<!-- @robo elementId="..." kind="Aggregate|Command|Event|ReadModel" item="..." -->`,
>    placed at the **end of the line** for the checkbox. The marker keys
>    the task to a design element so checkbox state can be reflected on
>    the Design tab (FR-007 / FR-008).
> 3. **Marker scope**: markers go in `tasks.md` only. **Never** instruct
>    the LLM to write marker comments into developer source code —
>    `/robo-implement` is explicitly forbidden from doing so (research
>    R7), and `/robo-sync` uses full AST extraction instead.

See [specs/029-robo-spec-skills/data-model.md](specs/029-robo-spec-skills/data-model.md) §2.3 for the marker shape and [contracts/mcp-tools.md](specs/029-robo-spec-skills/contracts/mcp-tools.md) for the MCP surface.
