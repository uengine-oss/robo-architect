/**
 * Backend child-process manager (T019 dev-mode + T020 partial).
 *
 * Dev-mode contract:
 *   Spawns `uv run uvicorn api.main:app --host 127.0.0.1 --port <freePort>`
 *   with `cwd` set to the existing project root (the main checkout — env
 *   `ROBO_BACKEND_DIR` overrides). The Python interpreter, deps, and
 *   `.env` come from that checkout exactly as they do today.
 *
 * Production-mode (NOT YET WIRED — lands in T018 + a switch here):
 *   Spawns `<resources>/python/<os-arch>/python -m uvicorn api.main:app …`
 *   from the asar-unpacked bundle. The CLI invocation, env-var contract,
 *   and readiness probe are identical, so only the spawn target changes.
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
 * What this module does NOT do (deferred):
 *   - Bundled-Python resolution (T018)
 *   - Neo4j start/stop (T023)
 *   - Auto-restart loop with backoff after crash (T020 full)
 *   - Status-cycle pushes integrated with electron-updater (T031)
 */

import { spawn, type ChildProcess } from "node:child_process";
import { existsSync } from "node:fs";
import { setTimeout as delay } from "node:timers/promises";

import type { RuntimeStatus } from "../shared/ipc-contract";

import { pickFreePort } from "./ports";
import { log } from "./logging";

const DEFAULT_BACKEND_CWD_CANDIDATES = [
  process.env.ROBO_BACKEND_DIR,
  // Dev convenience: the main checkout sits two levels up from the worktree.
  // `<repo>/.claude/worktrees/023-electron-desktop/` → walk back to `<repo>`
  // doesn't help (worktree is a separate checkout). Prefer the env var or
  // the well-known main location below.
  "/Users/uengine/main-robo-arch/robo-architect",
].filter((v): v is string => typeof v === "string" && v.length > 0);

const READINESS_TIMEOUT_MS = 60_000;
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
  for (const candidate of DEFAULT_BACKEND_CWD_CANDIDATES) {
    if (existsSync(candidate)) return candidate;
  }
  throw new Error(
    `backend.cwd_not_found: tried ${DEFAULT_BACKEND_CWD_CANDIDATES.join(", ")}; ` +
      `set ROBO_BACKEND_DIR to the api/ project root`,
  );
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
  let backoff = READINESS_INITIAL_BACKOFF_MS;
  const ac = new AbortController();
  while (Date.now() < deadline) {
    const ok = await probeHealth(port, ac.signal);
    if (ok) return;
    if (child && child.exitCode !== null) {
      throw new Error(`backend.exited_before_ready: code=${child.exitCode}`);
    }
    await delay(backoff);
    backoff = Math.min(backoff * 1.5, READINESS_MAX_BACKOFF_MS);
  }
  ac.abort();
  throw new Error(`backend.readiness_timeout: ${READINESS_TIMEOUT_MS}ms`);
}

export async function startBackend(): Promise<{ port: number }> {
  if (child && child.exitCode === null) {
    throw new Error("backend.already_running");
  }
  setStatus("starting-backend");

  const cwd = resolveBackendCwd();
  const port = await pickFreePort();
  log("info", "backend.spawn", { cwd, port });

  const env: NodeJS.ProcessEnv = {
    ...process.env,
    // The backend already reads NEO4J_* / LLM_* / *_API_KEY from its own
    // .env via python-dotenv; we don't override them here. Production-mode
    // injection from DesktopSettings / OS secure store lands in T040.
    PYTHONUNBUFFERED: "1",
  };

  const spawned = spawn(
    "uv",
    [
      "run",
      "uvicorn",
      "api.main:app",
      "--host",
      "127.0.0.1",
      "--port",
      String(port),
      "--log-level",
      "info",
    ],
    { cwd, env, stdio: ["ignore", "pipe", "pipe"] },
  );
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
