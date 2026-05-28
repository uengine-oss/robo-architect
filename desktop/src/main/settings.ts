/**
 * Atomic load + save for `<dataDir>/settings.json` (spec 023 D9, spec 032 T008).
 *
 * Single-flight: every load and save serialises through an in-process
 * promise chain so concurrent callers never race the tmp→target rename.
 * The first load runs migration + write-back, every subsequent load
 * returns from cache. Saves invalidate-and-replace the cache atomically.
 *
 * Atomicity: writes go to a per-write `settings.<pid>-<seq>.tmp` → fsync
 * → rename, with a backup at `settings.bak` after each successful write.
 * On read failure we attempt `settings.bak` before falling back to defaults.
 */

import fs from "node:fs";
import path from "node:path";

import { type DesktopSettings } from "../shared/ipc-contract";

import { getDataDir } from "./data-dir";
import { log } from "./logging";
import { rekeyLegacyNeo4jPassword } from "./launcher/connections";
import {
  defaultSettings,
  migrateSettingsIfNeeded,
} from "./launcher/settings-migrate";

const SETTINGS_FILE = "settings.json";
const BACKUP_FILE = "settings.bak";

let cached: DesktopSettings | null = null;
/** Single in-flight load promise; collapses concurrent callers. */
let loadInFlight: Promise<DesktopSettings> | null = null;
/** Serialise saves so two concurrent saves can't clobber tmp files. */
let saveQueue: Promise<void> = Promise.resolve();
let tmpSeq = 0;

function settingsPath(): string {
  return path.join(getDataDir(), SETTINGS_FILE);
}
function backupPath(): string {
  return path.join(getDataDir(), BACKUP_FILE);
}
function nextTempPath(): string {
  tmpSeq += 1;
  return path.join(getDataDir(), `settings.${process.pid}-${tmpSeq}.tmp`);
}

function tryParse(filePath: string): unknown | null {
  try {
    const buf = fs.readFileSync(filePath, "utf8");
    return JSON.parse(buf) as unknown;
  } catch (err) {
    const code = (err as NodeJS.ErrnoException).code;
    if (code === "ENOENT") return null;
    log("warn", "settings.parse_failed", {
      file: path.basename(filePath),
      message: err instanceof Error ? err.message : String(err),
    });
    return null;
  }
}

async function loadFromDiskAndMigrate(): Promise<DesktopSettings> {
  let raw = tryParse(settingsPath());
  if (raw === null) {
    raw = tryParse(backupPath());
    if (raw !== null) {
      log("info", "settings.recovered_from_backup", {});
    }
  }

  const result = migrateSettingsIfNeeded(raw);

  if (result.migrated) {
    log("info", "settings.migrated", {
      hadMigratedConnection: result.newSavedConnectionForRekey !== null,
    });
    if (result.newSavedConnectionForRekey) {
      try {
        const moved = await rekeyLegacyNeo4jPassword(result.newSavedConnectionForRekey);
        log("info", "settings.keychain_rekey", {
          moved,
          newConnectionId: result.newSavedConnectionForRekey.id,
        });
      } catch (err) {
        log("warn", "settings.keychain_rekey_failed", {
          message: err instanceof Error ? err.message : String(err),
        });
      }
    }
    await writeSettings(result.settings);
  }

  return result.settings;
}

/**
 * Load settings (migrating from v1 if needed, persisting + re-keying on
 * first call). Subsequent calls return the in-memory cache. Concurrent
 * callers share the same in-flight promise.
 */
export async function loadSettings(): Promise<DesktopSettings> {
  if (cached) return cached;
  if (loadInFlight) return loadInFlight;
  loadInFlight = (async () => {
    try {
      const settings = await loadFromDiskAndMigrate();
      cached = settings;
      return settings;
    } finally {
      loadInFlight = null;
    }
  })();
  return loadInFlight;
}

/**
 * Atomically persist settings + update the cache. Queued so concurrent
 * saves never race the same tmp filename or partial backup-copy.
 */
export async function saveSettings(settings: DesktopSettings): Promise<void> {
  const work = saveQueue.then(async () => {
    await writeSettings(settings);
    cached = settings;
  });
  saveQueue = work.catch(() => {
    /* prevent unhandled rejection from killing the chain */
  });
  return work;
}

async function writeSettings(settings: DesktopSettings): Promise<void> {
  fs.mkdirSync(getDataDir(), { recursive: true });
  const json = JSON.stringify(settings, null, 2) + "\n";
  const tmp = nextTempPath();
  const target = settingsPath();
  const backup = backupPath();

  await fs.promises.writeFile(tmp, json, { encoding: "utf8" });
  try {
    const fh = await fs.promises.open(tmp, "r+");
    try {
      await fh.sync();
    } finally {
      await fh.close();
    }
  } catch {
    /* swallow */
  }
  // Snapshot previous settings as .bak before overwriting (only if a
  // primary file currently exists).
  try {
    await fs.promises.copyFile(target, backup);
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code !== "ENOENT") {
      log("warn", "settings.backup_copy_failed", {
        message: err instanceof Error ? err.message : String(err),
      });
    }
  }
  await fs.promises.rename(tmp, target);
}

/** Test/teardown only — drops the in-memory cache so the next loadSettings re-reads from disk. */
export function _resetSettingsCache(): void {
  cached = null;
  loadInFlight = null;
  saveQueue = Promise.resolve();
}

export { defaultSettings };
