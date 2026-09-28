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
/** 콘솔 미러가 한 번 깨지면 다시 시도하지 않는다. 아래 `mirrorToConsole` 참고. */
let consoleBroken = false;

/**
 * 콘솔 미러. **절대 던지지 않는다.**
 *
 * 이 줄이 실제로 앱을 죽였다(2026-09-28). 패키지 앱에서 다음 대화상자가 떴다 —
 *
 *     A JavaScript error occurred in the main process
 *     Error: EPIPE: broken pipe, write
 *       at writeSync (node:internal/fs/sync_write_stream)
 *       ... at console.log ... at log (app.asar/dist/...)
 *
 * 앱을 띄운 부모 프로세스(터미널·`Start-Process`)가 먼저 끝나면 물려받은 stdout
 * 핸들이 끊긴다. 그 뒤 첫 `console.log` 가 `writeSync` 에서 EPIPE 로 **동기
 * 예외**를 던지고, 그것이 main 프로세스의 uncaught exception 이 된다. 로그 한
 * 줄 때문에 앱이 죽는 것이다.
 *
 * `process.stdout.on("error")` 로는 못 막는다 — 동기 쓰기의 예외는 이벤트로
 * 오지 않는다. 감싸는 수밖에 없다.
 *
 * 원래 이 미러는 주석대로 `npm run dev` 편의용이다. **편의 기능이 제품을 죽이면
 * 안 된다.** 파일 로그가 진짜 기록이고 그쪽은 그대로 남는다.
 */
function mirrorToConsole(level: Level, line: string): void {
  if (consoleBroken) return;
  try {
    const consoleFn =
      level === "error" ? console.error : level === "warn" ? console.warn : console.log;
    consoleFn(line);
  } catch {
    // 한 번 끊긴 파이프는 돌아오지 않는다. 매 줄마다 던지고 잡는 비용을 아낀다.
    consoleBroken = true;
  }
}

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

  // Mirror to the console for `npm run dev` ergonomics — 던지지 않는다.
  mirrorToConsole(level, line.trimEnd());

  if (!logFilePath) return;
  try {
    rotateIfNeeded(logFilePath);
    fs.appendFileSync(logFilePath, line, { encoding: "utf8" });
  } catch (err) {
    // Last-resort: never throw from a log call.
    //
    // 예전에는 여기서 `console.error` 를 직접 불렀다. 그런데 그것도 EPIPE 로
    // 던질 수 있어서, **"절대 던지지 않는다"고 적어둔 자리가 던지고 있었다.**
    mirrorToConsole("error", `logging.write_failed ${String(err)}`);
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
