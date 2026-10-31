/**
 * Unit tests for getting the stack's images (src/main/docker-images.ts).
 *
 * No Docker: the docker CLI is a fake image store, and the engine API is a
 * small HTTP server on a unix socket that streams the same NDJSON messages the
 * engine sends while pulling. The real registry round trip is
 * scripts/test-image-pull.mjs.
 */

import { expect, test } from "@playwright/test";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";

import {
  ensureImages,
  identityMatches,
  parseImageRef,
  PullTracker,
  type DockerRunner,
  type ImageEntry,
  type ImageProgress,
} from "../../src/main/docker-images";

const ID_A = `sha256:${"a".repeat(64)}`;
const ID_B = `sha256:${"b".repeat(64)}`;
const ID_C = `sha256:${"c".repeat(64)}`;

/** A docker CLI over an in-memory image store: `image inspect`, `image tag`. */
function fakeDocker(store: Map<string, { id: string; repoDigests: string[] }>) {
  const calls: string[][] = [];
  const run: DockerRunner = async (args) => {
    calls.push(args);
    if (args[0] === "image" && args[1] === "inspect") {
      const key = args[2]!;
      const hit = store.get(key) ?? [...store.values()].find((v) => v.id === key);
      if (!hit) throw new Error(`No such image: ${key}`);
      return `${hit.id}|${JSON.stringify(hit.repoDigests)}`;
    }
    if (args[0] === "image" && args[1] === "tag") {
      const source = args[2]!;
      const hit = store.get(source) ?? [...store.values()].find((v) => v.id === source);
      if (!hit) throw new Error(`No such image: ${source}`);
      store.set(args[3]!, hit);
      return "";
    }
    throw new Error(`unexpected docker ${args.join(" ")}`);
  };
  return { run, calls };
}

const quiet = () => undefined;

test.describe("references and identity", () => {
  test("parseImageRef keeps registry ports and digests apart", () => {
    expect(parseImageRef("ghcr.io/uengine-oss/robo-architect-lite-analyzer:0.1.0")).toEqual({
      repository: "ghcr.io/uengine-oss/robo-architect-lite-analyzer",
      tag: "0.1.0",
      digest: null,
    });
    expect(parseImageRef("localhost:5000/a/b")).toEqual({ repository: "localhost:5000/a/b", tag: null, digest: null });
    expect(parseImageRef(`localhost:5000/a/b@${ID_A}`)).toEqual({
      repository: "localhost:5000/a/b",
      tag: null,
      digest: ID_A,
    });
  });

  test("identity: the ID, or the registry digest the release recorded", () => {
    const entry: ImageEntry = { name: "x", ref: "r/x:1", id: ID_A, digest: ID_B };
    expect(identityMatches({ id: ID_A, repoDigests: [] }, entry)).toBe(true);
    // classic image store: the ID is the config digest, the registry digest is in RepoDigests
    expect(identityMatches({ id: ID_C, repoDigests: [`r/x@${ID_B}`] }, entry)).toBe(true);
    expect(identityMatches({ id: ID_C, repoDigests: [`r/x@${ID_C}`] }, entry)).toBe(false);
  });
});

test.describe("progress", () => {
  test("bytes from Downloading; extraction seconds are not bytes", () => {
    const t = new PullTracker(0);
    t.feed({ status: "Pulling from x", id: "1.0" });
    t.feed({ status: "Pulling fs layer", id: "l1", progressDetail: {} });
    t.feed({ status: "Downloading", id: "l1", progressDetail: { current: 10, total: 100 } });
    t.feed({ status: "Downloading", id: "l2", progressDetail: { current: 50, total: 50 } });
    expect([t.current, t.total]).toEqual([60, 150]);
    t.feed({ status: "Extracting", id: "l2", progressDetail: { current: 3, units: "s" } });
    t.feed({ status: "Download complete", id: "l1", progressDetail: { hidecounts: true } });
    expect([t.current, t.total]).toEqual([150, 150]);
    expect(t.feed({ error: "boom" })).toBe("boom");
  });

  test("the recorded size is the total until the registry tells more", () => {
    const t = new PullTracker(1000);
    t.feed({ status: "Downloading", id: "l1", progressDetail: { current: 10, total: 100 } });
    expect([t.current, t.total]).toEqual([10, 1000]);
  });
});

test.describe("ensureImages", () => {
  test("reuses matching images and tags an image found by ID only when the reference is absent", async () => {
    const store = new Map([
      ["uengine/a:lite-mac", { id: ID_A, repoDigests: [] }],
      ["ghcr.io/o/b:0.1.0", { id: ID_B, repoDigests: [] }],
    ]);
    const docker = fakeDocker(store);
    const result = await ensureImages({
      images: [
        { name: "a", ref: "ghcr.io/o/a:0.1.0", id: ID_A },
        { name: "b", ref: "ghcr.io/o/b:0.1.0", id: ID_B },
      ],
      archive: null,
      pull: true,
      runDocker: docker.run,
      log: quiet,
    });
    expect(result).toEqual({ reused: ["b"], tagged: ["a"], loaded: [], pulled: [] });
    expect(store.get("ghcr.io/o/a:0.1.0")?.id).toBe(ID_A);
  });

  test("never moves a tag that points at another image (a fresh rebuild)", async () => {
    const store = new Map([
      ["uengine/a:lite-mac", { id: ID_C, repoDigests: [] }], // just rebuilt
      ["old", { id: ID_A, repoDigests: [] }], // what the manifest still names
    ]);
    const docker = fakeDocker(store);
    await expect(
      ensureImages({
        images: [{ name: "a", ref: "uengine/a:lite-mac", id: ID_A }],
        archive: null,
        pull: false,
        runDocker: docker.run,
        log: quiet,
      }),
    ).rejects.toThrow(/docker\.images_missing: uengine\/a:lite-mac/);
    expect(store.get("uengine/a:lite-mac")?.id).toBe(ID_C);
    expect(docker.calls.some((c) => c[1] === "tag")).toBe(false);
  });

  test("a development manifest with an archive that is not there keeps the old error", async () => {
    const docker = fakeDocker(new Map());
    await expect(
      ensureImages({
        images: [{ name: "a", ref: "uengine/a:lite-mac", id: ID_A }],
        archive: { path: path.join(os.tmpdir(), "no-such-robo-images.tar"), sha256: "0".repeat(64) },
        pull: false,
        runDocker: docker.run,
        log: quiet,
      }),
    ).rejects.toThrow(/docker\.image_archive_missing/);
  });

  test.describe("pull through the engine API", () => {
    let dir: string;
    let server: http.Server;
    let socket: string;
    let requests: string[] = [];
    let store: Map<string, { id: string; repoDigests: string[] }>;

    test.beforeEach(async () => {
      dir = fs.mkdtempSync(path.join(os.tmpdir(), "ra-pull-"));
      socket = path.join(dir, "docker.sock");
      requests = [];
      store = new Map();
      server = http.createServer((req, res) => {
        requests.push(`${req.method} ${req.url}`);
        const url = new URL(req.url ?? "/", "http://engine");
        const repo = url.searchParams.get("fromImage") ?? "";
        const tag = url.searchParams.get("tag") ?? "";
        if (repo.endsWith("/missing")) {
          res.writeHead(404, { "content-type": "application/json" });
          res.end(JSON.stringify({ message: `manifest unknown: ${repo}:${tag}` }));
          return;
        }
        res.writeHead(200, { "content-type": "application/json" });
        const lines = [
          { status: `Pulling from ${repo}`, id: tag },
          { status: "Pulling fs layer", id: "l1", progressDetail: {} },
          { status: "Downloading", id: "l1", progressDetail: { current: 400, total: 1000 } },
          { status: "Downloading", id: "l1", progressDetail: { current: 1000, total: 1000 } },
          { status: "Download complete", id: "l1", progressDetail: { hidecounts: true } },
          { status: "Pull complete", id: "l1", progressDetail: { hidecounts: true } },
          { status: `Digest: ${ID_B}` },
        ];
        // the pulled image lands in the store under repo@digest (classic store: another ID)
        store.set(tag.startsWith("sha256:") ? `${repo}@${tag}` : `${repo}:${tag}`, {
          id: ID_C,
          repoDigests: [`${repo}@${ID_B}`],
        });
        res.end(lines.map((l) => JSON.stringify(l)).join("\n") + "\n");
      });
      await new Promise<void>((resolve) => server.listen(socket, resolve));
    });

    test.afterEach(async () => {
      await new Promise<void>((resolve) => server.close(() => resolve()));
      fs.rmSync(dir, { recursive: true, force: true });
    });

    test("pinned to the digest, tagged as compose names it, verified by registry digest, progress reported", async () => {
      const docker = fakeDocker(store);
      const progress: ImageProgress[] = [];
      const result = await ensureImages({
        images: [{ name: "analyzer", ref: "ghcr.io/o/analyzer:0.1.0", id: ID_A, digest: ID_B, size: 900 }],
        archive: null,
        pull: true,
        runDocker: docker.run,
        log: quiet,
        onProgress: (p) => progress.push(p),
        engineSocket: socket,
      });
      expect(result.pulled).toEqual(["analyzer"]);
      expect(requests).toEqual([`POST /images/create?fromImage=ghcr.io%2Fo%2Fanalyzer&tag=${encodeURIComponent(ID_B)}`]);
      expect(store.get("ghcr.io/o/analyzer:0.1.0")?.repoDigests).toEqual([`ghcr.io/o/analyzer@${ID_B}`]);
      const last = progress[progress.length - 1]!;
      expect(last).toMatchObject({ phase: "pulling", name: "analyzer", index: 1, count: 1, currentBytes: 1000, totalBytes: 1000 });
      expect(last.overallBytes).toBe(1000);
      expect(progress[0]).toMatchObject({ currentBytes: 0, totalBytes: 900 });
    });

    test("a missing tag is reported once, with a hint, without retrying", async () => {
      const docker = fakeDocker(store);
      await expect(
        ensureImages({
          images: [{ name: "x", ref: "ghcr.io/o/missing:0.1.0", id: ID_A }],
          archive: null,
          pull: true,
          runDocker: docker.run,
          log: quiet,
          engineSocket: socket,
        }),
      ).rejects.toThrow(/docker\.image_pull_failed: ghcr\.io\/o\/missing:0\.1\.0: HTTP 404: manifest unknown.*no such image/);
      expect(requests).toHaveLength(1);
    });

    test("an image that comes back with another identity is refused", async () => {
      const docker = fakeDocker(store);
      await expect(
        ensureImages({
          // no digest recorded, and the pulled image is neither ID_A nor digest ID_A
          images: [{ name: "x", ref: "ghcr.io/o/x:0.1.0", id: ID_A }],
          archive: null,
          pull: true,
          runDocker: docker.run,
          log: quiet,
          engineSocket: socket,
        }),
      ).rejects.toThrow(/docker\.image_identity_mismatch: image=ghcr\.io\/o\/x:0\.1\.0/);
    });
  });
});
