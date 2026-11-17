/**
 * PATH for an app opened from Finder.
 *
 * macOS starts a .app with PATH=/usr/bin:/bin:/usr/sbin:/sbin — not the login
 * shell's. The stack needs `docker` (Docker Desktop links it into /usr/local/bin,
 * and `docker` needs `docker-credential-desktop` next to it), and proposals and
 * the analyzer's LLM bridge need the `claude` CLI (Homebrew, ~/.local/bin, npm
 * global, nvm …). Started from a terminal everything is found; from the icon
 * nothing would be. So: add the usual install places, and on a packaged macOS
 * app also take the login shell's PATH (that is where nvm and friends live).
 */

import { execFile } from "node:child_process";
import os from "node:os";
import path from "node:path";

import { log } from "./logging";

function usualDirs(): string[] {
  const home = os.homedir();
  if (process.platform === "win32") {
    return [
      path.join(process.env.APPDATA ?? "", "npm"),
      path.join(home, ".local", "bin"),
      path.join(home, "scoop", "shims"),
      "C:\\Program Files\\Docker\\Docker\\resources\\bin",
    ];
  }
  return [
    "/opt/homebrew/bin",
    "/opt/homebrew/sbin",
    "/usr/local/bin",
    path.join(home, ".local", "bin"),
    path.join(home, ".docker", "bin"),
    "/Applications/Docker.app/Contents/Resources/bin",
    path.join(home, ".claude", "local"),
    path.join(home, ".npm-global", "bin"),
    path.join(home, ".volta", "bin"),
    path.join(home, ".bun", "bin"),
    path.join(home, ".deno", "bin"),
  ];
}

function merge(first: string[], then: string[]): string {
  const out: string[] = [];
  for (const dir of [...first, ...then]) {
    if (dir && !out.includes(dir)) out.push(dir);
  }
  return out.join(path.delimiter);
}

function loginShellPath(timeoutMs: number): Promise<string[] | null> {
  const shell = process.env.SHELL || "/bin/zsh";
  const marker = "__ROBO_PATH__";
  return new Promise((resolve) => {
    const child = execFile(
      shell,
      ["-ilc", `printf '\\n${marker}%s${marker}\\n' "$PATH"`],
      { timeout: timeoutMs, env: { ...process.env, TERM: "dumb" }, maxBuffer: 1024 * 1024 },
      (_error, stdout) => {
        const m = new RegExp(`${marker}(.*)${marker}`).exec(stdout ?? "");
        if (!m || !m[1]) {
          resolve(null);
          return;
        }
        resolve(m[1].split(path.delimiter).filter(Boolean));
      },
    );
    // an rc file that asks a question gets end-of-input instead of waiting for the timeout
    child.stdin?.end();
  });
}

/** Call once, before anything spawns docker or claude. */
export async function adoptHostPath(packaged: boolean): Promise<void> {
  const before = (process.env.PATH ?? "").split(path.delimiter).filter(Boolean);
  let fromShell: string[] | null = null;
  if (packaged && process.platform === "darwin") {
    fromShell = await loginShellPath(5_000);
  }
  process.env.PATH = merge(before, [...(fromShell ?? []), ...usualDirs()]);
  log("info", "app.path", {
    fromLoginShell: fromShell ? fromShell.length : null,
    entries: process.env.PATH.split(path.delimiter).length,
  });
}
