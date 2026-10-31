/**
 * Getting the stack's seven images onto this machine.
 *
 * For every image in the runtime manifest, in this order:
 *
 *   1. the manifest's reference is already here with the expected identity  → reuse
 *   2. an image with the expected ID is here under another name               → tag it, reuse
 *      (a developer machine that built `uengine/*:lite-mac` runs a release
 *       manifest that names `ghcr.io/...:<version>` without downloading).
 *      Only when the reference is absent, or the manifest pulls (its references
 *      are the app's own, and a pull would move the tag anyway). A development
 *      reference that is here with another identity is never re-tagged — that
 *      would move a tag someone just rebuilt.
 *   3. an image archive is bundled with the runtime                          → `docker load` it
 *   4. the manifest allows pulls (`imagePull`, release runtimes only)        → pull from the registry
 *      A development manifest names local-only tags (`uengine/*:lite-mac`);
 *      pulling those would ask Docker Hub for them — so it never pulls.
 *
 * then every image is verified against the manifest (`imageIds`, or the
 * registry digest in `imageDigests`). Pulls are reported as progress so the
 * home screen can show which image is downloading and how far it is — the
 * first launch of a release downloads about 1 GB.
 *
 * No Electron imports: the docker runner and the logger are passed in, so this
 * module runs under plain node (scripts/test-image-pull.mjs).
 */

import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import fs from "node:fs";
import http from "node:http";

import type { ImagePullProgress } from "../shared/ipc-contract";

export type DockerRunner = (args: string[], options?: { timeoutMs?: number }) => Promise<string>;
export type Logger = (level: "info" | "warn" | "error", event: string, data?: Record<string, unknown>) => void;

export interface ImageEntry {
  /** manifest key — graphDb, analyzer, … */
  name: string;
  /** what compose runs — `ghcr.io/uengine-oss/robo-architect-lite-analyzer:0.1.0` */
  ref: string;
  /** `docker image inspect --format {{.Id}}` of the release image */
  id: string;
  /** registry manifest digest, when the release was pushed (pull is pinned to it) */
  digest?: string;
  /** compressed download size in bytes (progress total before the registry says) */
  size?: number;
}

/** Shared with the renderer (BackendStatusEvent.progress). */
export type ImageProgress = ImagePullProgress;

export type ProgressListener = (progress: ImageProgress) => void;

export interface EnsureImagesOptions {
  images: ImageEntry[];
  /** absolute path of a bundled `docker save` archive, or null when the runtime has none */
  archive: { path: string; sha256: string } | null;
  /** the manifest's `imagePull` — only release runtimes (registry references) may pull */
  pull: boolean;
  runDocker: DockerRunner;
  log: Logger;
  onProgress?: ProgressListener;
  /** test hook: skip step 2 (reuse by ID under another tag) */
  reuseById?: boolean;
  /** test hook: the engine socket instead of the docker context's */
  engineSocket?: string | null;
}

export interface EnsureImagesResult {
  reused: string[];
  tagged: string[];
  loaded: string[];
  pulled: string[];
}

// ---------------------------------------------------------------------------
// references
// ---------------------------------------------------------------------------

/** `host:5000/a/b:tag@sha256:…` → repository, tag, digest. */
export function parseImageRef(ref: string): { repository: string; tag: string | null; digest: string | null } {
  let rest = ref;
  let digest: string | null = null;
  const at = rest.indexOf("@");
  if (at >= 0) {
    digest = rest.slice(at + 1);
    rest = rest.slice(0, at);
  }
  let tag: string | null = null;
  const colon = rest.lastIndexOf(":");
  if (colon > rest.lastIndexOf("/")) {
    tag = rest.slice(colon + 1);
    rest = rest.slice(0, colon);
  }
  return { repository: rest, tag, digest };
}

interface Inspected {
  id: string;
  repoDigests: string[];
}

async function inspect(runDocker: DockerRunner, ref: string): Promise<Inspected | null> {
  try {
    const out = await runDocker(["image", "inspect", ref, "--format", "{{.Id}}|{{json .RepoDigests}}"], {
      timeoutMs: 20_000,
    });
    const bar = out.indexOf("|");
    const id = (bar >= 0 ? out.slice(0, bar) : out).trim();
    let repoDigests: string[] = [];
    try {
      const parsed = JSON.parse(bar >= 0 ? out.slice(bar + 1) : "[]");
      if (Array.isArray(parsed)) repoDigests = parsed.filter((d): d is string => typeof d === "string");
    } catch {
      repoDigests = [];
    }
    return id ? { id, repoDigests } : null;
  } catch {
    return null;
  }
}

/**
 * The identity check. The classic image store reports the config digest as the
 * ID, the containerd store the manifest (index) digest — so a pulled image is
 * also accepted when its registry digest is the one the release recorded.
 */
export function identityMatches(found: Inspected, entry: ImageEntry): boolean {
  const wanted = new Set([entry.id, entry.digest].filter((v): v is string => !!v));
  if (wanted.has(found.id)) return true;
  return found.repoDigests.some((rd) => wanted.has(rd.slice(rd.indexOf("@") + 1)));
}

// ---------------------------------------------------------------------------
// engine API pull (byte progress) with a CLI fallback
// ---------------------------------------------------------------------------

/** The unix socket (or Windows pipe) the docker CLI talks to — DOCKER_HOST, else the current context. */
export async function engineSocket(runDocker: DockerRunner): Promise<string | null> {
  let host = process.env.DOCKER_HOST ?? "";
  if (!host) {
    try {
      host = await runDocker(["context", "inspect", "--format", "{{.Endpoints.docker.Host}}"], {
        timeoutMs: 10_000,
      });
    } catch {
      host = "";
    }
  }
  host = host.trim();
  if (host.startsWith("unix://")) return host.slice("unix://".length);
  if (host.startsWith("npipe://")) return host.slice("npipe://".length).replace(/\//g, "\\");
  if (!host && process.platform !== "win32" && fs.existsSync("/var/run/docker.sock")) return "/var/run/docker.sock";
  return null;
}

interface LayerState {
  current: number;
  total: number;
  done: boolean;
}

/** Turns the engine's pull messages into "bytes so far / bytes in total" for one image. */
export class PullTracker {
  private readonly layers = new Map<string, LayerState>();

  constructor(private readonly expectedSize = 0) {}

  /** returns an error message when the engine reported one */
  feed(message: Record<string, unknown>): string | null {
    if (typeof message.error === "string") return message.error;
    const id = typeof message.id === "string" ? message.id : null;
    const status = typeof message.status === "string" ? message.status : "";
    if (!id || /^Pulling from /.test(status)) return null;
    const detail = (message.progressDetail ?? {}) as { current?: number; total?: number; units?: string };
    const layer = this.layers.get(id) ?? { current: 0, total: 0, done: false };
    if (status === "Downloading" && (!detail.units || detail.units === "bytes")) {
      if (typeof detail.total === "number" && detail.total > 0) layer.total = detail.total;
      if (typeof detail.current === "number") layer.current = detail.current;
    } else if (/^(Download complete|Verifying Checksum|Extracting|Pull complete|Already exists)/.test(status)) {
      layer.done = true;
      if (layer.total > 0) layer.current = layer.total;
    }
    this.layers.set(id, layer);
    return null;
  }

  /** the pull succeeded — whatever was already here (no byte counts) counts as downloaded */
  finish(): void {
    this.finished = true;
  }

  private finished = false;

  get current(): number {
    if (this.finished) return this.total;
    let sum = 0;
    for (const l of this.layers.values()) sum += l.current;
    return sum;
  }

  /** what the registry has told so far, never less than the recorded size */
  get total(): number {
    let sum = 0;
    let current = 0;
    for (const l of this.layers.values()) {
      sum += l.total;
      current += l.current;
    }
    return Math.max(sum, this.expectedSize, current);
  }
}

const STALL_MS = 5 * 60_000;

function pullViaEngine(
  socketPath: string,
  ref: string,
  tracker: PullTracker,
  onTick: () => void,
): Promise<void> {
  const { repository, tag, digest } = parseImageRef(ref);
  const query = new URLSearchParams({ fromImage: repository, tag: digest ?? tag ?? "latest" });
  return new Promise<void>((resolve, reject) => {
    const req = http.request(
      { socketPath, method: "POST", path: `/images/create?${query.toString()}`, headers: { "content-length": 0 } },
      (res) => {
        let buffer = "";
        let failure: string | null = null;
        if ((res.statusCode ?? 500) >= 400) {
          res.setEncoding("utf8");
          res.on("data", (chunk: string) => (buffer += chunk));
          res.on("end", () => {
            let message = buffer.trim();
            try {
              message = (JSON.parse(buffer) as { message?: string }).message ?? message;
            } catch {
              /* plain text */
            }
            reject(new Error(`HTTP ${res.statusCode}: ${message}`));
          });
          return;
        }
        res.setEncoding("utf8");
        res.on("data", (chunk: string) => {
          buffer += chunk;
          let newline: number;
          while ((newline = buffer.indexOf("\n")) >= 0) {
            const line = buffer.slice(0, newline).trim();
            buffer = buffer.slice(newline + 1);
            if (!line) continue;
            try {
              failure = tracker.feed(JSON.parse(line) as Record<string, unknown>) ?? failure;
            } catch {
              /* a partial or non-JSON line — ignore */
            }
          }
          onTick();
        });
        res.on("end", () => (failure ? reject(new Error(failure)) : resolve()));
        res.on("error", reject);
      },
    );
    req.setTimeout(STALL_MS, () => req.destroy(new Error(`no data for ${STALL_MS / 60_000} minutes`)));
    req.on("error", reject);
    req.end();
  });
}

/** `docker pull` when the engine socket is not reachable — layer counts instead of bytes. */
function pullViaCli(ref: string, tracker: PullTracker, onTick: () => void): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const child = spawn("docker", ["pull", ref], { windowsHide: true });
    let tail = "";
    const onData = (chunk: Buffer) => {
      const text = chunk.toString();
      tail = (tail + text).slice(-2000);
      for (const line of text.split(/\r?\n/)) {
        const m = /^([0-9a-f]{12}): (.+)$/.exec(line.trim());
        if (m) tracker.feed({ id: m[1], status: m[2] });
      }
      onTick();
    };
    child.stdout.on("data", onData);
    child.stderr.on("data", onData);
    child.on("error", reject);
    child.on("exit", (code) => (code === 0 ? resolve() : reject(new Error(tail.trim() || `exit ${code}`))));
  });
}

function explainPullFailure(ref: string, err: unknown): Error {
  const message = err instanceof Error ? err.message : String(err);
  const hint = /denied|unauthorized|401|403/i.test(message)
    ? " (the registry refused an anonymous pull — is the package public?)"
    : /not found|manifest unknown|404/i.test(message)
      ? " (the registry has no such image or tag)"
      : /ENOTFOUND|EAI_AGAIN|ECONNREFUSED|ETIMEDOUT|network|dial tcp|TLS handshake/i.test(message)
        ? " (check the internet connection)"
        : "";
  return new Error(`docker.image_pull_failed: ${ref}: ${message}${hint}`);
}

// ---------------------------------------------------------------------------
// archive
// ---------------------------------------------------------------------------

async function sha256File(filePath: string): Promise<string> {
  const hash = createHash("sha256");
  await new Promise<void>((resolve, reject) => {
    const stream = fs.createReadStream(filePath);
    stream.on("data", (chunk) => hash.update(chunk));
    stream.on("error", reject);
    stream.on("end", resolve);
  });
  return hash.digest("hex");
}

// ---------------------------------------------------------------------------
// the whole step
// ---------------------------------------------------------------------------

export async function ensureImages(options: EnsureImagesOptions): Promise<EnsureImagesResult> {
  const { images, runDocker, log } = options;
  const result: EnsureImagesResult = { reused: [], tagged: [], loaded: [], pulled: [] };
  let missing: ImageEntry[] = [];

  for (const entry of images) {
    const found = await inspect(runDocker, entry.ref);
    if (found && identityMatches(found, entry)) {
      result.reused.push(entry.name);
      continue;
    }
    if ((!found || options.pull) && options.reuseById !== false) {
      const byId = await inspect(runDocker, entry.id);
      if (byId && identityMatches(byId, entry)) {
        await runDocker(["image", "tag", entry.id, entry.ref], { timeoutMs: 20_000 });
        log("info", "docker.image.tagged_from_id", { name: entry.name, ref: entry.ref, id: entry.id });
        result.tagged.push(entry.name);
        continue;
      }
    }
    missing.push(entry);
  }
  if (missing.length === 0) return result;

  const total = (list: ImageEntry[]) => list.reduce((sum, e) => sum + (e.size ?? 0), 0);

  // 3. a bundled archive — the offline install
  if (options.archive && !options.pull && !fs.existsSync(options.archive.path)) {
    throw new Error(`docker.image_archive_missing: ${options.archive.path}`);
  }
  if (!options.archive && !options.pull) {
    throw new Error(
      `docker.images_missing: ${missing.map((e) => e.ref).join(", ")} — this runtime neither bundles an archive nor pulls (rebuild the runtime manifest?)`,
    );
  }
  if (options.archive && fs.existsSync(options.archive.path)) {
    const first = missing[0]!;
    options.onProgress?.({
      phase: "loading", name: first.name, ref: first.ref, index: 1, count: missing.length,
      currentBytes: 0, totalBytes: 0, overallBytes: 0, overallTotal: total(missing),
    });
    log("info", "docker.image_archive.verifying", { missingCount: missing.length });
    const actualSha = await sha256File(options.archive.path);
    if (actualSha !== options.archive.sha256) {
      throw new Error(
        `docker.image_archive_checksum_mismatch: expected=${options.archive.sha256} actual=${actualSha}`,
      );
    }
    log("info", "docker.image_archive.loading", { missingCount: missing.length });
    await runDocker(["load", "--input", options.archive.path]);
    result.loaded.push(...missing.map((e) => e.name));
    missing = [];
  }

  // 4. the registry
  if (missing.length > 0) {
    const socket = options.engineSocket !== undefined ? options.engineSocket : await engineSocket(runDocker);
    const overallTotal = total(missing);
    let overallDone = 0;
    for (const [i, entry] of missing.entries()) {
      // pinned to the digest the release recorded, then tagged as compose names it
      const { repository } = parseImageRef(entry.ref);
      const source = entry.digest ? `${repository}@${entry.digest}` : entry.ref;
      log("info", "docker.image.pulling", { name: entry.name, ref: entry.ref, source, via: socket ? "engine" : "cli" });
      let tracker = new PullTracker(entry.size ?? 0);
      let lastTick = 0;
      const tick = (force = false) => {
        const now = Date.now();
        if (!force && now - lastTick < 400) return;
        lastTick = now;
        options.onProgress?.({
          phase: "pulling", name: entry.name, ref: entry.ref, index: i + 1, count: missing.length,
          currentBytes: tracker.current, totalBytes: tracker.total,
          overallBytes: overallDone + tracker.current,
          overallTotal: Math.max(overallTotal, overallDone + tracker.total),
        });
      };
      tick(true);
      const started = Date.now();
      let lastError: unknown = null;
      for (let attempt = 1; attempt <= 3; attempt += 1) {
        try {
          if (socket) await pullViaEngine(socket, source, tracker, tick);
          else await pullViaCli(source, tracker, tick);
          lastError = null;
          break;
        } catch (err) {
          lastError = err;
          const message = err instanceof Error ? err.message : String(err);
          log("warn", "docker.image.pull_retry", { name: entry.name, attempt, message });
          // a refusal or a missing tag will not change by asking again
          if (/denied|unauthorized|not found|manifest unknown|HTTP 40[134]/i.test(message)) break;
          tracker = new PullTracker(entry.size ?? 0);
        }
      }
      if (lastError) throw explainPullFailure(entry.ref, lastError);
      tracker.finish();
      if (source !== entry.ref) {
        await runDocker(["image", "tag", source, entry.ref], { timeoutMs: 20_000 });
      }
      tick(true);
      overallDone += Math.max(tracker.total, entry.size ?? 0);
      log("info", "docker.image.pulled", {
        name: entry.name, ref: entry.ref, bytes: tracker.total, seconds: Math.round((Date.now() - started) / 1000),
      });
      result.pulled.push(entry.name);
    }
  }

  // every image, whichever way it came
  for (const entry of images) {
    const found = await inspect(runDocker, entry.ref);
    if (!found || !identityMatches(found, entry)) {
      throw new Error(
        `docker.image_identity_mismatch: image=${entry.ref} expected=${entry.id} actual=${found?.id ?? "missing"}`,
      );
    }
  }
  return result;
}
