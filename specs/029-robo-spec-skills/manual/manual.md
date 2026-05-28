---
title: "Robo Spec Skills & MCP Bridge — Phase 1+2+3 E2E Validation Manual"
subtitle: "Feature 029 — install path, classification surface, MCP mount"
author: "Robo Architect team"
date: "2026-05-27"
---

# Purpose

This manual documents the end-to-end smoke test for the **Phase 1 + Phase 2 + Phase 3 (US6)** slice of feature `029-robo-spec-skills` — covering tasks T001 through T019. The slice delivers the foundations that every later user story builds on:

- Backend feature scaffold + dependency wiring (T001..T005)
- Neo4j schema delta for `BoundedContext.classification`, `:ImplementationFile`, `[:IMPLEMENTED_IN]` (T006..T009)
- MCP server mount at `/mcp` (T010)
- Classification HTTP surface E2 / E3 (T011)
- `BoundedContext.classification` exposed on the `/tree` response (T012)
- Verbatim install of the `robo-spec/` skill tree by `POST /api/claude-code/setup-project` (T013, E1)
- Skeleton `SKILL.md` files for `robo-plan`, `robo-tasks`, `robo-implement`, `robo-sync` + extractor stubs (T014..T018)
- Install-integrity check script (T019)

The five user-story phases (US1 through US5 — `/robo-plan` through `/robo-sync`) are deferred to follow-on sessions; their acceptance criteria are intentionally **out of scope** for this manual.

# Pre-flight

| Requirement | Verified by | Notes |
| --- | --- | --- |
| Project venv at `.venv/` | `/Users/uengine/main-robo-arch/robo-architect/.venv/bin/python` exists | Python 3.14, `uv` managed |
| `mcp` Python SDK + `watchfiles` installed | `uv pip install 'mcp>=1.0.0' 'watchfiles>=0.24.0'` | Pinned in `pyproject.toml` |
| Headless Chrome | `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` | Used for Swagger UI screenshot |
| `pandoc` | `/opt/homebrew/bin/pandoc` | Used for `.docx` conversion |
| Port `8765` free | `lsof -nP -iTCP:8765 -sTCP:LISTEN` returns nothing | Chosen to avoid colliding with a dev backend on `:8000` |

Neo4j is **not** required for this smoke — the routes exercised don't actually need a live graph; classification writes against a non-existent BC would return `404 Not Found`, which is correct for an empty database.

# Test plan & results

Five checks, executed in order against a fresh `uvicorn api.main:app` running on `127.0.0.1:8765`.

## Check 1/5 — `/api/robo-spec/health` responds

The simplest proof that the new `api/features/robo_spec/router.py` was registered in `api/main.py`. Returns a static JSON document — no graph involved.

```text
$ curl http://127.0.0.1:8765/api/robo-spec/health
```

```json
{
  "status": "ok",
  "feature": "robo-spec",
  "spec": "029"
}
```

**Result: PASS** — captured at `screenshots/01_health.txt`.

## Check 2/5 — OpenAPI lists the new + extended routes

Hit `/openapi.json` and filter for the three surfaces this slice should have introduced (E1 extension, E2/E3 classification, the new robo-spec prefix).

```text
$ jq -r '.paths | to_entries
       | map(select(.key | test("/api/robo-spec|/classification|/setup-project")))
       | sort_by(.key)
       | .[] | "\(.value | keys | map(ascii_upcase) | join(",")) \(.key)"' openapi.json
```

```text
POST     /api/claude-code/setup-project
GET,PATCH /api/contexts/{bc_id}/classification
GET      /api/robo-spec/health
```

All three expected routes are present. **Result: PASS** — captured at `screenshots/02_routes.txt`.

## Check 3/5 — Swagger UI renders the new tags

Headless Chrome screenshot of `/docs` at `1400×12000` so all FastAPI tags fit on one page. The robo-spec tag and the new `/classification` routes are visible inline.

![Swagger UI — full page (1400×12000)](screenshots/03b_swagger_docs_full.png){ width=100% }

Above-the-fold view at `1600×2400`:

![Swagger UI — above the fold](screenshots/03_swagger_docs.png){ width=100% }

**Result: PASS** — files `screenshots/03_swagger_docs.png` (above-the-fold) and `screenshots/03b_swagger_docs_full.png` (full page).

## Check 4/5 — Verbatim install into a temp workspace

Calls `api.features.claude_code.router._install_robo_spec(<tmp>)` directly. The function does what `POST /api/claude-code/setup-project` does for the robo-spec portion: copy `skills/robo-spec/` byte-for-byte into the workspace, then generate `.claude/robo-project.json` + `.claude/mcp.json`, and return a sha256 checksum of the copied subtree.

```json
{
  "roboSpecInstalled": true,
  "roboSpecChecksum": "sha256:9855e1e0a93a24032171fb78e871c164389e43d1c25acd8fa219f8a6b0d0607e",
  "roboProjectId": "ws-53778d3667b257afaca3d42e7edeae7e"
}
```

Resulting workspace tree:

```text
.claude
.claude/mcp.json
.claude/robo-project.json
.claude/skills
.claude/skills/robo-implement
.claude/skills/robo-implement/SKILL.md
.claude/skills/robo-plan
.claude/skills/robo-plan/SKILL.md
.claude/skills/robo-sync
.claude/skills/robo-sync/SKILL.md
.claude/skills/robo-sync/extractors
.claude/skills/robo-sync/extractors/package.json
.claude/skills/robo-sync/extractors/python_extract.py
.claude/skills/robo-sync/extractors/ts_extract.mjs
.claude/skills/robo-tasks
.claude/skills/robo-tasks/SKILL.md
```

Generated `.claude/robo-project.json`:

```json
{
  "projectId": "ws-53778d3667b257afaca3d42e7edeae7e",
  "backendUrl": "http://localhost:8000",
  "mcpEndpoint": "http://localhost:8000/mcp",
  "createdAt": "2026-05-26T21:59:15.565916+00:00"
}
```

Generated `.claude/mcp.json`:

```json
{
  "mcpServers": {
    "robo-spec": {
      "type": "streamable-http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

Then the install-integrity check script runs the three guarantees mandated by FR-012, SC-006, and research R7:

```text
[check 1/3] diff -r skills/robo-spec/skills <tmp>/.claude/skills
  ok — installed tree is byte-identical to source
[check 2/3] grep for Jinja markers under skills/robo-spec/skills
  ok — no Jinja markers in source
[check 3/3] grep '@robo:' in workspace source (R7 enforcement)
  ok — no @robo: markers in workspace source

PASS: robo-spec install at <tmp> is byte-identical and marker-free.
```

**Result: PASS** — captured at `screenshots/04_install_result.txt`, `screenshots/05_workspace_tree.txt`, `screenshots/06_check_install.txt`. A copy of the installed workspace's `.claude/` subtree is kept under `artifacts/workspace_sample/` for inspection.

This is **quickstart S1 passing** in the canonical sense — the US6 acceptance gate.

## Check 5/5 — MCP transport mount is alive

A live streamable-HTTP MCP transport accepts JSON-RPC POSTs at the mount path; a GET is correctly rejected. What we want to confirm here is the mount itself is registered.

```text
/mcp           -> HTTP 307   (FastAPI trailing-slash redirect — mount exists
                              and points at the MCP sub-app)
/mcp/          -> HTTP 404   (MCP sub-app's own 404 for GET — expected,
                              no JSON-RPC body was POSTed)
/mcp/sse       -> HTTP 404   (no SSE child path under streamable-HTTP)
/mcp/messages  -> HTTP 404
```

The `307` from `/mcp` can only come from FastAPI when `/mcp` is mounted as a sub-application — if `build_mcp_server()` had returned `None`, FastAPI would have returned a generic top-level `404` with no redirect. The MCP transport is therefore constructed at startup and serving requests.

A future US1+ task that actually registers tools (T1..T8 + T6b) will verify tool discovery by POSTing a JSON-RPC `tools/list` request and asserting the expected tools come back.

**Result: PASS** — captured at `screenshots/07_mcp_mount.txt`.

# Summary

| # | Check | Result | Evidence |
| --- | --- | --- | --- |
| 1 | `/api/robo-spec/health` responds | **PASS** | `screenshots/01_health.txt` |
| 2 | OpenAPI lists new + extended routes | **PASS** | `screenshots/02_routes.txt` |
| 3 | Swagger UI renders | **PASS** | `screenshots/03_swagger_docs.png`, `screenshots/03b_swagger_docs_full.png` |
| 4 | Verbatim install + integrity check | **PASS** | `screenshots/04_install_result.txt`, `screenshots/05_workspace_tree.txt`, `screenshots/06_check_install.txt` |
| 5 | MCP transport mount alive | **PASS** | `screenshots/07_mcp_mount.txt` |

**Overall: PASS.** Phase 1 + 2 + 3 is ready for the next session's Phase 4 (US1 — `/robo-plan` end-to-end) work.

# Reproducing this manual

The full procedure is captured as the shell script [`scripts/e2e_phase3.sh`](scripts/e2e_phase3.sh). Re-run with:

```sh
specs/029-robo-spec-skills/manual/scripts/e2e_phase3.sh
```

The script is idempotent: it frees the port, restarts the backend, regenerates every artifact under `screenshots/` and `artifacts/`, and tears down on exit. Override the port with `E2E_PORT=…` if `8765` is already taken by something you care about.

To regenerate the DOCX after editing this `.md`:

```sh
pandoc manual.md -o manual.docx --reference-doc=<optional template> --resource-path=.
```

# What's deferred (not covered by this manual)

| Phase | Story | Surface | Verified by |
| --- | --- | --- | --- |
| 4 | US1 | `/robo-plan` end-to-end | quickstart S2 / S3 / S4 |
| 5 | US2 | `/robo-tasks` + Design-tab progress | quickstart S5 / S13 |
| 6 | US3 | Click-to-open implementation file | quickstart S6 / S7 |
| 7 | US4 | `/robo-implement` constrained loop | quickstart S8 |
| 8 | US5 | `/robo-sync` AST round-trip | quickstart S9 / S10 / S11 |
| 9 | — | Polish + S14 inheritance regression | quickstart S14 |

Each of those phases will get its own e2e manual following the same shape: a runnable script under `manual/scripts/`, captures under `manual/screenshots/`, and a focused `.md` + `.docx` next to this one (e.g., `manual_us1.md`).
