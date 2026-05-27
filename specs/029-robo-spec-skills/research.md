# Phase 0 Research: Robo Spec Skills & MCP Bridge

**Feature**: 029-robo-spec-skills

**Date**: 2026-05-25

This document resolves every NEEDS CLARIFICATION raised by the Technical Context section of `plan.md` and records the supporting findings from the codebase survey.

---

## R1. MCP transport and hosting

**Decision**: Run the MCP server **in-process** with the existing FastAPI app, exposed over **streamable-HTTP** transport. Add a single MCP endpoint mount (e.g., `/mcp`) inside `api/features/robo_spec/router.py` using the official `mcp` Python SDK. The target workspace's `.mcp.json` (shipped under `robo-spec/.claude/mcp.json`) points to that URL.

**Rationale**:

- The backend FastAPI process is already running for the rest of the product; adding a second standalone MCP process would double the runtime surface and split Neo4j connection pools, SmartLogger correlation IDs (Principle VII), and the LLM runtime config (Principle VI) across two processes — exactly the kind of "second source of truth" Principle I forbids at the design level.
- Streamable-HTTP transport (HTTP + SSE for tool output streaming) is the MCP profile that survives behind tunnels (the same tunnels we already use for the Figma plugin per Principle IX) and across remote-Claude-Code deployments. stdio transport would require Claude Code to spawn a local Python process per workspace, which fails the moment the backend lives on a different machine than the workspace.
- Tool calls share the existing `api/platform/observability/` correlation-ID middleware automatically when mounted as a sub-app, satisfying Principle VII without extra plumbing.

**Alternatives considered**:

- **stdio MCP via a launcher script copied into the workspace** — rejected: cannot reach a remote backend, and creates a third place (after backend HTTP + WebSocket) where Robo Architect speaks to the outside world.
- **Re-implement the bridge as a normal HTTP API and call it from a slash-command bash hook** — rejected: throws away MCP's tool-discovery, schema validation, and Claude-Code-native error surfacing that the user explicitly asked for ("mcp 가 그 역할을 한다").

---

## R2. Where `/robo-spec` lives and how it is copied verbatim

**Decision**: Create a new directory `robo-spec/` at the repository root with the structure below, and copy it **with `shutil.copytree` (or equivalent verbatim copy)** into the target workspace as part of the existing `POST /api/claude-code/setup-project` flow. **No Jinja rendering** is applied to anything under `robo-spec/`.

```text
robo-spec/
└── .claude/
    ├── skills/
    │   ├── robo-plan/SKILL.md
    │   ├── robo-tasks/SKILL.md
    │   ├── robo-implement/SKILL.md
    │   └── robo-sync/SKILL.md
    └── mcp.json
```

**Rationale**:

- `api/features/prd_generation/routes/prd_export.py:109` currently *generates* skills via Jinja (`generate_claude_skill_ddd_principles`, etc.). Reusing that path for robo-* skills would re-introduce the per-install drift the user explicitly rejected (FR-012, SC-006).
- `setup_project()` at `api/features/claude_code/router.py:148` already targets the workspace as a directory — a verbatim recursive copy from `robo-spec/` is a one-line addition and is byte-checkable against the source tree.
- Putting the directory at the repo root (not inside `api/features/`) makes the "source of truth for skill text" obvious to skill authors and prevents accidental Python-import coupling.

**Alternatives considered**:

- **Ship robo-* skills inside `api/features/prd_generation/`** — rejected: places skill markdown next to Jinja templates and almost guarantees a future contributor will "just template it".
- **Vendor the skills as a separate package** — rejected: overkill for v1; we own both sides and want one-edit-one-deploy.

---

## R3. Workspace path discovery (for code-link and "open file in editor")

**Decision**: Reuse the existing per-session workspace path established by spec 021 (`claude-code-ide-workspace`). The MCP server resolves the calling workspace's path by reading the per-project `WorkspaceState` keyed by the project ID that the MCP client (the skill) passes in every call. The skill knows its project ID from a small file written at install time (`robo-spec/.claude/robo-project.json`, populated by `setup-project` from the requesting Robo Architect project).

**Rationale**:

- `App.vue:25` already holds a `claudeCodeWorkdir` ref, and `setup-project` already accepts a target workspace path, so the linkage exists. We just persist it back into the workspace.
- Persisting project ID in the workspace (instead of asking the user every time) is what makes "click an Aggregate in Design tab → open file" work without re-pairing on every session.

**Alternatives considered**:

- **Re-pair on every Claude Code session via a chooser dialog** — rejected: violates the "one developer loop" feel the user is after.
- **Encode project ID into the MCP URL** — rejected: leaks routing into transport and breaks tunnel rotation.

---

## R4. BC `core | supporting` classification

**Decision**: Add an optional `classification: "core" | "supporting"` property to the `BoundedContext` node label in Neo4j. Document it in `docs/cypher/schema/03_node_types.cypher` before any code that emits it ships (Principle I + Development Workflow rule). Default behavior when the property is missing: `/robo-plan` asks the developer and, on answer, persists the chosen classification back to Robo Architect via MCP (`set_bc_classification` tool) so the question is never re-asked.

**Rationale**:

- The codebase survey confirmed there is no existing core/supporting flag — `domainType` is unrelated. Adding a single optional string property is the minimum-invasive shape and keeps existing queries unaffected.
- Persisting the developer's first answer back into the graph respects Principle I (graph is the single source of truth for what the BC's classification *is*).

**Alternatives considered**:

- **Re-derive classification from heuristics** (e.g., aggregate count) — rejected: opaque, brittle, and would silently re-classify across reads.
- **Keep the answer local in `plan.md`** — rejected: same BC may be planned twice (different developers, different repos) and we want the answer to converge in Robo Architect.

---

## R5. Element-to-file mapping (forward and reverse navigation)

**Decision**: Store source mapping **exclusively inside Robo Architect's Neo4j ontology** via a new node label `:ImplementationFile` and a new relationship `[:IMPLEMENTED_IN]` from design elements to implementation files. The relationship is N:M (one element may have multiple files; one file may back multiple elements).

```cypher
(:Aggregate|:Command|:Event|:ReadModel)-[:IMPLEMENTED_IN]->(:ImplementationFile {
  projectId,            // routing key (workspace-agnostic; same project may be linked to multiple workspaces)
  path,                 // workspace-relative path
  role,                 // 'primary' | 'interface-adapter' | 'infrastructure' | 'test' | 'other'
  createdAt,
  lastSeenAt
})
```

**No workspace-local mapping file** is maintained. Every read of "which file backs this element" goes through MCP → graph. Every write (`/robo-implement` after scaffolding, `/robo-sync` after detecting moved files) goes through MCP back to the graph.

When the developer clicks a node in the Design tab, the frontend calls a new endpoint that resolves `(:Element)-[:IMPLEMENTED_IN]->(:ImplementationFile)` and asks the workspace bridge to open the file. Multiple files per element are presented as a picker (FR-009 / US3 scenario 3); zero files renders the "not implemented yet" affordance.

**Rationale**:

- Principle I (graph is the single source of truth) applies to *runtime relationships between design and code* just as it does to the design itself. A workspace-local mapping file would be a parallel store that goes stale the moment the developer moves a file outside `/robo-sync`'s view, or links the same Robo Architect project to a second workspace.
- Keeping the mapping in the graph lets multiple linked workspaces (and the Design tab itself) read the same truth without any reconciliation step.
- Resetting the design (`/api/graph/clear` etc.) wipes the `:ImplementationFile` nodes along with the elements that point at them — there is no orphaned local file to clean up.

**Alternatives considered**:

- **Per-feature `.robo-link.json` in the workspace** *(rejected; this was the original proposal)* — created a second source of truth for mapping, broke down whenever the developer moved a file outside the skill flow, and required reconciliation logic for multi-workspace projects.
- **Store file paths as a list property on element nodes** — rejected: list properties query poorly in Neo4j and cannot easily carry the `role` discriminator. A dedicated node is cheap and queryable.
- **Re-derive on every click via path conventions** — rejected (unchanged from original analysis): cannot represent overrides or multi-file elements.

---

## R6. Progress reflection (`tasks.md` ↔ Design tab)

**Decision**: Use a **file-watcher inside the backend** (`watchfiles`) scoped to `<workspace>/specs/**/tasks.md` for each linked project. On change, the backend reparses the tasks.md, diffs checkbox states against the link manifest, and pushes the per-element progress over the existing **SSE** channel (matches Principle III). The Design tab subscribes and renders per-node "todo / in-progress / done / blocked" badges.

**Rationale**:

- A file watcher gives us within-5s latency (SC-003) without polling.
- Reusing SSE keeps a single push channel between backend and frontend (the same one Principle III already endorses for ingestion/LLM progress).
- Parsing markdown checkboxes is trivial (`- [x] ...` / `- [ ] ...`).

**Alternatives considered**:

- **Have the skill PATCH the backend every time it ticks a box** — rejected: doesn't catch *manual* edits to `tasks.md` (the user explicitly wants those reflected) and creates a second channel that has to stay coherent with on-disk state.
- **Poll tasks.md every N seconds** — rejected: either too slow (>5s) or wasteful CPU, and `watchfiles` is already used elsewhere in the Python ecosystem.

---

## R7. `/robo-sync` diff strategy

**Decision**: `/robo-sync` uses **full AST extraction** of the files reached via `[:IMPLEMENTED_IN]` (R5), with **no marker comments** written into source at codegen time. v1 supports two languages — **Python (stdlib `ast`)** and **TypeScript (`@typescript-eslint/typescript-estree` driven by a small Node helper)** — chosen to match the project's own stacks and to keep the v1 parser surface small. The AST extractors are shipped verbatim under `robo-spec/.claude/skills/robo-sync/extractors/` and run locally inside the developer's workspace via Claude Code's Bash tool — they do not ship in the backend, so adding a new language later does not require a backend release.

The flow:

1. `/robo-sync` calls MCP `lookup_implementation_files` (folded into T2; see contract) to learn which files back which elements.
2. The skill runs the language-appropriate extractor over each file and emits a normalized structural shape per element (the element's properties, the event's payload fields, the command's parameters — names and types only, free-form code ignored).
3. The skill calls MCP `propose_sync` with the structural extract.
4. The MCP server diffs the extract against the live graph and returns a proposal listing `added` / `modified` / `removed` per element plus the subset that requires explicit confirmation (renames, deletions) — Principle IV.
5. The developer confirms; the skill calls `apply_proposal`; the server applies through Robo Architect's existing mutation pathways. Concurrent design edits surface as `CONFLICT` (T6a).

**Disambiguation for renames** (the one case full-AST can't decide on its own): when a removal and an addition look like a rename candidate (same type, similar name distance), the proposal flags them as a *candidate rename pair* in `requiresConfirmation` and asks the developer to confirm rename-vs-delete-and-create. The MCP server may optionally use the configured LLM runtime to pre-rank candidate pairs by structural and lexical similarity, but the **final call always goes to the developer** (Principle IV). LLM ranking is a UX nicety, not a source of truth.

**Rationale**:

- Source code is the developer's; writing magic comments into it at codegen time is invasive, hostile to formatters, and creates a parallel mapping that has to stay in sync with the graph — exactly the trap Principle I exists to prevent.
- Full AST extraction recovers element structure from the *actual* code at sync time, so it reflects whatever the developer last edited (no marker rot).
- Per-language extractors are small and run in the workspace via Bash — the backend stays language-agnostic and parser-free.
- LLM is reserved for ranking ambiguous renames; it never decides what to apply.

**Alternatives considered**:

- **`@robo:aggregate=...` marker comments at codegen time** *(rejected; this was the original proposal)* — invasive, formatter-fragile, creates a second mapping (in source comments) alongside the graph, and rots silently when the developer edits without running `/robo-sync`.
- **Pure-LLM diff** — rejected as the primary path: non-deterministic, expensive, and inverts Principle IV (the LLM would effectively decide what changed). Kept as an optional ranking helper for ambiguous rename pairs only.
- **Decorator-based annotation** — rejected: same coupling problem as marker comments, and TS decorators are still pre-stage-3 in many setups.

---

## R8. Drift detection (FR-013)

**Decision**: Drift detection is **stateless** — there is no locally-stored fingerprint. On the first MCP call inside every robo-* command, the skill calls `compute_drift` with the set of element names + element IDs it currently references in the workspace's `tasks.md` (and, where applicable, `plan.md`). The MCP server resolves each referenced ID against the live graph and reports:

- **renamed** — ID exists, current name differs from the name referenced in `tasks.md`
- **deleted** — ID is referenced locally but no longer exists in the graph
- **reclassified** — BC classification changed since `plan.md`'s architecture section was rendered
- **added** — informational: new design elements exist that the local `tasks.md` doesn't yet cover (not blocking)

The first three categories block the command and surface a clear report; the developer must regenerate `tasks.md` (and/or `plan.md`) before proceeding. `added` is non-blocking but the skill suggests re-running `/robo-tasks`.

**Rationale**:

- Pulling drift from "what the live graph says now" vs. "what `tasks.md` references" makes the local side trivially honest — there is no hidden cache that could itself be stale, and no separate fingerprint format to keep in sync with anything.
- This matches the user's "source mapping in ontology only" rule: the only persistent state is in the graph, and drift is computed at call time.

**Alternatives considered**:

- **Local fingerprint stored in `.robo-link.json`** *(rejected; was the original proposal)* — added a parallel store and added the obvious "what if the fingerprint file gets out of sync with `tasks.md`?" failure mode.
- **Server-side fingerprint stored on a `:WorkspaceLink` node** — rejected for v1: adds bookkeeping without much benefit when we already version every element and can compare names at request time. May be revisited if request-time drift checks become too expensive at scale.
- **Push notifications from Robo Architect** — rejected (unchanged): workspace may be offline; pull-on-next-use is sufficient.

---

## R9. New endpoints + Swagger discipline

**Decision**: All new HTTP routes live under `/api/robo-spec/` and `/api/contexts/{bc_id}/classification` (the one cross-feature touch — adding the new field write path). Every route gets a Pydantic request/response model and shows in `/docs` per the constitution's Development Workflow rule.

**Rationale**: Constitutional requirement; non-optional.

---

## R10. Frontend feature layout

**Decision**: Add `frontend/src/features/robo_spec/` mirroring the backend feature (Principle V). Inside it:

- `ProgressBadge.vue` — per-node badge component imported by `EventModelingPanel.vue` and `InspectorPanel.vue`.
- `useRoboProgressStream.ts` — composable that subscribes to the SSE channel and exposes a reactive map `elementId → status`.
- `openImplFile.ts` — small helper that calls the new endpoint to open a file in the workspace editor, and surfaces the "not implemented yet" affordance when the path is absent.

Cross-feature edits in `EventModelingPanel.vue` and `InspectorPanel.vue` go through the platform/composables — no direct imports from one feature into another (Principle V).

**Rationale**: Constitutional, plus it keeps the design-tab changes diff-reviewable in isolation.

---

## R11. Skill inheritance — how `/robo-plan`, `/robo-tasks`, `/robo-implement` extend speckit *without* Jinja

**Decision**: Each robo-* skill is a **thin delegation-and-override `SKILL.md`** that explicitly tells Claude Code to (1) read the upstream `speckit-{plan|tasks|implement}/SKILL.md` already present in the workspace as the default behavior, and (2) apply a numbered list of overrides on top, keyed to anchors in the upstream document. No Jinja, no build-time merge, no patching — the override file is the entire diff, expressed in prose Claude Code can interpret directly. `/robo-sync` has no speckit counterpart and is fully self-contained.

The frontmatter of each thin-override file declares:

```yaml
---
name: robo-plan
description: Robo Architect-aware planning — inherits speckit-plan, replaces local spec source with MCP, drops data-model.md and contracts/, picks architecture by BC classification.
extends: speckit-plan          # documentary; Claude Code does not interpret this natively
requires-speckit: ">=0.8.13, <0.9.0"
user-invocable: true
---
```

And the body opens with a short delegation header, e.g. (this is the shape, not the exact final text):

```markdown
## Inheritance

This skill **inherits** `/speckit-plan`. Before executing anything below,
read `.claude/skills/speckit-plan/SKILL.md` and treat its Outline + Phases
as the default workflow. Apply the **Overrides** in the next section on top.

## Overrides

1. **Skip Outline step 2's `setup-plan.sh` step** for spec loading.
   Instead, resolve the user-supplied argument to a BC via MCP
   `resolve_design_element` and call `get_bc_design` for the full slice.
2. **Replace Phase 1 step 1** (`data-model.md`) with: do nothing.
   The data model is the Robo Architect graph; we never write `data-model.md`.
3. **Replace Phase 1 step 2** (`contracts/`) with: do nothing.
   Contracts are the Robo Architect commands/events; we never write `contracts/`.
4. **Replace Phase 1 step 3's architecture template** with:
   - if `BoundedContext.classification == "core"`, use clean architecture
     (entities / use cases / interface adapters / frameworks-and-drivers);
   - if `"supporting"`, use speckit's default plan layout unchanged;
   - if absent, ask the developer once, then call MCP `set_bc_classification`.
5. **Add a final step**: call MCP `register_implementation_files` with `mode="merge"`
   and empty `files: []` for every element, so the Design tab can render
   "not implemented yet" affordances immediately.
```

**Rationale**:

- **Verbatim copy is preserved** (FR-012): the thin override file is itself the source of truth in `robo-spec/` and is copied byte-for-byte. There is no rendering step at install time.
- **Speckit upstream stays the single source of base workflow** — when speckit ships a fix to its `plan` skill, the next install picks it up automatically; the robo-* overrides only re-apply the same patches on top.
- **The mechanism is documentation, not code** — there is no inheritance runtime to maintain. Claude Code reads two markdown files; the LLM applies the directives. This is the same shape as the existing `extension hooks` pattern in speckit, just at the skill-body level.

**Risks and mitigations**:

- *Risk:* speckit refactors its numbered steps and the override anchors silently stop matching → robo-plan reverts to upstream behavior or produces a half-merged plan.
  - *Mitigation 1:* `requires-speckit` version range in frontmatter — the robo-* skill refuses to run (or warns) when the installed speckit version is outside the tested range.
  - *Mitigation 2:* a manual smoke step in `quickstart.md` (S14) re-runs the inheritance flow after every speckit upgrade.
  - *Mitigation 3:* anchors in the override file reference both the **step number** and a **distinctive verbatim phrase** from the upstream text, so a renumbering alone does not break the match (the LLM falls back to the phrase).
- *Risk:* an LLM interpreter that does not follow the delegation header → it executes only the override section, missing the base workflow.
  - *Mitigation:* the delegation header is the **first** prose in the body, before any "Outline" / "Steps" headings — the LLM cannot reach the overrides without reading the inheritance instruction.

**Alternatives considered**:

- **Build-time merge (Jinja / a small Python script that overlays a patch)** — rejected: violates FR-012 (verbatim copy) and re-introduces the per-install drift the user explicitly forbade.
- **Self-contained `robo-*/SKILL.md` that copies the upstream text** — rejected: speckit upstream fixes never propagate; we own a full fork instead of an override, and "speckit-plan vs robo-plan" diverge silently.
- **A new `extends:` directive interpreted by Claude Code itself** — out of scope: requires upstream Claude Code work; cannot be shipped by this feature.
- **Inheritance via MCP** (the MCP server returns "the speckit-plan workflow with these overrides applied" as text) — rejected: makes the MCP server a build tool, and ties skill text to backend availability at command time.

**Scope clarification**:

- Inheritance covers **`/robo-plan`, `/robo-tasks`, `/robo-implement`** only — these have direct speckit counterparts.
- `/robo-sync` has no upstream counterpart and is a self-contained SKILL.md.
- Any other future `/robo-*` skill that mirrors a speckit skill MUST follow the same delegation-and-override shape so we keep one inheritance pattern across the suite.

---

## Unresolved items

None. All NEEDS CLARIFICATION markers from the Technical Context have been resolved above. Items deliberately deferred to `/speckit-tasks` (not to research): exact override anchor phrases for each upstream speckit version supported; whether to support a third language (Java) in v1.5 for `/robo-sync`'s AST extraction.
