/**
 * Electron main entry — orchestrates Phase 2 + US1 (partial):
 *   T007 lifecycle skeleton, T014 single-instance lock, T015 BrowserWindow +
 *   app:// protocol (+ /api/* proxy to the backend port), T025 startup
 *   orchestration (port → backend spawn → wait ready → load window), T026
 *   IPC handlers (app:getRuntimeState, backend:retry, logs:reveal,
 *   app:openExternal) + push channel app:onBackendStatus.
 *
 * Pieces NOT yet implemented (deferred to their own tasks):
 *   - Strict CSP (T015 polish — needs SPA index.html injection or a
 *     defaultSession header rewrite; deferred to T027 with the splash UI)
 *   - Neo4j child lifecycle (T023) — for dev we rely on whatever Neo4j the
 *     existing project setup already runs (docker-compose)
 *   - Settings UI + secret store + apiBase rewrite (US3 T038–T047)
 *   - Auto-update (US2 T031–T037)
 */

import { BrowserWindow, app, dialog, nativeImage, net, protocol, shell } from "electron";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

import { IpcErrorCodes, type RuntimeState } from "../shared/ipc-contract";

import { ensureDataDirs, getLogsDir } from "./data-dir";
import { backendLogLines, disableConsoleMirror, initLogging, log, revealLogs } from "./logging";
import { isStreamingResponse } from "./proxy-stream";
import { RuntimeRegistry } from "./runtime-state";
import { RUNTIME_CHANNELS, type ManagedServiceId } from "../shared/runtime-contract";
import {
  getDockerStackRuntime,
  restartOwnedService,
  stopDockerStack,
} from "./docker-stack";
import { COMPOSE_PROJECT_NAME, graphPassword } from "./docker-stack";
import { graphTopology } from "./graph-topology";
import {
  containerNames as probeContainerNames,
  containerNamesFor,
  hasCapabilityProbe,
  probedServiceIds,
  runProbe,
  type ProbeContext,
} from "./probes";
import { readServiceLogs } from "./service-logs";
import {
  containerLogs,
  dockerAvailable,
  listRunningContainers,
  presentContainerNames,
} from "./probes/net";
import {
  aliveFrom,
  decideDockerAvailability,
  startSupervision,
  type Supervision,
} from "./supervision";
import { IpcHandlerError, pushToRenderer, registerHandler } from "./ipc";
import {
  copy,
  listDir,
  mkdir,
  readFile,
  rename,
  stageProject,
  trash,
  writeFile,
} from "./fs-browser";
import {
  getRuntimeBackend,
  onBackendStatusChange,
  retryBackend,
  startBackend,
  stopBackend,
} from "./backend";
// 032: register stub launcher handlers so the renderer's window.desktop
// surface answers (with a typed VALIDATION error) for every launcher channel
// until each gating task lands a real handler.
import { registerLauncherIpcStubs } from "./launcher/ipc-handlers";
import { markPending } from "./launcher/launcher-state";

let mainWindow: BrowserWindow | null = null;

// T015 (US1): register `app://` as a privileged scheme so the renderer can
// load the bundled SPA from disk with the same guarantees as https — fetch
// API, streams, secure context. MUST run before app.whenReady().
protocol.registerSchemesAsPrivileged([
  {
    scheme: "app",
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      stream: true,
      corsEnabled: true,
    },
  },
]);

// ---------------------------------------------------------------------------
// T014 single-instance lock — must run synchronously at module load so the
// second-instance process exits before it spawns child processes of its own.
// ---------------------------------------------------------------------------

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  // 파일 로거는 아직 초기화 전이라 콘솔뿐인데, **콘솔 쓰기는 던질 수 있다**
  // (부모 프로세스가 먼저 끝나면 stdout 이 EPIPE 를 낸다 — `logging.ts` 참고).
  // 종료하려던 자리에서 예외로 죽으면 "두 번째 인스턴스가 조용히 나간다" 가
  // "오류 대화상자가 뜬다" 로 바뀐다.
  try {
    console.log("single-instance.already_running — exiting");
  } catch {
    /* 두 번째 인스턴스는 어차피 나간다 */
  }
  app.quit();
  // Note: no `process.exit` — Electron tears down on `app.quit` and we
  // explicitly skip the rest of the wiring below in the second instance.
}

app.on("second-instance", () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function resolveFrontendDist(): string {
  // Dev: `<repo-root>/frontend/dist` lives one level up from `desktop/`.
  // Production (asar): T028 packs frontend/dist into the asar at this same
  // relative location, so the resolution is identical in both modes.
  return path.resolve(app.getAppPath(), "..", "frontend", "dist");
}

/**
 * 감독 상태를 들고 있는 것 (spec 058). 프로세스 안에 사는 값이고 디스크에 안 쓴다 —
 * 재기동하면 처음부터 다시 잰다(옛 값을 믿는 것보다 싸고 정확하다).
 */
export const runtimeRegistry = new RuntimeRegistry();

/**
 * 프로브를 주기적으로 돌리는 것 (spec 058 T018).
 *
 * **2026-10-07 까지 이것이 없었다.** 프로브와 판정은 다 있었는데 돌려 주는 쪽이
 * 없어서 `runtimeRegistry` 가 언제나 비었고, 그래서 `buildRuntimeState()` 가
 * 서비스 목록을 아예 싣지 않았다 — 설계는 서비스 9개를 따로 보는데 동작은
 * 백엔드 상태 하나였다.
 */
let supervision: Supervision | null = null;

/**
 * 프로브에 필요한 설정. **스택이 아직 안 뜨면 `null`** — 추측해서 재지 않는다.
 *
 * 비밀번호는 한 번 얻어 두고 다시 쓴다(중앙 모드에서는 환경변수, 번들 모드에서는
 * 시크릿 저장소). 못 얻으면 **한 번만** 말하고 재지 않는다 — 틱마다 같은 경고를
 * 쌓으면 로그가 그 한 줄로 덮인다.
 */
function makeProbeContextProvider(): () => Promise<ProbeContext | null> {
  let password: string | null = null;
  let passwordFailed = false;
  return async () => {
    const runtime = getDockerStackRuntime();
    if (!runtime) return null;
    if (password === null) {
      if (passwordFailed) return null;
      try {
        password = await graphPassword();
      } catch (error) {
        passwordFailed = true;
        log("warn", "runtime.supervision.no_graph_password", {
          message: error instanceof Error ? error.message : String(error),
        });
        return null;
      }
    }
    const topology = graphTopology();
    return {
      projectName: runtime.projectName,
      ports: {
        // **중앙 모드에서는 포트도 중앙의 것이다.** 호스트만 바꾸고 포트를 이 PC 의
        // 스택 값(59006)으로 두면 `172.27.64.1:59006` 를 두드려 늘 "bolt closed" 가
        // 난다 — 2026-10-07 설치본에서 실제로 그 줄을 봤다.
        graph: topology.mode === "central" ? topology.boltPort : runtime.ports.graph,
        analyzer: runtime.ports.analyzer,
        gateway: runtime.ports.gateway,
        architect: runtime.ports.architect,
        pdf2bpmn: runtime.ports.pdf2bpmn,
        wireframe: runtime.ports.wireframe,
      },
      // 중앙 모드에서는 그래프만 다른 기계에 있다. 이 값이 없으면 프로브가
      // 멀쩡한 중앙 저장소를 "bolt closed" 로 읽는다.
      graphHost: topology.mode === "central" ? topology.host : undefined,
      graph: {
        user: runtime.manifest.graphs.user,
        password,
        design: runtime.manifest.graphs.design,
        analysis: runtime.manifest.graphs.analysis,
      },
    };
  };
}

function startRuntimeSupervision(): void {
  if (supervision) return;
  const context = makeProbeContextProvider();
  supervision = startSupervision<ProbeContext>({
    ids: () => probedServiceIds(),
    hasCapability: (id) => hasCapabilityProbe(id),
    context,
    probe: (ctx, id, kind) => runProbe(ctx, id, kind),
    running: async () => {
      // 같은 `docker ps` 로 **도커 자체의 유무**까지 적는다 (T030).
      // 여기서 안 적으면 `setDockerAvailable` 의 호출자가 0개로 남고, 화면의
      // "도커를 준비하세요" 안내는 **뜰 수가 없다** — 10/8 에 그걸 세었다.
      const seen = await listRunningContainers();
      runtimeRegistry.setDockerAvailable(
        decideDockerAvailability(seen.dockerOk, seen.dockerOk || (await dockerAvailable())),
      );
      return seen.names;
    },
    alive: (ctx, id, running) => {
      // 백엔드는 **호스트 프로세스**다 — 컨테이너 목록에 없다. 거기서 `docker ps`
      // 로 판정하면 멀쩡히 응답하는 백엔드가 "실행 중이 아닙니다" 가 된다.
      // 우리가 띄운 프로세스이므로 pid 가 가장 강한 근거다.
      if (id === "architect") return getRuntimeBackend().pid !== null;
      return aliveFrom(running, probeContainerNames(ctx, id));
    },
    apply: (id, facts) => runtimeRegistry.applyProbe(id, facts),
    register: (ids) => runtimeRegistry.register(ids),
    changed: () => {
      // `diff` 는 **넘긴 목록과 지금을 비교해** 바뀐 id 만 준다. 앞 틱의 목록을
      // 들고 있다가 넘기고, 바뀐 것들의 **지금 값**을 돌려준다.
      const changedIds = runtimeRegistry.diff(lastServices);
      const snapshot = runtimeRegistry.snapshot();
      lastServices = snapshot.services;
      if (changedIds.length > 0) {
        // **바뀔 때만 민다** — 계약이 그렇고(`RuntimeStatusPayload`), 5초마다 같은
        // 값을 보내면 렌더러가 그때마다 다시 그린다. 스토어도 "바뀐 것이 있을 때만
        // 진전으로 센다" 로 받고 있어, 매번 밀면 **멎은 기동이 멎지 않은 것처럼** 보인다.
        pushToRenderer(RUNTIME_CHANNELS.onStatus, {
          services: snapshot.services,
          capabilities: snapshot.capabilities,
          graphGuard: snapshot.graphGuard,
          changedServiceIds: changedIds,
        });
      }
      // **기능이 막히고 풀리는 것도 남긴다.** 서비스 상태만 적으면, 나중에
      // "그때 사용자가 무엇을 못 했나" 를 되짚을 때 표를 손으로 다시 계산해야 한다.
      // 그 표(`CAPABILITY_REQUIREMENTS`)는 바뀔 수 있고, 바뀐 뒤의 표로 옛 사고를
      // 되짚으면 틀린 답이 나온다. 사실을 그때 적어 둔다.
      for (const capability of snapshot.capabilities) {
        if (lastCapabilityState.get(capability.id) === capability.state) continue;
        lastCapabilityState.set(capability.id, capability.state);
        log("info", "runtime.capability.state", {
          capability: capability.id,
          state: capability.state,
          reason: capability.blockedReason,
        });
      }
      const changedSet = new Set(changedIds);
      return snapshot.services
        .filter((service) => changedSet.has(service.id))
        .map((service) => ({
          id: service.id,
          state: service.state,
          stateReason: service.stateReason,
        }));
    },
    log: (level, event, params) => log(level, event, params),
  });
  log("info", "runtime.supervision.started", {
    services: probedServiceIds().length,
  });
}

/** 앞 틱의 기능 상태. 바뀐 것만 기록한다. */
const lastCapabilityState = new Map<string, string>();

/** 앞 틱의 서비스 목록. `diff` 에 넘겨 **바뀐 것만** 기록한다. */
let lastServices: ReturnType<RuntimeRegistry["snapshot"]>["services"] = [];

function buildRuntimeState(): RuntimeState {
  const be = getRuntimeBackend();
  const snapshot = runtimeRegistry.snapshot();
  const base: RuntimeState = {
    appVersion: app.getVersion(),
    backendPort: be.port,
    boltPort: null, // T023 — Neo4j-managed mode not yet implemented
    backendPid: be.pid,
    neo4jPid: null,
    // 감독 대상이 등록돼 있으면 파생 status 를 쓴다. 없으면 예전 값 그대로 —
    // **하위 호환을 위해 필드를 지우지도, 뜻을 바꾸지도 않는다.**
    status: snapshot.services.length > 0 ? snapshot.legacyStatus : be.status,
    dataSource: "bundled",
    dataDir: app.getPath("userData"),
    updateState: "idle",
  };
  // **등록이 비어 있으면 신규 필드를 아예 안 실는다.** 빈 목록을 실으면 렌더러가
  // "서비스가 없다"로 읽고, 그건 "아직 안 쟀다"와 완전히 다른 화면이 된다.
  if (snapshot.services.length === 0) return base;
  return {
    ...base,
    services: snapshot.services,
    legacyData: snapshot.legacyData,
    capabilities: snapshot.capabilities,
    graphGuard: snapshot.graphGuard,
    dockerAvailable: snapshot.dockerAvailable,
    releaseId: snapshot.releaseId,
  };
}

// ---------------------------------------------------------------------------
/**
 * 진행 중인 upstream 프록시 요청들. **문서가 바뀌면 전부 끊는다.**
 *
 * ## 왜 필요한가 — 2026-09-29 실측
 *
 * 화면이 `Analyzer 로드 중…` 에서 멈췄다. 로그를 보니 요청이 **시작만 되고
 * 끝나지 않았다** — `protocol.api_proxy.headers` 는 찍히는데 `done` 도 `failed`
 * 도 안 온다. 그런데 백엔드를 직접 때리면 19~223ms 로 멀쩡히 답했다.
 *
 *     Robo-Architect → backend :  Established 6
 *
 * **정확히 6이다.** Chromium 의 호스트당 동시 연결 한도다. `/api/collab/stream`
 * 같은 SSE 가 오래 살아서 자리를 물고, 렌더러가 재적재될 때마다(그날 4번) 앞
 * 문서의 스트림이 남아 쌓였다. 6개가 다 차면 새 요청은 소켓을 기다리며
 * **무한 대기**한다 — 화면에는 "로딩 중" 으로만 보인다.
 *
 * `net.fetch` 에 `request.signal` 을 넘기는 것은 이미 하고 있다. 그것은 렌더러가
 * 요청을 취소할 때를 덮는다. 그런데 **하드 리로드는 그 신호를 태워 보내지
 * 못한다** — 문서가 통째로 사라지므로 취소해 줄 주체가 없다. 그래서 main 이
 * 문서 전환을 보고 직접 끊는다.
 */
/** 이만큼 기다렸는데도 응답이 없으면 로그로 말한다. */
const STALL_WARN_MS = 15_000;

const inflightProxy = new Set<AbortController>();

function abortInflightProxy(reason: string): void {
  if (inflightProxy.size === 0) return;
  log("info", "protocol.api_proxy.aborted_all", { count: inflightProxy.size, reason });
  for (const controller of [...inflightProxy]) {
    try {
      controller.abort();
    } catch {
      /* 이미 끝난 것 */
    }
  }
  inflightProxy.clear();
}

// T015 protocol handler — serves the SPA from frontend/dist AND proxies
// `/api/*` to the live backend port. Putting the proxy here avoids editing
// the SPA's API client (T017 will replace this with a clean apiBase.js).
// ---------------------------------------------------------------------------

function registerAppProtocol(): void {
  const frontendDist = resolveFrontendDist();
  log("info", "protocol.app.registering", { frontendDist });

  protocol.handle("app", async (request) => {
    const url = new URL(request.url);
    let pathname = decodeURIComponent(url.pathname);
    if (!pathname || pathname === "/") {
      pathname = "/index.html";
    }

    // Proxy /api/** upstream. /api/gateway/** → analyzer API Gateway (9000);
    // every other /api/** → the spawned architect backend. Mirrors the vite
    // dev-server proxy (frontend/vite.config.js) for the app:// production path,
    // where there is no vite to route the analyzer's gateway calls.
    if (pathname === "/api" || pathname.startsWith("/api/")) {
      let upstreamBase: string;
      if (pathname === "/api/gateway" || pathname.startsWith("/api/gateway/")) {
        upstreamBase = process.env.ROBO_GATEWAY_URL ?? "http://127.0.0.1:9000";
      } else {
        const be = getRuntimeBackend();
        if (be.port === null) {
          // 이유를 실어 보낸다. 지금 프런트의 `apiFailure` 는 본문을 안 읽고
          // "Failed to fetch <무엇> (HTTP 503)" 만 만들지만, 로그·네트워크 탭·
          // 나중에 붙일 화면에는 이게 유일한 단서다.
          const reason =
            be.status === "fatal" && be.detail ? be.detail : "Backend not ready";
          return new Response(reason, { status: 503 });
        }
        const port = be.port;
        upstreamBase = `http://127.0.0.1:${port}`;
      }
      const upstream = `${upstreamBase}${pathname}${url.search}`;
      let proxyHeaders = request.headers;
      let proxyBody: BodyInit | null = request.body;

      // 릴리스 구성요소의 버전이 잠시 어긋나도 분석이 막히지 않게 gateway 경계에서
      // 계약을 좁힌다. 구 Analyzer UI는 Parser용 메타데이터 전체를 /robo/analyze로
      // 보내지만 현재 Analyzer는 아래 네 필드만 허용(extra="forbid")한다.
      // 그 결과 파싱 성공 직후 422 detail 객체 네 개가 `[object Object]`로 보였다.
      if (pathname === "/api/gateway/robo/analyze" && request.method === "POST") {
        try {
          const input = await request.clone().json() as Record<string, unknown>;
          proxyBody = JSON.stringify({
            strategy: input.strategy,
            locale: typeof input.locale === "string" ? input.locale : "ko",
            selected_source_ids: Array.isArray(input.selected_source_ids)
              ? input.selected_source_ids
              : [],
            datasource: input.datasource ?? input.datasourceName ?? null,
          });
          const headers = new Headers(request.headers);
          headers.delete("content-length");
          headers.set("content-type", "application/json");
          proxyHeaders = headers;
        } catch (err) {
          log("warn", "protocol.analyzer_request_normalize_failed", {
            message: err instanceof Error ? err.message : String(err),
          });
        }
      }
      // 진단: 렌더러가 Neo4j override 헤더를 실었는지 (여기서 끊기면 프록시 문제).
      //
      // **method 를 함께 남긴다.** 전에는 경로만 남겨서 `GET /api/proposals/`(조회)
      // 와 `POST /api/proposals/`(생성)가 로그에서 같게 보였다 — "무엇을 했나" 를
      // 되짚을 때 가장 알고 싶은 것이 그 차이다.
      const startedAt = Date.now();
      log("info", "protocol.api_proxy.headers", {
        method: request.method,
        pathname,
        // 붙잡힌 요청 수. 6 에 가까워지면 아래 `stalled` 가 곧 뜬다 —
        // Chromium 의 호스트당 동시 연결 한도가 6이다.
        inflight: inflightProxy.size,
        neo4jUri: request.headers.get("x-neo4j-uri") ?? "(none)",
        neo4jDb: request.headers.get("x-neo4j-database") ?? "(none)",
      });
      // 렌더러의 취소 신호와 **문서 전환**을 하나로 묶는다. `request.signal` 만
      // 넘기면 하드 리로드를 못 덮는다 — 위 `inflightProxy` 주석 참고.
      const controller = new AbortController();
      inflightProxy.add(controller);
      if (request.signal.aborted) controller.abort();
      else request.signal.addEventListener("abort", () => controller.abort(), { once: true });

      // **멈춘 것을 멈췄다고 말한다.** 연결 풀이 차면 `net.fetch` 는 던지지도
      // 끝나지도 않고 소켓을 기다린다 — 화면은 "로딩 중" 이고 로그에는 시작만
      // 남아, 2026-09-29 에 그 상태를 알아내는 데 로그 대조가 필요했다.
      const stallTimer = setTimeout(() => {
        log("warn", "protocol.api_proxy.stalled", {
          method: request.method,
          pathname,
          waitedMs: Date.now() - startedAt,
          inflight: inflightProxy.size,
          hint: "호스트당 동시 연결 6개가 다 찼을 수 있다(SSE 가 오래 문다)",
        });
      }, STALL_WARN_MS);

      try {
        const response = await net.fetch(upstream, {
          method: request.method,
          headers: proxyHeaders,
          body: proxyBody,
          // 프로젝트 전환은 renderer 전체 새로고침이다. 이전 문서가 사라질 때
          // app:// Request 는 abort 되므로 그 신호를 upstream 에도 전달해야 한다.
          // 전달하지 않으면 collab SSE 와 초기 API 요청이 백엔드/gateway 쪽에
          // 계속 남고, 전환을 반복한 뒤 새 요청이 연결 풀을 기다리며 무한대기한다.
          signal: controller.signal,
          redirect: "manual",
          // duplex required when sending a streaming body — net.fetch follows
          // the Web Fetch spec.
          ...(proxyBody ? { duplex: "half" as const } : {}),
        });
        // 결과까지 남긴다. 401·403·5xx 가 언제 몇 건 났는지가 사후에 가장
        // 자주 필요한 정보다 — 오늘 fail-open 을 이 줄들로 확인했다.
        clearTimeout(stallTimer);
        log(response.ok ? "info" : "warn", "protocol.api_proxy.done", {
          method: request.method,
          pathname,
          status: response.status,
          ms: Date.now() - startedAt,
        });
        // SSE 는 헤더를 받은 뒤에도 본문이 계속 흐르고, **그 스트림이 소켓을
        // 물고 있는 장본인**이다. 그것만 다음 문서 전환까지 등록해 둔다.
        //
        // 끝난 요청까지 남겨 두면 집합이 **세션 내내 자란다**. 2026-10-01 실측:
        // 하루 동안 0 → 860 으로 올라가기만 했다(한 번도 안 내려왔다). 그러면
        // 위에 적어 둔 "6 에 가까워지면 stalled 가 곧 뜬다" 가 뜻을 잃고,
        // **붙잡힌 요청 수를 보려고 둔 숫자가 누적 요청 수**가 된다.
        // 측정 수단이 거짓말을 하면 그 자리를 다시 못 본다.
        //
        // 멈춘 요청은 애초에 여기까지 오지 못하므로 그대로 남는다 — 끊어야 할
        // 것은 계속 끊을 수 있다.
        if (!isStreamingResponse(response)) inflightProxy.delete(controller);
        return response;
      } catch (err) {
        clearTimeout(stallTimer);
        inflightProxy.delete(controller);
        log("error", "protocol.api_proxy.failed", {
          method: request.method,
          pathname,
          upstream,
          ms: Date.now() - startedAt,
          message: err instanceof Error ? err.message : String(err),
        });
        return new Response("Bad Gateway", { status: 502 });
      }
    }

    // Static SPA assets from frontend/dist.
    const filePath = path.normalize(path.join(frontendDist, pathname));
    if (!filePath.startsWith(frontendDist + path.sep) && filePath !== frontendDist) {
      log("warn", "protocol.app.forbidden", { pathname, filePath });
      return new Response("Forbidden", { status: 403 });
    }

    if (!fs.existsSync(filePath)) {
      const hasExtension = path.extname(filePath).length > 0;
      if (hasExtension) {
        log("warn", "protocol.app.missing_asset", { pathname });
        return new Response("Not Found", { status: 404 });
      }
      // SPA fallback for client-side routing.
      return net.fetch(pathToFileURL(path.join(frontendDist, "index.html")).toString());
    }
    return net.fetch(pathToFileURL(filePath).toString());
  });
}

// ---------------------------------------------------------------------------
// BrowserWindow
// ---------------------------------------------------------------------------

function createMainWindow(): BrowserWindow {
  const preloadPath = path.join(app.getAppPath(), "dist", "preload", "preload", "index.js");
  const iconPath = path.resolve(app.getAppPath(), "resources", "icons", "icon_512x512.png");

  const window = new BrowserWindow({
    width: 1280,
    height: 800,
    title: "Robo Architect",
    icon: iconPath,
    show: false,
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  });

  // T015 polish: deny new BrowserWindows; route http(s) to OS browser (FR-021).
  window.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http://") || url.startsWith("https://")) {
      void shell.openExternal(url);
    } else {
      log("warn", "window.open_blocked", { url });
    }
    return { action: "deny" };
  });
  // Block in-page navigations to non-`app://` origins (defence in depth).
  window.webContents.on("will-navigate", (event, url) => {
    if (!url.startsWith("app://")) {
      event.preventDefault();
      if (url.startsWith("http://") || url.startsWith("https://")) {
        void shell.openExternal(url);
      } else {
        log("warn", "window.navigate_blocked", { url });
      }
    }
  });

  // Prevent the SPA's <title> tag from overriding the window title.
  window.on("page-title-updated", (event) => {
    event.preventDefault();
  });

  void window.loadURL("app://app/");

  // Cmd+Shift+I (macOS) / Ctrl+Shift+I opens DevTools for debugging.
  window.webContents.on("before-input-event", (_e, input) => {
    if (input.type === "keyDown" && input.key === "I" && input.shift && (input.meta || input.control)) {
      window.webContents.toggleDevTools();
    }
  });

  // 렌더러 문서가 새로 뜨면 런처 상태를 되돌린다.
  //
  // `markEntered` 는 main 에 남고 렌더러의 `session.entered` 는 문서와 함께
  // 사라진다. 그래서 새로고침(프로젝트 전환이 `location.reload()` 를 쓴다)이나
  // 재적재 뒤에 렌더러가 다시 `launcher:enter` 를 부르면 main 이
  // **`launcher:enter called twice without an intervening reopen`** 으로 막았다.
  // 화면에는 런처가 뜬 채 붉은 오류만 남는다.
  //
  // 이중 진입을 막으려던 가드인데, 정작 막은 것은 **정상적인 재적재**였다.
  // 문서가 바뀌면 그 전 렌더러는 존재하지 않으므로 pending 이 맞다.
  // 새 문서가 뜨기 **시작할 때** 앞 문서의 upstream 요청을 끊는다. 끊지 않으면
  // SSE 가 소켓을 물고 남아, 재적재를 몇 번 반복하면 호스트당 6개 한도가 차서
  // 새 요청이 무한 대기한다(화면에는 "로딩 중" 으로만 보인다).
  window.webContents.on("did-start-navigation", (_e, _url, _isInPlace, isMainFrame) => {
    if (isMainFrame) abortInflightProxy("main frame navigation");
  });

  window.webContents.on("did-finish-load", () => {
    markPending();
    log("info", "launcher.phase_reset", { reason: "renderer document loaded" });
  });

  window.once("ready-to-show", () => window.show());
  window.webContents.on("did-fail-load", (_e, errorCode, errorDescription, validatedURL) => {
    log("error", "window.did_fail_load", { errorCode, errorDescription, validatedURL });
  });

  // 화면 쪽 활동을 파일에 남긴다.
  //
  // 프런트엔드는 `app/logging/logger.js`(LDVC) 로 기록하는데, 그 로거는
  // **브라우저 콘솔에만** 쓴다. DevTools 를 열어 둔 사람만 볼 수 있으니 사실상
  // 남지 않는다. 여기서 한 번 받으면 8개 호출 지점을 고치지 않고도 전부 파일에
  // 들어온다.
  //
  // `level` 은 0~3 = verbose·info·warning·error. `verbose` 는 버린다 —
  // Vite·Vue 내부 잡담이 하루치 파일을 채운다.
  // Electron 31 의 WebContents 는 아직 (level, message, line, sourceId) 를 준다 —
  // `MessageDetails` 를 받는 쪽은 `ServiceWorkers` 다. 올릴 때 여기가 조용히
  // 어긋나므로 형태를 적어 둔다.
  const CONSOLE_LEVELS = ["debug", "info", "warn", "error"] as const;
  window.webContents.on("console-message", (_e, level, message, line, sourceId) => {
    if (level <= 0) return;
    log(CONSOLE_LEVELS[level] ?? "info", "renderer.console", {
      message: message.length > 2000 ? `${message.slice(0, 2000)}…` : message,
      source: sourceId ? path.basename(sourceId) : undefined,
      line,
    });
  });

  // 화면이 죽거나 멈춘 것. 사용자는 "앱이 하얘졌다" 로만 말할 수 있다.
  window.webContents.on("render-process-gone", (_e, d) => {
    log("error", "renderer.gone", { reason: d.reason, exitCode: d.exitCode });
  });
  window.on("unresponsive", () => log("warn", "renderer.unresponsive", {}));
  window.on("responsive", () => log("info", "renderer.responsive", {}));

  // 사용자의 창 조작. "그때 창을 최소화해 뒀나" 같은 질문에 답한다.
  window.on("focus", () => log("info", "window.focus", {}));
  window.on("blur", () => log("info", "window.blur", {}));
  window.on("minimize", () => log("info", "window.minimize", {}));
  window.on("restore", () => log("info", "window.restore", {}));
  window.on("maximize", () => log("info", "window.maximize", {}));
  window.on("unmaximize", () => log("info", "window.unmaximize", {}));
  window.on("close", () => log("info", "window.close", {}));
  window.on("closed", () => {
    log("info", "window.closed", {});
    if (mainWindow === window) {
      mainWindow = null;
    }
  });

  return window;
}

// ---------------------------------------------------------------------------
// T026 IPC handlers
// ---------------------------------------------------------------------------

function registerIpcHandlers(): void {
  registerHandler("app:getRuntimeState", () => buildRuntimeState());

  registerHandler("backend:retry", async () => {
    try {
      await retryBackend();
      return { ok: true as const };
    } catch (err) {
      throw new IpcHandlerError(
        IpcErrorCodes.INTERNAL,
        err instanceof Error ? err.message : String(err),
      );
    }
  });

  registerHandler("logs:reveal", async () => {
    await revealLogs();
    return { ok: true as const };
  });

  // ---------------------------------------------------------------------------
  // spec 058 런타임 감독 — 기존 `app:*` 채널은 그대로 둔다
  // ---------------------------------------------------------------------------

  registerHandler(RUNTIME_CHANNELS.retryService, async ({ serviceId }) => {
    // 자동 되살리기가 한계에 도달해 `stopped` 가 된 뒤에도 **이 길은 열려 있다**(FR-018).
    // 사람이 원인을 고친 뒤 다시 시도하는 자리다.
    if (!runtimeRegistry.knows(serviceId)) {
      throw new IpcHandlerError(IpcErrorCodes.VALIDATION, `unknown service: ${serviceId}`);
    }
    try {
      await restartOwnedService(serviceId);
      return { ok: true as const };
    } catch (err) {
      throw new IpcHandlerError(
        IpcErrorCodes.INTERNAL,
        err instanceof Error ? err.message : String(err),
      );
    }
  });

  registerHandler(RUNTIME_CHANNELS.stopEngine, async ({ confirm }) => {
    // `confirm` 을 요구하는 이유: 실수로 부르면 **남의 화면에서 서비스가 사라진다.**
    if (confirm !== true) {
      throw new IpcHandlerError(IpcErrorCodes.VALIDATION, "stopEngine requires confirm: true");
    }
    const before = getDockerStackRuntime();
    try {
      // `stop` 이고 `down` 이 아니다 — **named volume 을 지우지 않는다**(FR-015).
      await stopDockerStack();
    } catch (err) {
      throw new IpcHandlerError(
        IpcErrorCodes.INTERNAL,
        err instanceof Error ? err.message : String(err),
      );
    }
    const stoppedServiceIds = before ? runtimeRegistry.containerServiceIds() : [];
    for (const id of stoppedServiceIds) runtimeRegistry.markStopped(id, "사용자가 내렸습니다.");
    log("info", "runtime.stop_engine", { count: stoppedServiceIds.length });
    return { ok: true as const, stoppedServiceIds };
  });

  registerHandler(RUNTIME_CHANNELS.openDiagnostics, async () => {
    // 폴더를 여는 길은 **남겨 둔다** — 전문을 봐야 할 때가 있고, 로그는 파일이 원본이다.
    await revealLogs();
    return { ok: true as const };
  });

  /**
   * 고장 난 서비스의 로그를 **그 자리에서** 읽는다 (T028 의 남은 반).
   *
   * 판정과 가리기는 `service-logs.ts` 의 순수 함수가 한다 — 여기서는 **어디서
   * 읽을지** 만 이어 준다. 그래야 그 규칙을 단위 검사로 걸 수 있다.
   */
  registerHandler(RUNTIME_CHANNELS.serviceLogs, async ({ serviceId, tail }) => {
    const logs = await readServiceLogs(
      {
        candidatesOf: (id: ManagedServiceId) => containerNamesFor(COMPOSE_PROJECT_NAME, id),
        ownerOf: (id: ManagedServiceId) =>
          runtimeRegistry.snapshot().services.find((s) => s.id === id)?.owner ?? "app",
        dockerAvailable: () => dockerAvailable(),
        presentContainers: () => presentContainerNames(),
        containerLogs: (name: string, n: number) => containerLogs(name, n),
        backendLines: async (n: number) => backendLogLines(n),
      },
      serviceId,
      tail,
    );
    // **줄은 남기지 않는다.** 비밀이 가려졌다 해도 로그에 로그를 또 적을 이유가 없다.
    log("info", "runtime.service_logs.read", {
      service: serviceId,
      source: logs.source,
      lines: logs.lines.length,
      highlights: logs.highlights.length,
    });
    return logs;
  });

  registerHandler("app:openExternal", async ({ url }) => {
    if (!url.startsWith("http://") && !url.startsWith("https://")) {
      throw new IpcHandlerError(IpcErrorCodes.BLOCKED_SCHEME, `refused to open: ${url}`);
    }
    await shell.openExternal(url);
    return { ok: true as const };
  });

  // 014 analysis-scope-browser: 경로 모드 트리/미리보기 + 파일 작업(root 하위 한정).
  registerHandler("fs:listDir", listDir);
  registerHandler("fs:readFile", readFile);
  registerHandler("fs:rename", rename);
  registerHandler("fs:copy", copy);
  registerHandler("fs:trash", trash);
  registerHandler("fs:mkdir", mkdir);
  registerHandler("fs:writeFile", writeFile);
  registerHandler("fs:stageProject", stageProject);

  // Bridge backend status changes to the renderer.
  let fatalDialogShown = false;
  onBackendStatusChange((status, detail) => {
    const be = getRuntimeBackend();
    pushToRenderer("app:onBackendStatus", {
      status,
      backendPort: be.port,
      boltPort: null,
      detail,
    });
    // **기동이 끝내 실패하면 사람이 볼 수 있게 말한다.**
    //
    // `app:onBackendStatus` 로 밀긴 하는데, 그것을 **그리는 화면이 없다** —
    // `features/runtime-status` 는 스토어만 있고 컴포넌트가 없어서 어디에도
    // 안 붙어 있다(058 US1 의 남은 몫). 그래서 백엔드가 이유를 대고 멈춰도
    // 화면에는 그 이유가 아니라 **가장 먼저 실패한 API 호출**이 보인다 —
    // 프록시의 `503 Backend not ready` 가 `Failed to fetch contexts (HTTP 503)`
    // 로 나오는 식이다(실측). 원인과 증상이 완전히 떨어져 있다.
    //
    // 화면을 제대로 붙이기 전까지는 OS 대화상자가 가장 확실하다 — 렌더러가
    // 안 떴어도, 스토어를 아무도 안 읽어도 보인다.
    // 한 번만 띄운다. `showErrorBox` 는 모달이라, 재시도마다 뜨면 대화상자가
    // 쌓여 앱을 끄지도 못하게 된다.
    if (status === "fatal" && detail && !fatalDialogShown) {
      fatalDialogShown = true;
      dialog.showErrorBox("Robo Architect 를 시작할 수 없다", detail);
    }
  });

  // Stubs for 023 channels whose owning task hasn't shipped yet — kept here so
  // the renderer can call them without crashing the bridge. Each returns a
  // typed `VALIDATION` error pointing at the gating task.
  const unimplemented = [
    "settings:get",
    "settings:set",
    "settings:setSecret",
    "settings:testNeo4jConnection",
    "dataDir:get",
    "dataDir:choose",
    "update:check",
    "update:apply",
  ] as const;
  for (const channel of unimplemented) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (registerHandler as any)(channel, () => {
      throw new IpcHandlerError(
        IpcErrorCodes.VALIDATION,
        `${channel}: not implemented yet (deferred to US2/US3 tasks)`,
      );
    });
  }

  // 032 launcher channels — same pattern but in a separate module so each
  // gating task can opt out of the stub by passing its channel to the skip
  // set when it registers a real handler.
  registerLauncherIpcStubs();
}

// ---------------------------------------------------------------------------
// T025 startup orchestration
// ---------------------------------------------------------------------------

async function bootstrap(): Promise<void> {
  await ensureDataDirs();
  initLogging();
  log("info", "app.ready", { appVersion: app.getVersion() });

  // **죽더라도 기록은 남긴다.**
  //
  // 처리기가 없으면 Electron 이 기본 대화상자("A JavaScript error occurred in the
  // main process")를 띄우고 끝난다 — `desktop.log` 에는 **아무것도 안 남는다.**
  // 사용자가 스크린샷을 보내 주지 않으면 무슨 일이 있었는지 알 길이 없다.
  //
  // EPIPE 는 삼킨다. 앱을 띄운 부모 프로세스가 먼저 끝나면 물려받은 stdout 이
  // 끊기고, 그 뒤 쓰기가 EPIPE 를 낸다. **앱의 잘못이 아니고 기능에도 영향이
  // 없다** — 이것 때문에 죽는 것이 오히려 결함이다(2026-09-28 실측).
  //
  // **삼키는 것만으로는 부족하다.** 2026-09-30 실측: EPIPE 를 기록하는 이
  // `log()` 가 콘솔 미러를 통해 또 EPIPE 를 냈고, 그것이 다시 여기로 왔다.
  // 15분에 `app.uncaught_exception` 32,178줄(21MB), main 프로세스가 한 코어를
  // 100% 물고 응답 정지, SSE 프록시가 막혀 **백엔드 전체 탐색이 3번째 프로세스
  // 에서 멈췄다.** 그래서 (1) 첫 EPIPE 에 콘솔 미러를 끄고, (2) 한 번만 적고,
  // (3) 처리기 재진입을 막는다. 셋 중 하나만 빠져도 되돌아온다.
  let handling = false;
  let epipeSeen = 0;
  process.on("uncaughtException", (error: NodeJS.ErrnoException) => {
    const epipe = error?.code === "EPIPE";
    if (epipe) {
      // 미러가 원인일 수 있다 — 기록하기 **전에** 끊는다.
      disableConsoleMirror();
      epipeSeen += 1;
      // 두 번째부터는 적지 않는다. 같은 줄이 로그를 통째로 덮어 버린다.
      if (epipeSeen > 1) return;
    }
    if (handling) return; // 기록 자체가 던진 경우
    handling = true;
    try {
      log(epipe ? "warn" : "error", "app.uncaught_exception", {
        code: error?.code,
        message: error?.message,
        stack: error?.stack?.split("\n").slice(0, 8).join(" | "),
        swallowed: epipe,
        ...(epipe ? { note: "콘솔 미러를 껐다. 이후 EPIPE 는 적지 않는다." } : {}),
      });
    } finally {
      handling = false;
    }
    if (epipe) return;
    // 그 밖의 예외는 사람에게 보이고 끝낸다 — 기본 동작과 같되 기록이 남는다.
    try {
      dialog.showErrorBox(
        "Robo Architect 에 오류가 발생했다",
        `${error?.message ?? error}\n\n자세한 내용은 로그를 보라:\n${getLogsDir()}`,
      );
    } catch {
      /* 대화상자를 못 띄우는 상황이라도 위 로그는 남았다 */
    }
    app.exit(1);
  });

  // Set macOS Dock icon.
  if (process.platform === "darwin" && app.dock) {
    const iconPath = path.resolve(app.getAppPath(), "resources", "icons", "icon_512x512.png");
    if (fs.existsSync(iconPath)) {
      const img = nativeImage.createFromPath(iconPath);
      if (!img.isEmpty()) {
        app.dock.setIcon(img);
        log("info", "app.dock_icon_set", { iconPath });
      } else {
        log("warn", "app.dock_icon_empty", { iconPath });
      }
    } else {
      log("warn", "app.dock_icon_missing", { iconPath });
    }
  }

  registerAppProtocol();
  registerIpcHandlers();

  // Create the window early so the user gets a splash even while the backend
  // starts up. The SPA proxy returns 503 for /api calls until backend is
  // ready — the renderer will retry; full splash UI lands in T027.
  mainWindow = createMainWindow();

  try {
    await startBackend();
  } catch (err) {
    log("error", "app.backend_start_failed", {
      message: err instanceof Error ? err.message : String(err),
    });
    // **실패해도 감독은 돈다.** 무엇이 준비되지 않았는지는 그때가 가장 알고 싶다.
    // status is already set to "fatal" by backend.ts; the renderer will see
    // the push and (post-T027) show the fatal screen.
  }

  // 스택이 떴으면(또는 뜨다 실패했으면) 서비스별로 재기 시작한다 (T018).
  startRuntimeSupervision();
}

// ---------------------------------------------------------------------------
// App lifecycle
// ---------------------------------------------------------------------------

if (gotLock) {
  // Set the Dock icon as early as possible — before bootstrap() so it appears
  // on first paint rather than being updated after the window is shown.
  if (process.platform === "darwin") {
    app.on("will-finish-launching", () => {
      // Compiled file is at dist/main/index.js → ../../resources/
      const iconPath = path.resolve(__dirname, "..", "..", "resources", "icons", "icon_512x512.png");
      if (fs.existsSync(iconPath)) {
        const img = nativeImage.createFromPath(iconPath);
        if (!img.isEmpty() && app.dock) {
          app.dock.setIcon(img);
        }
      }
    });
  }

  app.whenReady().then(() => {
    bootstrap().catch((err: unknown) => {
      log("error", "app.bootstrap.failed", {
        message: err instanceof Error ? err.message : String(err),
      });
    });
  });

  app.on("window-all-closed", () => {
    log("info", "app.window_all_closed", {});
    app.quit();
  });

  app.on("before-quit", async (event) => {
    log("info", "app.before-quit", {});
    // 감독을 먼저 세운다 — 내리는 중의 프로브는 "죽었다" 를 새로 기록할 뿐이다.
    supervision?.stop();
    supervision = null;
    // Best-effort: give the backend a graceful shutdown before Electron exits.
    if (getRuntimeBackend().pid !== null) {
      event.preventDefault();
      try {
        await stopBackend();
      } finally {
        log("info", "app.exit", { reason: "backend stopped" });
        app.exit(0);
      }
    }
  });

  // **끝났다는 사실 자체를 남긴다.** `before-quit` 은 백엔드가 떠 있을 때만
  // 뒤를 마저 돌고, 강제 종료(작업관리자·`Stop-Process`)는 아무 흔적도 안 남긴다.
  // 그러면 로그의 마지막 줄만 보고는 "여기서 껐다" 와 "여기서 죽었다" 를 구별할
  // 수 없다 — 다음 기동의 `app.ready` 와 짝이 맞는지로만 짐작해야 했다.
  app.on("will-quit", () => log("info", "app.will_quit", {}));
  app.on("quit", (_e, exitCode) => log("info", "app.quit", { exitCode }));
}
