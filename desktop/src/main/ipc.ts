/**
 * IPC plumbing for the Electron main process.
 *
 * Every renderer-facing `ipcMain.handle` is registered through `registerHandler`,
 * which wraps the handler in the `{ ok, data } | { ok: false, error }` envelope
 * defined in `shared/ipc-contract.ts` and maps thrown errors to the closed
 * `IpcErrorCode` enum (defaulting to `INTERNAL`).
 *
 * `pushToRenderer` is the symmetrical helper for main → renderer subscription
 * channels (`app:onBackendStatus`, `app:onUpdateState`, `app:onDataSourceChanged`).
 *
 * Concrete handlers are registered by their owning user-story tasks
 * (T026 / T033 / T043). Phase 2 only delivers the envelope + push primitives.
 */

import { BrowserWindow, ipcMain } from "electron";

import type {
  IpcChannel,
  IpcError,
  IpcErrorCode,
  IpcRequestMap,
  IpcResult,
  IpcSubscriptionChannel,
  IpcSubscriptionMap,
} from "../shared/ipc-contract";
import { IpcErrorCodes } from "../shared/ipc-contract";

import { log } from "./logging";

/**
 * Errors thrown from a handler with a typed `code` propagate through the
 * envelope as `{ ok: false, error: { code, message } }`. Any other thrown
 * value is mapped to `INTERNAL` and logged with a stack trace.
 */
export class IpcHandlerError extends Error {
  readonly code: IpcErrorCode;

  constructor(code: IpcErrorCode, message: string) {
    super(message);
    this.name = "IpcHandlerError";
    this.code = code;
  }
}

export type IpcHandler<C extends IpcChannel> = (
  args: IpcRequestMap[C][0],
) => Promise<IpcRequestMap[C][1]> | IpcRequestMap[C][1];

const registeredChannels = new Set<IpcChannel>();

export function registerHandler<C extends IpcChannel>(
  channel: C,
  handler: IpcHandler<C>,
): void {
  if (registeredChannels.has(channel)) {
    // Re-registration is almost always a bug — fail loudly in dev.
    throw new Error(`ipc.duplicate_handler: ${channel}`);
  }
  registeredChannels.add(channel);

  ipcMain.handle(channel, async (_event, args: IpcRequestMap[C][0]) => {
    try {
      const data = await handler(args);
      const result: IpcResult<IpcRequestMap[C][1]> = { ok: true, data };
      return result;
    } catch (err) {
      const error = toIpcError(err);
      log("error", "ipc.handler_failed", {
        channel,
        code: error.code,
        message: error.message,
        stack: err instanceof Error ? err.stack : undefined,
      });
      const result: IpcResult<IpcRequestMap[C][1]> = { ok: false, error };
      return result;
    }
  });
}

function toIpcError(err: unknown): IpcError {
  if (err instanceof IpcHandlerError) {
    return { code: err.code, message: err.message };
  }
  if (err instanceof Error) {
    return { code: IpcErrorCodes.INTERNAL, message: err.message };
  }
  return { code: IpcErrorCodes.INTERNAL, message: String(err) };
}

/**
 * Broadcasts a subscription event to every open BrowserWindow. The renderer
 * side delivers it to all listeners registered via the preload bridge.
 */
export function pushToRenderer<C extends IpcSubscriptionChannel>(
  channel: C,
  payload: IpcSubscriptionMap[C],
): void {
  for (const window of BrowserWindow.getAllWindows()) {
    if (window.isDestroyed()) continue;
    window.webContents.send(channel, payload);
  }
}

/**
 * Test/teardown helper. Not used by production code; kept here so US-story
 * modules and Playwright tests can reset state without re-registering.
 */
export function _unregisterAll(): void {
  for (const channel of registeredChannels) {
    ipcMain.removeHandler(channel);
  }
  registeredChannels.clear();
}
