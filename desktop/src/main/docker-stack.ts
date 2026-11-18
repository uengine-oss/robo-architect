/**
 * Packaged Analyzer stack lifecycle.
 *
 * The distributable Electron app keeps the filesystem/PTY-sensitive Architect
 * API on the host and runs the remaining services in one app-owned Docker
 * Compose project. This module is the only place that knows how to:
 *
 *   manifest -> images (local / archive / registry pull) -> Compose environment -> warm stack
 *
 * Getting the images is docker-images.ts.
 *
 * It intentionally does not own the Architect API child process; backend.ts
 * consumes the returned ports and starts that process with bundled Python.
 *
 * Two configurations (runtime-variant.ts), chosen by the manifest's `deployVariant`:
 * the default (compose.yml, Ontological single — this file's original path, unchanged)
 * and `age-fabric` (compose.age-fabric.yml: AGE + og-fabric), whose steps between
 * bringing containers up are age-fabric-stack.ts.
 */

import { execFile } from "node:child_process";
import { createHash, randomBytes } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

import {
  deliverKeychainSecrets,
  ensureAgeFabricSecrets,
  FabricClient,
  migrateV1Plaintext,
  newToken,
  prepareAgeDb,
  prepareFabricDb,
  type AgeFabricSecrets,
  type ExecInService,
  type SecretStoreLike,
} from "./age-fabric-stack";
import { getDataDir } from "./data-dir";
import { ensureImages as fetchImages, type ImageEntry, type ProgressListener } from "./docker-images";
import { GRAPH_ANALYSIS, GRAPH_DESIGN, GRAPH_USER } from "./graphs";
import { ensureBundledConnection } from "./launcher/connections";
import { log } from "./logging";
import { pickFreePort } from "./ports";
import { deleteSecret, getSecret, setSecret } from "./secret-store";
import { loadSettings } from "./settings";
import {
  composeProjectName,
  DEFAULT_COMPOSE_PROJECT_NAME,
  deployVariantOf,
  profileOf,
  requiredImageKeys,
  type BaseImageKey,
  type DeployVariant,
  type ImageKey,
  type RuntimeProfile,
} from "./runtime-variant";

const MANIFEST_NAME = "runtime-manifest.json";
const STATE_SCHEMA_VERSION = 2;
const MANIFEST_SCHEMA_VERSION = 4;
// ROBO_COMPOSE_PROJECT: a second stack next to the usual one (packaged-app test with a
// fresh data folder — the same project name would recreate the running containers).
// Without it: robo-architect-desktop, or robo-architect-desktop-age for age-fabric.
function projectNameOf(manifest: RuntimeManifest): string {
  return composeProjectName(deployVariantOf(manifest.deployVariant), process.env.ROBO_COMPOSE_PROJECT);
}
const NEO4J_PASSWORD_SECRET_ID = "runtime.docker.neo4j.password";
const DOCKER_COMMAND_TIMEOUT_MS = 10 * 60_000;

export interface RuntimeManifest {
  schemaVersion: number;
  /** "age-fabric" for compose.age-fabric.yml; absent (or "ontological") is the default configuration */
  deployVariant?: string;
  releaseId: string;
  composeFile: string;
  /** a bundled `docker save` archive (offline install) */
  imageArchive?: string | null;
  imageArchiveSha256?: string | null;
  /** release runtimes: missing images are pulled from the registry the references name */
  imagePull?: boolean;
  images: {
    graphDb: string;
    graphBolt: string;
    analyzer: string;
    catalog: string;
    fabric: string;
    parser: string;
    gateway: string;
    // open-pencil 렌더러. 없으면 와이어프레임 단계가 **조용히** 빈다(compose 의 주석에 실측).
    wireframe: string;
    /** age-fabric: og-fabric's own PostgreSQL (og_fabric + FDWs) */
    fabricDb?: string;
  };
  imageIds: Record<BaseImageKey, string> & { fabricDb?: string };
  /** registry manifest digests recorded when the release images were pushed — pulls are pinned to them */
  imageDigests?: Partial<Record<ImageKey, string>>;
  /** compressed download sizes (bytes) — the progress total before the registry reports one */
  imageSizes?: Partial<Record<ImageKey, number>>;
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
  // Bolt 게이트웨이가 듣는 포트. 이름은 **프로토콜**을 가리킨다.
  neo4j: number;
  // 엔진(postgres)이 듣는 포트 — 호스트 백엔드가 사용자·프로젝트 표에 직접 붙는다.
  graphPg: number;
  analyzer: number;
  gateway: number;
  architect: number;
  // open-pencil 렌더러. Architect API 가 호스트에서 돌므로 호스트 포트가 있어야 닿는다.
  wireframe: number;
  /** age-fabric: og-fabric on 127.0.0.1 — the shell's secrets channel */
  fabric?: number;
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
  const variant = deployVariantOf(manifest.deployVariant);
  if (manifest.schemaVersion !== MANIFEST_SCHEMA_VERSION) {
    throw new Error(
      `runtime.manifest_version_unsupported: expected=${MANIFEST_SCHEMA_VERSION} actual=${manifest.schemaVersion}`,
    );
  }
  if (!/^[A-Za-z0-9._-]{1,80}$/.test(manifest.releaseId ?? "")) {
    throw new Error("runtime.manifest_invalid: releaseId");
  }
  if (manifest.imageArchive && !/^[a-f0-9]{64}$/.test(manifest.imageArchiveSha256 ?? "")) {
    throw new Error("runtime.manifest_invalid: imageArchiveSha256");
  }
  for (const [name, image] of Object.entries(manifest.images ?? {})) {
    if (typeof image !== "string" || image.length === 0 || /\s/.test(image)) {
      throw new Error(`runtime.manifest_invalid: images.${name}`);
    }
  }
  for (const required of requiredImageKeys(variant)) {
    if (!manifest.images?.[required as keyof RuntimeManifest["images"]]) {
      throw new Error(`runtime.manifest_invalid: missing image ${required}`);
    }
    const imageId = manifest.imageIds?.[required as keyof RuntimeManifest["imageIds"]];
    if (!/^sha256:[a-f0-9]{64}$/.test(imageId ?? "")) {
      throw new Error(`runtime.manifest_invalid: imageIds.${required}`);
    }
    const digest = manifest.imageDigests?.[required as keyof RuntimeManifest["images"]];
    if (digest !== undefined && !/^sha256:[a-f0-9]{64}$/.test(digest)) {
      throw new Error(`runtime.manifest_invalid: imageDigests.${required}`);
    }
    const size = manifest.imageSizes?.[required as keyof RuntimeManifest["images"]];
    if (size !== undefined && !(Number.isInteger(size) && size >= 0)) {
      throw new Error(`runtime.manifest_invalid: imageSizes.${required}`);
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
  if (manifest.imageArchive) ensureRuntimeChild(root, manifest.imageArchive, "imageArchive");
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
  options: { env?: NodeJS.ProcessEnv; timeoutMs?: number; secret?: string; secrets?: string[]; input?: string } = {},
): Promise<string> {
  const timeout = options.timeoutMs ?? DOCKER_COMMAND_TIMEOUT_MS;
  return await new Promise<string>((resolve, reject) => {
    const child = execFile(
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
        let redacted = secret ? detail.split(secret).join("***") : detail;
        for (const s of options.secrets ?? []) if (s) redacted = redacted.split(s).join("***");
        reject(
          new Error(
            `docker.command_failed: docker ${args.slice(0, 4).join(" ")}: ${redacted}`,
          ),
        );
      },
    );
    // 비밀 값은 명령줄(프로세스 목록에 보인다)이 아니라 표준 입력으로 넘긴다
    if (options.input !== undefined) child.stdin?.end(options.input);
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

async function ensureImages(
  root: string,
  manifest: RuntimeManifest,
  onProgress?: ProgressListener,
): Promise<void> {
  const images: ImageEntry[] = Object.entries(manifest.images).map(([name, ref]) => {
    const key = name as keyof RuntimeManifest["imageIds"];
    return {
      name,
      ref,
      id: manifest.imageIds[key] as string, // readManifest: every required image has its id
      digest: manifest.imageDigests?.[key],
      size: manifest.imageSizes?.[key],
    };
  });
  const archive = manifest.imageArchive
    ? {
        path: ensureRuntimeChild(root, manifest.imageArchive, "imageArchive"),
        sha256: manifest.imageArchiveSha256 ?? "",
      }
    : null;
  const result = await fetchImages({
    images,
    archive,
    pull: manifest.imagePull === true,
    runDocker: (args, options) => runDocker(args, options),
    log,
    onProgress,
  });
  log("info", "docker.images.ready", {
    releaseId: manifest.releaseId,
    reused: result.reused.length,
    tagged: result.tagged,
    loaded: result.loaded,
    pulled: result.pulled,
  });
}

async function neo4jPassword(): Promise<string> {
  const existing = await getSecret(NEO4J_PASSWORD_SECRET_ID);
  if (existing) return existing;
  const created = randomBytes(32).toString("base64url");
  await setSecret(NEO4J_PASSWORD_SECRET_ID, created);
  return created;
}

// 컨테이너 안 유닉스 소켓은 trust(pg_hba `local all all trust`)라 비밀번호 없이 들어가 바꾼다.
// healthcheck 는 pg_isready 뿐이라 첫 기동의 초기화 서버에 걸릴 수 있어 몇 번 다시 해 본다.
// 끝내 안 되면 경고만 남긴다 — 비밀번호가 맞으면 그대로 뜨고, 틀리면 다음 `up` 이 실제 원인을 보인다.
async function syncGraphPassword(
  root: string,
  manifest: RuntimeManifest,
  env: NodeJS.ProcessEnv,
  password: string,
): Promise<void> {
  if (!/^[A-Za-z0-9_-]+$/.test(password)) throw new Error("docker.graph_password_invalid");
  const args = composeArgs(root, manifest, [
    "exec", "-T", "graph-db", "psql", "-v", "ON_ERROR_STOP=1", "-q", "-U", GRAPH_USER, "-d", GRAPH_DESIGN,
  ]);
  const input = `ALTER ROLE "${GRAPH_USER}" WITH PASSWORD '${password}';\n`;
  let lastError: unknown = null;
  for (let attempt = 1; attempt <= 10; attempt++) {
    try {
      await runDocker(args, { env, secret: password, input, timeoutMs: 30_000 });
      log("info", "docker.graph_password.synced", { user: GRAPH_USER, attempt });
      return;
    } catch (err) {
      lastError = err;
      await new Promise((resolve) => setTimeout(resolve, 2_000));
    }
  }
  log("warn", "docker.graph_password.sync_failed", {
    user: GRAPH_USER,
    message: lastError instanceof Error ? lastError.message : String(lastError),
  });
}

// 지난 기동에서 (예: 비밀번호가 어긋나) 재시작을 되풀이하던 서비스는 재시작 대기(백오프) 중이라,
// `up --wait` 가 그 unhealthy 를 보자마자 실패한다 — 그대로 두면 몇십 초 뒤 혼자 살아나도 앱은 이미 멈췄다.
// 비밀번호를 맞춘 뒤 그런 서비스만 다시 시작시켜 대기를 끊는다.
async function restartFailingServices(
  root: string,
  manifest: RuntimeManifest,
  env: NodeJS.ProcessEnv,
  password: string,
): Promise<void> {
  const listed = await runDocker(
    composeArgs(root, manifest, ["ps", "--all", "--format", "{{.Service}}\t{{.State}}\t{{.Health}}"]),
    { env, secret: password, timeoutMs: 30_000 },
  );
  const failing = listed
    .split("\n")
    .map((line) => line.trim().split("\t"))
    .filter(([service, state, health]) => service && (state === "restarting" || health === "unhealthy"))
    .map(([service]) => service as string);
  if (failing.length === 0) return;
  log("info", "docker.stack.restarting_failing", { services: failing });
  await runDocker(composeArgs(root, manifest, ["restart", ...failing]), { env, secret: password });
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
    // ⚠ 개수로 세면 어긋난다. 2026-11-05 까지 이 검사는 `!== 4` 였는데 `createState` 는
    //   **다섯**을 썼다 — 그래서 저장된 상태가 **매번 버려지고** 호스트 포트가 실행마다
    //   바뀌었다(50242… → 58832… 로 바뀌는 것을 실측). 키 집합으로 센다.
    const expected: (keyof DockerStackPorts)[] = [
      "neo4j",
      "graphPg",
      "analyzer",
      "gateway",
      "architect",
      "wireframe",
    ];
    // age-fabric adds og-fabric's port ("fabric"); the default configuration never has it.
    const optional: (keyof DockerStackPorts)[] = ["fabric"];
    const keys = Object.keys(parsed.ports);
    if (
      expected.some((k) => !keys.includes(k)) ||
      keys.some((k) => !expected.includes(k as keyof DockerStackPorts) && !optional.includes(k as keyof DockerStackPorts))
    ) {
      return null;
    }
    const ports = Object.values(parsed.ports);
    if (ports.some((port) => !Number.isInteger(port) || port < 1024 || port > 65535)) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

async function createState(releaseId: string, variant: DeployVariant = "ontological"): Promise<PersistedDockerState> {
  const state: PersistedDockerState = {
    schemaVersion: STATE_SCHEMA_VERSION,
    releaseId,
    ports: {
      neo4j: await pickFreePort(),
      graphPg: await pickFreePort(),
      analyzer: await pickFreePort(),
      gateway: await pickFreePort(),
      architect: await pickFreePort(),
      wireframe: await pickFreePort(),
    },
  };
  if (variant === "age-fabric") state.ports.fabric = await pickFreePort();
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
    COMPOSE_PROJECT_NAME: projectNameOf(manifest),
    ROBO_RELEASE_ID: manifest.releaseId,
    ROBO_IMAGE_GRAPH_DB: manifest.images.graphDb,
    ROBO_IMAGE_GRAPH_BOLT: manifest.images.graphBolt,
    // ⚠ graph 이름 셋은 이 가지에서 **상수**다. 납품 가지는 매니페스트
    //   (`manifest.graphs`)에서 읽는다 — 거기서는 설치마다 달라질 수 있어서다.
    //   ⚠ 설계와 분석이 **같으면 엔진이 기동을 거절한다**(분석이 설계를 지운다).
    ROBO_GRAPH_USER: GRAPH_USER,
    ROBO_GRAPH_DESIGN: GRAPH_DESIGN,
    ROBO_GRAPH_ANALYSIS: GRAPH_ANALYSIS,
    ROBO_IMAGE_ANALYZER: manifest.images.analyzer,
    ROBO_IMAGE_CATALOG: manifest.images.catalog,
    ROBO_IMAGE_FABRIC: manifest.images.fabric,
    ROBO_IMAGE_PARSER: manifest.images.parser,
    ROBO_IMAGE_GATEWAY: manifest.images.gateway,
    ROBO_IMAGE_WIREFRAME: manifest.images.wireframe,
    ROBO_NEO4J_PASSWORD: password,
    ROBO_NEO4J_PORT: String(state.ports.neo4j),
    ROBO_GRAPH_PG_LOCAL_PORT: String(state.ports.graphPg),
    ROBO_ANALYZER_PORT: String(state.ports.analyzer),
    ROBO_GATEWAY_PORT: String(state.ports.gateway),
    ROBO_ARCHITECT_API_PORT: String(state.ports.architect),
    ROBO_WIREFRAME_PORT: String(state.ports.wireframe),
  };
}

/** age-fabric: what compose.age-fabric.yml reads on top of the common environment. */
function ageFabricEnvironment(
  manifest: RuntimeManifest,
  state: PersistedDockerState,
  secrets: AgeFabricSecrets,
  internalToken: string,
): NodeJS.ProcessEnv {
  if (!manifest.images.fabricDb || !state.ports.fabric) throw new Error("runtime.manifest_invalid: images.fabricDb");
  return {
    ROBO_IMAGE_FABRIC_DB: manifest.images.fabricDb,
    ROBO_AGE_ADMIN_PASSWORD: secrets.adminPassword,
    ROBO_FABRIC_DB_PASSWORD: secrets.fabricDbPassword,
    ROBO_FABRIC_QUERY_PASSWORD: secrets.fabricQueryPassword,
    ROBO_FABRIC_SERVICE_TOKEN: secrets.fabricServiceToken,
    // new every boot: only this process can use og-fabric's secrets channel
    ROBO_FABRIC_INTERNAL_TOKEN: internalToken,
    ROBO_FABRIC_PORT: String(state.ports.fabric),
  };
}

function composeArgs(root: string, manifest: RuntimeManifest, command: string[]): string[] {
  const composeFile = ensureRuntimeChild(root, manifest.composeFile, "composeFile");
  return ["compose", "--project-name", projectNameOf(manifest), "--file", composeFile, ...command];
}

export async function startDockerStack(onProgress?: ProgressListener): Promise<DockerStackRuntime> {
  if (current) return current;
  const root = runtimeDirectory();
  const manifest = readManifest(root);
  await ensureEnvironmentSnapshots(root, manifest);
  await ensureDockerDaemon();
  await ensureImages(root, manifest, onProgress);

  const password = await neo4jPassword();
  const variant = deployVariantOf(manifest.deployVariant);
  if (variant === "age-fabric") {
    const state = loadPersistedState(manifest.releaseId) ?? (await createState(manifest.releaseId, variant));
    if (!state.ports.fabric) state.ports.fabric = await pickFreePort();
    await startAgeFabricServices(root, manifest, state, password);
    return await finishStart(root, manifest, state, password);
  }
  const COMPOSE_PROJECT_NAME = projectNameOf(manifest);
  const state = loadPersistedState(manifest.releaseId) ?? (await createState(manifest.releaseId));
  const env = composeEnvironment(manifest, state, password);

  log("info", "docker.stack.starting", {
    releaseId: manifest.releaseId,
    projectName: COMPOSE_PROJECT_NAME,
  });
  // ⚠ graph-db 를 **먼저** 올려 역할 비밀번호를 이 설치의 값으로 맞춘 뒤 나머지를 올린다.
  //   POSTGRES_PASSWORD 는 볼륨을 처음 만들 때만 쓰인다 — 앱 데이터만 지우고 다시 설치했거나,
  //   다른 설치(예전 판 · 개발 실행)가 같은 프로젝트로 만든 볼륨이면 비밀번호가 어긋나
  //   fabric 이 `password authentication failed for user "robo"` 로 죽는다.
  await runDocker(
    composeArgs(root, manifest, ["up", "--detach", "--wait", "--wait-timeout", "300", "graph-db"]),
    { env, secret: password },
  );
  await syncGraphPassword(root, manifest, env, password);
  await restartFailingServices(root, manifest, env, password);
  await runDocker(composeArgs(root, manifest, ["up", "--detach", "--wait", "--wait-timeout", "300"]), {
    env,
    secret: password,
  });
  return await finishStart(root, manifest, state, password);
}

/** What the app's own processes need once the stack is up (both configurations). */
async function finishStart(
  root: string,
  manifest: RuntimeManifest,
  state: PersistedDockerState,
  password: string,
): Promise<DockerStackRuntime> {
  const COMPOSE_PROJECT_NAME = projectNameOf(manifest);
  const hostNeo4jUri = `bolt://127.0.0.1:${state.ports.neo4j}`;
  process.env.ROBO_GATEWAY_URL = `http://127.0.0.1:${state.ports.gateway}`;
  process.env.ROBO_CLUSTER_MCP_URL = `http://127.0.0.1:${state.ports.analyzer}/robo/mcp/`;
  // ⚠ 이 한 줄이 Architect 를 렌더러에 붙인다. 없으면 컨테이너는 뜨는데
  //   `open_pencil_client` 가 기본값 `http://localhost:7610` 을 보고 못 찾아,
  //   와이어프레임이 **오류 없이** 빈다(is_available() 이 False 를 돌려준다).
  process.env.WIREFRAME_SERVICE_URL = `http://127.0.0.1:${state.ports.wireframe}`;
  process.env.ROBO_NEO4J_URI = hostNeo4jUri;
  // Bolt 사용자는 엔진의 PG 역할 그대로다 — "neo4j" 로 붙으면 인증이 실패한다.
  process.env.ROBO_NEO4J_USER = GRAPH_USER;
  process.env.ROBO_NEO4J_PASSWORD = password;
  // 백엔드가 볼 프로젝트 그래프 — 지난번에 들어간 프로젝트가 있으면 그것으로 띄워
  // 런처에서 같은 프로젝트로 들어갈 때 백엔드를 다시 띄우지 않게 한다(enter 가 바꾼다).
  process.env.ROBO_NEO4J_DATABASE = (await lastProjectGraph()) ?? GRAPH_DESIGN;
  await ensureBundledConnection({
    uri: hostNeo4jUri,
    user: GRAPH_USER,
    password,
    database: GRAPH_DESIGN,
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

async function lastProjectGraph(): Promise<string | null> {
  const settings = await loadSettings();
  const profile = settings.lastProfile;
  if (!profile?.graph) return null;
  const connection = settings.savedConnections.find((c) => c.id === profile.connectionId);
  return connection?.source === "bundled" ? profile.graph : null;
}

export async function stopDockerStack(): Promise<void> {
  const runtime = current;
  if (!runtime) return;
  const password = await neo4jPassword();
  if (ageFabric) {
    // the environment the stack was started with (its per-boot token included)
    await runDocker(composeArgs(runtime.runtimeDir, runtime.manifest, ["stop"]), {
      env: ageFabric.env,
      secrets: ageFabric.redact,
    });
    ageFabric = null;
    current = null;
    log("info", "docker.stack.stopped", { projectName: runtime.projectName });
    return;
  }
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
  log("info", "docker.stack.stopped", { projectName: runtime.projectName });
}

// ─────────────────────────────────────────────────────────────── age-fabric

interface AgeFabricRuntime {
  env: NodeJS.ProcessEnv;
  /** every secret in env: never in an error message */
  redact: string[];
  client: FabricClient;
}

let ageFabric: AgeFabricRuntime | null = null;

/** The keychain-aware store age-fabric-stack.ts writes through (safeStorage for source passwords). */
const secretStore: SecretStoreLike = {
  get: getSecret,
  set: (id, value, options) => setSecret(id, value, options),
  remove: deleteSecret,
};

/** og-fabric's client while the age-fabric stack runs (null otherwise): the IPC handlers use it. */
export function getFabricClient(): FabricClient | null {
  return ageFabric?.client ?? null;
}

/**
 * The configuration this start uses, read from the runtime manifest before the stack is up (the
 * shell shows it while the containers start). null when the manifest cannot be read yet.
 */
export function readRuntimeProfile(): RuntimeProfile | null {
  try {
    return profileOf(deployVariantOf(readManifest().deployVariant));
  } catch {
    return null;
  }
}

export function getDeployVariant(): DeployVariant | null {
  return current ? deployVariantOf(current.manifest.deployVariant) : null;
}

/**
 * compose.age-fabric.yml: the two databases first (roles, graphs, passwords of this install), then
 * og-fabric and the gateway (the keychain secrets handed over, the v1 migration once), then the rest.
 */
async function startAgeFabricServices(
  root: string,
  manifest: RuntimeManifest,
  state: PersistedDockerState,
  password: string,
): Promise<void> {
  const secrets = await ensureAgeFabricSecrets(secretStore);
  const internalToken = newToken();
  const env = {
    ...composeEnvironment(manifest, state, password),
    ...ageFabricEnvironment(manifest, state, secrets, internalToken),
  };
  const redact = [
    password,
    secrets.adminPassword,
    secrets.fabricDbPassword,
    secrets.fabricQueryPassword,
    secrets.fabricServiceToken,
    internalToken,
  ];
  const compose = (command: string[], options: { input?: string; timeoutMs?: number } = {}) =>
    runDocker(composeArgs(root, manifest, command), { env, secrets: redact, ...options });
  const up = (...services: string[]) => compose(["up", "--detach", "--wait", "--wait-timeout", "300", ...services]);
  const exec: ExecInService = (service, args, options = {}) =>
    compose(["exec", "-T", service, ...args], { input: options.input, timeoutMs: 60_000 });

  log("info", "docker.stack.starting", {
    releaseId: manifest.releaseId,
    projectName: projectNameOf(manifest),
    variant: "age-fabric",
  });
  await up("age-db", "fabric-db");
  await prepareAgeDb(exec, { user: GRAPH_USER, password, graphs: [GRAPH_DESIGN, GRAPH_ANALYSIS] }, log);
  await prepareFabricDb(exec, secrets);
  await restartFailingServices(root, manifest, env, password);
  await up("fabric", "age-bolt");

  const client = new FabricClient(
    `http://127.0.0.1:${state.ports.fabric}`,
    secrets.fabricServiceToken,
    internalToken,
  );
  await client.waitHealthy();
  await deliverKeychainSecrets(client, secretStore, log);
  try {
    await migrateV1Plaintext(
      {
        findV1: () => findV1GraphDb(),
        runMigrate: (extra, args) => runFabricMigrate(root, manifest, env, redact, extra, args),
        store: secretStore,
        markerFile: path.join(getDataDir(), "runtime", "age-fabric-migration.json"),
        log,
      },
      { user: GRAPH_USER, password, database: GRAPH_DESIGN },
    );
  } catch (err) {
    // the stack still starts: migrated datasources are not lost (v1 keeps them), the next start tries again
    log("warn", "fabric.migrate.error", { message: err instanceof Error ? err.message : String(err) });
  }
  await up();
  ageFabric = { env, redact, client };
}

/** The default configuration's graph-db, if one is running (the plaintext migration reads it). */
async function findV1GraphDb(): Promise<{ hostPort: number } | null> {
  const project = process.env.ROBO_V1_COMPOSE_PROJECT || DEFAULT_COMPOSE_PROJECT_NAME;
  const names = await runDocker(
    [
      "ps",
      "--filter",
      `label=com.docker.compose.project=${project}`,
      "--filter",
      "label=com.docker.compose.service=graph-db",
      "--format",
      "{{.Names}}",
    ],
    { timeoutMs: 30_000 },
  );
  const name = names.split("\n").map((n) => n.trim()).find(Boolean);
  if (!name) return null;
  const published = await runDocker(["port", name, "5432/tcp"], { timeoutMs: 30_000 }).catch(() => "");
  const port = Number(published.split("\n")[0]?.split(":").pop());
  return Number.isInteger(port) && port > 0 ? { hostPort: port } : null;
}

/**
 * og-fabric-migrate inside the fabric container. Its standard output holds the secrets, so this
 * never goes through runDocker (whose error message carries the output) and never logs it.
 */
async function runFabricMigrate(
  root: string,
  manifest: RuntimeManifest,
  env: NodeJS.ProcessEnv,
  redact: string[],
  extra: Record<string, string>,
  args: string[],
): Promise<{ stdout: string; stderr: string; code: number }> {
  const passEnv = Object.keys(extra).flatMap((name) => ["-e", name]);
  const command = composeArgs(root, manifest, ["exec", "-T", ...passEnv, "fabric", ...args]);
  return await new Promise((resolve) => {
    execFile(
      "docker",
      command,
      { env: { ...env, ...extra }, timeout: 5 * 60_000, windowsHide: true, maxBuffer: 16 * 1024 * 1024 },
      (error, stdout, stderr) => {
        const code = error ? (typeof (error as { code?: unknown }).code === "number" ? (error as { code: number }).code : -1) : 0;
        let report = String(stderr ?? "");
        for (const s of [...redact, ...Object.values(extra)]) if (s) report = report.split(s).join("***");
        resolve({ stdout: String(stdout ?? ""), stderr: report, code });
      },
    );
  });
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
