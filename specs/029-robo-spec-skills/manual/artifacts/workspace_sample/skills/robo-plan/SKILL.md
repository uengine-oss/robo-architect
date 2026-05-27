---
name: robo-plan
description: Robo Architect-aware planning. Resolves a feature-id / BC / Aggregate argument via the robo-spec MCP bridge, drafts plan.md with classification-driven architecture (clean for core, default speckit for supporting), and never emits spec.md / data-model.md / contracts/ — those live in the Robo Architect graph.
extends: speckit-plan
requires-speckit: ">=0.8.13, <0.9.0"
argument-hint: "<feature-id | BC-name | Aggregate-name>"
user-invocable: true
---

## Inheritance

This skill **inherits** the workflow of `/speckit-plan`. Before executing
anything else, read `.claude/skills/speckit-plan/SKILL.md` and treat its
Outline + Phases as the **default behavior**. Then apply the Overrides
section below on top.

If the installed speckit version is outside the `requires-speckit` range
declared in the frontmatter above, **warn the developer explicitly** in
your first reply and ask for confirmation before continuing. The override
anchors below assume that range.

## Overrides

> TODO (US1 — T024): replace this section with the numbered override
> list per research R11. Anchors must reference both the upstream step
> number **and** a verbatim phrase from `speckit-plan/SKILL.md`, so a
> renumbering alone does not break the match. Outline:
>
> 1. **Outline step 2 — `setup-plan.sh`**: skip. Instead, call MCP
>    `resolve_design_element` with `$ARGUMENTS`; on `ambiguous`, list the
>    candidates and ask the developer to pick one. Then call
>    `get_bc_design` (or the equivalent for Aggregate-scoped arguments).
> 2. **Phase 1 step 1 — `data-model.md`**: do not write this file.
>    The data model is the Robo Architect graph; recording a local copy
>    would create a second source of truth (research R5 + Principle I).
> 3. **Phase 1 step 2 — `contracts/`**: do not create this directory.
>    Commands and events are the contracts; they live in the graph.
> 4. **Phase 1 step 3 — architecture template**: pick by classification —
>    `core` ⇒ clean architecture (entities / use cases / interface
>    adapters / frameworks-and-drivers); `supporting` ⇒ default speckit
>    layout unchanged. If classification is null, ask the developer once
>    and persist via `set_bc_classification` (FR-005).
> 5. **After plan.md is written**: call `register_implementation_files`
>    in `mode="merge"` with an empty `files: []` for every element under
>    the BC, so the Design tab can render "not implemented yet"
>    affordances before any code is written.

See [specs/029-robo-spec-skills/research.md](specs/029-robo-spec-skills/research.md) §R11 for the override-anchor strategy.
