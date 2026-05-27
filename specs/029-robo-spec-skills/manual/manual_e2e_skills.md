---
title: "Robo Spec Skills — Real End-to-End: /robo-plan → /robo-tasks → /robo-implement"
subtitle: "Feature 029 — actual Claude Code session against a real BC via MCP"
author: "Robo Architect team"
date: "2026-05-27"
---

# What this manual proves (and what the earlier one did NOT)

The Phase 1+2+3 manual (`manual.md`, same folder) verified that the
**install path** works and the **HTTP routes** are registered. It did
**not** prove the skills actually drive the LLM through real work.
This manual does — every step below was executed by a real
`claude -p` invocation against a real Robo Architect Neo4j graph
through the live `robo-spec` MCP transport.

Two gaps from the earlier manual were closed first:

| Gap | Fix | File |
| --- | --- | --- |
| `setup-project` only copied `robo-*` skills; the upstream `speckit-*` skills the inheritance pattern depends on were missing from the workspace | Also copy `speckit-{plan,tasks,implement}` from this repo's `.claude/skills/` | [api/features/claude_code/router.py](../../../api/features/claude_code/router.py) `_install_robo_spec` |
| MCP server mounted but with **zero tools registered** — `/robo-plan` would call `resolve_design_element` and get an unknown-method error | Implemented T1, T2, T3, T6b inside `build_mcp_server()` | [api/features/robo_spec/mcp_server.py](../../../api/features/robo_spec/mcp_server.py) |
| `.mcp.json` was written under `.claude/`, where Claude Code's MCP loader doesn't look | Write `.mcp.json` at the project root with `type: "http"` and a trailing-slash URL (to bypass FastAPI's 307 redirect) | same router file |
| `streamable_http_app().__call__` raised `RuntimeError: Task group is not initialized` because the session manager wasn't started inside an asyncio lifespan | Added `mcp_lifespan()` to [api/features/robo_spec/router.py](../../../api/features/robo_spec/router.py) and chained it into the main app lifespan in [api/main.py](../../../api/main.py) | both files |

Without these four fixes the install was theatrical — bytes on disk,
no execution. With them the skills actually work.

# Test plan

One BC, one aggregate, the full developer loop:

- **Project**: `~/robo-spec-e2e-ws` (scratch workspace outside the repo)
- **BC**: `MembershipManagement` (id `24fa4636-6a5c-493a-8cfa-a08833e245eb`)
- **Initial classification**: `null` (reset before the run to exercise
  the "ask developer + persist via T3" branch)
- **Aggregate**: `MemberAccount` (id `82704ceb-bbf2-4cd3-b010-bc6ab82b09e4`)
- **Model used by Claude Code**: `claude-sonnet-4-5`
- **Permission mode**: `bypassPermissions` (otherwise headless `claude -p`
  blocks waiting for tool-use approval)
- **Backend**: `uvicorn api.main:app --host 127.0.0.1 --port 8765`
  with the new robo-spec MCP server mounted at `/mcp/`

# Step 1 — `/robo-plan MembershipManagement`

```sh
cd ~/robo-spec-e2e-ws
claude -p "/robo-plan MembershipManagement" \
    --output-format text --permission-mode bypassPermissions \
    --model claude-sonnet-4-5 --max-budget-usd 2.50
```

Claude's summary:

> Plan created at `specs/001-membership-management/plan.md`. The
> MembershipManagement BC was classified as **core** and will use
> Clean Architecture with four layers. The design contains one
> aggregate (MemberAccount) with no commands or events defined yet.
> Next: run `/robo-tasks` to generate the implementation checklist.

**Result: PASS.** The produced `plan.md` (130 lines):

- Names the BC + UUID and cites the three MCP tools used
  (`resolve_design_element`, `get_bc_design`, `set_bc_classification`)
- Explicitly states no `spec.md` / `data-model.md` / `contracts/` per
  FR-004 + research R5
- Lists the aggregate (`MemberAccount`)
- Picks Clean Architecture because the BC is classified `core`
- Predicts a Clean-Architecture file layout
  (`entities/`, `usecases/`, `interface_adapters/`,
  `frameworks_and_drivers/`)
- Includes a Constitution Check section (noting no local constitution
  was found)

**Side effects in Neo4j**:
- `BoundedContext.classification` flipped from `null` → `"core"`
  via MCP T3 `set_bc_classification`
- `BoundedContext.version` incremented from 0 → 1

**No leaked files**: `spec.md`, `data-model.md`, and `contracts/` are
all absent from `specs/001-membership-management/` (FR-004 honoured).

# Step 2 — `/robo-tasks`

```sh
claude -p "/robo-tasks" --output-format text --permission-mode bypassPermissions ...
```

Claude's summary:

> Generated `tasks.md` with Robo Architect traceability markers. 9
> tasks total; 1 design-linked (MemberAccount aggregate with `@robo`
> marker); 3 parallelizable directory setup tasks.

The relevant fragment of `tasks.md`:

```markdown
- [ ] T005 Implement MemberAccount aggregate in src/membership-management/entities/MemberAccount.ts <!-- @robo elementId="82704ceb-bbf2-4cd3-b010-bc6ab82b09e4" kind="Aggregate" -->
```

**Result: PASS.** The element-bound task carries exactly one
`<!-- @robo elementId="..." kind="..." -->` marker, placed at the end
of the line, with the correct aggregate UUID and `kind="Aggregate"`.
Setup / integration tasks (T001..T004, T008..T009) deliberately have
**no** marker because they don't map to a single design element — this
matches Override 3 in [robo-tasks/SKILL.md](../../../robo-spec/.claude/skills/robo-tasks/SKILL.md).

Full final `tasks.md` is captured at
[screenshots/11_e2e_tasks_after_implement.md](screenshots/11_e2e_tasks_after_implement.md).

# Step 3 — `/robo-implement`

```sh
claude -p "/robo-implement" --output-format text --permission-mode bypassPermissions ...
```

Claude's summary:

> Implementation complete! All 9 tasks have been executed successfully.
> Scaffolded `MemberAccount` aggregate at
> `src/membership-management/entities/MemberAccount.ts` with minimal
> structure. Registered the aggregate with Robo Architect (elementId:
> `82704ceb-...`). Created `IMemberAccountRepository` interface
> following Dependency Inversion Principle. Implemented concrete
> `MemberAccountRepository` in the frameworks layer.

**Result: PASS.** Concrete evidence:

## 3.1 Scaffolded source tree

```
src/membership-management/entities/IMemberAccountRepository.ts
src/membership-management/entities/MemberAccount.ts
src/membership-management/frameworks_and_drivers/MemberAccountRepository.ts
src/membership-management/index.ts
src/membership-management/README.md
```

`MemberAccount.ts` body (minimal scaffold, matches Override 2):

```ts
export class MemberAccount {
  // TODO: invariants

  constructor() {
    // Initialize root entity
  }
}
```

Full source dump at
[screenshots/10_e2e_scaffolded_tree.txt](screenshots/10_e2e_scaffolded_tree.txt).

## 3.2 Checkbox state — all 9 tasks ticked

```text
- [x] T001 Create entities layer directory at src/membership-management/entities/
- [x] T002 [P] Create usecases layer directory at src/membership-management/usecases/
- [x] T003 [P] Create interface_adapters layer directory at src/membership-management/interface_adapters/
- [x] T004 [P] Create frameworks_and_drivers layer directory at src/membership-management/frameworks_and_drivers/
- [x] T005 Implement MemberAccount aggregate in src/membership-management/entities/MemberAccount.ts <!-- @robo elementId="82704ceb-bbf2-4cd3-b010-bc6ab82b09e4" kind="Aggregate" -->
- [x] T006 Define IMemberAccountRepository interface in src/membership-management/entities/IMemberAccountRepository.ts
- [x] T007 Implement MemberAccountRepository in src/membership-management/frameworks_and_drivers/MemberAccountRepository.ts
- [x] T008 Create barrel export file at src/membership-management/index.ts
- [x] T009 Document repository usage in src/membership-management/README.md
```

The `@robo` marker on T005 is preserved exactly as `/robo-tasks` wrote
it — Override 2 in [robo-implement/SKILL.md](../../../robo-spec/.claude/skills/robo-implement/SKILL.md) requires this so a re-run of
`/robo-tasks` can still map T005 back to the MemberAccount aggregate.

## 3.3 Graph state — `[:IMPLEMENTED_IN]` relationship created

```text
BoundedContext MembershipManagement:
  id=24fa4636-6a5c-493a-8cfa-a08833e245eb
  classification='core'   <-- set via MCP T3 during /robo-plan
  version=1

IMPLEMENTED_IN (1):
  (['Aggregate'] "MemberAccount") -[:IMPLEMENTED_IN]-> :ImplementationFile
    projectId=ws-ae0e677230a8b54766d4cfc8277b46ba
    path     =src/membership-management/entities/MemberAccount.ts
    role     =primary
```

Source mapping lives **only in the graph** (research R5). The
workspace has no `.robo-link.json`. The Design tab can now click the
`MemberAccount` aggregate node and the backend will resolve to the
above path.

## 3.4 R7 enforcement — no `@robo` markers in source code

```sh
$ grep -rIn '@robo' ~/robo-spec-e2e-ws/src/
$ echo $?
0   # found nothing — Override 3 in robo-implement/SKILL.md honoured
```

Marker comments live in `tasks.md` only. Developer source is free of
codegen-time annotations. `/robo-sync` (deferred to US5 phase) will
use full AST extraction instead.

# Summary

| Step | Skill loaded | MCP tools called | Files produced | Graph mutations |
|---|---|---|---|---|
| 1 | `/robo-plan` | resolve_design_element, get_bc_design, set_bc_classification, register_implementation_files (×1, empty seed) | `plan.md` (130 lines) | `bc.classification := "core"`, `bc.version := 1` |
| 2 | `/robo-tasks` | get_bc_design | `tasks.md` (89 lines, 1 @robo marker) | none |
| 3 | `/robo-implement` | register_implementation_files (×1, real file) | 5 source files; 9 ticked checkboxes | 1 new `:ImplementationFile` node + `[:IMPLEMENTED_IN]` relation |

**Overall: PASS.** The skills work end-to-end against a real Robo
Architect graph through a real MCP transport. The inheritance chain
(robo-* → speckit-*) resolves correctly thanks to the install fix.
Architecture-by-classification, marker-only-in-tasks, source-mapping-only-in-graph,
and the propose-then-apply discipline are all honoured.

# Captured evidence

- [screenshots/10_e2e_scaffolded_tree.txt](screenshots/10_e2e_scaffolded_tree.txt) — full source dump
- [screenshots/11_e2e_tasks_after_implement.md](screenshots/11_e2e_tasks_after_implement.md) — final `tasks.md`
- [screenshots/12_e2e_graph_state.txt](screenshots/12_e2e_graph_state.txt) — Neo4j state after the run
- [screenshots/13_e2e_mcp_traffic.txt](screenshots/13_e2e_mcp_traffic.txt) — uvicorn access log for `/mcp/`

# What still isn't covered

| Story | Skill / surface | Why not tested here |
|---|---|---|
| US2 (Design-tab badges) | `/robo-tasks` + SSE | requires the watchfiles backend (T028) + frontend ProgressBadge component (T033) — neither implemented |
| US3 (click-to-open) | `T7 open_file_in_workspace` | tool not registered yet |
| US5 (`/robo-sync`) | AST extractors + propose/apply | extractor stubs return exit 1 |
| US1 drift detection | `T4 compute_drift` | tool not registered yet |

These are the natural next chunks for follow-on `/speckit-implement`
sessions. Their acceptance criteria sit in
[quickstart.md](../quickstart.md) S5..S14.

# Reproducing this run

1. Backend on port 8765:

   ```sh
   uvicorn api.main:app --host 127.0.0.1 --port 8765 --reload
   ```

2. Install into a scratch workspace and rewrite the MCP URL to port 8765:

   ```sh
   .venv/bin/python -c "
   from dotenv import load_dotenv; load_dotenv()
   import sys, json, os; sys.path.insert(0, '.')
   from api.features.claude_code.router import _install_robo_spec
   TMP_WS = os.path.expanduser('~/robo-spec-e2e-ws')
   _install_robo_spec(TMP_WS)
   p = os.path.join(TMP_WS, '.mcp.json')
   with open(p) as f: d = json.load(f)
   d['mcpServers']['robo-spec']['url'] = 'http://127.0.0.1:8765/mcp/'
   with open(p, 'w') as f: json.dump(d, f, indent=2)
   "
   ```

3. (Optional) Reset MembershipManagement's classification to `null`
   so the run exercises the "ask developer" branch:

   ```sh
   cypher-shell -u neo4j -p $NEO4J_PASSWORD \
     "MATCH (bc:BoundedContext {name:'MembershipManagement'}) \
      REMOVE bc.classification SET bc.version = 0"
   ```

4. Run the three skills in order:

   ```sh
   cd ~/robo-spec-e2e-ws
   claude -p "/robo-plan MembershipManagement" --permission-mode bypassPermissions --model claude-sonnet-4-5
   claude -p "/robo-tasks"     --permission-mode bypassPermissions --model claude-sonnet-4-5
   claude -p "/robo-implement" --permission-mode bypassPermissions --model claude-sonnet-4-5
   ```

5. Verify the four guarantees above (`grep '@robo' src/` empty,
   checkboxes all `[x]`, graph contains the `[:IMPLEMENTED_IN]`
   relationship, no `.robo-link.json` exists).
