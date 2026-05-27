/**
 * Structured JSONL logger for the Electron main process.
 *
 * - Writes to `<dataDir>/logs/desktop.log` as newline-delimited JSON.
 * - Rotates by size (default 5 MB) with up to 5 historical files.
 * - `revealLogs()` opens the logs directory in the OS file manager (FR-016).
 *
 * Used by every Phase-2 subsystem (data-dir, ipc) and by all US1+ modules.
 * No external log dependency — keeps the main bundle small and avoids
 * pulling node_modules into asarUnpack.
 */

import { shell } from "electron";
import fs from "node:fs";
import path from "node:path";

import { getLogsDir } from "./data-dir";

type Level = "debug" | "info" | "warn" | "error";

interface LogEntry {
  ts: string;
  level: Level;
  event: string;
  data?: Record<string, unknown>;
}

const MAX_BYTES = 5 * 1024 * 1024;
const MAX_FILES = 5;
const LOG_FILE = "desktop.log";

let logFilePath: string | null = null;
let initialized = false;

export function initLogging(): void {
  if (initialized) return;
  const dir = getLogsDir();
  fs.mkdirSync(dir, { recursive: true });
  logFilePath = path.join(dir, LOG_FILE);
  initialized = true;
  log("info", "logging.initialized", { path: logFilePath });
}

export function log(level: Level, event: string, data?: Record<string, unknown>): void {
  const entry: LogEntry = { ts: new Date().toISOString(), level, event };
  if (data && Object.keys(data).length > 0) {
    entry.data = data;
  }
  const line = JSON.stringify(entry) + "\n";

  // Mirror to the console for `npm run dev` ergonomics.
  const consoleFn =
    level === "error" ? console.error : level === "warn" ? console.warn : console.log;
  consoleFn(line.trimEnd());

  if (!logFilePath) return;
  try {
    rotateIfNeeded(logFilePath);
    fs.appendFileSync(logFilePath, line, { encoding: "utf8" });
  } catch (err) {
    // Last-resort: never throw from a log call.
    console.error("logging.write_failed", err);
  }
}

function rotateIfNeeded(file: string): void {
  let size = 0;
  try {
    size = fs.statSync(file).size;
  } catch {
    return; // File doesn't exist yet — first write will create it.
  }
  if (size < MAX_BYTES) return;

  // Shift desktop.log.(N-1) → desktop.log.N, dropping the oldest.
  for (let i = MAX_FILES - 1; i >= 1; i--) {
    const from = `${file}.${i}`;
    const to = `${file}.${i + 1}`;
    if (fs.existsSync(from)) {
      try {
        fs.renameSync(from, to);
      } catch {
        /* swallow — best-effort rotation */
      }
    }
  }
  try {
    fs.renameSync(file, `${file}.1`);
  } catch {
    /* swallow */
  }
}

/** Opens the logs directory in the OS file manager. Always succeeds (creates the dir if missing). */
export async function revealLogs(): Promise<void> {
  const dir = getLogsDir();
  fs.mkdirSync(dir, { recursive: true });
  await shell.openPath(dir);
}
