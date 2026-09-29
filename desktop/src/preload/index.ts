/**
 * Preload script — the only bridge between the renderer and the main process.
 *
 * Exposes exactly the channels declared in `shared/ipc-contract.ts` on
 * `window.desktop`. Nothing else (`ipcRenderer`, `require`, `process`,
 * `Buffer`, Node APIs) is exposed (FR-021).
 *
 * Sandbox: this file runs in a sandboxed renderer process pre-page-load.
 * `contextBridge` clones values across the realm boundary; subscription
 * payloads are plain objects per the IPC contract.
 *
 * Subscription channels return an unsubscribe function. The closure-captured
 * listener reference is the one that gets `removeListener`-ed.
 */

import { contextBridge, ipcRenderer, type IpcRendererEvent } from "electron";

import type { ManagedServiceId, RuntimeStatusPayload } from "../shared/runtime-contract";

/**
 * `RUNTIME_CHANNELS` 의 **지역 사본**. 왜 베끼는가.
 *
 * 이 preload 는 `sandbox: true` 로 뜬다(`src/main/index.ts`). 샌드박스 preload 의
 * `require` 는 `electron` 과 일부 내장 모듈만 해소한다 — **상대 경로는 못 찾는다.**
 * 그래서 값 import 하나가 브리지를 통째로 죽인다:
 *
 *     Unable to load preload script: …\app.asar\dist\preload\preload\index.js
 *     Error: module not found: ../shared/runtime-contract
 *
 * 실제로 그랬다. `bba8be6`(2026-09-18)이 이 파일의 **최초 값 import** 로
 * `RUNTIME_CHANNELS` 를 들여왔고, 그 뒤 11일 동안 패키지 앱의 IPC 가 하나도
 * 동작하지 않았다 — `window.robo` 가 없으니 화면은 자기를 웹 SPA 로 알고
 * 런처를 건너뛰었다. HTTP 는 `app://` 프록시로 멀쩡히 흘러서 **증상이 없었다.**
 * 2026-09-29 에 렌더러 콘솔을 파일로 받기 시작한 뒤에야 드러났다.
 *
 * 번들러를 붙이면 근본 해결이지만 오프라인 설치본에 빌드 의존성을 더하는 값이
 * 이 4개 문자열보다 크지 않다. 대신 **어긋나면 컴파일이 깨지게** 묶는다.
 */
const RUNTIME_CHANNELS = {
  onStatus: "runtime:onStatus",
  retryService: "runtime:retryService",
  stopEngine: "runtime:stopEngine",
  openDiagnostics: "runtime:openDiagnostics",
} as const;

// 원본과 양방향으로 대조한다. 한쪽에 채널이 생기거나 문자열이 달라지면 여기서
// 컴파일이 깨진다. `import(...)` 는 타입 위치라 런타임 require 를 만들지 않는다.
type SharedRuntimeChannels = typeof import("../shared/runtime-contract")["RUNTIME_CHANNELS"];
const _channelsAreComplete: SharedRuntimeChannels = RUNTIME_CHANNELS;
const _channelsAreExact: typeof RUNTIME_CHANNELS = _channelsAreComplete;
void _channelsAreExact;

import type {
  BackendStatusEvent,
  DataDirChooseResult,
  DataDirInfo,
  DataSourceChangedEvent,
  DesktopBridge,
  DesktopSettings,
  DesktopSettingsWritable,
  IpcResult,
  IpcSubscriptionChannel,
  IpcSubscriptionMap,
  OpenExternalParams,
  RuntimeState,
  SetSecretParams,
  SettingsGetResult,
  TestNeo4jConnectionData,
  TestNeo4jConnectionParams,
  Unsubscribe,
  UpdateCheckResult,
  UpdateStateEvent,
} from "../shared/ipc-contract";
// 032: extend window.desktop with launcher channels.
import type {
  ActiveBackendConnection,
  ConnectionsDeleteInput,
  ConnectionsSaveInput,
  ConnectionsUpdateInput,
  DiscoveredConnection,
  IdentityResolveInput,
  IdentitySetGitConfigInput,
  LauncherDesktopBridge,
  LauncherEnterInput,
  LauncherEnterResult,
  ProbeStatusInput,
  ProbeStatusResult,
  ProjectRootChooseResult,
  ProjectRootCreateInput,
  ProjectRootEntry,
  ProjectRootValidateInput,
  ProjectRootValidateResult,
  SavedConnection,
  SessionUser,
} from "../shared/launcher-contract";
// 014: extend window.desktop with local FS browse channels.
import type {
  FsBrowserDesktopBridge,
  FsEntry,
  FsListInput,
  FsMovePairInput,
  FsPathInput,
  FsReadInput,
  FsReadResult,
  FsStageProjectInput,
  FsStageProjectResult,
  FsWriteInput,
} from "../shared/fs-browser-contract";

function invoke<T>(channel: string, args?: unknown): Promise<IpcResult<T>> {
  return ipcRenderer.invoke(channel, args) as Promise<IpcResult<T>>;
}

function subscribe<C extends IpcSubscriptionChannel>(
  channel: C,
  cb: (payload: IpcSubscriptionMap[C]) => void,
): Unsubscribe {
  const listener = (_e: IpcRendererEvent, payload: IpcSubscriptionMap[C]) => cb(payload);
  ipcRenderer.on(channel, listener);
  return () => {
    ipcRenderer.removeListener(channel, listener);
  };
}

// 032 launcher surface — built separately and merged into the exposed bridge
// below. Keeps the 023 DesktopBridge type clean while letting us share the
// `invoke` helper.
const launcherBridge: LauncherDesktopBridge = {
  connections: {
    list: () => invoke<SavedConnection[]>("connections:list"),
    save: (input: ConnectionsSaveInput) => invoke<SavedConnection>("connections:save", input),
    update: (input: ConnectionsUpdateInput) =>
      invoke<SavedConnection>("connections:update", input),
    delete: (input: ConnectionsDeleteInput) =>
      invoke<{ ok: true }>("connections:delete", input),
    resolveActiveForBackend: () =>
      invoke<ActiveBackendConnection | null>("connections:resolveActiveForBackend"),
    discoverNeo4jDesktop: () =>
      invoke<DiscoveredConnection[]>("connections:discoverNeo4jDesktop"),
    probeStatus: (input: ProbeStatusInput) =>
      invoke<ProbeStatusResult>("connections:probeStatus", input),
    test: (params: TestNeo4jConnectionParams) =>
      invoke<TestNeo4jConnectionData>("connections:test", params),
  },
  projectRoot: {
    choose: () => invoke<ProjectRootChooseResult>("projectRoot:choose"),
    createNew: (input: ProjectRootCreateInput) =>
      invoke<ProjectRootChooseResult>("projectRoot:createNew", input),
    listRecent: () => invoke<ProjectRootEntry[]>("projectRoot:listRecent"),
    validate: (input: ProjectRootValidateInput) =>
      invoke<ProjectRootValidateResult>("projectRoot:validate", input),
  },
  identity: {
    resolve: (input: IdentityResolveInput) => invoke<SessionUser>("identity:resolve", input),
    setGitConfig: (input: IdentitySetGitConfigInput) =>
      invoke<SessionUser>("identity:setGitConfig", input),
  },
  launcher: {
    enter: (input: LauncherEnterInput) =>
      invoke<LauncherEnterResult>("launcher:enter", input),
    reopen: () => invoke<{ ok: true }>("launcher:reopen"),
  },
};

// `DesktopBridge` now also includes the launcher surface (via module
// augmentation in launcher-contract.ts). We compose it in two literals
// and merge below — the `Omit` narrows the annotation to the 023 half so
// TypeScript doesn't ask for launcher methods in the same literal.
const fsBridge: FsBrowserDesktopBridge = {
  fs: {
    listDir: (input: FsListInput) => invoke<FsEntry[]>("fs:listDir", input),
    readFile: (input: FsReadInput) => invoke<FsReadResult>("fs:readFile", input),
    rename: (input: FsMovePairInput) => invoke<{ ok: true }>("fs:rename", input),
    copy: (input: FsMovePairInput) => invoke<{ ok: true }>("fs:copy", input),
    trash: (input: FsPathInput) => invoke<{ ok: true }>("fs:trash", input),
    mkdir: (input: FsPathInput) => invoke<{ ok: true }>("fs:mkdir", input),
    writeFile: (input: FsWriteInput) => invoke<{ ok: true }>("fs:writeFile", input),
    stageProject: (input: FsStageProjectInput) =>
      invoke<FsStageProjectResult>("fs:stageProject", input),
  },
};

const bridge: Omit<DesktopBridge, "connections" | "projectRoot" | "identity" | "launcher" | "fs"> = {
  app: {
    getRuntimeState: () => invoke<RuntimeState>("app:getRuntimeState"),
    openExternal: (params: OpenExternalParams) =>
      invoke<{ ok: true }>("app:openExternal", params),
    onBackendStatus: (cb: (e: BackendStatusEvent) => void) =>
      subscribe("app:onBackendStatus", cb),
    onUpdateState: (cb: (e: UpdateStateEvent) => void) => subscribe("app:onUpdateState", cb),
    onDataSourceChanged: (cb: (e: DataSourceChangedEvent) => void) =>
      subscribe("app:onDataSourceChanged", cb),
  },
  settings: {
    get: () => invoke<SettingsGetResult>("settings:get"),
    set: (patch: Partial<DesktopSettingsWritable>) =>
      invoke<DesktopSettings>("settings:set", patch),
    setSecret: (params: SetSecretParams) =>
      invoke<{ ok: true }>("settings:setSecret", params),
    testNeo4jConnection: (params: TestNeo4jConnectionParams) =>
      invoke<TestNeo4jConnectionData>("settings:testNeo4jConnection", params),
  },
  dataDir: {
    get: () => invoke<DataDirInfo>("dataDir:get"),
    choose: () => invoke<DataDirChooseResult>("dataDir:choose"),
  },
  backend: {
    retry: () => invoke<{ ok: true }>("backend:retry"),
  },
  runtime: {
    // 상태가 **바뀔 때만** 온다(계약). 렌더러가 5초마다 다시 그리지 않게 하려면
    // 미는 쪽이 지켜야 하는 약속이다.
    onStatus: (cb: (e: RuntimeStatusPayload) => void) => subscribe(RUNTIME_CHANNELS.onStatus, cb),
    retryService: (input: { serviceId: ManagedServiceId }) =>
      invoke<{ ok: true }>(RUNTIME_CHANNELS.retryService, input),
    stopEngine: (input: { confirm: true }) =>
      invoke<{ ok: true; stoppedServiceIds: ManagedServiceId[] }>(
        RUNTIME_CHANNELS.stopEngine,
        input,
      ),
    openDiagnostics: (input: { serviceId?: ManagedServiceId }) =>
      invoke<{ ok: true }>(RUNTIME_CHANNELS.openDiagnostics, input),
  },
  logs: {
    reveal: () => invoke<{ ok: true }>("logs:reveal"),
  },
  update: {
    check: () => invoke<UpdateCheckResult>("update:check"),
    apply: () => invoke<{ ok: true }>("update:apply"),
  },
};

// Merge 023 surface + 032 launcher surface into the single `window.desktop`
// object. Spread is safe because the two halves share no top-level keys.
contextBridge.exposeInMainWorld("desktop", { ...bridge, ...launcherBridge, ...fsBridge });
