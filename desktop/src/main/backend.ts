/**
 * Backend child-process manager (T019 dev-mode + T020 partial).
 *
 * Dev-mode contract:
 *   Spawns `uv run uvicorn api.main:app --host 127.0.0.1 --port <freePort>`
 *   with `cwd` set to the existing project root (the main checkout — env
 *   `ROBO_BACKEND_DIR` overrides). The Python interpreter, deps, and
 *   `.env` come from that checkout exactly as they do today.
 *
 * Packaged mode:
 *   Starts/reuses the app-owned Docker stack, then spawns the bundled
 *   relocatable Python interpreter for the host Architect API. Keeping this
 *   API on the host preserves Windows project paths and local Claude/PTY
 *   integration; Neo4j and Analyzer services stay isolated in Compose.
 *
 * What this module owns:
 *   - resolveBackendCwd()   — where to spawn from (env override → fallback)
 *   - startBackend()        — picks port, spawns, waits for /api/health,
 *                              resolves with the live port.
 *   - retryBackend()        — re-spawns on a fresh port (FR-017).
 *   - stopBackend()         — graceful SIGTERM → grace → SIGKILL.
 *   - getRuntimeBackend()   — { port, pid, status } snapshot.
 *   - onBackendStatusChange — subscription for the renderer push channel.
 *
 * What this module does NOT do:
 *   - Build runtime artifacts (the Workspace release command owns that)
 *   - Stop the warm Docker stack on ordinary window close
 *   - Status-cycle pushes integrated with an auto-updater (T031 — 자동 갱신은
 *     사내망 납품에 쓰지 않는다. 의존성도 지웠다)
 *
 * What this module DOES do since 2026-10-06:
 *   - 떠 있던 백엔드가 죽으면 **상한을 두고 되살린다**(STAB-1 ⒝ ·
 *     `shouldRestartAfterCrash`). 무한 재시작은 원인을 가리므로 창 안의 횟수를 센다
 */

import { app } from "electron";
import { spawn, type ChildProcess } from "node:child_process";
import { existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { setTimeout as delay } from "node:timers/promises";

import type { RuntimeStatus } from "../shared/ipc-contract";

import {
  resolveBundledArchitectRuntime,
  startDockerStack,
} from "./docker-stack";
import { pickFreePort } from "./ports";
import { log } from "./logging";

/** 백엔드 루트임을 확정하는 표식 — 후보가 진짜 api/ 프로젝트인지 검증. */
const BACKEND_MARKER = join("api", "main.py");

/**
 * 백엔드 루트 후보. 앞에서부터 표식(`api/main.py`)이 있는 첫 후보를 쓴다.
 *
 * 1. `ROBO_BACKEND_DIR` — 명시 지정(최우선)
 * 2. **이 파일 위치 기준 상대경로** — `desktop/dist/main/` → `desktop/` → `robo-architect/`.
 *    개발·패키징 모두 여기서 해소되므로 env 없이 동작한다(옛 하드코딩 Mac 경로 제거).
 */
function backendCwdCandidates(): string[] {
  // 이 파일 위치에서 위로 올라가며 표식을 찾는다 — 빌드 출력 깊이(dist/main/main …)나
  // 패키징 레이아웃이 바뀌어도 안 깨진다(층수 하드코딩 금지).
  // 패키징 시 __dirname 은 asar 안이라 레포 루트까지 깊다:
  //   <repo>/desktop/out/dist/win-unpacked/resources/app.asar/dist/main/main  → 10단계 위
  // 개발 시는 3단계. 표식으로 검증하므로 넉넉히 훑어도 오탐이 없다.
  const ancestors: string[] = [];
  let dir = __dirname;
  for (let i = 0; i < 12; i += 1) {
    ancestors.push(dir);
    const parent = resolve(dir, "..");
    if (parent === dir) break;   // 루트 도달
    dir = parent;
  }
  return [process.env.ROBO_BACKEND_DIR, ...ancestors]
    .filter((v): v is string => typeof v === "string" && v.length > 0);
}

// 첫 설치에서는 Python import와 MCP 초기화가 2분을 넘길 수 있다. 60초는 경고
// 경계일 뿐 실패 판정이 아니다. 프로세스가 살아 있으면 최대 5분까지 이어받는다.
const READINESS_WARNING_MS = 60_000;
const READINESS_TIMEOUT_MS = 5 * 60_000;
const READINESS_INITIAL_BACKOFF_MS = 200;
const READINESS_MAX_BACKOFF_MS = 1_500;
const STOP_GRACE_MS = 5_000;

/**
 * 떠 있던 백엔드가 죽었을 때 **몇 번까지 되살리나.**
 *
 * 10/1 저녁에 백엔드가 힙 손상(`0xC0000374`)으로 내려갔고, 그 뒤 앱은 **아무것도
 * 하지 않았다** — 사람이 껐다 켜야 했다. 화면은 그냥 안 되는 상태로 남는다.
 *
 * 그렇다고 무한히 되살리면 더 나쁘다. 같은 이유로 계속 죽는 백엔드를 끝없이
 * 다시 띄우면 **로그만 채우고 원인을 가린다** — 사람은 "느리다" 고만 느낀다.
 * 그래서 창(window) 안에서 횟수를 센다. 넘으면 멈추고, **왜 멈췄는지 말한다.**
 */
export const CRASH_RESTART_LIMIT = 3;
export const CRASH_WINDOW_MS = 10 * 60_000;

/** 되살리기 전 기다리는 시간. 뒤로 갈수록 길다 — 즉사하는 고장에 매달리지 않는다. */
export const CRASH_BACKOFF_MS = [2_000, 5_000, 15_000] as const;

/**
 * 이번 크래시에 **되살릴 것인가**.
 *
 * `history` 는 크래시 시각들(이번 것 포함)이다. 창 밖의 것은 센 적 없는 것으로
 * 친다 — 어제 두 번 죽은 것이 오늘의 한 번을 막으면 안 된다.
 *
 * 순수 함수로 둔다. 타이머와 spawn 을 섞으면 **이 판정만 따로 잴 수 없다**.
 */
export function shouldRestartAfterCrash(
  history: readonly number[],
  now: number,
  options: { limit?: number; windowMs?: number } = {},
): { restart: boolean; recent: number; waitMs: number } {
  const limit = options.limit ?? CRASH_RESTART_LIMIT;
  const windowMs = options.windowMs ?? CRASH_WINDOW_MS;
  const recent = history.filter((at) => now - at < windowMs).length;
  const waitMs = CRASH_BACKOFF_MS[Math.min(recent, CRASH_BACKOFF_MS.length) - 1] ?? 0;
  return { restart: recent <= limit, recent, waitMs };
}

/** 창 안의 크래시 시각들. 되살리기 판정이 이것만 본다. */
const crashHistory: number[] = [];
/** 우리가 내린 것인가. 내린 것을 되살리면 종료가 안 된다. */
let intentionalStop = false;
/** 되살리기가 예약돼 있는가. 두 번 예약하면 두 번 뜬다. */
let restartTimer: ReturnType<typeof setTimeout> | null = null;

export interface BackendRuntime {
  port: number | null;
  pid: number | null;
  status: RuntimeStatus;
  /**
   * 마지막 상태 변화의 사유. `fatal` 일 때 **왜 못 떴는지**가 여기 있다.
   *
   * 예전에는 리스너에게만 넘기고 어디에도 안 남겨서, 나중에 상태를 물어본
   * 쪽(예: API 프록시)은 "안 떴다" 까지만 알고 이유를 몰랐다.
   */
  detail?: string;
}

export type BackendStatusListener = (
  status: RuntimeStatus,
  detail?: string,
) => void;

let child: ChildProcess | null = null;
let runtime: BackendRuntime = { port: null, pid: null, status: "initializing" };
const listeners = new Set<BackendStatusListener>();

export function getRuntimeBackend(): BackendRuntime {
  return { ...runtime };
}

export function onBackendStatusChange(cb: BackendStatusListener): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

function setStatus(next: RuntimeStatus, detail?: string): void {
  runtime = { ...runtime, status: next, detail };
  log("info", "backend.status", { status: next, detail, port: runtime.port, pid: runtime.pid });
  for (const cb of listeners) {
    try {
      cb(next, detail);
    } catch (err) {
      log("error", "backend.listener_threw", {
        message: err instanceof Error ? err.message : String(err),
      });
    }
  }
}

export function resolveBackendCwd(): string {
  const candidates = backendCwdCandidates();
  for (const candidate of candidates) {
    if (existsSync(join(candidate, BACKEND_MARKER))) return candidate;
  }
  throw new Error(
    `backend.cwd_not_found: tried ${candidates.join(", ")} (looking for ${BACKEND_MARKER}); ` +
      `set ROBO_BACKEND_DIR to the api/ project root`,
  );
}

function usePackagedRuntime(): boolean {
  if (process.env.ROBO_RUNTIME_MODE === "docker") return true;
  if (process.env.ROBO_RUNTIME_MODE === "development") return false;
  return app.isPackaged && !process.env.ROBO_BACKEND_DIR;
}

async function probeHealth(port: number, signal: AbortSignal): Promise<boolean> {
  try {
    const res = await fetch(`http://127.0.0.1:${port}/api/health`, { signal });
    return res.status >= 200 && res.status < 500;
  } catch {
    return false;
  }
}

async function waitForReady(port: number): Promise<void> {
  const deadline = Date.now() + READINESS_TIMEOUT_MS;
  const warningAt = Date.now() + READINESS_WARNING_MS;
  let warned = false;
  let backoff = READINESS_INITIAL_BACKOFF_MS;
  const ac = new AbortController();
  while (Date.now() < deadline) {
    const ok = await probeHealth(port, ac.signal);
    if (ok) return;
    if (child && child.exitCode !== null) {
      throw new Error(`backend.exited_before_ready: code=${child.exitCode}`);
    }
    if (!warned && Date.now() >= warningAt) {
      warned = true;
      log("warn", "backend.readiness_slow", {
        port,
        elapsedMs: READINESS_WARNING_MS,
        timeoutMs: READINESS_TIMEOUT_MS,
      });
      setStatus("starting-backend", "백엔드 초기화가 계속 진행 중입니다.");
    }
    await delay(backoff);
    backoff = Math.min(backoff * 1.5, READINESS_MAX_BACKOFF_MS);
  }
  ac.abort();
  throw new Error(`backend.readiness_timeout: ${READINESS_TIMEOUT_MS}ms`);
}

async function startBackendInternal(): Promise<{ port: number }> {
  if (child && child.exitCode === null) {
    throw new Error("backend.already_running");
  }
  const packaged = usePackagedRuntime();
  let cwd: string;
  let port: number;
  let executable: string;
  let args: string[];

  if (packaged) {
    setStatus("starting-db");
    const stack = await startDockerStack();
    const bundled = resolveBundledArchitectRuntime(stack);
    cwd = bundled.app;
    port = stack.ports.architect;
    executable = bundled.python;
    args = [
      "-m",
      "uvicorn",
      bundled.entrypoint,
      "--host",
      "127.0.0.1",
      "--port",
      String(port),
      "--log-level",
      "info",
    ];
  } else {
    cwd = resolveBackendCwd();
    port = await pickFreePort();
    executable = "uv";
    args = [
      "run",
      // Windows 앱 제어 정책(WDAC/Smart App Control)이 `uvicorn.exe` 콘솔
      // 스크립트 셔임 실행을 차단할 수 있어 python module로 실행한다.
      "python",
      "-m",
      "uvicorn",
      "api.main:app",
      "--host",
      "127.0.0.1",
      "--port",
      String(port),
      "--log-level",
      "info",
    ];
  }

  setStatus("starting-backend");
  log("info", "backend.spawn", { cwd, port, mode: packaged ? "packaged" : "development" });

  const env: NodeJS.ProcessEnv = {
    ...process.env,
    PYTHONUNBUFFERED: "1",
    // **stdout 은 UTF-8 이어야 한다.** 아래 `buf.toString()` 이 UTF-8 로 디코딩하고,
    // 한국어 Windows 에서 파이프에 붙은 python 의 기본 인코딩은 cp949 다. 둘이
    // 어긋나면 두 가지가 같이 터진다 — 로그의 한글이 전부 깨지고(U+FFFD),
    // cp949 에 없는 글자(`—` U+2014 등)를 담은 로그 한 줄이 `print()` 에서
    // UnicodeEncodeError 를 던져 **그 요청을 죽인다**. 2026-09-30 에 문서 업로드
    // 인제스천이 Phase 1 직후 매번 죽은 원인이 이것이었다("facade produced
    // Phase 1 bundle — using it" 의 em dash). 앱을 셸에서 띄우면 그 셸의
    // PYTHONUTF8 를 물려받아 우연히 살아나므로, 개발 중에는 안 보인다.
    PYTHONUTF8: "1",
    PYTHONIOENCODING: "utf-8",
    API_PORT: String(port),
    ROBO_SPEC_BACKEND_URL: `http://127.0.0.1:${port}`,
    NEO4J_URI: process.env.ROBO_NEO4J_URI ?? process.env.NEO4J_URI,
    NEO4J_USER: process.env.ROBO_NEO4J_USER ?? process.env.NEO4J_USER,
    NEO4J_PASSWORD: process.env.ROBO_NEO4J_PASSWORD ?? process.env.NEO4J_PASSWORD,
    NEO4J_DATABASE: process.env.ROBO_NEO4J_DATABASE ?? process.env.NEO4J_DATABASE,
    OG_PG_HOST: process.env.OG_PG_HOST,
    OG_PG_PORT: process.env.OG_PG_PORT,
    OG_PG_DATABASE: process.env.OG_PG_DATABASE,
    OG_PG_USER: process.env.OG_PG_USER,
    OG_PG_PASSWORD: process.env.OG_PG_PASSWORD,
    // 패키지 앱은 로그인 사용자가 만든 프로젝트 graph 를 요청마다 고른다.
    // 이 값이 꺼져 있으면 X-Project-Graph 가 권한 경계를 만들지 못하고 런처
    // 연결의 기본 graph 로 모든 프로젝트가 합쳐진다. 명시 설정은 존중하되,
    // 납품 경로(packaged)는 안전한 기본값을 사용한다.
    // 번들 런타임(= 설치본)인지 알려 준다. 백엔드가 **읽는 사람이 누구인지**
    // 알아야 안내를 맞출 수 있다 — 예: 코드 생성 템플릿이 비었을 때, 개발에서는
    // "fetch-templates.sh 를 돌려라" 가 맞지만 설치본에서는 쓸모없는 말이다.
    ROBO_PACKAGED_RUNTIME: packaged ? "1" : undefined,
    // 백엔드가 **중앙 DB 구성인지** 알아야 한다. 중앙에서는 이미 있는 role 의
    // 비밀번호를 덮어쓰지 않는다 — 비밀을 잘못 넣은 PC 한 대가 그 사용자를
    // 다른 모든 PC 에서 끊어 버리기 때문이다(`projects/roles.py`).
    ROBO_GRAPH_MODE: process.env.ROBO_GRAPH_MODE,
    AUTH_BIND_CONNECTION:
      process.env.AUTH_BIND_CONNECTION ?? (packaged ? "true" : undefined),
    // **설계 graph 로 덮지 않는다.** analyzer 는 대상 graph 를 통째로 비우고 다시
    // 쓰므로, 여기에 설계 graph 가 들어가면 첫 분석에서 설계가 사라진다. 예전에
    // `ROBO_NEO4J_DATABASE` 로 덮던 건 번들 Neo4j 가 Community 라 database 가 하나
    // 뿐이어서였다 — 그때는 그게 유일한 구성이었다. 이제는 갈라져 있다.
    ANALYZER_NEO4J_DATABASE:
      process.env.ROBO_ANALYZER_NEO4J_DATABASE ?? process.env.ANALYZER_NEO4J_DATABASE,
  };

  const spawned = spawn(executable, args, {
    cwd,
    env,
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });
  child = spawned;
  runtime = { ...runtime, port, pid: spawned.pid ?? null };

  spawned.stdout?.on("data", (buf: Buffer) => {
    const line = buf.toString().trimEnd();
    if (line) log("info", "backend.stdout", { line });
  });
  spawned.stderr?.on("data", (buf: Buffer) => {
    const line = buf.toString().trimEnd();
    if (line) log("info", "backend.stderr", { line });
  });

  spawned.on("exit", (code, signal) => {
    log("warn", "backend.exit", { code, signal });
    const wasReady = runtime.status === "ready";
    runtime = { port: null, pid: null, status: runtime.status, detail: runtime.detail };
    if (child === spawned) child = null;
    if (wasReady && !intentionalStop) {
      const detail = `exit code=${code} signal=${signal ?? "none"}`;
      setStatus("backend-crashed", detail);
      const now = Date.now();
      crashHistory.push(now);
      const verdict = shouldRestartAfterCrash(crashHistory, now);
      log("warn", "backend.crash", {
        detail,
        recent: verdict.recent,
        limit: CRASH_RESTART_LIMIT,
        willRestart: verdict.restart,
        waitMs: verdict.waitMs,
      });
      if (verdict.restart) {
        // 사람이 아무것도 안 해도 돌아오게 한다. **다만 횟수를 센다.**
        restartTimer = setTimeout(() => {
          restartTimer = null;
          void startBackend().catch((err) => {
            log("error", "backend.crash_restart_failed", {
              message: err instanceof Error ? err.message : String(err),
            });
          });
        }, verdict.waitMs);
      } else {
        // 멈추는 것도 결정이다 — **왜 멈췄는지** 말한다. 무한 재시작은 원인을 가린다.
        setStatus(
          "fatal",
          `백엔드가 ${CRASH_WINDOW_MS / 60_000}분 안에 ${verdict.recent}번 죽었습니다. ` +
            "되살리기를 멈춥니다 — 앱을 껐다 켜고, 그래도 같으면 로그를 담당자에게 보내 주세요 " +
            `(마지막 사유: ${detail}).`,
        );
      }
    }
  });

  try {
    await waitForReady(port);
  } catch (err) {
    setStatus("fatal", err instanceof Error ? err.message : String(err));
    throw err;
  }

  // 떴으면 다음 종료는 다시 "우리가 내린 것" 이 아니다.
  intentionalStop = false;
  setStatus("ready");
  return { port };
}

/**
 * Public startup boundary. Preparation failures (Docker unavailable, corrupt
 * archive, invalid manifest, bundled Python missing) happen before the child
 * readiness loop, so they must be mapped to the same fatal runtime state.
 */
export async function startBackend(): Promise<{ port: number }> {
  try {
    return await startBackendInternal();
  } catch (err) {
    if (getRuntimeBackend().status !== "fatal") {
      setStatus("fatal", err instanceof Error ? err.message : String(err));
    }
    throw err;
  }
}

export async function retryBackend(): Promise<{ port: number }> {
  log("info", "backend.retry_requested", {});
  await stopBackend();
  return startBackend();
}

export async function stopBackend(): Promise<void> {
  // 우리가 내리는 것이다 — 아래 `exit` 핸들러가 이것을 크래시로 읽으면 안 된다.
  intentionalStop = true;
  if (restartTimer) {
    clearTimeout(restartTimer);
    restartTimer = null;
  }
  const c = child;
  if (!c || c.exitCode !== null) {
    child = null;
    return;
  }
  log("info", "backend.stop_requested", { pid: c.pid });
  c.kill("SIGTERM");
  const exited = await Promise.race([
    new Promise<boolean>((resolve) => c.once("exit", () => resolve(true))),
    delay(STOP_GRACE_MS).then(() => false),
  ]);
  if (!exited && c.exitCode === null) {
    log("warn", "backend.sigkill", { pid: c.pid });
    c.kill("SIGKILL");
  }
  child = null;
  runtime = { port: null, pid: null, status: "initializing" };
}
