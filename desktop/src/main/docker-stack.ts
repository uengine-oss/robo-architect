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
import {
  graphEndpoint,
  graphTopology,
  type GraphTopology,
} from "./graph-topology";
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
// 4: 호스트 Architect API 가 Ontological PostgreSQL 에 직접 붙도록 graphPg 포트를 추가.
// 5: open-pencil 와이어프레임 렌더러(7610) 가 스택에 들어와 포트가 하나 늘었다.
//    **옛 상태를 그대로 읽으면 `ports.wireframe` 이 undefined 가 되고**, compose 는
//    `ROBO_WIREFRAME_PORT` 가 빈 채로 포트 매핑을 만들려다 죽는다. 버리고 다시 뽑는다.
const STATE_SCHEMA_VERSION = 5;
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
    /** open-pencil 와이어프레임 렌더러. 없으면 sceneGraph 가 조용히 빈다. */
    wireframe: string;
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
  /**
   * 이 릴리스가 **일부러 굽지 않은** 비밀의 이름들. 값은 없다.
   *
   * 예전 릴리스는 `robo-workspace/.env` 의 값을 `config/*.env` 에 그대로
   * 베껴 넣었다. 그래서 같은 OpenAI 키가 설치본 안에 5개 파일·7개 이름으로
   * 들어 있었다(2026-09-23 감사). 이제 릴리스가 빼고, 설치한 사람이
   * 환경변수로 넣는다 — 무엇을 넣어야 하는지는 이 목록이 말해 준다.
   *
   * 옛 매니페스트에는 없는 필드다. 없으면 검사도 없다(하위 호환).
   */
  credentialNames?: string[];
  /**
   * 이 릴리스가 **로그인을 강제하는지**. 굽는 쪽의 의도이고, 실제 스위치는
   * `architect/app/.env` 의 `AUTH_ENFORCE` 다. 여기 적어 두는 이유는
   * 아래 `assertAuthPostureNotOverridden` 이 "이건 잠긴 납품본인가" 를 알아야
   * 하기 때문이다. 옛 매니페스트에는 없다(하위 호환).
   */
  authEnforced?: boolean;
  /** `none` 이면 사내 인증이 아니다. `posco`·`swp` 면 SSO 납품본이다. */
  authProvider?: string;
  /**
   * `delivery` 또는 `internal-test`. `robo.ps1` 의 `Get-ReleaseAuthPosture` 가 정한다.
   *
   * 사내망 밖에서는 인증을 켠 설치본으로 화면을 밟을 수 없다. 그래서 길을
   * 없애지 않고 **이름을 붙였다** — `internal-test` 로 구우면 인증을 끈 빌드를
   * 만들 수 있고, 그 사실이 여기 남는다. 없으면 `delivery` 로 본다(하위 호환):
   * 모르는 빌드를 느슨한 쪽으로 가정하면 안 된다.
   */
  releaseChannel?: string;
  source: Record<string, string>;
}

export interface DockerStackPorts {
  /** Bolt 게이트웨이의 호스트 포트. 엔진이 아니라 **프로토콜**을 가리키는 이름이다. */
  graph: number;
  /** Ontological PostgreSQL의 호스트 포트. Architect 사용자/프로젝트 저장소가 쓴다. */
  graphPg: number;
  analyzer: number;
  gateway: number;
  architect: number;
  /** 문서→BPMN 을 뽑는 자체 호스팅 서비스. 루프백에만 연다. */
  pdf2bpmn: number;
  /** open-pencil 와이어프레임 렌더러(JSX→SceneGraph). 루프백에만 연다. */
  wireframe: number;
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
    "wireframe",
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
  // **imageArchive 는 여기서 존재를 보지 않는다.** 설치 파일 안에 넣지 않으므로
  // (NSIS 32비트 한계 — `resolveImageArchive` 주석) 패키지 밖에 있을 수 있다.
  // 값이 파일 이름으로 쓸 만한지만 본다. 실제 자리와 무결성은 기동 시점에 잰다.
  if (typeof manifest.imageArchive !== "string"
      || !/^[A-Za-z0-9._-]{1,120}$/.test(path.basename(manifest.imageArchive))) {
    throw new Error("runtime.manifest_invalid: imageArchive");
  }
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

/**
 * 매니페스트가 이름을 댄 비밀이 실제로 환경에 있는지 본다.
 *
 * **경고로 끝내지 않는 이유.** 키가 비면 서비스는 뜬다. 떠서 healthy 를
 * 보고하고, 분석도 "완료" 라고 말한다 — 다만 결과가 비거나 폴백으로
 * 내려간다. 이 앱이 반복해서 밟은 실패 모양이 정확히 그것이라(058:
 * "healthcheck 는 준비의 근거가 아니다"), 여기서 이름을 대고 멈춘다.
 * `runtime.environment_checksum_mismatch` 와 같은 급으로 다룬다.
 */
function assertCredentialsPresent(manifest: RuntimeManifest): void {
  const names = manifest.credentialNames ?? [];
  if (names.length === 0) return;
  const missing = names.filter((n) => !(process.env[n] ?? "").trim());
  if (missing.length === 0) {
    log("info", "runtime.credentials.verified", {
      releaseId: manifest.releaseId,
      count: names.length,
    });
    return;
  }
  // 값은 절대 찍지 않는다 — 있는 것의 이름조차 굳이 남길 이유가 없다.
  log("error", "runtime.credentials_missing", { names: missing });
  throw new Error(
    `runtime.credentials_missing: 이 릴리스는 비밀을 굽지 않는다. ` +
      `다음 환경변수를 채우고 다시 실행하라 — ${missing.join(", ")}. ` +
      `설정 예: [Environment]::SetEnvironmentVariable('${missing[0]}', '<값>', 'User') ` +
      `(설정 뒤 로그아웃·재로그인해야 아이콘으로 켠 앱에 반영된다)`,
  );
}

const ENFORCE_VAR = "AUTH_ENFORCE";
const DEV_LOGIN_VAR = "AUTH_DEV_LOGIN_ENABLED";
const TRUTHY = new Set(["1", "true", "yes", "on"]);
const FALSY = new Set(["0", "false", "no", "off"]);

/**
 * 납품본의 **인증 자세를 환경변수로 뒤집은 것**을 막는다.
 *
 * ## 체크섬만으로는 부족하다
 *
 * `architect/app/.env` 는 sha256 으로 잠가 뒀다. 그런데 백엔드가
 * `load_dotenv()` 를 기본값(`override=False`)으로 부르므로 **이미 프로세스
 * 환경에 있는 값이 잠긴 파일을 이긴다.** 파일은 한 글자도 안 바뀌니
 * `runtime.environment.verified` 는 그대로 통과한다.
 *
 * 2026-09-29 에 이 PC 가 정확히 그 상태였다 — `.env` 는
 * `AUTH_DEV_LOGIN_ENABLED=false`, 서버 응답은 `devLogin.enabled: true`.
 *
 * ## 둘을 함께 본다
 *
 * ```
 * AUTH_ENFORCE=false            문을 통째로 없앤다        (더 큰 구멍)
 * AUTH_DEV_LOGIN_ENABLED=true   SSO 를 건너뛰는 길을 연다
 * ```
 *
 * ## 채널로 갈린다 — 끌 수 있느냐가 아니라 이름이 있느냐
 *
 * `robo.ps1` 의 `Get-ReleaseAuthPosture` 가 같은 원칙을 이미 적어 뒀다:
 * *"문제는 끌 수 있다는 것이 아니라, 이름 없는 예외가 납품으로 새는 것"*.
 * 그래서 `internal-test` 채널 빌드는 경고만 하고 통과시키고,
 * `delivery` 채널에서는 멈춘다.
 *
 * ## 왜 경고가 아니라 중단인가
 *
 * 우회가 열려 있어도 앱은 정상으로 보인다. 로그인 화면이 뜨고, 개발용 칸이
 * 하나 더 있을 뿐이다 — **증상이 없다.** 증상이 없는 우회는 발견되지 않으므로
 * 기동 시점에 이름을 대고 멈춘다. `runtime.credentials_missing` 과 같은 급이다.
 *
 * 릴리스가 스스로 그렇게 구운 경우(`.env` 자체의 값)는 여기서 막지 않는다.
 * 그건 굽는 쪽의 결정이고 체크섬과 `robo.ps1` 관문이 이미 덮는다.
 */
export function assertAuthPostureNotOverridden(manifest: RuntimeManifest): void {
  const enterprise =
    manifest.authEnforced === true &&
    (manifest.authProvider ?? "none").toLowerCase() !== "none";
  if (!enterprise) return;

  const read = (name: string) => (process.env[name] ?? "").trim().toLowerCase();
  const found: { name: string; state: string }[] = [];
  // 빈 값은 "설정하지 않음" 으로 본다 — 지운 흔적일 뿐이다.
  if (FALSY.has(read(ENFORCE_VAR))) found.push({ name: ENFORCE_VAR, state: "꺼짐" });
  if (TRUTHY.has(read(DEV_LOGIN_VAR))) found.push({ name: DEV_LOGIN_VAR, state: "켜짐" });
  const first = found[0];
  if (!first) return;
  const overrides = found.map((f) => `${f.name}=${f.state}`);

  const channel = (manifest.releaseChannel ?? "delivery").toLowerCase();
  if (channel === "internal-test") {
    // 이름이 붙은 예외다. 매니페스트에 채널로 남아 있으므로 통과시키되,
    // 이 빌드로 납품하지 말라는 것을 로그에 남긴다.
    log("warn", "runtime.auth_posture_override_allowed", {
      releaseId: manifest.releaseId,
      releaseChannel: channel,
      overrides,
    });
    return;
  }

  log("error", "runtime.auth_posture_override", {
    releaseId: manifest.releaseId,
    releaseChannel: channel,
    overrides,
  });
  throw new Error(
    `runtime.auth_posture_override: 이 릴리스는 사내 인증 납품본이다` +
      `(releaseChannel=${channel}, authProvider=${manifest.authProvider}). ` +
      `그런데 환경변수가 그 자세를 뒤집고 있다 — ${overrides.join(", ")}. ` +
      `환경변수가 체크섬으로 잠근 .env 를 이기기 때문에(load_dotenv 는 ` +
      `override=False) 파일 검사로는 걸리지 않는다. 지우고 다시 실행하라: ` +
      `[Environment]::SetEnvironmentVariable('${first.name}', $null, 'User') ` +
      `(이 명령은 값을 빈 문자열로 남길 수 있다 — 빈 값은 "설정하지 않음" 으로 ` +
      `보므로 그대로도 된다. 이름까지 없애려면 ` +
      `Remove-ItemProperty HKCU:\\Environment -Name ${first.name}. ` +
      `어느 쪽이든 로그아웃·재로그인해야 아이콘으로 켠 앱에 반영된다). ` +
      `사내망 밖에서 화면을 밟아야 한다면 ROBO_RELEASE_CHANNEL=internal-test 로 ` +
      `따로 구워라 — 그 빌드에서는 이 검사가 경고로 끝난다.`,
  );
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

/**
 * 오프라인 이미지 아카이브를 찾는다.
 *
 * **이 파일은 설치 파일 안에 넣지 않는다.** 넣으면 NSIS 가 설치본을 못 만든다 —
 * `makensis` 는 32비트라 주소공간이 2GB 남짓인데, 이미지 tar 하나가 2.5GB 다
 * (2026-09-23 실측: 페이로드 3.27GB, `failed creating mmap of …nsis.7z`).
 * 이미지를 줄여서 넘길 수 있는 벽이 아니다 — analyzer 한 장이 2.1GB 다.
 *
 * 그래서 tar 는 설치 파일 **옆에** 함께 전달하고, 설치한 사람이 아래 자리 중
 * 하나에 둔다. 어디서 찾았든 `imageArchiveSha256` 으로 무결성을 검사하므로
 * 자리가 늘어도 신뢰는 그대로다.
 *
 *   1. `ROBO_IMAGE_ARCHIVE`       — 절대 경로로 명시 (운영자가 원하는 자리)
 *   2. `<앱 데이터>/runtime/<이름>` — 권장. 설치 후 여기에 복사한다
 *   3. `<설치 폴더>/runtime/<이름>` — 옛 구성(패키지 안에 넣던 시절) 하위 호환
 */
function resolveImageArchive(root: string, manifest: RuntimeManifest): string {
  const candidates: string[] = [];

  const override = (process.env.ROBO_IMAGE_ARCHIVE ?? "").trim();
  if (override) candidates.push(path.resolve(override));

  // manifest 의 값은 파일 이름으로만 쓴다 — 경로 조작을 막는다.
  const name = path.basename(manifest.imageArchive);
  const recommended = path.join(getDataDir(), "runtime", name);
  candidates.push(recommended);
  candidates.push(path.join(path.resolve(root), name));

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      log("info", "docker.image_archive.located", { path: candidate });
      return candidate;
    }
  }
  // **어디를 봤는지 말해 준다.** 그러지 않으면 "파일이 없다" 만 남아서
  // 어디에 두어야 하는지 사람이 알 수 없다.
  // **서수로 말하지 않는다.** `ROBO_IMAGE_ARCHIVE` 가 있고 없고에 따라 후보의
  // 순번이 밀려서, "두 번째 자리" 같은 안내가 틀린 곳을 가리킨다(실측).
  throw new Error(
    `docker.image_archive_missing: ${name} 을 찾지 못했다. 찾아본 자리: ` +
      candidates.join(" | ") +
      ` — 전달받은 ${name} 을 ${recommended} 로 복사하거나 ` +
      `ROBO_IMAGE_ARCHIVE 에 절대 경로를 지정하라`,
  );
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

  const archive = resolveImageArchive(root, manifest);
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
    if (ports.length !== 6 || ports.some((port) => !Number.isInteger(port) || port < 1024 || port > 65535)) {
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
      graphPg: await pickFreePort(),
      analyzer: await pickFreePort(),
      gateway: await pickFreePort(),
      architect: await pickFreePort(),
      pdf2bpmn: await pickFreePort(),
      wireframe: await pickFreePort(),
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
  topology: GraphTopology = graphTopology(),
): NodeJS.ProcessEnv {
  const endpoint = graphEndpoint(state.ports, topology);
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
    ROBO_IMAGE_WIREFRAME: manifest.images.wireframe,
    // 이름은 `ROBO_NEO4J_*` 그대로 둔다 — 컨테이너 안의 서비스들이 Neo4j 드라이버로
    // 붙고, 그 드라이버가 읽는 변수 이름이다. **엔진이 아니라 프로토콜의 이름이다.**
    ROBO_NEO4J_PASSWORD: password,
    // **이 둘은 "이 PC 에 발행하는 포트"** 다. 번들 DB 를 띄울 때만 쓰인다.
    // 아래 `ROBO_GRAPH_*_PORT` 와 뜻이 다르므로 이름을 갈라 둔다 — 한 이름이 두
    // 뜻을 가지면 중앙 모드에서 어느 쪽이 이겼는지 읽는 사람이 알 수 없다.
    ROBO_NEO4J_PORT: String(state.ports.graph),
    ROBO_GRAPH_PG_LOCAL_PORT: String(state.ports.graphPg),
    // **이 셋은 "그래프가 어디 있는가"** 다. 두 모드에서 뜻이 같다 — bundled 면 이
    // PC, central 이면 사내 서버. `compose.remote-graph.yml` 이 읽는 값이고,
    // bundled 에서도 채워 둔다. 모드별로 비워 두면 나중에 overlay 를 얹었을 때
    // `bolt://:7687` 이 조용히 만들어진다.
    ROBO_GRAPH_HOST: endpoint.host,
    ROBO_GRAPH_BOLT_PORT: String(endpoint.boltPort),
    ROBO_GRAPH_PG_PORT: String(endpoint.pgPort),
    ROBO_GRAPH_USER: manifest.graphs.user,
    ROBO_GRAPH_DESIGN: manifest.graphs.design,
    ROBO_GRAPH_ANALYSIS: manifest.graphs.analysis,
    ROBO_ANALYZER_PORT: String(state.ports.analyzer),
    ROBO_GATEWAY_PORT: String(state.ports.gateway),
    ROBO_ARCHITECT_API_PORT: String(state.ports.architect),
    ROBO_PDF2BPMN_PORT: String(state.ports.pdf2bpmn),
    ROBO_WIREFRAME_PORT: String(state.ports.wireframe),
  };
}

/** 중앙 DB 모드에서 겹쳐 얹는 overlay. `compose.yml` 과 같은 자리에 있다. */
const REMOTE_GRAPH_COMPOSE = "compose.remote-graph.yml";

function composeArgs(
  root: string,
  manifest: RuntimeManifest,
  command: string[],
  topology: GraphTopology = graphTopology(),
): string[] {
  const composeFile = ensureRuntimeChild(root, manifest.composeFile, "composeFile");
  const files = ["--file", composeFile];
  if (topology.mode === "central") {
    // overlay 가 번들 DB 를 프로필로 빼고 Bolt 주소를 중앙으로 돌린다.
    // **모든 compose 호출에 같이 실어야 한다** — 한 번이라도 빠지면 그 호출은
    // 번들 DB 가 있다고 보고, `down` 이 남의 컨테이너를 건드리거나 `up` 이
    // 로컬 DB 를 되살린다.
    files.push("--file", ensureRuntimeChild(root, REMOTE_GRAPH_COMPOSE, "remoteGraphCompose"));
  }
  return ["compose", "--project-name", COMPOSE_PROJECT_NAME, ...files, ...command];
}

export async function startDockerStack(): Promise<DockerStackRuntime> {
  if (current) return current;
  const root = runtimeDirectory();
  const manifest = readManifest(root);
  // 아래 둘은 **이미지를 적재하기 전에** 본다. 4분짜리 tar 적재를 끝내고 나서
  // "키가 없다"·"주소가 없다" 고 말하는 것은 사람 시간을 버리는 일이다.
  const topology = graphTopology();
  await ensureEnvironmentSnapshots(root, manifest);
  assertCredentialsPresent(manifest);
  assertAuthPostureNotOverridden(manifest);
  await ensureDockerDaemon();
  await ensureImages(root, manifest);

  const password = await graphPassword();
  const state = loadPersistedState(manifest.releaseId) ?? (await createState(manifest.releaseId));
  const env = composeEnvironment(manifest, state, password, topology);
  const endpoint = graphEndpoint(state.ports, topology);

  log("info", "docker.stack.starting", {
    releaseId: manifest.releaseId,
    projectName: COMPOSE_PROJECT_NAME,
    graphMode: topology.mode,
    // **주소는 비밀이 아니다.** 어느 저장소를 쓰는지 로그에서 못 보면 "왜 내 프로젝트가
    // 안 보이나" 를 사람이 추측으로 풀어야 한다.
    graphHost: endpoint.host,
  });
  await runDocker(
    composeArgs(root, manifest, ["up", "--detach", "--wait", "--wait-timeout", "300"], topology),
    { env, secret: password },
  );

  const hostBoltUri = `bolt://${endpoint.host}:${endpoint.boltPort}`;
  process.env.ROBO_GATEWAY_URL = `http://127.0.0.1:${state.ports.gateway}`;
  // 문서→BPMN 은 **안에서 돈다.** 이 줄이 없으면 Architect 는 번들 `.env` 의
  // 값(= 바깥 SaaS)이나 빈 값을 쓰고, 사내망에서는 그 호출이 막힌다. 막히면
  // 폴백으로 내려가는데 **그게 눈에 안 띈다** — 화면에는 그대로 BPM 이 나온다.
  // (폴백 품질이 실제로 얼마나 나쁜지는 아직 안 쟀다.)
  // `load_dotenv()` 는 기본이 override=False 라 여기서 준 값이 번들 .env 를 이긴다.
  process.env.PDF2BPMN_FACADE_URL = `http://127.0.0.1:${state.ports.pdf2bpmn}`;
  process.env.ROBO_CLUSTER_MCP_URL = `http://127.0.0.1:${state.ports.analyzer}/robo/mcp/`;
  // 와이어프레임 렌더러도 **안에서 돈다.** 이 줄이 없으면 Architect 는
  // `open_pencil_client` 의 기본값 `http://localhost:7610` 을 쓰는데, 그건 `dev.sh`
  // 가 Bun 으로 띄울 때의 주소다 — 설치본에는 거기 아무것도 없다.
  //
  // **그리고 그 부재가 오류로 안 보인다.** `run_render_agent` 는 서비스가 없으면
  // `(None, None)` 을 내는데 인제스천 경로는 `on_event=None` 으로 부르므로 error
  // 이벤트가 아무 데도 안 간다. 화면에는 "UI 와이어프레임 생성 중…" 이 그대로
  // 흐르고 UI 노드만 `sceneGraph=null` 로 남는다. 증상은 한참 뒤 Figma 싱크에서
  // "이 UI 노드에는 아직 sceneGraph가 없습니다" 로 나온다 — 원인과 증상이 멀다.
  // 2026-09-23 실측(같은 입력, 렌더러만 추가): 0/27 → 와이어프레임 29/29.
  process.env.WIREFRAME_SERVICE_URL = `http://127.0.0.1:${state.ports.wireframe}`;
  process.env.ROBO_NEO4J_URI = hostBoltUri;
  // 사용자 = Postgres role. Bolt 게이트웨이는 받은 자격증명을 Postgres 에 그대로 넘긴다.
  process.env.ROBO_NEO4J_USER = manifest.graphs.user;
  process.env.ROBO_NEO4J_PASSWORD = password;
  // **설계와 분석을 갈라 준다.** 예전에는 둘이 같은 값이었는데, 그건 무능이 아니라
  // 제약이었다 — 번들 이미지가 Neo4j Community 라 database 가 하나뿐이었다.
  // 이제 갈라지므로, 여기서 같은 값을 주면 분석이 설계를 지운다.
  process.env.ROBO_NEO4J_DATABASE = manifest.graphs.design;
  process.env.ROBO_ANALYZER_NEO4J_DATABASE = manifest.graphs.analysis;
  // 사용자·프로젝트 저장소는 Bolt가 아니라 같은 Ontological PostgreSQL에 직접 붙는다.
  // 비밀번호는 파일로 내리지 않고 DPAPI에서 읽은 값을 백엔드 spawn 환경으로만 넘긴다.
  //
  // **여기를 루프백으로 못 박으면 중앙 모드가 반쪽이 된다.** Bolt 는 중앙을 보는데
  // 사용자·프로젝트 저장소만 이 PC 를 보게 되고, 그러면 같은 프로젝트를 남이 만든
  // 그래프에서 "없는 프로젝트" 로 읽는다 — 오류 없이.
  process.env.OG_PG_HOST = endpoint.host;
  process.env.OG_PG_PORT = String(endpoint.pgPort);
  process.env.OG_PG_DATABASE = manifest.graphs.design;
  process.env.OG_PG_USER = manifest.graphs.user;
  process.env.OG_PG_PASSWORD = password;
  await ensureBundledConnection({
    uri: hostBoltUri,
    user: manifest.graphs.user,
    password,
    database: manifest.graphs.design,
    central: topology.mode === "central",
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
    graphMode: topology.mode,
    graphHost: endpoint.host,
    graphPort: endpoint.boltPort,
    graphPgPort: endpoint.pgPort,
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
  // **중앙 모드에서 graph 는 우리 것이 아니다.** 그리고 이 거부가 없으면 조용히
  // 틀리지 않고 **더 나쁘게** 틀린다 — overlay 가 번들 DB 를 프로필로 빼 두지만,
  // `compose up <서비스>` 로 그 서비스를 **지목하면 프로필이 자동 활성된다**
  // (2026-09-28 실측: compose v2, `up -d a` 가 `profiles: [bundled-db]` 인 a 를 띄웠다).
  // 즉 재시도 한 번에 빈 로컬 DB 가 살아나고, 앱은 중앙을 보는 채로 남는다.
  if (serviceId === "graph") {
    const topology = graphTopology();
    if (topology.mode === "central") {
      throw new Error(
        `docker.graph_is_remote: 그래프가 중앙 서버(${topology.host})에 있어 이 PC 에서 ` +
          "되살릴 수 없다. 서버에서 compose.central-db.yml 로 확인하라",
      );
    }
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
