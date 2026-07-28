/**
 * Packaged Analyzer stack lifecycle.
 *
 * The distributable Electron app keeps the filesystem/PTY-sensitive Architect
 * API on the Windows host and runs the remaining services in one app-owned
 * Docker Compose project. This module is the only place that knows how to:
 *
 *   manifest -> offline image archive -> Compose environment -> warm stack
 *
 * It intentionally does not own the Architect API child process; backend.ts
 * consumes the returned ports and starts that process with bundled Python.
 */

import { execFile } from "node:child_process";
import { createHash, randomBytes } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

import { getDataDir } from "./data-dir";
import { ensureBundledConnection } from "./launcher/connections";
import { log } from "./logging";
import { pickFreePort } from "./ports";
import { getSecret, setSecret } from "./secret-store";

const MANIFEST_NAME = "runtime-manifest.json";
const STATE_SCHEMA_VERSION = 1;
const MANIFEST_SCHEMA_VERSION = 3;
const COMPOSE_PROJECT_NAME = "robo-architect-desktop";
const NEO4J_PASSWORD_SECRET_ID = "runtime.docker.neo4j.password";
const DOCKER_COMMAND_TIMEOUT_MS = 10 * 60_000;

export interface RuntimeManifest {
  schemaVersion: number;
  releaseId: string;
  composeFile: string;
  imageArchive: string;
  imageArchiveSha256: string;
  images: {
    neo4j: string;
    mindsdb: string;
    analyzer: string;
    catalog: string;
    fabric: string;
    parser: string;
    gateway: string;
  };
  imageIds: Record<keyof RuntimeManifest["images"], string>;
  architect: {
    python: string;
    app: string;
    entrypoint: string;
  };
  environment: Record<
    "analyzer" | "catalog" | "fabric" | "parser" | "gateway" | "architect",
    { file: string; sha256: string }
  >;
  source: Record<string, string>;
}

export interface DockerStackPorts {
  neo4j: number;
  analyzer: number;
  gateway: number;
  architect: number;
}

interface PersistedDockerState {
  schemaVersion: number;
  releaseId: string;
  ports: DockerStackPorts;
}

export interface DockerStackRuntime {
  releaseId: string;
  runtimeDir: string;
  manifest: RuntimeManifest;
  ports: DockerStackPorts;
  projectName: string;
}

let current: DockerStackRuntime | null = null;

function runtimeDirectory(): string {
  const override = process.env.ROBO_DOCKER_RUNTIME_DIR;
  if (override) return path.resolve(override);
  return path.join(process.resourcesPath, "runtime");
}

function statePath(): string {
  return path.join(getDataDir(), "runtime", "docker-state.json");
}

function ensureRuntimeChild(root: string, relative: string, label: string): string {
  if (typeof relative !== "string" || relative.length === 0 || path.isAbsolute(relative)) {
    throw new Error(`runtime.manifest_invalid: ${label} must be a relative path`);
  }
  const resolvedRoot = path.resolve(root);
  const resolved = path.resolve(resolvedRoot, relative);
  const prefix = `${resolvedRoot}${path.sep}`;
  if (!resolved.startsWith(prefix)) {
    throw new Error(`runtime.manifest_invalid: ${label} escapes runtime directory`);
  }
  return resolved;
}

function readManifest(root = runtimeDirectory()): RuntimeManifest {
  const manifestPath = path.join(root, MANIFEST_NAME);
  let raw: unknown;
  try {
    raw = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  } catch (err) {
    throw new Error(
      `runtime.manifest_unreadable: ${manifestPath}: ${
        err instanceof Error ? err.message : String(err)
      }`,
    );
  }
  if (!raw || typeof raw !== "object") {
    throw new Error("runtime.manifest_invalid: root must be an object");
  }
  const manifest = raw as RuntimeManifest;
  if (manifest.schemaVersion !== MANIFEST_SCHEMA_VERSION) {
    throw new Error(
      `runtime.manifest_version_unsupported: expected=${MANIFEST_SCHEMA_VERSION} actual=${manifest.schemaVersion}`,
    );
  }
  if (!/^[A-Za-z0-9._-]{1,80}$/.test(manifest.releaseId ?? "")) {
    throw new Error("runtime.manifest_invalid: releaseId");
  }
  if (!/^[a-f0-9]{64}$/.test(manifest.imageArchiveSha256 ?? "")) {
    throw new Error("runtime.manifest_invalid: imageArchiveSha256");
  }
  for (const [name, image] of Object.entries(manifest.images ?? {})) {
    if (typeof image !== "string" || image.length === 0 || /\s/.test(image)) {
      throw new Error(`runtime.manifest_invalid: images.${name}`);
    }
  }
  for (const required of [
    "neo4j",
    "mindsdb",
    "analyzer",
    "catalog",
    "fabric",
    "parser",
    "gateway",
  ]) {
    if (!manifest.images?.[required as keyof RuntimeManifest["images"]]) {
      throw new Error(`runtime.manifest_invalid: missing image ${required}`);
    }
    const imageId = manifest.imageIds?.[required as keyof RuntimeManifest["images"]];
    if (!/^sha256:[a-f0-9]{64}$/.test(imageId ?? "")) {
      throw new Error(`runtime.manifest_invalid: imageIds.${required}`);
    }
  }
  for (const required of [
    "workspace",
    "architect",
    "openPencil",
    "analyzer",
    "catalog",
    "fabric",
    "frontend",
    "parser",
    "gateway",
  ]) {
    if (!/^[a-f0-9]{40}$/.test(manifest.source?.[required] ?? "")) {
      throw new Error(`runtime.manifest_invalid: source.${required}`);
    }
  }
  ensureRuntimeChild(root, manifest.composeFile, "composeFile");
  ensureRuntimeChild(root, manifest.imageArchive, "imageArchive");
  ensureRuntimeChild(root, manifest.architect.python, "architect.python");
  ensureRuntimeChild(root, manifest.architect.app, "architect.app");
  if (!/^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*$/.test(manifest.architect.entrypoint)) {
    throw new Error("runtime.manifest_invalid: architect.entrypoint");
  }
  for (const required of ["analyzer", "catalog", "fabric", "parser", "gateway", "architect"]) {
    const snapshot = manifest.environment?.[required as keyof RuntimeManifest["environment"]];
    if (!snapshot || !/^[a-f0-9]{64}$/.test(snapshot.sha256 ?? "")) {
      throw new Error(`runtime.manifest_invalid: environment.${required}.sha256`);
    }
    ensureRuntimeChild(root, snapshot.file, `environment.${required}.file`);
  }
  return manifest;
}

async function runDocker(
  args: string[],
  options: { env?: NodeJS.ProcessEnv; timeoutMs?: number; secret?: string } = {},
): Promise<string> {
  const timeout = options.timeoutMs ?? DOCKER_COMMAND_TIMEOUT_MS;
  return await new Promise<string>((resolve, reject) => {
    execFile(
      "docker",
      args,
      {
        env: options.env ?? process.env,
        timeout,
        windowsHide: true,
        maxBuffer: 16 * 1024 * 1024,
      },
      (error, stdout, stderr) => {
        if (!error) {
          resolve(stdout.trim());
          return;
        }
        const secret = options.secret;
        const detail = `${stderr || stdout || error.message}`.trim();
        const redacted = secret ? detail.split(secret).join("***") : detail;
        reject(
          new Error(
            `docker.command_failed: docker ${args.slice(0, 4).join(" ")}: ${redacted}`,
          ),
        );
      },
    );
  });
}

async function ensureDockerDaemon(): Promise<void> {
  try {
    await runDocker(["info", "--format", "{{.ServerVersion}}"], { timeoutMs: 15_000 });
  } catch (err) {
    throw new Error(
      `docker.daemon_unavailable: start Docker Desktop and retry: ${
        err instanceof Error ? err.message : String(err)
      }`,
    );
  }
}

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

async function ensureEnvironmentSnapshots(
  root: string,
  manifest: RuntimeManifest,
): Promise<void> {
  for (const [name, snapshot] of Object.entries(manifest.environment)) {
    const file = ensureRuntimeChild(root, snapshot.file, `environment.${name}.file`);
    if (!fs.existsSync(file)) {
      throw new Error(`runtime.environment_missing: ${name}`);
    }
    const actualSha = await sha256File(file);
    if (actualSha !== snapshot.sha256) {
      throw new Error(
        `runtime.environment_checksum_mismatch: name=${name} expected=${snapshot.sha256} actual=${actualSha}`,
      );
    }
  }
  log("info", "runtime.environment.verified", {
    releaseId: manifest.releaseId,
    count: Object.keys(manifest.environment).length,
  });
}

async function inspectImageId(image: string): Promise<string | null> {
  try {
    return await runDocker(["image", "inspect", image, "--format", "{{.Id}}"], {
      timeoutMs: 20_000,
    });
  } catch {
    return null;
  }
}

async function ensureImages(root: string, manifest: RuntimeManifest): Promise<void> {
  const missing: string[] = [];
  for (const [name, image] of Object.entries(manifest.images)) {
    const actualId = await inspectImageId(image);
    const expectedId = manifest.imageIds[name as keyof RuntimeManifest["images"]];
    if (actualId !== expectedId) missing.push(image);
  }
  if (missing.length === 0) {
    log("info", "docker.images.reused", {
      releaseId: manifest.releaseId,
      count: Object.keys(manifest.images).length,
    });
    return;
  }

  const archive = ensureRuntimeChild(root, manifest.imageArchive, "imageArchive");
  if (!fs.existsSync(archive)) {
    throw new Error(`docker.image_archive_missing: ${archive}`);
  }
  log("info", "docker.image_archive.verifying", {
    releaseId: manifest.releaseId,
    missingCount: missing.length,
  });
  const actualSha = await sha256File(archive);
  if (actualSha !== manifest.imageArchiveSha256) {
    throw new Error(
      `docker.image_archive_checksum_mismatch: expected=${manifest.imageArchiveSha256} actual=${actualSha}`,
    );
  }
  log("info", "docker.image_archive.loading", {
    releaseId: manifest.releaseId,
    missingCount: missing.length,
  });
  await runDocker(["load", "--input", archive]);
  for (const [name, image] of Object.entries(manifest.images)) {
    const actualId = await inspectImageId(image);
    const expectedId = manifest.imageIds[name as keyof RuntimeManifest["images"]];
    if (actualId !== expectedId) {
      throw new Error(
        `docker.image_identity_mismatch: image=${image} expected=${expectedId} actual=${actualId ?? "missing"}`,
      );
    }
  }
  log("info", "docker.image_archive.loaded", {
    releaseId: manifest.releaseId,
    count: Object.keys(manifest.images).length,
  });
}

async function neo4jPassword(): Promise<string> {
  const existing = await getSecret(NEO4J_PASSWORD_SECRET_ID);
  if (existing) return existing;
  const created = randomBytes(32).toString("base64url");
  await setSecret(NEO4J_PASSWORD_SECRET_ID, created);
  return created;
}

function loadPersistedState(releaseId: string): PersistedDockerState | null {
  try {
    const parsed = JSON.parse(fs.readFileSync(statePath(), "utf8")) as PersistedDockerState;
    if (
      parsed.schemaVersion !== STATE_SCHEMA_VERSION ||
      parsed.releaseId !== releaseId ||
      !parsed.ports
    ) {
      return null;
    }
    const ports = Object.values(parsed.ports);
    if (ports.length !== 4 || ports.some((port) => !Number.isInteger(port) || port < 1024 || port > 65535)) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

async function createState(releaseId: string): Promise<PersistedDockerState> {
  const state: PersistedDockerState = {
    schemaVersion: STATE_SCHEMA_VERSION,
    releaseId,
    ports: {
      neo4j: await pickFreePort(),
      analyzer: await pickFreePort(),
      gateway: await pickFreePort(),
      architect: await pickFreePort(),
    },
  };
  const file = statePath();
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const temporary = `${file}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify(state, null, 2)}\n`, "utf8");
  fs.renameSync(temporary, file);
  return state;
}

function composeEnvironment(
  manifest: RuntimeManifest,
  state: PersistedDockerState,
  password: string,
): NodeJS.ProcessEnv {
  return {
    ...process.env,
    COMPOSE_PROJECT_NAME,
    ROBO_RELEASE_ID: manifest.releaseId,
    ROBO_IMAGE_NEO4J: manifest.images.neo4j,
    ROBO_IMAGE_MINDSDB: manifest.images.mindsdb,
    ROBO_IMAGE_ANALYZER: manifest.images.analyzer,
    ROBO_IMAGE_CATALOG: manifest.images.catalog,
    ROBO_IMAGE_FABRIC: manifest.images.fabric,
    ROBO_IMAGE_PARSER: manifest.images.parser,
    ROBO_IMAGE_GATEWAY: manifest.images.gateway,
    ROBO_NEO4J_PASSWORD: password,
    ROBO_NEO4J_PORT: String(state.ports.neo4j),
    ROBO_ANALYZER_PORT: String(state.ports.analyzer),
    ROBO_GATEWAY_PORT: String(state.ports.gateway),
    ROBO_ARCHITECT_API_PORT: String(state.ports.architect),
  };
}

function composeArgs(root: string, manifest: RuntimeManifest, command: string[]): string[] {
  const composeFile = ensureRuntimeChild(root, manifest.composeFile, "composeFile");
  return ["compose", "--project-name", COMPOSE_PROJECT_NAME, "--file", composeFile, ...command];
}

export async function startDockerStack(): Promise<DockerStackRuntime> {
  if (current) return current;
  const root = runtimeDirectory();
  const manifest = readManifest(root);
  await ensureEnvironmentSnapshots(root, manifest);
  await ensureDockerDaemon();
  await ensureImages(root, manifest);

  const password = await neo4jPassword();
  const state = loadPersistedState(manifest.releaseId) ?? (await createState(manifest.releaseId));
  const env = composeEnvironment(manifest, state, password);

  log("info", "docker.stack.starting", {
    releaseId: manifest.releaseId,
    projectName: COMPOSE_PROJECT_NAME,
  });
  await runDocker(composeArgs(root, manifest, ["up", "--detach", "--wait", "--wait-timeout", "300"]), {
    env,
    secret: password,
  });

  const hostNeo4jUri = `bolt://127.0.0.1:${state.ports.neo4j}`;
  process.env.ROBO_GATEWAY_URL = `http://127.0.0.1:${state.ports.gateway}`;
  process.env.ROBO_CLUSTER_MCP_URL = `http://127.0.0.1:${state.ports.analyzer}/robo/mcp/`;
  process.env.ROBO_NEO4J_URI = hostNeo4jUri;
  process.env.ROBO_NEO4J_USER = "neo4j";
  process.env.ROBO_NEO4J_PASSWORD = password;
  process.env.ROBO_NEO4J_DATABASE = "neo4j";
  await ensureBundledConnection({
    uri: hostNeo4jUri,
    user: "neo4j",
    password,
    database: "neo4j",
  });

  current = {
    releaseId: manifest.releaseId,
    runtimeDir: root,
    manifest,
    ports: state.ports,
    projectName: COMPOSE_PROJECT_NAME,
  };
  log("info", "docker.stack.ready", {
    releaseId: manifest.releaseId,
    projectName: COMPOSE_PROJECT_NAME,
    neo4jPort: state.ports.neo4j,
    analyzerPort: state.ports.analyzer,
    gatewayPort: state.ports.gateway,
  });
  return current;
}

export async function stopDockerStack(): Promise<void> {
  const runtime = current;
  if (!runtime) return;
  const password = await neo4jPassword();
  const persisted = loadPersistedState(runtime.releaseId);
  if (!persisted) throw new Error("docker.state_missing: cannot stop owned stack safely");
  await runDocker(
    composeArgs(runtime.runtimeDir, runtime.manifest, ["stop"]),
    {
      env: composeEnvironment(runtime.manifest, persisted, password),
      secret: password,
    },
  );
  current = null;
  log("info", "docker.stack.stopped", { projectName: COMPOSE_PROJECT_NAME });
}

export function getDockerStackRuntime(): DockerStackRuntime | null {
  return current
    ? {
        ...current,
        ports: { ...current.ports },
        manifest: {
          ...current.manifest,
          images: { ...current.manifest.images },
          imageIds: { ...current.manifest.imageIds },
          architect: { ...current.manifest.architect },
          environment: Object.fromEntries(
            Object.entries(current.manifest.environment).map(([name, value]) => [
              name,
              { ...value },
            ]),
          ) as RuntimeManifest["environment"],
          source: { ...current.manifest.source },
        },
      }
    : null;
}

export function resolveBundledArchitectRuntime(runtime: DockerStackRuntime): {
  python: string;
  app: string;
  entrypoint: string;
} {
  return {
    python: ensureRuntimeChild(
      runtime.runtimeDir,
      runtime.manifest.architect.python,
      "architect.python",
    ),
    app: ensureRuntimeChild(runtime.runtimeDir, runtime.manifest.architect.app, "architect.app"),
    entrypoint: runtime.manifest.architect.entrypoint,
  };
}
