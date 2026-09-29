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
  // ---------- projectRoot 는 **선택이다** ----------
  //
  // 인제스천(분석 → BPM → 룰 매핑 → ES 승격)은 결과를 전부 graph 에 쓴다. 폴더가
  // 필요한 것은 제품의 **코드를 건드리는 쪽**뿐이다 —
  //
  //   Code 탭(Claude Code PTY)   `claude` CLI 의 cwd
  //   Proposals 샌드박스          <projectRoot>/.sandbox/proposal/<PRO-NNN> worktree
  //   Analysis 탭                 ImplementationFile 경로를 실제 소스로 여는 데
  //   identity:resolve            그 폴더의 git config
  //
  // 사내망에는 `claude` CLI 가 없어서 Code 탭과 Proposals 를 쓰지 않는다. 그러면
  // 기동 때 폴더를 묻는 것은 **아무도 쓰지 않을 값을 사람에게 요구하는 일**이다.
  //
  // 그래서 없으면 없는 대로 진입한다. 주면 예전처럼 검증한다 — 잘못된 경로를
  // 받아 두면 나중에 그 탭들이 조용히 엉뚱한 곳을 본다.
  const projectRoot = typeof input.projectRoot === "string" ? input.projectRoot : "";
  if (projectRoot.length > 0) {
    const rootValidation = await validateProjectRoot(projectRoot);
    if (!rootValidation.valid) {
      const code =
        rootValidation.reason === "unreadable"
          ? IpcErrorCodes.PROJECT_ROOT_UNREADABLE
          : IpcErrorCodes.PROJECT_ROOT_INVALID;
      throw new IpcHandlerError(code, `projectRoot is ${rootValidation.reason}`);
    }
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
    projectRoot,
    enteredAt,
  };

  await markConnectionUsed(connection.id);
  // 빈 값은 최근 목록에 넣지 않는다 — 넣으면 다음 기동에서 빈 항목이 최신으로 뜬다.
  if (projectRoot.length > 0) await pushRecentProjectRoot(projectRoot);
  // Re-read after the helpers' modifications, then set lastProfile.
  const settings2 = await loadSettings();
  settings2.lastProfile = profile;
  await saveSettings(settings2);

  // ---------- re-resolve identity with the chosen projectRoot ----------
  // Project-local git config may now apply, overriding the renderer's
  // pre-Enter resolution. The renderer treats the returned identity as
  // authoritative and writes it into the session store.
  // 폴더가 없으면 전역 git config 로 푼다(런처 마운트 때 이미 그렇게 한다).
  const authoritativeIdentity = await resolveSessionUser(projectRoot || null);

  markEntered(profile);

  return {
    identity: authoritativeIdentity,
    activeConnectionId: connection.id,
  };
}
