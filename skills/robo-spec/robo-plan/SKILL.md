---
name: robo-plan
description: Robo Architect-aware planning. Resolves a feature-id / BC / Aggregate argument via the robo-spec MCP bridge, drafts plan.md with classification-driven architecture (clean for core, default speckit for supporting), and never emits spec.md / data-model.md / contracts/ — those live in the Robo Architect graph.
extends: speckit-plan
requires-speckit: ">=0.8.13, <0.9.0"
argument-hint: "<feature-id | BC-name | Aggregate-name>"
user-invocable: true
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Inheritance

This skill inherits the workflow of `/speckit-plan`. Before any other
step, read `.claude/skills/speckit-plan/SKILL.md` to understand the
default outline and phase structure. **Then apply the Overrides
section below verbatim on top of it** — the overrides replace, skip,
or extend specific steps from upstream.

If the installed speckit version is outside the `requires-speckit`
range declared in the frontmatter, warn the developer explicitly in
your first reply and ask for confirmation before continuing.

## Overrides

The argument `$ARGUMENTS` is a Robo Architect feature id, BC name, or
Aggregate name. Source-of-truth is the graph reachable through the
`robo-spec` MCP server (configured in `.claude/mcp.json`).

Apply the following overrides on top of the upstream `/speckit-plan`
workflow:

### Override 1 — replace the Setup step (Outline §1)

Upstream Outline §1 says: *"Run `.specify/scripts/bash/setup-plan.sh
--json` from repo root and parse JSON for FEATURE_SPEC, IMPL_PLAN,
SPECS_DIR, BRANCH."*

**Replace** with the following resolution:

0. **If `$ARGUMENTS` is empty or whitespace**, call MCP tool
   `list_design_elements()` first, present the available
   BoundedContexts (with their classification + nested aggregates) to
   the developer as a numbered picker, and use their answer as the
   `query` for the next step. **Do not** assume a name or call
   `resolve_design_element` with a wildcard — it will return
   `not-found`.
1. Call MCP tool `resolve_design_element(query="$ARGUMENTS")` with
   the developer-supplied or developer-picked name.
2. If status is `ambiguous`, list the candidates and ask the developer
   to pick exactly one by id; re-call with that id.
3. If status is `not-found`, stop and report it — do not write any
   file. Suggest the developer check the spelling against the
   Robo Architect Design tab, or re-run `/robo-plan` with no argument
   to get a fresh listing.
4. Call MCP tool `get_bc_design(bcId=<resolved id>)`. If the resolved
   element is an Aggregate, derive its parent BC and call with that
   instead.
5. Derive the local feature directory yourself (do NOT call
   `setup-plan.sh`):
   - Slug = lowercased, kebab-cased element name (e.g.,
     `MembershipManagement` → `membership-management`).
   - Pick the next available `NNN` by scanning existing `specs/NNN-*`
     directories; if none exists, start at `001`.
   - `FEATURE_DIRECTORY = specs/<NNN>-<slug>/`.
   - Create the directory.
6. Set `IMPL_PLAN = <FEATURE_DIRECTORY>/plan.md`. Do **not** create
   `spec.md` — Robo Architect is the spec source of truth.

### Override 2 — skip Phase 0 (research.md)

This feature inherits its design from the graph. There is no
NEEDS CLARIFICATION reservoir to drain into a `research.md`. Skip the
entire upstream Phase 0 — do not call any research agent and do not
write `research.md`.

### Override 3 — skip Phase 1 data-model.md (FR-004)

Upstream Phase 1 §1 says: *"Extract entities from feature spec →
`data-model.md`."*

**Skip entirely.** The data model is the Robo Architect graph. Writing
a local `data-model.md` would create a second source of truth
(Principle I + research R5). Confirm in `plan.md`'s summary that the
data model is owned by Robo Architect and link the BC id.

### Override 4 — skip Phase 1 contracts/ (FR-004)

Upstream Phase 1 §2 says: *"Define interface contracts → `/contracts/`."*

**Skip entirely.** Commands and events are the contracts; they live in
the graph. Do **not** create a `contracts/` subdirectory.

### Override 5 — classification-driven architecture template (FR-005)

The architecture section of `plan.md` is determined by the BC's
`classification` field (returned by `get_bc_design`):

- **`"core"`** ⇒ use **Clean Architecture**: organize the file plan
  into the four standard layers — `entities/`, `usecases/`,
  `interface_adapters/`, `frameworks_and_drivers/`.
- **`"supporting"`** ⇒ use the **default speckit-plan architecture
  template** unchanged (whatever upstream produces).
- **`null` (missing)** ⇒ ask the developer ONCE which style to use.
  Present the choice clearly:

  > The BoundedContext `<NAME>` has no classification recorded in
  > Robo Architect. Pick one:
  >   - **core** — domain-critical; produce a clean-architecture plan.
  >   - **supporting** — utility / commodity; produce the default
  >     speckit-plan layout.

  Wait for the answer. Then **immediately** call MCP tool
  `set_bc_classification(bcId=<id>, classification=<answer>)` so the
  next run does not re-ask. Then proceed with the chosen template.

For each aggregate / command / event / read model returned by
`get_bc_design`, predict a file path and record it in `plan.md`'s
"File layout" section. Example for `core` (Clean Architecture):

```
src/<bc-slug>/entities/<Aggregate>.ts
src/<bc-slug>/usecases/<Command>.ts
src/<bc-slug>/interface_adapters/<Command>Controller.ts
src/<bc-slug>/frameworks_and_drivers/<Aggregate>Repository.ts
```

### Override 6 — seed empty implementation-file links (FR-009, US3 prep)

After `plan.md` is written, for every element returned by
`get_bc_design` (every aggregate, every command, every event, every
read model), call MCP tool:

```
register_implementation_files(
    projectId   = <from .claude/robo-project.json>,
    elementId   = <element id>,
    files       = [],
    mode        = "merge"
)
```

This seeds the source-mapping side of the graph with empty file lists,
so the Design tab can render "not implemented yet" affordances before
`/robo-implement` has scaffolded anything. Read `projectId` from
`<workspace>/.claude/robo-project.json` (key `projectId`).

### Override 7 — Constitution Check & Complexity Tracking (Phase 1 §3)

Upstream Phase 1 §3 says: *"Re-evaluate Constitution Check post-design."*

Keep this step, but the constitution to evaluate against is **Robo
Architect's own constitution** at `.specify/memory/constitution.md` if
present; otherwise skip the gate-by-gate eval and inline a short note
saying so. Do not invent a constitution.

## Output

`plan.md` MUST contain at least:

1. **Summary** — one paragraph naming the BC + classification + chosen
   architecture style + the MCP tools used to fetch the design.
2. **Source of truth** — explicit statement that the data model lives
   in the graph + the BC id, plus the rationale for not emitting
   `data-model.md` / `contracts/`.
3. **Design slice** — bulleted list of aggregates / commands / events
   / read models pulled from `get_bc_design`, with their ids in
   parens.
4. **File layout** — the predicted path for every element (see
   Override 5).
5. **Next steps** — point at `/robo-tasks` for the next phase, and
   note that `/robo-implement` will fill in the files at the predicted
   paths and call `register_implementation_files` per element.

## What this skill does NOT do

- Does **not** write `spec.md`. Robo Architect is the spec.
- Does **not** write `data-model.md`. The graph is the data model.
- Does **not** write `contracts/`. Commands and events in the graph
  are the contracts.
- Does **not** write `research.md`. Inherited from the graph.
- Does **not** put marker comments into developer source code at any
  point. `/robo-sync` uses full AST extraction instead (research R7).
