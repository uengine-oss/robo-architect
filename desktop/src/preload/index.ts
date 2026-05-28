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
const bridge: Omit<DesktopBridge, "connections" | "projectRoot" | "identity" | "launcher"> = {
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
contextBridge.exposeInMainWorld("desktop", { ...bridge, ...launcherBridge });
