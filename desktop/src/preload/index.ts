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

const bridge: DesktopBridge = {
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

contextBridge.exposeInMainWorld("desktop", bridge);
