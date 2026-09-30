/**
 * Structured JSONL logger for the Electron main process.
 *
 * - Writes to `<dataDir>/logs/desktop-YYYY-MM-DD.log` as newline-delimited JSON.
 * - **날짜별 파일**이 기본이고, 한 날짜 안에서 커지면 크기로 한 번 더 나눈다.
 * - 오래된 날짜 파일은 `RETENTION_DAYS` 뒤에 지운다.
 * - `revealLogs()` opens the logs directory in the OS file manager (FR-016).
 *
 * ## 왜 날짜별인가
 *
 * 전에는 `desktop.log` 한 파일에 5MB 씩 돌려썼다(`.1`~`.5`). 그러면 **"어제
 * 무슨 일이 있었나" 를 물을 수가 없다** — 경계가 크기라서 날짜와 안 맞고,
 * 바쁜 하루가 조용한 한 주를 밀어낸다. 실제로 2026-09-28 의 설치 검증 기록이
 * 다음 날 기동 로그와 같은 파일에 섞여 있었다.
 *
 * 날짜는 **로컬 시각**으로 정한다. 줄 안의 `ts` 는 ISO(UTC)지만, 파일을 찾는
 * 사람은 "9월 29일 오전" 처럼 자기 시계로 생각한다. UTC 로 나누면 KST 오전 9시가
 * 전날 파일에 들어가 아무도 못 찾는다.
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

/** 한 날짜 파일이 이만큼 커지면 `-1`, `-2` … 로 이어 쓴다. */
const MAX_BYTES = 20 * 1024 * 1024;
/** 하루 안에서 나눌 수 있는 최대 조각 수. 넘으면 마지막 조각에 계속 쓴다. */
const MAX_PARTS = 20;
/** 이보다 오래된 날짜 파일은 지운다. */
const RETENTION_DAYS = 30;
const PREFIX = "desktop-";
const SUFFIX = ".log";

/** `desktop-2026-09-29.log` 와 `desktop-2026-09-29-3.log` 를 둘 다 잡는다. */
const DAILY_FILE = /^desktop-(\d{4})-(\d{2})-(\d{2})(?:-(\d+))?\.log$/;

let logsDir: string | null = null;
let initialized = false;
/** 콘솔 미러가 한 번 깨지면 다시 시도하지 않는다. 아래 `mirrorToConsole` 참고. */
let consoleBroken = false;
/** 지금 쓰고 있는 파일. 날짜가 바뀌면 다시 계산한다. */
let activeDay: string | null = null;
let activePath: string | null = null;
/**
 * 지금 조각에 쌓인 바이트. **메모리로 센다.**
 *
 * 매 줄 `statSync` 를 부르면 로그 한 줄마다 파일 시스템 왕복이 생긴다. 이
 * 프로세스가 유일한 기록자이므로 세어 두면 맞고, 틀려도 조각 경계가 조금
 * 밀리는 것뿐이다.
 */
let activeBytes = 0;

/** 로컬 시각의 `YYYY-MM-DD`. `toISOString()` 은 UTC 라 쓸 수 없다. */
export function localDayKey(at: Date = new Date()): string {
  const y = at.getFullYear();
  const m = String(at.getMonth() + 1).padStart(2, "0");
  const d = String(at.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/**
 * 그 날짜에 **지금 써야 하는** 파일 경로.
 *
 * 조각이 이미 있으면 마지막 조각을 이어 쓰고, 그것이 한도를 넘었으면 다음
 * 조각을 만든다. 예전처럼 파일을 밀어 올리지(rename) 않는다 — 날짜별에서는
 * 밀어 올릴 이유가 없고, rename 은 열려 있는 핸들과 싸운다.
 */
export function resolveDayFile(dir: string, day: string): string {
  const base = (part: number) =>
    path.join(dir, part === 0 ? `${PREFIX}${day}${SUFFIX}` : `${PREFIX}${day}-${part}${SUFFIX}`);

  let part = 0;
  for (; part < MAX_PARTS; part += 1) {
    const file = base(part);
    let size: number;
    try {
      size = fs.statSync(file).size;
    } catch {
      return file; // 없다 — 여기가 새 조각이다.
    }
    if (size < MAX_BYTES) return file;
  }
  // 한도를 다 썼다. 마지막 조각에 계속 쓴다 — 로그가 커지는 것보다 로그를
  // 잃는 것이 나쁘다.
  return base(MAX_PARTS - 1);
}

/**
 * 보존 기간이 지난 날짜 파일을 지운다.
 *
 * 이름의 날짜로만 판단한다 — mtime 은 파일을 복사하거나 백업에서 되살리면
 * 바뀌어서, "언제의 기록인가" 를 말해 주지 못한다.
 */
export function pruneOldDays(
  dir: string,
  now: Date = new Date(),
  retentionDays: number = RETENTION_DAYS,
): string[] {
  let names: string[];
  try {
    names = fs.readdirSync(dir);
  } catch {
    return [];
  }
  const cutoff = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  cutoff.setDate(cutoff.getDate() - retentionDays);

  const removed: string[] = [];
  for (const name of names) {
    const m = DAILY_FILE.exec(name);
    if (!m) continue; // 옛 `desktop.log` 등은 건드리지 않는다.
    const day = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
    if (day >= cutoff) continue;
    try {
      fs.unlinkSync(path.join(dir, name));
      removed.push(name);
    } catch {
      /* 못 지워도 로깅은 계속된다 */
    }
  }
  return removed;
}

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

/**
 * 콘솔 미러를 **영구히** 끈다.
 *
 * ## 왜 위의 try/catch 로 부족한가
 *
 * 위 주석은 EPIPE 가 `console.log` 에서 **동기로** 올라온다고 적어 두었다. 그런데
 * 2026-09-30 실측에서 그 예외가 저 `catch` 를 **지나쳤다** — 스택이
 * `writeSync → SyncWriteStream._write → writeOrBuffer → Writable.write →
 * console.log` 로 끝났고, `uncaughtException` 으로 왔다. 그래서 `consoleBroken`
 * 이 켜지지 않았고, **로그 한 줄마다 예외가 하나** 생겼다.
 *
 * 그 예외를 처리기가 다시 `log()` 로 기록했고, 그 `log()` 가 또 미러를 불러
 * 또 EPIPE 를 냈다. 15분 만에 `app.uncaught_exception` **32,178줄 · 21MB** 가
 * 쌓이고 main 프로세스가 한 코어를 100% 물고 응답을 멈췄다. 그 결과 SSE 프록시가
 * 스트림을 못 비워 **백엔드의 전체 탐색이 3번째 프로세스에서 멈췄다** — 로그
 * 미러 하나가 인제스천을 세운 것이다.
 *
 * 그래서 예외가 **어디로 오든** 한 번 보면 끄는 입구를 따로 둔다.
 */
export function disableConsoleMirror(): void {
  consoleBroken = true;
}

/** 콘솔 미러가 꺼졌는지. 검사용. */
export function isConsoleMirrorDisabled(): boolean {
  return consoleBroken;
}

/**
 * 미러를 다시 켠다. **검사에서만 쓴다** — 한 파일 안의 검사들이 모듈 상태를
 * 공유하므로, 먼저 돈 검사가 끈 것을 되돌리지 않으면 뒤 검사가 헛돈다.
 * 제품 코드에는 호출자가 없다(`log-mirror-epipe.spec.ts` 가 그것도 잰다).
 */
export function resetConsoleMirrorForTests(): void {
  consoleBroken = false;
}

/**
 * stdout·stderr 의 `error` 를 우리가 받는다.
 *
 * 처리기가 없으면 이 이벤트가 `uncaughtException` 이 된다. 비동기로 오는 EPIPE
 * 는 이 경로다 — 위의 `catch` 가 못 잡는 쪽.
 */
function guardStandardStreams(): void {
  for (const stream of [process.stdout, process.stderr]) {
    try {
      stream.on("error", () => {
        consoleBroken = true;
      });
    } catch {
      /* 스트림이 없는 환경(윈도우 GUI 빌드)에서는 그냥 넘어간다 */
    }
  }
}

export function initLogging(): void {
  if (initialized) return;
  guardStandardStreams();
  const dir = getLogsDir();
  fs.mkdirSync(dir, { recursive: true });
  logsDir = dir;
  initialized = true;
  const removed = pruneOldDays(dir);
  log("info", "logging.initialized", {
    dir,
    file: path.basename(currentPath() ?? ""),
    retentionDays: RETENTION_DAYS,
    ...(removed.length > 0 ? { pruned: removed.length } : {}),
  });
}

/** 그 경로로 갈아타면서 이미 들어 있는 바이트를 읽어 센다. */
function switchTo(file: string): string {
  activePath = file;
  try {
    activeBytes = fs.statSync(file).size;
  } catch {
    activeBytes = 0; // 아직 없는 파일
  }
  return file;
}

/** 지금 쓸 파일. 날짜가 넘어가면 여기서 새 파일로 갈아탄다. */
function currentPath(): string | null {
  if (!logsDir) return null;
  const day = localDayKey();
  if (day !== activeDay || activePath === null) {
    activeDay = day;
    // 자정을 넘겨 돌고 있던 앱이라면, 넘어간 시점에 한 번 정리한다.
    pruneOldDays(logsDir);
    return switchTo(resolveDayFile(logsDir, day));
  }
  return activePath;
}

export function log(level: Level, event: string, data?: Record<string, unknown>): void {
  const entry: LogEntry = { ts: new Date().toISOString(), level, event };
  if (data && Object.keys(data).length > 0) {
    entry.data = data;
  }
  const line = JSON.stringify(entry) + "\n";

  // Mirror to the console for `npm run dev` ergonomics — 던지지 않는다.
  mirrorToConsole(level, line.trimEnd());

  const file = currentPath();
  if (!file) return;
  try {
    fs.appendFileSync(file, line, { encoding: "utf8" });
    activeBytes += Buffer.byteLength(line, "utf8");
    // 조각이 한도를 넘었으면 다음 줄부터 다음 조각으로 간다.
    if (activeBytes >= MAX_BYTES && logsDir && activeDay) {
      switchTo(resolveDayFile(logsDir, activeDay));
    }
  } catch (err) {
    // Last-resort: never throw from a log call.
    //
    // 예전에는 여기서 `console.error` 를 직접 불렀다. 그런데 그것도 EPIPE 로
    // 던질 수 있어서, **"절대 던지지 않는다"고 적어둔 자리가 던지고 있었다.**
    mirrorToConsole("error", `logging.write_failed ${String(err)}`);
  }
}

/** Opens the logs directory in the OS file manager. Always succeeds (creates the dir if missing). */
export async function revealLogs(): Promise<void> {
  const dir = getLogsDir();
  fs.mkdirSync(dir, { recursive: true });
  await shell.openPath(dir);
}
