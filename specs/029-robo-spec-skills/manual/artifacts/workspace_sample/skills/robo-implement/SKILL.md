---
name: robo-implement
description: Robo Architect-aware implementation loop. Inherits speckit-implement; constrains file placement to the layout dictated by plan.md, ticks tasks.md checkboxes as work completes, registers scaffolded files in the graph via MCP, and never writes marker comments into developer source code.
extends: speckit-implement
requires-speckit: ">=0.8.13, <0.9.0"
user-invocable: true
---

## Inheritance

This skill **inherits** the workflow of `/speckit-implement`. Before
executing anything else, read `.claude/skills/speckit-implement/SKILL.md`
and treat its Outline + Implementation Execution Rules as the **default
behavior**. Then apply the Overrides section below on top.

If the installed speckit version is outside the `requires-speckit` range
declared in the frontmatter above, **warn the developer explicitly** in
your first reply and ask for confirmation before continuing.

## Overrides

> TODO (US4 — T043): replace this section with the override list per
> research R11. Outline:
>
> 1. **Constrain file placement**: every file you scaffold MUST live at
>    the path predicted by the upstream `plan.md` (clean-architecture
>    layout for `core` BCs, default speckit layout for `supporting`).
>    Do not improvise paths.
> 2. **After scaffolding each file**: call MCP `register_implementation_files`
>    with `mode="merge"` to record the new path + `role` against the
>    matching `elementId` (FR-010, source mapping lives only in the
>    graph per research R5).
> 3. **Checkbox updates**: after completing a task, atomically rewrite
>    its `tasks.md` line from `- [ ]` to `- [x]` using a write-temp-then-
>    rename pattern (data-model.md §4). Preserve the existing `@robo`
>    marker exactly — the watcher relies on it to map the tick back to
>    its element.
> 4. **Blocked tasks**: when a task cannot complete (e.g., ambiguous
>    invariant), leave the checkbox unticked and append a short reason
>    annotation on the next line. The Design-tab progress badge will
>    render this element as `blocked` rather than `done`.
> 5. **NO marker comments in source**: under no circumstances write
>    `// @robo:aggregate=...` or any equivalent annotation into the
>    developer's source files. `/robo-sync` uses full AST extraction
>    instead (research R7); marker comments are explicitly rejected as
>    invasive and formatter-fragile.

See [specs/029-robo-spec-skills/contracts/mcp-tools.md](specs/029-robo-spec-skills/contracts/mcp-tools.md) §T6b for `register_implementation_files`.
