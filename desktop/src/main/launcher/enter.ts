/**
 * `launcher:enter` handler (spec 032 T028 + T048).
 *
 * Validates the chosen profile, runs a final auth probe with the stored
 * keychain password, persists lastProfile + lastConnectedAt + recent
 * project root, re-resolves identity with `cwd = projectRoot`, and
 * returns the authoritative SessionUser + activeConnectionId.
 *
 * Backend env swap (pointing the live uvicorn at the chosen Neo4j) is
 * out of scope for the foundation MVP — for now the renderer is allowed
 * to enter and any subsequent Neo4j requests go to whatever the backend
 * was configured with. A full backend.ts modification lands as a future
 * task; the launcher handshake itself is the user-visible deliverable.
 */

import { IpcErrorCodes } from "../../shared/ipc-contract";
import type {
  LaunchProfile,
  LauncherEnterInput,
  LauncherEnterResult,
} from "../../shared/launcher-contract";
import { connectionPasswordSecretId } from "../../shared/launcher-contract";
import { IpcHandlerError } from "../ipc";
import { getSecret } from "../secret-store";
import { loadSettings, saveSettings } from "../settings";

import { markConnectionUsed, testConnection } from "./connections";
import { resolveSessionUser } from "./identity";
import { canEnter, markEntered } from "./launcher-state";
import { pushRecentProjectRoot, validateProjectRoot } from "./project-root";

export async function handleLauncherEnter(input: LauncherEnterInput): Promise<LauncherEnterResult> {
  if (!canEnter()) {
    throw new IpcHandlerError(
      IpcErrorCodes.LAUNCHER_ALREADY_ENTERED,
      "launcher:enter called twice without an intervening reopen",
    );
  }

  // ---------- validate inputs ----------
  if (typeof input?.connectionId !== "string" || input.connectionId.length === 0) {
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, "connectionId required");
  }
  if (typeof input.projectRoot !== "string" || input.projectRoot.length === 0) {
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, "projectRoot required");
  }

  const rootValidation = await validateProjectRoot(input.projectRoot);
  if (!rootValidation.valid) {
    const code =
      rootValidation.reason === "unreadable"
        ? IpcErrorCodes.PROJECT_ROOT_UNREADABLE
        : IpcErrorCodes.PROJECT_ROOT_INVALID;
    throw new IpcHandlerError(code, `projectRoot is ${rootValidation.reason}`);
  }

  // ---------- look up the saved connection ----------
  const settings = await loadSettings();
  const connection = settings.savedConnections.find((c) => c.id === input.connectionId);
  if (!connection) {
    throw new IpcHandlerError(
      IpcErrorCodes.CONNECTION_NOT_FOUND,
      `no SavedConnection with id ${input.connectionId}`,
    );
  }

  // ---------- final auth probe using keychain password ----------
  const password = await getSecret(connectionPasswordSecretId(connection.id));
  if (password === null) {
    throw new IpcHandlerError(
      IpcErrorCodes.NEO4J_AUTH_FAILED,
      "no stored password for this connection; please re-enter it",
    );
  }

  // testConnection throws on any failure with the right NEO4J_* code,
  // which surfaces to the renderer through the ipc envelope.
  await testConnection({
    uri: connection.uri,
    user: connection.user,
    password,
    database: connection.database ?? "",
  });

  // ---------- persist lastProfile + bump timestamps ----------
  const enteredAt = new Date().toISOString();
  const profile: LaunchProfile = {
    connectionId: connection.id,
    projectRoot: input.projectRoot,
    enteredAt,
  };

  await markConnectionUsed(connection.id);
  await pushRecentProjectRoot(input.projectRoot);
  // Re-read after the helpers' modifications, then set lastProfile.
  const settings2 = await loadSettings();
  settings2.lastProfile = profile;
  await saveSettings(settings2);

  // ---------- re-resolve identity with the chosen projectRoot ----------
  // Project-local git config may now apply, overriding the renderer's
  // pre-Enter resolution. The renderer treats the returned identity as
  // authoritative and writes it into the session store.
  const authoritativeIdentity = await resolveSessionUser(input.projectRoot);

  markEntered(profile);

  return {
    identity: authoritativeIdentity,
    activeConnectionId: connection.id,
  };
}
