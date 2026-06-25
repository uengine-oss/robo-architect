/**
 * Launcher IPC handler registration (spec 032 T014 + T024 / T037 / T044 / T053 / T061).
 *
 * Real handlers replace stubs as their gating tasks land. Currently:
 *   ✅ connections:list           (T022, US1)
 *   ✅ connections:save           (T032, US2)
 *   ✅ connections:test           (T033, US2)
 *   ✅ projectRoot:choose         (T034, US2)
 *   ✅ projectRoot:validate       (T035, US2)
 *   ✅ projectRoot:listRecent     (T036, US2)
 *   ✅ identity:resolve           (T043, US3)
 *   ✅ launcher:enter             (T028 + T048, US1 + US3)
 *
 * Still stubbed:
 *   ⏳ connections:update         (T059, US5)
 *   ⏳ connections:delete         (T060, US5)
 *   ⏳ connections:discoverNeo4jDesktop  (T052, US4)
 *   ⏳ connections:probeStatus    (T023, US1) — launcher functions without it
 *                                  (no live status badge in MVP);
 *   ⏳ launcher:reopen            (T065, US5)
 */

import type { LauncherIpcChannel } from "../../shared/launcher-contract";
import { IpcErrorCodes } from "../../shared/ipc-contract";
import { IpcHandlerError, registerHandler } from "../ipc";

import {
  listConnections,
  resolveActiveForBackend,
  saveConnection,
  testConnection,
} from "./connections";
import { handleLauncherEnter } from "./enter";
import { resolveSessionUser, setGitConfigGlobal } from "./identity";
import {
  chooseProjectRoot,
  createProjectRoot,
  listRecentProjectRoots,
  validateProjectRoot,
} from "./project-root";

const STUB_BY_CHANNEL: Record<LauncherIpcChannel, string> = {
  "connections:list": "US1 T022",
  "connections:save": "US2 T032",
  "connections:update": "US5 T059",
  "connections:delete": "US5 T060",
  "connections:resolveActiveForBackend": "neo4j-electron-override",
  "connections:discoverNeo4jDesktop": "US4 T052",
  "connections:probeStatus": "US1 T023",
  "connections:test": "US2 T033",
  "projectRoot:choose": "US2 T034",
  "projectRoot:createNew": "US2 T034b",
  "projectRoot:listRecent": "US2 T036",
  "projectRoot:validate": "US2 T035",
  "identity:resolve": "US3 T043",
  "identity:setGitConfig": "US3 T043b",
  "launcher:enter": "US1 T028",
  "launcher:reopen": "US5 T065",
};

const IMPLEMENTED_CHANNELS: ReadonlySet<LauncherIpcChannel> = new Set([
  "connections:list",
  "connections:save",
  "connections:test",
  "connections:resolveActiveForBackend",
  "projectRoot:choose",
  "projectRoot:createNew",
  "projectRoot:validate",
  "projectRoot:listRecent",
  "identity:resolve",
  "identity:setGitConfig",
  "launcher:enter",
]);

/**
 * Register real handlers for implemented channels, plus VALIDATION-stub
 * handlers for the rest so the renderer can probe the surface without
 * crashing.
 */
export function registerLauncherIpcHandlers(): void {
  // --- real handlers ---
  registerHandler("connections:list", listConnections);
  registerHandler("connections:save", saveConnection);
  registerHandler("connections:test", testConnection);
  registerHandler("connections:resolveActiveForBackend", resolveActiveForBackend);
  registerHandler("projectRoot:choose", chooseProjectRoot);
  registerHandler("projectRoot:createNew", ({ path }) => createProjectRoot(path));
  registerHandler("projectRoot:validate", ({ path }) => validateProjectRoot(path));
  registerHandler("projectRoot:listRecent", listRecentProjectRoots);
  registerHandler("identity:resolve", ({ projectRoot }) => resolveSessionUser(projectRoot));
  registerHandler("identity:setGitConfig", ({ name, email }) => setGitConfigGlobal(name, email));
  registerHandler("launcher:enter", handleLauncherEnter);

  // --- stubs for the rest ---
  for (const channel of Object.keys(STUB_BY_CHANNEL) as LauncherIpcChannel[]) {
    if (IMPLEMENTED_CHANNELS.has(channel)) continue;
    const gatingTask = STUB_BY_CHANNEL[channel];
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (registerHandler as any)(channel, () => {
      throw new IpcHandlerError(
        IpcErrorCodes.VALIDATION,
        `${channel}: not implemented yet (gating task ${gatingTask})`,
      );
    });
  }
}

/** @deprecated Use `registerLauncherIpcHandlers` — kept for `main/index.ts` call-site compatibility. */
export const registerLauncherIpcStubs = registerLauncherIpcHandlers;
