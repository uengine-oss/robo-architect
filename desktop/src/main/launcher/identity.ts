/**
 * Git identity resolver (spec 032 T043).
 *
 * Spawns `git config --get user.name` + `git config --get user.email`
 * in parallel with `cwd = projectRoot` (or the app exec dir when no
 * project root is selected yet), shared 1-second deadline. Returns the
 * canonical `SessionUser` with a best-effort `source` label.
 *
 * Falls back silently to `unknown-fallback` on:
 *   - `git` not on PATH (ENOENT)
 *   - non-zero exit (no value configured at any level)
 *   - timeout
 *   - permission denied
 *
 * Never throws — callers can rely on the returned object always being
 * shaped per `SessionUser`.
 */

import { spawn } from "node:child_process";
import { hostname } from "node:os";
import path from "node:path";

import type { IdentitySource, SessionUser } from "../../shared/launcher-contract";

const TIMEOUT_MS = 1000;
const DISPLAY_NAME_MAX = 40;

function unknownFallback(): SessionUser {
  return {
    name: "unknown user",
    email: `unknown@${hostname()}`,
    source: "unknown-fallback",
    displayName: "unknown user",
  };
}

function truncate(name: string): string {
  if (name.length <= DISPLAY_NAME_MAX) return name;
  return name.slice(0, DISPLAY_NAME_MAX - 1) + "…";
}

/**
 * Run `git config --get <key>` once with a bounded deadline.
 * Resolves to the trimmed value on exit 0, or null on any failure.
 */
function gitConfigGet(key: string, cwd: string, signal: AbortSignal): Promise<string | null> {
  return new Promise<string | null>((resolve) => {
    let stdout = "";
    let settled = false;
    const finish = (value: string | null) => {
      if (settled) return;
      settled = true;
      resolve(value);
    };

    let child;
    try {
      child = spawn("git", ["config", "--get", key], {
        cwd,
        // No shell — argv is passed as array, no command injection risk
        // even if cwd contains shell metacharacters.
        shell: false,
        stdio: ["ignore", "pipe", "ignore"],
        signal,
      });
    } catch {
      finish(null);
      return;
    }

    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString("utf8");
    });
    child.on("error", () => finish(null));
    child.on("close", (code) => {
      if (code === 0) {
        const trimmed = stdout.trim();
        finish(trimmed.length > 0 ? trimmed : null);
      } else {
        finish(null);
      }
    });
  });
}

/**
 * Best-effort detection of *where* git found the value. The renderer-side
 * source labels (`env` / `project-local-git` / `global-git` / `system-git`)
 * are presentation-only — we infer them from a follow-up `git config
 * --show-scope --get` probe; on any failure we collapse to `global-git`
 * (the safe default for "git found something").
 */
async function detectSource(cwd: string): Promise<Exclude<IdentitySource, "unknown-fallback">> {
  // Env-var override has highest precedence and bypasses git entirely.
  if (process.env.GIT_AUTHOR_NAME && process.env.GIT_AUTHOR_EMAIL) {
    return "env";
  }
  return new Promise((resolve) => {
    let stdout = "";
    let settled = false;
    const finish = (s: Exclude<IdentitySource, "unknown-fallback">) => {
      if (settled) return;
      settled = true;
      resolve(s);
    };
    const timer = setTimeout(() => finish("global-git"), 500);
    try {
      const child = spawn(
        "git",
        ["config", "--show-scope", "--get", "user.name"],
        { cwd, shell: false, stdio: ["ignore", "pipe", "ignore"] },
      );
      child.stdout.on("data", (chunk: Buffer) => {
        stdout += chunk.toString("utf8");
      });
      child.on("error", () => {
        clearTimeout(timer);
        finish("global-git");
      });
      child.on("close", () => {
        clearTimeout(timer);
        const scope = stdout.trim().split(/\s+/)[0] ?? "";
        if (scope === "local" || scope === "worktree") return finish("project-local-git");
        if (scope === "global") return finish("global-git");
        if (scope === "system") return finish("system-git");
        finish("global-git");
      });
    } catch {
      clearTimeout(timer);
      finish("global-git");
    }
  });
}

/**
 * Write `user.name` + `user.email` to global git config.
 * Returns the freshly-resolved SessionUser so the caller can commit it.
 * Throws (string message) on any git failure.
 */
export async function setGitConfigGlobal(name: string, email: string): Promise<SessionUser> {
  const trimmedName = name.trim();
  const trimmedEmail = email.trim();
  if (!trimmedName) throw new Error("name must not be empty");
  if (!trimmedEmail) throw new Error("email must not be empty");

  async function runGitConfig(key: string, value: string): Promise<void> {
    return new Promise((resolve, reject) => {
      let settled = false;
      const finish = (err?: Error) => {
        if (settled) return;
        settled = true;
        err ? reject(err) : resolve();
      };
      let child;
      try {
        child = spawn("git", ["config", "--global", key, value], {
          shell: false,
          stdio: ["ignore", "ignore", "pipe"],
        });
      } catch (e) {
        finish(e instanceof Error ? e : new Error(String(e)));
        return;
      }
      child.on("error", (e) => finish(e));
      child.on("close", (code) => {
        if (code === 0) finish();
        else finish(new Error(`git config exited with code ${code}`));
      });
    });
  }

  await runGitConfig("user.name", trimmedName);
  await runGitConfig("user.email", trimmedEmail);
  // Re-resolve so the returned SessionUser reflects the new global config.
  return resolveSessionUser(null);
}

/**
 * Resolve the session user.
 *
 * `projectRoot` carries the user's chosen workspace folder. Setting it as
 * `cwd` lets git's normal precedence find a project-local override when
 * present. When null, we use the parent directory of `process.execPath`
 * — a benign neutral cwd that triggers global/system git config only.
 */
export async function resolveSessionUser(projectRoot: string | null): Promise<SessionUser> {
  const cwd = projectRoot ?? path.dirname(process.execPath);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    // Env-var precedence first — git respects this too, but reading the
    // env directly is faster and avoids spawning when we already have it.
    const envName = process.env.GIT_AUTHOR_NAME?.trim();
    const envEmail = process.env.GIT_AUTHOR_EMAIL?.trim();
    if (envName && envEmail) {
      return {
        name: envName,
        email: envEmail,
        source: "env",
        displayName: truncate(envName),
      };
    }

    const [name, email] = await Promise.all([
      gitConfigGet("user.name", cwd, controller.signal),
      gitConfigGet("user.email", cwd, controller.signal),
    ]);

    if (name && email) {
      const source = await detectSource(cwd);
      return {
        name,
        email,
        source,
        displayName: truncate(name),
      };
    }

    return unknownFallback();
  } catch {
    return unknownFallback();
  } finally {
    clearTimeout(timer);
  }
}
