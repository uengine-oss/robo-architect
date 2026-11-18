/**
 * age-fabric: source database passwords between the screen and the main process (FABRIC-SPLIT.md 3.4, Q13).
 *
 * A datasource form never sends a password to the fabric service. It hands the password to the main
 * process (`fabric:keepDatasourceSecret`), which keeps it in the OS keychain (safeStorage) as
 * `keychain:ds/<name>` and passes it to og-fabric's local channel; the form then registers the
 * datasource with `parameters.credentials` = the returned reference and no password.
 *
 * Only the age-fabric configuration has these; elsewhere the handlers answer VALIDATION.
 * Augments IpcRequestMap · DesktopBridge by declaration merging (ipc-contract.ts unchanged), as
 * launcher-contract.ts and fs-browser-contract.ts do.
 */

import type { IpcResult } from "./ipc-contract";

export interface FabricStatus {
  /** "age-fabric" | "ontological"; null before the stack is up */
  variant: string | null;
  /** whether og-fabric's channel is there (the age-fabric stack is up) */
  channel: boolean;
}

export interface KeepDatasourceSecretInput {
  /** the datasource's name in og-fabric: [a-z_][a-z0-9_]*, not pg_ / og_ */
  name: string;
  /** never logged, never echoed back */
  password: string;
}

export interface KeepDatasourceSecretResult {
  /** `keychain:ds/<name>` — what the form puts in parameters.credentials */
  credentials: string;
}

export interface ForgetDatasourceSecretInput {
  name: string;
}

export interface FabricIpcRequestMap {
  "fabric:status": [void, FabricStatus];
  "fabric:keepDatasourceSecret": [KeepDatasourceSecretInput, KeepDatasourceSecretResult];
  "fabric:forgetDatasourceSecret": [ForgetDatasourceSecretInput, { ok: true }];
}

export interface FabricDesktopBridge {
  fabric: {
    status(): Promise<IpcResult<FabricStatus>>;
    keepDatasourceSecret(input: KeepDatasourceSecretInput): Promise<IpcResult<KeepDatasourceSecretResult>>;
    forgetDatasourceSecret(input: ForgetDatasourceSecretInput): Promise<IpcResult<{ ok: true }>>;
  };
}

declare module "./ipc-contract" {
  interface IpcRequestMap extends FabricIpcRequestMap {}
  interface DesktopBridge extends FabricDesktopBridge {}
}
