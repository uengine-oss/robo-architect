/**
 * lite 프로젝트 = Ontological DB 의 그래프 (projects:list / projects:create).
 *
 * main 가지의 런처는 "Neo4j 연결"을 고르게 한다 — Neo4j(Desktop)는 DB 하나에 그래프가
 * 하나라 프로젝트를 나누려면 연결을 따로 둬야 했다. Ontological 은 한 DB 에 그래프를
 * 여럿 두고, Bolt 게이트웨이가 세션의 database 를 그래프 이름으로 받는다. 그래서 lite 는
 * 번들 연결 하나로 그래프 목록을 보여 주고(`SHOW GRAPHS`), 새 프로젝트는 그래프를 만든다
 * (`CREATE GRAPH`). 고른 그래프는 enter 가 백엔드의 NEO4J_DATABASE 로 넘긴다.
 *
 * 분석 그래프(analyzer_run)는 분석기가 통째로 비우고 다시 쓰는 자리라 목록에서 뺀다 —
 * 거기를 프로젝트로 고르면 다음 분석에서 설계가 사라진다.
 */

import neo4j, { auth } from "neo4j-driver";

import { IpcErrorCodes } from "../../shared/ipc-contract";
import type { GraphProject, ProjectsCreateInput, SavedConnection } from "../../shared/launcher-contract";
import { connectionPasswordSecretId } from "../../shared/launcher-contract";
import { GRAPH_ANALYSIS, GRAPH_DESIGN } from "../graphs";
import { IpcHandlerError } from "../ipc";
import { getSecret } from "../secret-store";
import { loadSettings } from "../settings";

import { mapDriverError } from "./connections";

const NAME_PATTERN = /^[a-z][a-z0-9_]{1,39}$/;
const TIMEOUT_MS = 10_000;

async function bundledConnection(): Promise<{ connection: SavedConnection; password: string } | null> {
  const settings = await loadSettings();
  const connection = settings.savedConnections.find((c) => c.source === "bundled");
  if (!connection) return null;
  const password = await getSecret(connectionPasswordSecretId(connection.id));
  if (password === null) return null;
  return { connection, password };
}

async function run(query: string): Promise<Record<string, unknown>[]> {
  const bundled = await bundledConnection();
  if (!bundled) return [];
  const driver = neo4j.driver(bundled.connection.uri, auth.basic(bundled.connection.user, bundled.password), {
    connectionAcquisitionTimeout: TIMEOUT_MS,
    connectionTimeout: TIMEOUT_MS,
    maxConnectionPoolSize: 1,
    disableLosslessIntegers: true,
  });
  try {
    const result = await driver.executeQuery(query);
    return result.records.map((r) => r.toObject());
  } catch (err) {
    throw mapDriverError(err);
  } finally {
    await driver.close().catch(() => undefined);
  }
}

export async function hasBundledConnection(): Promise<boolean> {
  return (await bundledConnection()) !== null;
}

export async function listProjects(): Promise<GraphProject[]> {
  const rows = await run("SHOW GRAPHS");
  const last = (await loadSettings()).lastProfile?.graph ?? null;
  return rows
    .map((row) => ({
      name: String(row.graph ?? ""),
      types: Number(row.types ?? 0),
      isDefault: row.graph === GRAPH_DESIGN,
      lastUsed: row.graph === last,
    }))
    .filter((p) => p.name && p.name !== GRAPH_ANALYSIS)
    .sort((a, b) => Number(b.isDefault) - Number(a.isDefault) || a.name.localeCompare(b.name));
}

export async function createProject(input: ProjectsCreateInput): Promise<GraphProject[]> {
  const name = (input?.name ?? "").trim();
  if (!NAME_PATTERN.test(name)) {
    throw new IpcHandlerError(
      IpcErrorCodes.VALIDATION,
      "프로젝트 이름은 영문 소문자로 시작하고 소문자·숫자·밑줄(_)로 2~40자여야 합니다.",
    );
  }
  if (name === GRAPH_ANALYSIS) {
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, `${GRAPH_ANALYSIS} 는 분석기가 쓰는 이름입니다.`);
  }
  if (!(await hasBundledConnection())) {
    throw new IpcHandlerError(IpcErrorCodes.CONNECTION_NOT_FOUND, "번들 그래프 DB 가 아직 준비되지 않았습니다.");
  }
  const existing = await listProjects();
  if (existing.some((p) => p.name === name)) {
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, `이미 있는 프로젝트입니다: ${name}`);
  }
  // 이름은 위 패턴으로만 통과한다 — 식별자 자리에 그대로 써도 된다.
  await run(`CREATE GRAPH ${name}`);
  // 만든 직후의 SHOW GRAPHS 에 새 그래프가 빠질 때가 있다 — 잠깐 기다려 다시 읽고, 그래도 없으면 목록에 붙인다.
  for (let i = 0; i < 5; i++) {
    const projects = await listProjects();
    if (projects.some((p) => p.name === name)) return projects;
    await new Promise((r) => setTimeout(r, 300));
  }
  return [...(await listProjects()), { name, types: 0, isDefault: false, lastUsed: false }];
}

/** enter 가 쓰는 확인 — 고른 그래프가 실제로 있는가. */
export async function assertProjectExists(name: string): Promise<void> {
  const projects = await listProjects();
  if (!projects.some((p) => p.name === name)) {
    throw new IpcHandlerError(IpcErrorCodes.VALIDATION, `없는 프로젝트입니다: ${name}`);
  }
}
