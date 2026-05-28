/**
 * Unit test for the DesktopSettings v1 → v2 migration (spec 032 T007).
 *
 * Pure function test — no Electron, no filesystem, no keychain. The
 * caller-side side effects (atomic write-back, keychain re-key) are
 * covered separately by integration tests.
 *
 * Uses Playwright Test as the runner because the desktop module already
 * pulls it in for the smoke harness and we don't want a second runner.
 */

import { expect, test } from "@playwright/test";

import {
  defaultSettings,
  migrateSettingsIfNeeded,
} from "../../src/main/launcher/settings-migrate";
import { SETTINGS_SCHEMA_VERSION_V2 } from "../../src/shared/launcher-contract";

test.describe("migrateSettingsIfNeeded", () => {
  test("v1 with externalNeo4j → v2 with one SavedConnection", () => {
    const v1 = {
      schemaVersion: 1,
      dataSource: "external",
      externalNeo4j: { uri: "bolt://x:7687", user: "neo4j", database: "neo4j" },
      dataDir: null,
      llm: { provider: "openai", model: "gpt-4o-mini" },
      update: { autoCheck: true, lastCheckedAt: null },
      window: { bounds: null, maximized: false },
      lastPorts: { backend: null, bolt: null },
    };

    const result = migrateSettingsIfNeeded(v1);

    expect(result.migrated).toBe(true);
    expect(result.settings.schemaVersion).toBe(SETTINGS_SCHEMA_VERSION_V2);
    expect(result.settings.savedConnections).toHaveLength(1);
    const sc = result.settings.savedConnections[0]!;
    expect(sc.uri).toBe("bolt://x:7687");
    expect(sc.user).toBe("neo4j");
    expect(sc.database).toBe("neo4j");
    expect(sc.source).toBe("manual-migrated-from-023");
    expect(sc.label).toBe("Migrated from settings");
    expect(sc.id).toMatch(/^[0-9a-f-]{36}$/);
    // externalNeo4j kept as null for one release per data-model.md §4.
    expect(result.settings.externalNeo4j).toBeNull();
    // The caller is asked to re-key the keychain.
    expect(result.newSavedConnectionForRekey).toBe(sc);
  });

  test("v1 with null externalNeo4j → v2 with empty savedConnections", () => {
    const v1 = {
      schemaVersion: 1,
      dataSource: "bundled",
      externalNeo4j: null,
      dataDir: null,
      llm: { provider: "openai", model: "gpt-4o-mini" },
      update: { autoCheck: true, lastCheckedAt: null },
      window: { bounds: null, maximized: false },
      lastPorts: { backend: null, bolt: null },
    };

    const result = migrateSettingsIfNeeded(v1);

    expect(result.migrated).toBe(true);
    expect(result.settings.schemaVersion).toBe(SETTINGS_SCHEMA_VERSION_V2);
    expect(result.settings.savedConnections).toEqual([]);
    expect(result.newSavedConnectionForRekey).toBeNull();
    expect(result.settings.dataSource).toBe("bundled");
  });

  test("v2 input is idempotent (migrated=false, no reshape)", () => {
    const v2 = defaultSettings();
    v2.savedConnections = [
      {
        id: "00000000-0000-4000-8000-000000000001",
        label: "Local",
        uri: "bolt://localhost:7687",
        user: "neo4j",
        source: "manual",
        lastConnectedAt: null,
        createdAt: "2026-05-28T00:00:00.000Z",
      },
    ];

    const result = migrateSettingsIfNeeded(v2);

    expect(result.migrated).toBe(false);
    expect(result.settings.savedConnections).toHaveLength(1);
    expect(result.newSavedConnectionForRekey).toBeNull();
  });

  test("v2 missing the new fields gets gap-filled and flagged migrated", () => {
    // Simulates a hand-edited v2 file where someone removed savedConnections.
    const partial = {
      ...defaultSettings(),
    } as Record<string, unknown>;
    delete partial.savedConnections;
    delete partial.recentProjectRoots;
    delete partial.lastProfile;

    const result = migrateSettingsIfNeeded(partial);

    expect(result.migrated).toBe(true);
    expect(result.settings.savedConnections).toEqual([]);
    expect(result.settings.recentProjectRoots).toEqual([]);
    expect(result.settings.lastProfile).toBeNull();
  });

  test("non-object input (null, string, array) → defaults", () => {
    for (const bad of [null, "", "string", [], 42]) {
      const result = migrateSettingsIfNeeded(bad as unknown);
      expect(result.migrated).toBe(true);
      expect(result.settings.schemaVersion).toBe(SETTINGS_SCHEMA_VERSION_V2);
      expect(result.settings.savedConnections).toEqual([]);
    }
  });

  test("unknown future schemaVersion → defaults (corruption recovery)", () => {
    const result = migrateSettingsIfNeeded({ schemaVersion: 99 });
    expect(result.migrated).toBe(true);
    expect(result.settings.schemaVersion).toBe(SETTINGS_SCHEMA_VERSION_V2);
  });

  test("v1 with malformed externalNeo4j (no uri) → empty savedConnections", () => {
    const v1 = {
      schemaVersion: 1,
      dataSource: "external",
      externalNeo4j: { user: "neo4j" }, // missing uri
      dataDir: null,
      llm: { provider: "openai", model: "gpt-4o-mini" },
      update: { autoCheck: true, lastCheckedAt: null },
      window: { bounds: null, maximized: false },
      lastPorts: { backend: null, bolt: null },
    };
    const result = migrateSettingsIfNeeded(v1);
    expect(result.migrated).toBe(true);
    expect(result.settings.savedConnections).toEqual([]);
    expect(result.newSavedConnectionForRekey).toBeNull();
  });
});
