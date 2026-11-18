/**
 * IPC handlers of shared/fabric-contract.ts: the age-fabric datasource passwords (OS keychain → og-fabric).
 */

import "../shared/fabric-contract";
import { IpcErrorCodes } from "../shared/ipc-contract";

import { FabricError, forgetDatasourceSecret, keepDatasourceSecret } from "./age-fabric-stack";
import { getDeployVariant, getFabricClient } from "./docker-stack";
import { IpcHandlerError, registerHandler } from "./ipc";
import { deleteSecret, getSecret, setSecret } from "./secret-store";

const store = {
  get: getSecret,
  set: (id: string, value: string, options?: { keychain?: boolean }) => setSecret(id, value, options),
  remove: deleteSecret,
};

function ageFabricClient() {
  if (getDeployVariant() !== "age-fabric") {
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, "fabric: only the age-fabric configuration keeps source passwords");
  }
  const client = getFabricClient();
  if (!client) throw new IpcHandlerError(IpcErrorCodes.VALIDATION, "fabric: the stack is not up yet");
  return client;
}

function asIpcError(err: unknown): never {
  if (err instanceof FabricError) {
    throw new IpcHandlerError(err.status < 500 ? IpcErrorCodes.VALIDATION : IpcErrorCodes.INTERNAL, err.message);
  }
  throw err;
}

export function registerFabricIpc(): void {
  registerHandler("fabric:status", () => ({
    variant: getDeployVariant(),
    channel: getFabricClient() !== null,
  }));
  registerHandler("fabric:keepDatasourceSecret", async ({ name, password }) => {
    const client = ageFabricClient();
    try {
      return await keepDatasourceSecret(store, client, String(name ?? ""), String(password ?? ""));
    } catch (err) {
      return asIpcError(err);
    }
  });
  registerHandler("fabric:forgetDatasourceSecret", async ({ name }) => {
    const client = ageFabricClient();
    try {
      await forgetDatasourceSecret(store, client, String(name ?? ""));
      return { ok: true as const };
    } catch (err) {
      return asIpcError(err);
    }
  });
}
