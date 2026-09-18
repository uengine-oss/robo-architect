/**
 * Single source of truth for the Electron main ↔ renderer IPC surface.
 * Mirrors `specs/023-electron-desktop-app/contracts/ipc-contract.md` and the shapes
 * defined in `specs/023-electron-desktop-app/data-model.md`.
 *
 * The renderer only ever touches these types via the `window.desktop` object
 * exposed by `desktop/src/preload/index.ts`. No `ipcRenderer`, `require`,
 * `process`, or Node API leaks across the bridge (FR-021).
 */

// ---------------------------------------------------------------------------
// Closed error enum (every `invoke` resolves to the typed envelope below)
// ---------------------------------------------------------------------------

export const IpcErrorCodes = {
  VALIDATION: "VALIDATION",
  NEOJ4_UNVERIFIED: "NEOJ4_UNVERIFIED",
  NEO4J_UNREACHABLE: "NEO4J_UNREACHABLE",
  NEO4J_AUTH_FAILED: "NEO4J_AUTH_FAILED",
  NEO4J_TIMEOUT: "NEO4J_TIMEOUT",
  NEO4J_TLS_ERROR: "NEO4J_TLS_ERROR",
  DATA_DIR_NOT_WRITABLE: "DATA_DIR_NOT_WRITABLE",
  UNKNOWN_SECRET: "UNKNOWN_SECRET",
  UPDATE_NOT_READY: "UPDATE_NOT_READY",
  BLOCKED_SCHEME: "BLOCKED_SCHEME",
  INTERNAL: "INTERNAL",
  // ---- added by 032 (desktop launcher) ----
  CONNECTION_DUPLICATE: "CONNECTION_DUPLICATE",
  CONNECTION_NOT_FOUND: "CONNECTION_NOT_FOUND",
  DISCOVERY_UNAVAILABLE: "DISCOVERY_UNAVAILABLE",
  PROJECT_ROOT_INVALID: "PROJECT_ROOT_INVALID",
  PROJECT_ROOT_UNREADABLE: "PROJECT_ROOT_UNREADABLE",
  GIT_UNAVAILABLE: "GIT_UNAVAILABLE",
  LAUNCHER_ALREADY_ENTERED: "LAUNCHER_ALREADY_ENTERED",
} as const;

export type IpcErrorCode = (typeof IpcErrorCodes)[keyof typeof IpcErrorCodes];

export interface IpcError {
  code: IpcErrorCode;
  message: string;
}

export type IpcResult<T> = { ok: true; data: T } | { ok: false; error: IpcError };

// ---------------------------------------------------------------------------
// Persisted: DesktopSettings (mirrors data-model.md §"Persisted")
// ---------------------------------------------------------------------------

export type DataSource = "bundled" | "external";

export type LlmProvider = "openai" | "anthropic" | "google";

export interface WindowBounds {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface ExternalNeo4jConfig {
  uri: string;
  user: string;
  database: string;
}

export interface DesktopSettings {
  schemaVersion: number;
  dataSource: DataSource;
  externalNeo4j: ExternalNeo4jConfig | null;
  dataDir: string | null;
  llm: { provider: LlmProvider; model: string };
  update: { autoCheck: boolean; lastCheckedAt: string | null };
  window: { bounds: WindowBounds | null; maximized: boolean };
  lastPorts: { backend: number | null; bolt: number | null };
  // ---- added by 032 (DesktopSettings v2) ----
  // Each field is populated by the v1 → v2 migration; pre-existing
  // 023 v1 files are upgraded in-place on first load.
  savedConnections: import("./launcher-contract").SavedConnection[];
  /** Absolute paths, most-recent first, max 5. */
  recentProjectRoots: string[];
  lastProfile: import("./launcher-contract").LaunchProfile | null;
}

/**
 * Subset of DesktopSettings that the renderer is allowed to mutate via
 * `settings:set`. `schemaVersion` is managed exclusively by main.
 */
export type DesktopSettingsWritable = Omit<DesktopSettings, "schemaVersion">;

// ---------------------------------------------------------------------------
// Transient: RuntimeState (mirrors data-model.md §"Transient")
// ---------------------------------------------------------------------------

export type RuntimeStatus =
  | "initializing"
  | "starting-db"
  | "starting-backend"
  | "ready"
  | "backend-crashed"
  | "db-crashed"
  | "restarting"
  | "fatal";

export type UpdateState =
  | "idle"
  | "checking"
  | "available"
  | "downloading"
  | "ready-to-install"
  | "error";

export interface RuntimeState {
  /** spec 058 — 아래 신규 필드는 **모두 선택적**이다. 옛 렌더러를 깨뜨리지 않는다. */
  services?: ManagedService[];
  /** 옛 구성에 남은 데이터 안내(T049). `null` 은 "아직 안 봤다"다. */
  legacyData?: LegacyDataNotice | null;
  capabilities?: Capability[];
  graphGuard?: GraphGuard | null;
  releaseId?: string | null;
  /**
   * 컨테이너 실행 환경 자체의 유무.
   *
   * **세 값이다.** `false` 는 "없다"(화면이 준비 안내를 낸다), `null` 은 **"아직 못
   * 쟀다"** 다. 둘을 뭉치면 기동 초반에 "도커를 설치하세요"가 잘못 뜬다.
   */
  dockerAvailable?: boolean | null;
  appVersion: string;
  backendPort: number | null;
  boltPort: number | null;
  backendPid: number | null;
  neo4jPid: number | null;
  status: RuntimeStatus;
  dataSource: DataSource;
  dataDir: string;
  updateState: UpdateState;
}

// ---------------------------------------------------------------------------
// Secret store (OS keychain) reference enum (data-model.md §"SecretRef")
// ---------------------------------------------------------------------------

export const SecretIds = {
  Neo4jPassword: "neo4j.password",
  LlmOpenAi: "llm.openai.apiKey",
  LlmAnthropic: "llm.anthropic.apiKey",
  LlmGoogle: "llm.google.apiKey",
  FigmaApiToken: "figma.apiToken",
} as const;

export type SecretId = (typeof SecretIds)[keyof typeof SecretIds];

/** `secretsPresent` map returned from `settings:get` — never carries values. */
export type SecretsPresenceMap = Partial<Record<SecretId, boolean>>;

// ---------------------------------------------------------------------------
// Per-channel request/response signatures
// ---------------------------------------------------------------------------

export interface SettingsGetResult extends DesktopSettings {
  secretsPresent: SecretsPresenceMap;
}

export interface DataDirInfo {
  path: string;
  writable: boolean;
  isDefault: boolean;
}

export type DataDirChooseResult =
  | { path: string; writable: boolean }
  | { cancelled: true };

export interface TestNeo4jConnectionParams {
  uri: string;
  user: string;
  password: string;
  database: string;
}

export interface TestNeo4jConnectionData {
  ok: true;
  serverVersion?: string;
}

export interface UpdateCheckResult {
  state: UpdateState;
  version?: string;
}

export interface SetSecretParams {
  id: SecretId;
  /** Empty string clears the secret. Never logged, never echoed back. */
  value: string;
}

export interface OpenExternalParams {
  url: string;
}

/**
 * Per-channel signature map. Each entry: `[RequestArgs, ResponseData]`.
 * The actual transport always wraps `ResponseData` in `IpcResult<ResponseData>`.
 */
export interface IpcRequestMap {
  "app:getRuntimeState": [void, RuntimeState];
  "settings:get": [void, SettingsGetResult];
  "settings:set": [Partial<DesktopSettingsWritable>, DesktopSettings];
  "settings:setSecret": [SetSecretParams, { ok: true }];
  "settings:testNeo4jConnection": [TestNeo4jConnectionParams, TestNeo4jConnectionData];
  "dataDir:get": [void, DataDirInfo];
  "dataDir:choose": [void, DataDirChooseResult];
  "backend:retry": [void, { ok: true }];
  "logs:reveal": [void, { ok: true }];
  "update:check": [void, UpdateCheckResult];
  "update:apply": [void, { ok: true }];
  "app:openExternal": [OpenExternalParams, { ok: true }];
  // spec 058 — **이 표에 없으면 registerHandler 가 타입에서 걸린다.** 채널을 더하고
  // 여기 빠뜨리면 빌드가 막는다. 계약이 한 곳에 모여 있다는 뜻이다.
  "runtime:retryService": [{ serviceId: ManagedServiceId }, { ok: true }];
  "runtime:stopEngine": [
    { confirm: true },
    { ok: true; stoppedServiceIds: ManagedServiceId[] },
  ];
  "runtime:openDiagnostics": [{ serviceId?: ManagedServiceId }, { ok: true }];
}

export type IpcChannel = keyof IpcRequestMap;

// ---------------------------------------------------------------------------
// Subscription channels (main → renderer)
// ---------------------------------------------------------------------------

export interface BackendStatusEvent {
  status: RuntimeStatus;
  backendPort: number | null;
  boltPort: number | null;
  /** Short human-readable reason; never a stack trace, never a secret. */
  detail?: string;
}

export interface UpdateStateEvent {
  state: UpdateState;
  version?: string;
  progressPercent?: number;
}

export interface DataSourceChangedEvent {
  dataSource: DataSource;
  dataDir: string;
}

export interface IpcSubscriptionMap {
  "app:onBackendStatus": BackendStatusEvent;
  "app:onUpdateState": UpdateStateEvent;
  "app:onDataSourceChanged": DataSourceChangedEvent;
  /**
   * spec 058. **이 표에 없으면 preload 가 구독을 못 만든다** — 채널만 더하고 여기
   * 빠뜨리면 빌드에서 걸린다(실제로 걸렸다). 계약이 한 곳에 모여 있다는 뜻이다.
   */
  "runtime:onStatus": RuntimeStatusPayload;
}

export type IpcSubscriptionChannel = keyof IpcSubscriptionMap;

/** Returned from every `on*` subscription on the renderer side. */
export type Unsubscribe = () => void;

// ---------------------------------------------------------------------------
// The shape exposed on `window.desktop` (preload contextBridge surface)
// ---------------------------------------------------------------------------

/**
 * 런타임 감독 타입은 `runtime-contract.ts` 에 산다 — 이 파일은 023·032 계약이고
 * 섞으면 어느 스펙의 계약인지 안 보인다.
 */
import type {
  Capability,
  GraphGuard,
  LegacyDataNotice,
  ManagedService,
  ManagedServiceId,
  RuntimeStatusPayload,
} from "./runtime-contract";

export type {
  Capability,
  GraphGuard,
  LegacyDataNotice,
  ManagedService,
  ManagedServiceId,
  RuntimeStatusPayload,
};

export interface DesktopBridge {
  app: {
    getRuntimeState(): Promise<IpcResult<RuntimeState>>;
    openExternal(params: OpenExternalParams): Promise<IpcResult<{ ok: true }>>;
    onBackendStatus(cb: (e: BackendStatusEvent) => void): Unsubscribe;
    onUpdateState(cb: (e: UpdateStateEvent) => void): Unsubscribe;
    onDataSourceChanged(cb: (e: DataSourceChangedEvent) => void): Unsubscribe;
  };
  settings: {
    get(): Promise<IpcResult<SettingsGetResult>>;
    set(patch: Partial<DesktopSettingsWritable>): Promise<IpcResult<DesktopSettings>>;
    setSecret(params: SetSecretParams): Promise<IpcResult<{ ok: true }>>;
    testNeo4jConnection(
      params: TestNeo4jConnectionParams,
    ): Promise<IpcResult<TestNeo4jConnectionData>>;
  };
  dataDir: {
    get(): Promise<IpcResult<DataDirInfo>>;
    choose(): Promise<IpcResult<DataDirChooseResult>>;
  };
  backend: {
    retry(): Promise<IpcResult<{ ok: true }>>;
  };
  /**
   * 런타임 감독 (spec 058). **기존 `app.*` 을 대체하지 않는다** — `getRuntimeState` 와
   * `onBackendStatus` 는 그대로 살아 있고, 이쪽이 더해진다.
   */
  runtime: {
    /** 상태가 **바뀔 때만** 온다. 주기 전송이 아니다. */
    onStatus(cb: (e: RuntimeStatusPayload) => void): Unsubscribe;
    retryService(input: { serviceId: ManagedServiceId }): Promise<IpcResult<{ ok: true }>>;
    /** 앱이 소유한 컨테이너만 내린다. **사용자 데이터는 보존한다.** */
    stopEngine(input: { confirm: true }): Promise<
      IpcResult<{ ok: true; stoppedServiceIds: ManagedServiceId[] }>
    >;
    openDiagnostics(input: { serviceId?: ManagedServiceId }): Promise<IpcResult<{ ok: true }>>;
  };
  logs: {
    reveal(): Promise<IpcResult<{ ok: true }>>;
  };
  update: {
    check(): Promise<IpcResult<UpdateCheckResult>>;
    apply(): Promise<IpcResult<{ ok: true }>>;
  };
}

declare global {
  interface Window {
    /** Present only in the Electron renderer; `undefined` in web/server mode. */
    desktop?: DesktopBridge;
  }
}
