/**
 * DesktopSettings v1 → v2 migration (spec 032 — research.md D4, data-model.md §4).
 *
 * Pure function: takes a raw parsed JSON blob from disk and returns either
 * a fully-shaped v2 `DesktopSettings` value (with `migrated` flag set when
 * any reshaping happened) or — if the input cannot be safely interpreted —
 * a fresh defaults blob that the caller is free to persist as a new file.
 *
 * Side effects (keychain re-key, atomic write-back to disk) are the
 * caller's job. This module is pure so it's testable without Electron.
 *
 * Note on `externalNeo4j`: kept as `null` in v2 output for one release for
 * forward-rollback safety. A v1 build downgrading still sees `null` and
 * treats the user as un-configured rather than crashing on a missing field.
 */

import { randomUUID } from "node:crypto";

import type { DesktopSettings } from "../../shared/ipc-contract";
import {
  SETTINGS_SCHEMA_VERSION_V2,
  type SavedConnection,
} from "../../shared/launcher-contract";

export interface MigrationResult {
  /** True if any reshaping happened; caller should persist + re-key keychain. */
  migrated: boolean;
  settings: DesktopSettings;
  /**
   * Set when migration produced a SavedConnection that needs its keychain
   * password re-keyed from the legacy `neo4j.password` slot. The caller
   * (settings load path) invokes `rekeyLegacyNeo4jPassword(newConnection)`.
   */
  newSavedConnectionForRekey: SavedConnection | null;
}

/**
 * Default settings used when no file exists, or when the file is so corrupt
 * it cannot be repaired. Values match the 023 v1 defaults plus v2 additions.
 */
export function defaultSettings(): DesktopSettings {
  return {
    schemaVersion: SETTINGS_SCHEMA_VERSION_V2,
    dataSource: "external",
    externalNeo4j: null,
    dataDir: null,
    llm: { provider: "openai", model: "gpt-4o-mini" },
    update: { autoCheck: true, lastCheckedAt: null },
    window: { bounds: null, maximized: false },
    lastPorts: { backend: null, bolt: null },
    savedConnections: [],
    recentProjectRoots: [],
    lastProfile: null,
  };
}

function asString(v: unknown): string | null {
  return typeof v === "string" && v.length > 0 ? v : null;
}

function asObject(v: unknown): Record<string, unknown> | null {
  if (v === null || typeof v !== "object" || Array.isArray(v)) return null;
  return v as Record<string, unknown>;
}

function nowIso(): string {
  return new Date().toISOString();
}

/**
 * Migrate raw parsed JSON to v2. The contract:
 *   - v2 input (schemaVersion === 2) → returned as-is with migrated: false
 *     (after gap-filling any missing v2 fields with defaults).
 *   - v1 input (schemaVersion === 1) → reshape per data-model §4 table.
 *   - Anything else (no schemaVersion, schemaVersion > 2, non-object,
 *     null) → return defaults with migrated: true so the caller persists
 *     a fresh file. This is the corruption-recovery path.
 */
export function migrateSettingsIfNeeded(raw: unknown): MigrationResult {
  const obj = asObject(raw);
  if (!obj) {
    return {
      migrated: true,
      settings: defaultSettings(),
      newSavedConnectionForRekey: null,
    };
  }

  const version = obj.schemaVersion;

  if (version === SETTINGS_SCHEMA_VERSION_V2) {
    // v2 already — gap-fill any missing v2-only fields without flipping
    // `migrated` unless something was actually missing.
    return gapFillV2(obj);
  }

  if (version === 1) {
    return migrateV1(obj);
  }

  // Unknown / future / missing schemaVersion → recover to defaults.
  return {
    migrated: true,
    settings: defaultSettings(),
    newSavedConnectionForRekey: null,
  };
}

function gapFillV2(obj: Record<string, unknown>): MigrationResult {
  const defaults = defaultSettings();
  const merged: DesktopSettings = {
    schemaVersion: SETTINGS_SCHEMA_VERSION_V2,
    dataSource:
      obj.dataSource === "bundled" || obj.dataSource === "external"
        ? obj.dataSource
        : defaults.dataSource,
    externalNeo4j: (obj.externalNeo4j ?? null) as DesktopSettings["externalNeo4j"],
    dataDir: asString(obj.dataDir),
    llm: (asObject(obj.llm) ?? defaults.llm) as DesktopSettings["llm"],
    update: (asObject(obj.update) ?? defaults.update) as DesktopSettings["update"],
    window: (asObject(obj.window) ?? defaults.window) as DesktopSettings["window"],
    lastPorts: (asObject(obj.lastPorts) ?? defaults.lastPorts) as DesktopSettings["lastPorts"],
    savedConnections: Array.isArray(obj.savedConnections)
      ? (obj.savedConnections as SavedConnection[])
      : [],
    recentProjectRoots: Array.isArray(obj.recentProjectRoots)
      ? (obj.recentProjectRoots as string[]).filter((p) => typeof p === "string")
      : [],
    lastProfile: (obj.lastProfile ?? null) as DesktopSettings["lastProfile"],
  };
  // Detect if any gap-fill actually mutated the input shape.
  const missingNewField =
    !("savedConnections" in obj) ||
    !("recentProjectRoots" in obj) ||
    !("lastProfile" in obj);
  return {
    migrated: missingNewField,
    settings: merged,
    newSavedConnectionForRekey: null,
  };
}

function migrateV1(obj: Record<string, unknown>): MigrationResult {
  const defaults = defaultSettings();

  const v1External = asObject(obj.externalNeo4j);
  let savedConnections: SavedConnection[] = [];
  let newSavedConnectionForRekey: SavedConnection | null = null;

  if (v1External) {
    const uri = asString(v1External.uri);
    const user = asString(v1External.user);
    const database = asString(v1External.database) ?? undefined;
    if (uri && user) {
      const migrated: SavedConnection = {
        id: randomUUID(),
        label: "Migrated from settings",
        uri,
        user,
        database,
        source: "manual-migrated-from-023",
        lastConnectedAt: null,
        createdAt: nowIso(),
      };
      savedConnections = [migrated];
      newSavedConnectionForRekey = migrated;
    }
  }

  const settings: DesktopSettings = {
    schemaVersion: SETTINGS_SCHEMA_VERSION_V2,
    dataSource:
      obj.dataSource === "bundled" || obj.dataSource === "external"
        ? obj.dataSource
        : defaults.dataSource,
    // v2 keeps `externalNeo4j: null` for one release (forward-rollback safety).
    externalNeo4j: null,
    dataDir: asString(obj.dataDir),
    llm: (asObject(obj.llm) ?? defaults.llm) as DesktopSettings["llm"],
    update: (asObject(obj.update) ?? defaults.update) as DesktopSettings["update"],
    window: (asObject(obj.window) ?? defaults.window) as DesktopSettings["window"],
    lastPorts: (asObject(obj.lastPorts) ?? defaults.lastPorts) as DesktopSettings["lastPorts"],
    savedConnections,
    recentProjectRoots: [],
    lastProfile: null,
  };

  return { migrated: true, settings, newSavedConnectionForRekey };
}
