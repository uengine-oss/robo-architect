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
import net from "node:net";

import { pickFreePort } from "./ports";
import type { ManagedServiceId } from "../shared/runtime-contract";
import { getSecret, setSecret } from "./secret-store";

const MANIFEST_NAME = "runtime-manifest.json";
// 2: pdf2bpmn 포트가 늘어 포트가 넷에서 다섯이 됐다. 옛 상태는 버리고 다시 뽑는다.
// 3: 저장소가 Neo4j → Ontological 로 바뀌며 `ports.neo4j` 가 `ports.graph` 가 됐다.
//    키 이름이 바뀌었으므로 옛 상태는 읽지 않는다(읽으면 포트가 `undefined` 가 된다).
const STATE_SCHEMA_VERSION = 3;
// 4: images.neo4j → images.graphDb + images.graphBolt, graphs 항목 추가.
const MANIFEST_SCHEMA_VERSION = 4;
const COMPOSE_PROJECT_NAME = "robo-architect-desktop";
// 저장소 비밀번호. **이제 Postgres role 의 비밀번호다** — Bolt 게이트웨이는 받은
// 자격증명을 그대로 Postgres 에 넘긴다(사용자 = role). 이름을 엔진 중립으로 옮기되,
// 이미 깔린 앱의 키체인 항목을 잃지 않도록 옛 id 를 한 번 읽어 옮긴다.
const GRAPH_PASSWORD_SECRET_ID = "runtime.docker.graph.password";
const LEGACY_NEO4J_PASSWORD_SECRET_ID = "runtime.docker.neo4j.password";
// graph 이름 규칙 — `ontological-db/docker/runtime/10-ontological-init.sh` 와 **같은 식**.
// 이름이 그대로 SQL 문자열이 된다. 양쪽이 어긋나면 컨테이너는 뜨는데 앱이 못 읽는다.
const GRAPH_NAME_PATTERN = /^[A-Za-z_][A-Za-z0-9_]{0,62}$/;
const DOCKER_COMMAND_TIMEOUT_MS = 10 * 60_000;

export interface RuntimeManifest {
  schemaVersion: number;
  releaseId: string;
  composeFile: string;
  imageArchive: string;
  imageArchiveSha256: string;
  images: {
    /** Ontological 확장이 든 PostgreSQL. */
    graphDb: string;
    /** Neo4j Bolt 프로토콜 게이트웨이. 앱 코드는 이쪽만 본다. */
    graphBolt: string;
    mindsdb: string;
    analyzer: string;
    catalog: string;
    fabric: string;
    parser: string;
    gateway: string;
    pdf2bpmn: string;
  };
  imageIds: Record<keyof RuntimeManifest["images"], string>;
  /**
   * 설계 graph 와 분석 graph 의 이름. **반드시 달라야 한다** — 분석은 대상 graph 를
   * 통째로 비우고 다시 쓰므로, 같으면 분석이 설계를 지운다(FR-008).
   * 컨테이너 엔트리포인트도 같은 검사를 하지만 여기서 먼저 막는다: 거기서 걸리면
   * 증상이 "컨테이너가 안 뜬다" 로만 보인다.
   */
  graphs: {
    /** Postgres role 이자 Bolt 로그인 사용자. */
    user: string;
    design: string;
    analysis: string;
  };
  architect: {
    python: string;
    app: string;
    entrypoint: string;
  };
  environment: Record<
    "analyzer" | "catalog" | "fabric" | "parser" | "gateway" | "pdf2bpmn" | "architect",
    { file: string; sha256: string }
  >;
  source: Record<string, string>;
}

export interface DockerStackPorts {
  /** Bolt 게이트웨이의 호스트 포트. 엔진이 아니라 **프로토콜**을 가리키는 이름이다. */
  graph: number;
  analyzer: number;
  gateway: number;
  architect: number;
  /** 문서→BPMN 을 뽑는 자체 호스팅 서비스. 루프백에만 연다. */
  pdf2bpmn: number;
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
    "graphDb",
    "graphBolt",
    "mindsdb",
    "analyzer",
    "catalog",
    "fabric",
    "parser",
    "gateway",
    "pdf2bpmn",
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
  const graphs = manifest.graphs;
  if (!graphs || typeof graphs !== "object") {
    throw new Error("runtime.manifest_invalid: graphs");
  }
  for (const key of ["user", "design", "analysis"] as const) {
    if (!GRAPH_NAME_PATTERN.test(graphs[key] ?? "")) {
      throw new Error(`runtime.manifest_invalid: graphs.${key}`);
    }
  }
  if (graphs.design === graphs.analysis) {
    // 조용히 넘어가면 첫 분석에서 설계가 사라진다. 기동 전에 멈춘다.
    throw new Error("runtime.manifest_invalid: graphs.design must differ from graphs.analysis");
  }
  ensureRuntimeChild(root, manifest.composeFile, "composeFile");
  ensureRuntimeChild(root, manifest.imageArchive, "imageArchive");
  ensureRuntimeChild(root, manifest.architect.python, "architect.python");
  ensureRuntimeChild(root, manifest.architect.app, "architect.app");
  if (!/^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*$/.test(manifest.architect.entrypoint)) {
    throw new Error("runtime.manifest_invalid: architect.entrypoint");
  }
  for (const required of ["analyzer", "catalog", "fabric", "parser", "gateway", "pdf2bpmn", "architect"]) {
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

async function graphPassword(): Promise<string> {
  const existing = await getSecret(GRAPH_PASSWORD_SECRET_ID);
  if (existing) return existing;
  // 저장소를 바꾸기 전에 깔린 앱은 옛 id 에 들고 있다. **새로 뽑으면 안 된다** —
  // 볼륨의 role 비밀번호는 그대로인데 앱만 다른 값을 쓰게 되어 인증만 실패한다.
  const legacy = await getSecret(LEGACY_NEO4J_PASSWORD_SECRET_ID);
  if (legacy) {
    await setSecret(GRAPH_PASSWORD_SECRET_ID, legacy);
    log("info", "docker.graph_password.migrated", { from: LEGACY_NEO4J_PASSWORD_SECRET_ID });
    return legacy;
  }
  const created = randomBytes(32).toString("base64url");
  await setSecret(GRAPH_PASSWORD_SECRET_ID, created);
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
    if (ports.length !== 5 || ports.some((port) => !Number.isInteger(port) || port < 1024 || port > 65535)) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

/**
 * 묵은 포트를 되잡는다 (spec 058 T040).
 *
 * `loadPersistedState` 는 **범위만** 본다 — 1024~65535 면 통과다. 그런데 앱이 꺼져 있던
 * 동안 다른 프로그램이 그 포트를 잡았을 수 있다. 그대로 쓰면 `compose up` 이
 * `bind: address already in use` 로 죽는데, 그 메시지는 **어느 서비스의 어느 포트인지**
 * 를 말해 주지 않는다.
 *
 * ## 이어받는 경우에는 막혀 있는 것이 정상이다
 *
 * 우리 컨테이너가 이미 그 포트를 쥐고 있으면 "막혀 있다"로 보이지만 그건 정상이다.
 * 그래서 **우리가 쥔 포트 목록을 받아 제외한다.** 이걸 빠뜨리면 재부팅마다 포트가
 * 바뀌고, 그때마다 외부 도구의 설정이 깨진다.
 *
 * ## 조용히 바꾸지 않는다
 *
 * 바뀐 포트를 알려야 한다. 외부 도구(브라우저 북마크·스크립트)가 옛 포트를 쥐고
 * 있으면 "갑자기 안 된다"가 된다. 그래서 바뀐 목록을 돌려준다.
 */
export interface PortReclaim {
  ports: DockerStackPorts;
  /** 바뀐 것만. 비어 있으면 그대로 쓴 것이다. */
  changed: Array<{ key: keyof DockerStackPorts; from: number; to: number }>;
}

export async function reclaimBlockedPorts(
  ports: DockerStackPorts,
  options: {
    /** 우리가 이미 쥐고 있는 포트 — 막혀 있어도 정상이다. */
    heldByUs?: number[];
    /** 포트가 쓸 수 있는지 보는 함수. 검사에서 갈아 끼운다. */
    isFree?: (port: number) => Promise<boolean>;
    /** 새 포트를 뽑는 함수. */
    pick?: () => Promise<number>;
  } = {},
): Promise<PortReclaim> {
  const held = new Set(options.heldByUs ?? []);
  const isFree = options.isFree ?? defaultIsFree;
  const pick = options.pick ?? (() => pickFreePort());

  const next = { ...ports };
  const changed: PortReclaim["changed"] = [];
  // 새로 뽑은 포트끼리 겹치지 않게 모아 둔다. 한 번에 여러 개를 바꿀 때 같은 번호가
  // 두 번 나오면 두 서비스가 같은 포트를 잡으려 든다.
  const taken = new Set<number>(Object.values(ports));

  for (const key of Object.keys(next) as Array<keyof DockerStackPorts>) {
    const current = next[key];
    if (held.has(current) || (await isFree(current))) continue;
    let candidate = await pick();
    for (let attempt = 0; attempt < 8 && taken.has(candidate); attempt += 1) {
      candidate = await pick();
    }
    taken.add(candidate);
    next[key] = candidate;
    changed.push({ key, from: current, to: candidate });
  }
  return { ports: next, changed };
}

async function defaultIsFree(port: number): Promise<boolean> {
  return await new Promise<boolean>((resolve) => {
    const server = net.createServer();
    server.unref();
    server.once("error", () => resolve(false));
    server.listen({ host: "127.0.0.1", port }, () => {
      server.close(() => resolve(true));
    });
  });
}

async function createState(releaseId: string): Promise<PersistedDockerState> {
  const state: PersistedDockerState = {
    schemaVersion: STATE_SCHEMA_VERSION,
    releaseId,
    ports: {
      graph: await pickFreePort(),
      analyzer: await pickFreePort(),
      gateway: await pickFreePort(),
      architect: await pickFreePort(),
      pdf2bpmn: await pickFreePort(),
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
    ROBO_IMAGE_GRAPH_DB: manifest.images.graphDb,
    ROBO_IMAGE_GRAPH_BOLT: manifest.images.graphBolt,
    ROBO_IMAGE_MINDSDB: manifest.images.mindsdb,
    ROBO_IMAGE_ANALYZER: manifest.images.analyzer,
    ROBO_IMAGE_CATALOG: manifest.images.catalog,
    ROBO_IMAGE_FABRIC: manifest.images.fabric,
    ROBO_IMAGE_PARSER: manifest.images.parser,
    ROBO_IMAGE_GATEWAY: manifest.images.gateway,
    ROBO_IMAGE_PDF2BPMN: manifest.images.pdf2bpmn,
    // 이름은 `ROBO_NEO4J_*` 그대로 둔다 — 컨테이너 안의 서비스들이 Neo4j 드라이버로
    // 붙고, 그 드라이버가 읽는 변수 이름이다. **엔진이 아니라 프로토콜의 이름이다.**
    ROBO_NEO4J_PASSWORD: password,
    ROBO_NEO4J_PORT: String(state.ports.graph),
    ROBO_GRAPH_USER: manifest.graphs.user,
    ROBO_GRAPH_DESIGN: manifest.graphs.design,
    ROBO_GRAPH_ANALYSIS: manifest.graphs.analysis,
    ROBO_ANALYZER_PORT: String(state.ports.analyzer),
    ROBO_GATEWAY_PORT: String(state.ports.gateway),
    ROBO_ARCHITECT_API_PORT: String(state.ports.architect),
    ROBO_PDF2BPMN_PORT: String(state.ports.pdf2bpmn),
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

  const password = await graphPassword();
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

  const hostBoltUri = `bolt://127.0.0.1:${state.ports.graph}`;
  process.env.ROBO_GATEWAY_URL = `http://127.0.0.1:${state.ports.gateway}`;
  // 문서→BPMN 은 **안에서 돈다.** 이 줄이 없으면 Architect 는 번들 `.env` 의
  // 값(= 바깥 SaaS)이나 빈 값을 쓰고, 사내망에서는 그 호출이 막힌다. 막히면
  // 폴백으로 내려가는데 **그게 눈에 안 띈다** — 화면에는 그대로 BPM 이 나온다.
  // (폴백 품질이 실제로 얼마나 나쁜지는 아직 안 쟀다.)
  // `load_dotenv()` 는 기본이 override=False 라 여기서 준 값이 번들 .env 를 이긴다.
  process.env.PDF2BPMN_FACADE_URL = `http://127.0.0.1:${state.ports.pdf2bpmn}`;
  process.env.ROBO_CLUSTER_MCP_URL = `http://127.0.0.1:${state.ports.analyzer}/robo/mcp/`;
  process.env.ROBO_NEO4J_URI = hostBoltUri;
  // 사용자 = Postgres role. Bolt 게이트웨이는 받은 자격증명을 Postgres 에 그대로 넘긴다.
  process.env.ROBO_NEO4J_USER = manifest.graphs.user;
  process.env.ROBO_NEO4J_PASSWORD = password;
  // **설계와 분석을 갈라 준다.** 예전에는 둘이 같은 값이었는데, 그건 무능이 아니라
  // 제약이었다 — 번들 이미지가 Neo4j Community 라 database 가 하나뿐이었다.
  // 이제 갈라지므로, 여기서 같은 값을 주면 분석이 설계를 지운다.
  process.env.ROBO_NEO4J_DATABASE = manifest.graphs.design;
  process.env.ROBO_ANALYZER_NEO4J_DATABASE = manifest.graphs.analysis;
  await ensureBundledConnection({
    uri: hostBoltUri,
    user: manifest.graphs.user,
    password,
    database: manifest.graphs.design,
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
    graphPort: state.ports.graph,
    analyzerPort: state.ports.analyzer,
    gatewayPort: state.ports.gateway,
  });
  return current;
}

/**
 * 앱이 소유한 컨테이너만 **멈춘다.** 지우지 않는다 (spec 058 T041 · FR-015).
 *
 * `docker compose stop` 이고 `down` 이 아니다. `down -v` 는 named volume 을 지우고,
 * 그건 사용자 데이터를 지우는 것이다. `down` 도 컨테이너를 지워 다음 기동을 느리게
 * 한다(2GB tar 재적재).
 *
 * **호출자가 0건이었다.** 내리는 길이 코드에 있는데 화면에서 닿을 수 없었다 —
 * 사용자는 Docker Desktop 을 직접 열어 끄는 수밖에 없었고, 그러면 우리 것과 남의 것을
 * 가려 주지 않는다. `runtime:stopEngine` 이 이 함수를 부른다.
 */
export async function stopDockerStack(): Promise<void> {
  const runtime = current;
  if (!runtime) return;
  const password = await graphPassword();
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

/**
 * 한 서비스만 다시 올린다 (spec 058 T041 · FR-018).
 *
 * `compose up --detach <service>` 다. 스택 전체를 흔들지 않는다 — 하나가 죽었는데
 * 전부 재기동하면 **멀쩡한 나머지의 연결이 끊긴다.**
 *
 * `architect` 는 컨테이너가 아니라 호스트 프로세스다. 그쪽은 `backend:retry` 가 담당하고
 * 여기서는 거부한다 — 한 사실을 두 곳에서 처리하면 어느 쪽이 이겼는지 모른다.
 */
export async function restartOwnedService(serviceId: ManagedServiceId): Promise<void> {
  if (serviceId === "architect") {
    throw new Error("docker.not_a_container: architect 는 backend:retry 로 되살린다");
  }
  const runtime = current;
  if (!runtime) throw new Error("docker.stack_not_started");
  const persisted = loadPersistedState(runtime.releaseId);
  if (!persisted) throw new Error("docker.state_missing: cannot restart safely");
  const password = await graphPassword();
  // 서비스 id 와 compose 서비스 이름이 다른 자리가 있다(`graph` → 컨테이너 둘).
  const targets = COMPOSE_SERVICES_OF[serviceId] ?? [serviceId];
  await runDocker(
    composeArgs(runtime.runtimeDir, runtime.manifest, ["up", "--detach", ...targets]),
    { env: composeEnvironment(runtime.manifest, persisted, password), secret: password },
  );
  log("info", "docker.service.restarted", { serviceId, targets: targets.join(",") });
}

/**
 * 서비스 id → compose 서비스 이름.
 *
 * **`graph` 는 컨테이너가 둘이다.** 앱이 보는 것은 Bolt 하나지만 되살릴 때는 둘을
 * 같이 봐야 한다 — Postgres 만 올리고 Bolt 를 안 올리면 **psql 은 되는데 앱만 죽는**
 * 상태가 된다. 이 저장소가 반복해 밟은 함정이다.
 */
const COMPOSE_SERVICES_OF: Partial<Record<ManagedServiceId, string[]>> = {
  graph: ["graph-db", "graph-bolt"],
};

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
