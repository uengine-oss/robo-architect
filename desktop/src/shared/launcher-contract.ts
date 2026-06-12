/**
 * 032 launcher: type surface for the desktop startup picker.
 *
 * Mirrors `specs/032-desktop-startup-picker/data-model.md` and
 * `specs/032-desktop-startup-picker/contracts/launcher-ipc-contract.md`.
 *
 * Consumed by Electron main, preload, renderer launcher feature, and
 * the renderer-side session store. No backend (Python) shapes here —
 * the identity-header contract lives in
 * `api/platform/identity/models.py` on the Python side.
 */

import type {
  IpcResult,
  TestNeo4jConnectionData,
  TestNeo4jConnectionParams,
} from "./ipc-contract";

// ---------------------------------------------------------------------------
// SavedConnection — persisted in settings.json (no password attribute)
// ---------------------------------------------------------------------------

export type ConnectionSource =
  | "manual"
  | "imported-from-neo4j-desktop"
  | "bundled"
  | "manual-migrated-from-023";

export interface SavedConnection {
  /** uuid v4; main-process-assigned at creation, immutable thereafter. */
  id: string;
  /** User-chosen label; 1–60 chars, trimmed. */
  label: string;
  /** Bolt URI — bolt:// / bolt+s:// / bolt+ssc:// / neo4j:// / neo4j+s:// / neo4j+ssc://. */
  uri: string;
  /** Neo4j username; 1–256 chars, no embedded newlines. */
  user: string;
  /** Optional default database; lowercase + digits + dashes, 1–63 chars. */
  database?: string;
  source: ConnectionSource;
  /** ISO-8601 UTC. */
  lastConnectedAt: string | null;
  /** ISO-8601 UTC. */
  createdAt: string;
}

// ---------------------------------------------------------------------------
// DiscoveredConnection — transient, from local Neo4j Desktop config
// ---------------------------------------------------------------------------

export type DiscoveredStatus = "running" | "stopped" | "unknown";

export interface DiscoveredConnection {
  /** Stable per-scan id derived from the Neo4j Desktop DBMS UUID. */
  discoveryId: string;
  dbmsName: string;
  uri: string;
  neo4jVersion: string;
  status: DiscoveredStatus;
  /** Neo4j Desktop "Project" the DBMS belongs to; null if ungrouped. */
  projectName: string | null;
}

// ---------------------------------------------------------------------------
// ProjectRoot
// ---------------------------------------------------------------------------

export interface ProjectRootEntry {
  /** Absolute filesystem path. */
  path: string;
  /** ISO-8601 UTC of last hand-off using this root. */
  lastUsedAt: string;
}

// ---------------------------------------------------------------------------
// LaunchProfile — the (connection, project root) pair the launcher resumes
// ---------------------------------------------------------------------------

export interface LaunchProfile {
  connectionId: string;
  projectRoot: string;
  /** ISO-8601 UTC of the last successful Enter using this exact pair. */
  enteredAt: string;
}

// ---------------------------------------------------------------------------
// SessionUser — resolved from git config on the host; not persisted
// ---------------------------------------------------------------------------

export type IdentitySource =
  | "env"
  | "project-local-git"
  | "global-git"
  | "system-git"
  | "unknown-fallback";

export interface SessionUser {
  name: string;
  email: string;
  source: IdentitySource;
  /** `name` truncated at 40 chars with ellipsis; UI-only field. */
  displayName: string;
}

// ---------------------------------------------------------------------------
// IPC channel signatures (per contracts/launcher-ipc-contract.md)
// ---------------------------------------------------------------------------

export interface ConnectionsSaveInput {
  label: string;
  uri: string;
  user: string;
  database?: string;
  source: Exclude<ConnectionSource, "bundled" | "manual-migrated-from-023">;
  passwordPlaintext?: string;
}

export interface ConnectionsUpdateInput {
  id: string;
  label?: string;
  uri?: string;
  user?: string;
  database?: string | null;
  /** undefined = leave; null = clear keychain entry; non-empty = replace. */
  passwordPlaintext?: string | null;
}

export interface ConnectionsDeleteInput {
  id: string;
}

// ---------------------------------------------------------------------------
// ActiveBackendConnection — 임베드 백엔드(analyzer/catalog)가 사용할 활성 연결의
// 전체 자격증명(키체인 비밀번호 포함). 렌더러가 analyzer mount({neo4j}) 로 전달 →
// X-Neo4j-* 헤더로 백엔드에 override. SavedConnection 과 달리 password 를 포함하므로
// 영속(settings.json) 대상이 아니라 mount 직전 1회 조회용 — 비번은 키체인에서 즉시 읽어 반환.
// ---------------------------------------------------------------------------

export interface ActiveBackendConnection {
  uri: string;
  user: string;
  password: string;
  database?: string;
}

export type ProbeStatusState =
  | "connected"
  | "unreachable"
  | "auth-failed"
  | "stopped"
  | "timeout";

export interface ProbeStatusResult {
  state: ProbeStatusState;
  serverVersion?: string;
  /** Short human-readable reason; never a stack trace, never a secret. */
  detail?: string;
}

export interface ProbeStatusInput {
  id: string;
}

export type ProjectRootChooseResult =
  | { path: string; valid: boolean; basename: string; parent: string }
  | { cancelled: true };

export interface ProjectRootValidateInput {
  path: string;
}

export interface ProjectRootValidateResult {
  valid: boolean;
  reason?: "not-found" | "not-a-directory" | "unreadable";
}

export interface IdentityResolveInput {
  projectRoot: string | null;
}

export interface IdentitySetGitConfigInput {
  name: string;
  email: string;
}

export interface ProjectRootCreateInput {
  /** Absolute path for the new directory to create. */
  path: string;
}

export interface LauncherEnterInput {
  connectionId: string;
  projectRoot: string;
  /** Renderer's snapshot of identity; main re-resolves and may return a different value. */
  identity: SessionUser;
}

export interface LauncherEnterResult {
  /** Authoritative identity after main's re-resolution (FR-008, FR-009). */
  identity: SessionUser;
  /** The connection actually loaded into backend env. */
  activeConnectionId: string;
}

// ---------------------------------------------------------------------------
// Per-channel request/response map — composed with the 023 IpcRequestMap
// via TypeScript declaration merging in main+preload at registration time.
// ---------------------------------------------------------------------------

export interface LauncherIpcRequestMap {
  "connections:list": [void, SavedConnection[]];
  "connections:save": [ConnectionsSaveInput, SavedConnection];
  "connections:update": [ConnectionsUpdateInput, SavedConnection];
  "connections:delete": [ConnectionsDeleteInput, { ok: true }];
  "connections:resolveActiveForBackend": [void, ActiveBackendConnection | null];
  "connections:discoverNeo4jDesktop": [void, DiscoveredConnection[]];
  "connections:probeStatus": [ProbeStatusInput, ProbeStatusResult];
  "connections:test": [TestNeo4jConnectionParams, TestNeo4jConnectionData];
  "projectRoot:choose": [void, ProjectRootChooseResult];
  "projectRoot:createNew": [ProjectRootCreateInput, ProjectRootChooseResult];
  "projectRoot:listRecent": [void, ProjectRootEntry[]];
  "projectRoot:validate": [ProjectRootValidateInput, ProjectRootValidateResult];
  "identity:resolve": [IdentityResolveInput, SessionUser];
  "identity:setGitConfig": [IdentitySetGitConfigInput, SessionUser];
  "launcher:enter": [LauncherEnterInput, LauncherEnterResult];
  "launcher:reopen": [void, { ok: true }];
}

export type LauncherIpcChannel = keyof LauncherIpcRequestMap;

// ---------------------------------------------------------------------------
// The shape exposed on `window.desktop` (renderer side)
// ---------------------------------------------------------------------------

export interface LauncherDesktopBridge {
  connections: {
    list(): Promise<IpcResult<SavedConnection[]>>;
    save(input: ConnectionsSaveInput): Promise<IpcResult<SavedConnection>>;
    update(input: ConnectionsUpdateInput): Promise<IpcResult<SavedConnection>>;
    delete(input: ConnectionsDeleteInput): Promise<IpcResult<{ ok: true }>>;
    resolveActiveForBackend(): Promise<IpcResult<ActiveBackendConnection | null>>;
    discoverNeo4jDesktop(): Promise<IpcResult<DiscoveredConnection[]>>;
    probeStatus(input: ProbeStatusInput): Promise<IpcResult<ProbeStatusResult>>;
    test(input: TestNeo4jConnectionParams): Promise<IpcResult<TestNeo4jConnectionData>>;
  };
  projectRoot: {
    choose(): Promise<IpcResult<ProjectRootChooseResult>>;
    createNew(input: ProjectRootCreateInput): Promise<IpcResult<ProjectRootChooseResult>>;
    listRecent(): Promise<IpcResult<ProjectRootEntry[]>>;
    validate(input: ProjectRootValidateInput): Promise<IpcResult<ProjectRootValidateResult>>;
  };
  identity: {
    resolve(input: IdentityResolveInput): Promise<IpcResult<SessionUser>>;
    setGitConfig(input: IdentitySetGitConfigInput): Promise<IpcResult<SessionUser>>;
  };
  launcher: {
    enter(input: LauncherEnterInput): Promise<IpcResult<LauncherEnterResult>>;
    reopen(): Promise<IpcResult<{ ok: true }>>;
  };
}

// ---------------------------------------------------------------------------
// Settings v2 extension — see data-model.md §2
// ---------------------------------------------------------------------------

/**
 * Fields added to `DesktopSettings` in v2. Composed with the 023 v1
 * `DesktopSettings` shape via the migration in `settings-migrate.ts`.
 */
export interface DesktopSettingsV2Additions {
  savedConnections: SavedConnection[];
  /** Absolute paths, most-recent first, max 5. */
  recentProjectRoots: string[];
  lastProfile: LaunchProfile | null;
}

export const SETTINGS_SCHEMA_VERSION_V2 = 2 as const;

/** Keychain key format for a SavedConnection's password. */
export function connectionPasswordSecretId(connectionId: string): string {
  return `connection.${connectionId}.password`;
}

// ---------------------------------------------------------------------------
// Module augmentation — fold launcher channels into the global IpcRequestMap
// so `registerHandler` and the preload bridge are type-checked end-to-end.
// ---------------------------------------------------------------------------

declare module "./ipc-contract" {
  // TypeScript interface merging extends the existing IpcRequestMap with the
  // launcher channels without modifying ipc-contract.ts.
  interface IpcRequestMap extends LauncherIpcRequestMap {}

  // Extend DesktopBridge itself so that `window.desktop?: DesktopBridge`
  // (declared in ipc-contract.ts) automatically includes the launcher
  // surface — no need to redeclare `interface Window`, which would conflict
  // with the original declaration's exact-type requirement.
  interface DesktopBridge extends LauncherDesktopBridge {}
}
