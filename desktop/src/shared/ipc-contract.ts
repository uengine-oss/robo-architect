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
}

export type IpcSubscriptionChannel = keyof IpcSubscriptionMap;

/** Returned from every `on*` subscription on the renderer side. */
export type Unsubscribe = () => void;

// ---------------------------------------------------------------------------
// The shape exposed on `window.desktop` (preload contextBridge surface)
// ---------------------------------------------------------------------------

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
