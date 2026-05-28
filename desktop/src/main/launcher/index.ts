/**
 * 032 launcher — Electron main barrel.
 *
 * Each module under this directory implements one slice of the launcher:
 *   - settings-migrate.ts  — DesktopSettings v1 → v2 migration
 *   - connections.ts       — SavedConnection CRUD + keychain glue
 *   - discovery.ts         — Neo4j Desktop read-only filesystem scan
 *   - identity.ts          — git config resolver
 *   - project-root.ts      — OS folder picker + validation + recent history
 *   - launcher-state.ts    — pending/entered state machine + enter handler
 *
 * Modules are added incrementally by tasks T006, T009, T010, T013, T028, …
 * Re-exports added as each file lands.
 */

export * from "./settings-migrate";
export * from "./connections";
export * from "./launcher-state";
