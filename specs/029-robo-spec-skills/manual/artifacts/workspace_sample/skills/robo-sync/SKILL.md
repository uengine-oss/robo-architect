---
name: robo-sync
description: Reverse sync — propagates developer-made edits to aggregate / event / command properties in source code back into the Robo Architect graph via full AST extraction (no marker comments). Propose→confirm→apply (Principle IV); destructive changes (renames, deletions) require explicit confirmation.
requires-speckit: ">=0.8.13, <0.9.0"
user-invocable: true
---

## No upstream inheritance

`/robo-sync` has no `/speckit-*` counterpart and is fully self-contained
(research R11). The frontmatter intentionally omits `extends:`.

If the installed speckit version is outside the `requires-speckit` range
declared in the frontmatter above, the warning is informational only —
this skill does not delegate to any speckit workflow, but the
`requires-speckit` pin keeps the robo-* skill suite consistent.

## Flow

> TODO (US5 — T050): replace this section with the end-to-end flow per
> research R7. Outline:
>
> 1. Read `<workspace>/.claude/robo-project.json` for `projectId` and
>    `mcpEndpoint`. Fail clearly if either is missing.
> 2. Call MCP `get_bc_design` (T2) to fetch the design + the current
>    `[:IMPLEMENTED_IN]` mapping. The skill needs both to know which
>    files to AST-extract and to know the `version` to send with
>    `propose_sync`.
> 3. For each file referenced by `implementationFiles[]`, run the
>    language-appropriate extractor:
>    - `*.py`:  `python extractors/python_extract.py <file>`
>    - `*.ts`:  `node extractors/ts_extract.mjs <file>`
>    The extractors emit normalized JSON per element on stdout.
> 4. Aggregate the extracts and call MCP `propose_sync` (T6) with one
>    entry per element you saw in source.
> 5. Render the resulting `diff` to the developer. For every entry in
>    `requiresConfirmation`, ask explicitly — do not assume yes. Rename
>    pairs (entries in `renameCandidates`) need a rename-vs-delete-and-
>    create decision.
> 6. Call MCP `apply_proposal` (T6a) with the confirmed subset. On
>    `status: "conflict"`, fetch via `get_bc_design` again and re-propose
>    **once** before giving up — the design changed underneath us.

## Extractors

Per-language AST extractors ship verbatim under `extractors/`:

- `extractors/python_extract.py` — uses stdlib `ast`.
- `extractors/ts_extract.mjs` — uses `@typescript-eslint/typescript-estree`.

Both emit one JSON document per element to stdout (see [specs/029-robo-spec-skills/contracts/mcp-tools.md](specs/029-robo-spec-skills/contracts/mcp-tools.md) §T6 for the shape).

## What is NOT in scope

- Writing marker comments into developer source code at any phase
  (research R7 explicitly forbids this).
- Applying destructive changes (renames, deletions) without explicit
  developer confirmation (Principle IV).
- Bypassing `propose_sync` to write directly to the graph.
