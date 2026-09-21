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
 *   - Auto-restart loop with backoff after crash (T020 full)
 *   - Status-cycle pushes integrated with electron-updater (T031)
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

export interface BackendRuntime {
  port: number | null;
  pid: number | null;
  status: RuntimeStatus;
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
  runtime = { ...runtime, status: next };
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
    runtime = { port: null, pid: null, status: runtime.status };
    if (child === spawned) child = null;
    if (wasReady) {
      setStatus("backend-crashed", `exit code=${code} signal=${signal ?? "none"}`);
    }
  });

  try {
    await waitForReady(port);
  } catch (err) {
    setStatus("fatal", err instanceof Error ? err.message : String(err));
    throw err;
  }

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
