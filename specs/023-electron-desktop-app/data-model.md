# Phase 1 Data Model: Robo-Architect Desktop Application Packaging

**Feature**: `023-electron-desktop-app` | **Date**: 2026-05-11

## Scope statement (read first)

This feature introduces **no Neo4j schema changes** and **no new Pydantic API request/response models**. The graph remains the single source of truth (Constitution I); `docs/cypher/schema/*.cypher` is untouched; the FastAPI backend is bundled as-is. The only new "data" is **Electron-side state**: a small persisted settings file, transient runtime state held in the main process, and a list of which secrets live in the OS secure store. These are TypeScript shapes in `desktop/src/shared/`, never persisted to Neo4j, never touched by the backend.

---

## Persisted: `DesktopSettings`

Stored as a single JSON file at `<userData>/settings.json`. Non-secret only — secret *values* live in the OS secure store (see `SecretRef`); this file holds at most non-secret identifiers (URIs, usernames, provider/model names).

| Field | Type | Default | Notes / validation |
|-------|------|---------|--------------------|
| `schemaVersion` | `number` | `1` | Bumped if the settings shape changes; main migrates forward on read. |
| `dataSource` | `"bundled" \| "external"` | `"bundled"` | Which Neo4j the backend points at. Switching is allowed; never deletes either side's data; renderer warns the user (FR-011). |
| `externalNeo4j` | `{ uri: string; user: string; database: string } \| null` | `null` | Required & validated when `dataSource === "external"`. `uri` must be a `bolt://`/`neo4j://`(+s variants) URL. Password is **not** here — see `SecretRef("neo4j.password")`. Connection is verified via `settings:testNeo4jConnection` before this is persisted (FR-010). |
| `dataDir` | `string \| null` | `null` (→ resolves to `app.getPath('userData')`) | Overridable if the default isn't writable or the user picks another location (FR-009). Holds `neo4j/`, `logs/`, `settings.json`. |
| `llm` | `{ provider: "openai" \| "anthropic" \| "google"; model: string }` | from `.env.example` defaults (`openai` / `gpt-4.1-2025-04-14`) | Mapped to backend env `LLM_PROVIDER` / `LLM_MODEL`. Keys are `SecretRef`s, not here. Constitution VI: never hardcoded, always overridable. |
| `update` | `{ autoCheck: boolean; lastCheckedAt: string \| null }` | `{ autoCheck: true, lastCheckedAt: null }` | `autoCheck` gates the periodic update check; `lastCheckedAt` is informational. |
| `window` | `{ bounds: Rect \| null; maximized: boolean }` | `{ bounds: null, maximized: false }` | Restored on next launch. Pure UX, no product impact. |
| `lastPorts` | `{ backend: number \| null; bolt: number \| null }` | `{ backend: null, bolt: null }` | Hint for the next launch (still re-verified free; FR-018). Informational only. |

**Lifecycle**: created on first launch with defaults → read at startup, migrated by `schemaVersion` → written on any change via `settings:set` (atomic write: temp file + rename). Corrupt/unreadable file → main backs it up to `settings.json.bak` and recreates defaults (never blocks launch).

---

## Transient: `RuntimeState` (main process, exposed read-only to renderer)

Not persisted. Reconstructed every launch. Surfaced to the renderer via `app:getRuntimeState` and kept fresh via `app:onBackendStatus` pushes.

| Field | Type | Notes |
|-------|------|-------|
| `appVersion` | `string` | From `package.json` / build metadata. |
| `backendPort` | `number \| null` | The free port uvicorn was launched on; `null` until ready. The renderer derives its API/SSE/WS base URL from this. |
| `boltPort` | `number \| null` | The free Bolt port the bundled Neo4j was launched on; `null` in external mode or until ready. |
| `backendPid` / `neo4jPid` | `number \| null` | For lifecycle management & log diagnostics. |
| `status` | `"initializing" \| "starting-db" \| "starting-backend" \| "ready" \| "backend-crashed" \| "db-crashed" \| "restarting" \| "fatal"` | Drives the renderer's splash / banners. `ready` ⇒ window is interactive (FR-005). `*-crashed` ⇒ recoverable banner with Retry (FR-017). `fatal` ⇒ unrecoverable error screen with "Reveal logs". |
| `dataSource` | `"bundled" \| "external"` | Echo of the effective setting, so the renderer can label which dataset is in view (FR-011). |
| `dataDir` | `string` | The resolved, writable data directory in use (FR-009). |
| `updateState` | `"idle" \| "checking" \| "available" \| "downloading" \| "ready-to-install" \| "error"` | Drives the update notification UI; `available`/`ready-to-install` are non-blocking prompts (FR-012/FR-013). |

**State transitions (status)**:
`initializing → starting-db → starting-backend → ready`
`ready → backend-crashed → restarting → ready` (auto, ≤ N quick retries) or `ready → backend-crashed → (user Retry) → restarting → ready`
`(any) → fatal` when retries are exhausted or a precondition can't be met (e.g. no writable data dir and user cancels the picker). Neo4j has the analogous `db-crashed` path.

---

## Reference list: `SecretRef`

Not a stored object — a documented enumeration of which secret keys the app reads/writes from the OS secure store (`safeStorage`, `keytar` fallback). Each is referenced by a stable string id; the *value* never appears in `settings.json`, logs, or git.

| Secret id | Maps to backend env var | Set via | Required when |
|-----------|------------------------|---------|---------------|
| `neo4j.password` | `NEO4J_PASSWORD` | Settings UI (external mode) | `dataSource === "external"`. In bundled mode the password is generated locally by the app on first run and also stored here. |
| `llm.openai.apiKey` | `OPENAI_API_KEY` | Settings UI | `llm.provider === "openai"` and the user uses LLM features. |
| `llm.anthropic.apiKey` | `ANTHROPIC_API_KEY` | Settings UI | `llm.provider === "anthropic"` and the user uses LLM features. |
| `llm.google.apiKey` | `GOOGLE_API_KEY` | Settings UI | `llm.provider === "google"` and the user uses LLM features. |
| `figma.apiToken` | `FIGMA_API_TOKEN` | Settings UI | Only if the Figma binding feature (016) is present in the build and the user uses it. |

**Injection**: when main spawns the backend child, it reads the needed secrets from the secure store and adds them to the child's `env` alongside the non-secret settings — exactly the variable names the backend already consumes. The backend remains unaware it's running under Electron (Constitution V boundary preserved).

---

## What is explicitly NOT modeled here

- **Domain entities** (Requirements, UserStories, BoundedContexts, Aggregates, Commands, Events, Policies, Properties, UI, ReadModels, CQRSConfig): owned entirely by Neo4j, unchanged. The desktop layer never reads or writes them — it only routes the backend at the right Neo4j instance.
- **API request/response bodies**: no new endpoints, so no new Pydantic models.
- **`.env` file contents**: the shipped `.env`/`.env.example` carry no secrets; runtime env is assembled by main from `DesktopSettings` + `SecretRef`s. (`.env.example` only gains *documentation* of the desktop-mode env contract.)
