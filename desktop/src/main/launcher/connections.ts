/**
 * SavedConnection CRUD + Neo4j connection-test glue (spec 032 T009 / T022 / T032 / T033).
 *
 * Phase 2 (T009): keychain re-key helper used by the v1 → v2 migration.
 * US1   (T022): `connections:list` — ordered by lastConnectedAt desc.
 * US2   (T032): `connections:save` — validates, dedupes, writes keychain.
 * US2   (T033): `connections:test` — Neo4j handshake without persisting.
 *
 * Edit/Delete (US5 T059/T060) and probeStatus (US1 T023) land in future
 * tasks; the stubs in `ipc-handlers.ts` remain wired until then.
 */

import { randomUUID } from "node:crypto";
import neo4j, { auth, type Driver, type ServerInfo } from "neo4j-driver";

import { IpcErrorCodes } from "../../shared/ipc-contract";
import type {
  ActiveBackendConnection,
  ConnectionsSaveInput,
  SavedConnection,
} from "../../shared/launcher-contract";
import { connectionPasswordSecretId } from "../../shared/launcher-contract";
import { IpcHandlerError } from "../ipc";
import { getSecret, rekeySecret as rekey, setSecret } from "../secret-store";
import { loadSettings, saveSettings } from "../settings";

const TEST_TIMEOUT_MS = 5000;

// ---------------------------------------------------------------------------
// Re-key helper (T009) — used by migration; predates the rest of CRUD.
// ---------------------------------------------------------------------------

export async function rekeyLegacyNeo4jPassword(newConnection: SavedConnection): Promise<boolean> {
  const newId = connectionPasswordSecretId(newConnection.id);
  return rekey("neo4j.password", newId);
}

// ---------------------------------------------------------------------------
// connections:list (T022)
// ---------------------------------------------------------------------------

export async function listConnections(): Promise<SavedConnection[]> {
  const settings = await loadSettings();
  return [...settings.savedConnections].sort(byLastConnectedDesc);
}

function byLastConnectedDesc(a: SavedConnection, b: SavedConnection): number {
  const ta = a.lastConnectedAt ? Date.parse(a.lastConnectedAt) : 0;
  const tb = b.lastConnectedAt ? Date.parse(b.lastConnectedAt) : 0;
  return tb - ta;
}

// ---------------------------------------------------------------------------
// Validation rules (mirrors data-model.md §1)
// ---------------------------------------------------------------------------

const BOLT_SCHEMES = ["bolt://", "bolt+s://", "bolt+ssc://", "neo4j://", "neo4j+s://", "neo4j+ssc://"];

function validateLabel(label: string): string {
  const trimmed = (label ?? "").trim();
  if (trimmed.length < 1 || trimmed.length > 60) {
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, "label must be 1–60 chars");
  }
  return trimmed;
}

function validateUri(uri: string): string {
  if (typeof uri !== "string") {
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, "uri must be a string");
  }
  if (!BOLT_SCHEMES.some((s) => uri.startsWith(s))) {
    throw new IpcHandlerError(
      IpcErrorCodes.VALIDATION,
      `uri must start with one of: ${BOLT_SCHEMES.join(", ")}`,
    );
  }
  try {
    // eslint-disable-next-line no-new
    new URL(uri.replace(/^bolt(\+s|\+ssc)?:/, "http:").replace(/^neo4j(\+s|\+ssc)?:/, "http:"));
  } catch {
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, "uri is malformed");
  }
  return uri;
}

function validateUser(user: string): string {
  if (typeof user !== "string" || user.length < 1 || user.length > 256 || /[\r\n]/.test(user)) {
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, "user must be 1–256 chars, no newlines");
  }
  return user;
}

function validateDatabase(db: string | undefined | null): string | undefined {
  if (db == null || db === "") return undefined;
  if (!/^[a-z0-9][a-z0-9-]{0,62}$/.test(db)) {
    throw new IpcHandlerError(
      IpcErrorCodes.VALIDATION,
      "database must be lowercase letters/digits/dashes, 1–63 chars",
    );
  }
  return db;
}

function detectDuplicate(
  existing: SavedConnection[],
  draft: { label: string; uri: string; user: string; database?: string },
  ignoreId?: string,
): SavedConnection | null {
  const sameLabel = existing.find((c) => c.id !== ignoreId && c.label === draft.label);
  if (sameLabel) return sameLabel;
  const sameTuple = existing.find(
    (c) =>
      c.id !== ignoreId &&
      c.uri === draft.uri &&
      c.user === draft.user &&
      (c.database ?? "") === (draft.database ?? ""),
  );
  return sameTuple ?? null;
}

// ---------------------------------------------------------------------------
// connections:save (T032)
// ---------------------------------------------------------------------------

export async function saveConnection(input: ConnectionsSaveInput): Promise<SavedConnection> {
  const label = validateLabel(input.label);
  const uri = validateUri(input.uri);
  const user = validateUser(input.user);
  const database = validateDatabase(input.database);

  const settings = await loadSettings();
  const dup = detectDuplicate(settings.savedConnections, { label, uri, user, database });
  if (dup) {
    throw new IpcHandlerError(
      IpcErrorCodes.CONNECTION_DUPLICATE,
      `duplicate: ${dup.label} (${dup.uri})`,
    );
  }

  const sc: SavedConnection = {
    id: randomUUID(),
    label,
    uri,
    user,
    database,
    source: input.source,
    lastConnectedAt: null,
    createdAt: new Date().toISOString(),
  };

  if (input.passwordPlaintext && input.passwordPlaintext.length > 0) {
    await setSecret(connectionPasswordSecretId(sc.id), input.passwordPlaintext);
  }

  settings.savedConnections = [sc, ...settings.savedConnections];
  await saveSettings(settings);
  return sc;
}

// ---------------------------------------------------------------------------
// connections:test (T033) — Neo4j handshake without persisting
// ---------------------------------------------------------------------------

export interface TestParams {
  uri: string;
  user: string;
  password: string;
  database: string;
}

export interface TestResult {
  ok: true;
  serverVersion?: string;
}

/**
 * Open a one-shot driver, run a server-info handshake, then close.
 * Maps every failure to one of the closed `NEO4J_*` IpcErrorCodes so the
 * renderer can render a precise error message.
 */
export async function testConnection(params: TestParams): Promise<TestResult> {
  validateUri(params.uri);
  validateUser(params.user);
  if (typeof params.password !== "string" || params.password.length === 0) {
    throw new IpcHandlerError(IpcErrorCodes.NEO4J_AUTH_FAILED, "password is required");
  }

  let driver: Driver | null = null;
  try {
    driver = neo4j.driver(params.uri, auth.basic(params.user, params.password), {
      connectionAcquisitionTimeout: TEST_TIMEOUT_MS,
      connectionTimeout: TEST_TIMEOUT_MS,
      maxConnectionPoolSize: 1,
    });

    const verifyP = driver.getServerInfo({
      database: params.database && params.database.length > 0 ? params.database : undefined,
    });

    const info = await Promise.race<ServerInfo>([
      verifyP,
      new Promise<ServerInfo>((_resolve, reject) =>
        setTimeout(
          () => reject(Object.assign(new Error("timeout"), { code: "ETIMEDOUT" })),
          TEST_TIMEOUT_MS,
        ),
      ),
    ]);

    return {
      ok: true,
      serverVersion:
        // ServerInfo exposes a few shapes across driver versions.
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (info as any)?.agent ?? (info as any)?.protocolVersion?.toString?.() ?? undefined,
    };
  } catch (err) {
    throw mapDriverError(err);
  } finally {
    if (driver) {
      try {
        await driver.close();
      } catch {
        /* swallow */
      }
    }
  }
}

function mapDriverError(err: unknown): IpcHandlerError {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const code = (err as any)?.code ?? "";
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const message = (err as any)?.message ?? String(err);

  // Neo4j driver error codes — see neo4j-driver source
  if (typeof code === "string" && code.includes("Unauthorized")) {
    return new IpcHandlerError(IpcErrorCodes.NEO4J_AUTH_FAILED, "wrong username or password");
  }
  if (typeof code === "string" && code.includes("Security")) {
    return new IpcHandlerError(IpcErrorCodes.NEO4J_TLS_ERROR, message);
  }
  if (
    code === "ETIMEDOUT" ||
    code === "ServiceUnavailable" ||
    /timeout/i.test(message) ||
    /unable to connect/i.test(message)
  ) {
    // Distinguish hard unreachable from soft timeout when we can.
    if (code === "ETIMEDOUT") {
      return new IpcHandlerError(IpcErrorCodes.NEO4J_TIMEOUT, "connection timed out");
    }
    return new IpcHandlerError(IpcErrorCodes.NEO4J_UNREACHABLE, "host unreachable");
  }
  if (typeof code === "string" && code.includes("DatabaseNotFound")) {
    return new IpcHandlerError(IpcErrorCodes.VALIDATION, "database not found");
  }
  // Fallback
  return new IpcHandlerError(IpcErrorCodes.NEO4J_UNREACHABLE, message);
}

// ---------------------------------------------------------------------------
// connections:resolveActiveForBackend — 임베드 백엔드용 활성 연결 자격증명 조회.
//
// lastProfile(마지막 Enter 한 연결)의 SavedConnection + 키체인 비밀번호를 합쳐
// 전체 자격증명을 반환한다. 렌더러(AnalysisPanel)가 mount 직전 1회 호출 →
// analyzer mount({neo4j}) → X-Neo4j-* 헤더로 백엔드 override.
// 활성 프로필 또는 비번이 없으면 null → 백엔드는 자체 env(ROBO_NEO4J_*) 폴백.
//
// 비번은 키체인에서 즉시 읽어 반환만 하고 영속(settings.json)하지 않는다 —
// 렌더러는 헤더로 흘려보낼 뿐 localStorage 에 저장하지 않는다(localhost 전용 전송).
// ---------------------------------------------------------------------------

export async function resolveActiveForBackend(): Promise<ActiveBackendConnection | null> {
  const settings = await loadSettings();
  const connectionId = settings.lastProfile?.connectionId;
  if (!connectionId) return null;

  const connection = settings.savedConnections.find((c) => c.id === connectionId);
  if (!connection) return null;

  const password = await getSecret(connectionPasswordSecretId(connection.id));
  if (password === null) return null;

  return {
    uri: connection.uri,
    user: connection.user,
    password,
    database: connection.database,
  };
}

/** Internal helper used by launcher:enter to refresh the timestamp. */
export async function markConnectionUsed(id: string): Promise<void> {
  const settings = await loadSettings();
  const idx = settings.savedConnections.findIndex((c) => c.id === id);
  if (idx === -1) return;
  settings.savedConnections[idx] = {
    ...settings.savedConnections[idx]!,
    lastConnectedAt: new Date().toISOString(),
  };
  await saveSettings(settings);
}
