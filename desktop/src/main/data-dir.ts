/**
 * Per-user data directory resolution (basic — Phase 2 / T009).
 *
 * Default root = `app.getPath('userData')`.
 * Guarantees `logs/` and `neo4j/` subdirectories exist on first access.
 *
 * NOT yet implemented (lands in later tasks):
 *   - Writability verification + fallback (T024 / US1)
 *   - User-chosen override via folder picker (T042 / US3)
 *   - Persisted override from DesktopSettings (T038 / US3)
 *
 * Keep this module dependency-free apart from `electron` so logging.ts and
 * other Phase-2 modules can depend on it without a cycle.
 */

import { app } from "electron";
import fs from "node:fs";
import path from "node:path";

const SUBDIRS = ["logs", "neo4j"] as const;

let resolvedRoot: string | null = null;

function resolveRoot(): string {
  if (resolvedRoot) return resolvedRoot;
  resolvedRoot = app.getPath("userData");
  return resolvedRoot;
}

export function getDataDir(): string {
  return resolveRoot();
}

export function getLogsDir(): string {
  return path.join(resolveRoot(), "logs");
}

export function getNeo4jDir(): string {
  return path.join(resolveRoot(), "neo4j");
}

/** Idempotent — safe to call on every launch. */
export async function ensureDataDirs(): Promise<void> {
  const root = resolveRoot();
  fs.mkdirSync(root, { recursive: true });
  for (const sub of SUBDIRS) {
    fs.mkdirSync(path.join(root, sub), { recursive: true });
  }
}
