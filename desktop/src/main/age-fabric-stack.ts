/**
 * The age-fabric configuration's part of starting the stack (compose.age-fabric.yml).
 *
 * docker-stack.ts brings the containers up; this module does what has to happen in between and after,
 * and keeps the source passwords where FABRIC-SPLIT.md 3.4 / Q13 puts them on a desktop — the OS
 * keychain (Electron safeStorage), handed to og-fabric over its local channel, never to compose:
 *
 *   1. age-db (Supabase Postgres + AGE) — the login role robo (a SCRAM verifier made here, so the plain
 *      password reaches neither the server nor its log) and the fixed graphs robo / analyzer_run, made
 *      as robo so robo owns them (the gateway does not make graphs on first use).
 *   2. fabric-db — its two roles' passwords set to this install's values (a volume made by another
 *      install, or before the app's data was wiped, has other ones).
 *   3. og-fabric up: every `keychain:` reference it lists (GET /api/credentials) is handed over
 *      (PUT /internal/secrets/{ref}) with the channel token that is new every boot.
 *   4. once: datasources a v1 Ontological engine (the default configuration's graph-db) keeps with an
 *      inline password move to og-fabric with a keychain reference (og-fabric-migrate --keychain; the
 *      secrets come back on its standard output and go into the keychain here).
 *
 * No Electron here: everything that touches Docker, the keychain or HTTP comes in as a function, so the
 * unit tests and the E2E driver (tests/e2e-age-fabric) run the same code.
 */

import { createHash, createHmac, pbkdf2Sync, randomBytes } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

// ---------------------------------------------------------------------------------- secrets

export interface SecretStoreLike {
  get(id: string): Promise<string | null>;
  /** `keychain: true`: the OS keychain (safeStorage) whatever the store's file mode is */
  set(id: string, value: string, options?: { keychain?: boolean }): Promise<void>;
  remove(id: string): Promise<void>;
}

export type LogFn = (level: "info" | "warn" | "error", event: string, fields?: Record<string, unknown>) => void;

/** Infrastructure secrets of the age-fabric stack (the same store as the graph password). */
export const SECRET_IDS = {
  ageAdmin: "runtime.docker.age.admin.password",
  fabricDb: "runtime.docker.fabric.db.password",
  fabricQuery: "runtime.docker.fabric.query.password",
  fabricService: "runtime.docker.fabric.service.token",
} as const;

export interface AgeFabricSecrets {
  /** supabase_admin / postgres of age-db */
  adminPassword: string;
  /** og (superuser) of fabric-db */
  fabricDbPassword: string;
  /** og_fabric_service (the query role) of fabric-db */
  fabricQueryPassword: string;
  /** what callers of og-fabric send (Authorization: Bearer) */
  fabricServiceToken: string;
}

const TOKEN = /^[A-Za-z0-9_-]{16,}$/;

export function newToken(): string {
  return randomBytes(32).toString("base64url");
}

/** The secrets of this install, made on first use. */
export async function ensureAgeFabricSecrets(store: SecretStoreLike): Promise<AgeFabricSecrets> {
  const get = async (id: string): Promise<string> => {
    const existing = await store.get(id);
    if (existing && TOKEN.test(existing)) return existing;
    const created = newToken();
    await store.set(id, created);
    return created;
  };
  return {
    adminPassword: await get(SECRET_IDS.ageAdmin),
    fabricDbPassword: await get(SECRET_IDS.fabricDb),
    fabricQueryPassword: await get(SECRET_IDS.fabricQuery),
    fabricServiceToken: await get(SECRET_IDS.fabricService),
  };
}

/**
 * A SCRAM-SHA-256 verifier (RFC 5802 / 7677) in the form PostgreSQL keeps in pg_authid: what
 * `ALTER ROLE … PASSWORD 'SCRAM-SHA-256$…'` takes, so the password itself is never sent.
 * Passwords here are base64url tokens (ASCII), for which SASLprep changes nothing.
 */
export function scramSha256Verifier(password: string, salt: Buffer = randomBytes(16), iterations = 4096): string {
  if (!TOKEN.test(password)) throw new Error("scram: the password must be a token ([A-Za-z0-9_-], 16+)");
  const salted = pbkdf2Sync(Buffer.from(password, "utf8"), salt, iterations, 32, "sha256");
  const clientKey = createHmac("sha256", salted).update("Client Key").digest();
  const serverKey = createHmac("sha256", salted).update("Server Key").digest();
  const storedKey = createHash("sha256").update(clientKey).digest();
  return `SCRAM-SHA-256$${iterations}:${salt.toString("base64")}$${storedKey.toString("base64")}:${serverKey.toString("base64")}`;
}

// ---------------------------------------------------------------------------------- SQL

const ROLE = /^[a-z_][a-z0-9_]{0,62}$/;
const GRAPH = /^[a-z][a-z0-9_]{1,39}$/;
const VERIFIER = /^SCRAM-SHA-256\$\d+:[A-Za-z0-9+/=]+\$[A-Za-z0-9+/=]+:[A-Za-z0-9+/=]+$/;

function role(name: string): string {
  if (!ROLE.test(name)) throw new Error(`invalid role name ${JSON.stringify(name)}`);
  return `"${name}"`;
}

function verifier(v: string): string {
  if (!VERIFIER.test(v)) throw new Error("not a SCRAM-SHA-256 verifier");
  return `'${v}'`;
}

/** As supabase_admin in database `graph`: the login role (age-supabase/sql/robo-role.sql, same grants). */
export function ageRoleSql(user: string, scram: string, database = "graph"): string {
  const r = role(user);
  if (!ROLE.test(database)) throw new Error("invalid database name");
  return [
    `SELECT 'CREATE ROLE ${r} LOGIN' WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${user}') \\gexec`,
    `ALTER ROLE ${r} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD ${verifier(scram)};`,
    `GRANT USAGE ON SCHEMA ag_catalog TO ${r};`,
    `GRANT SELECT ON ag_catalog.ag_graph, ag_catalog.ag_label TO ${r};`,
    `GRANT CONNECT, CREATE ON DATABASE "${database}" TO ${r};`,
    "",
  ].join("\n");
}

/** As the login role in database `graph`: the graphs it always uses, if missing (it then owns them). */
export function ageGraphsSql(graphs: readonly string[]): string {
  return graphs
    .map((g) => {
      if (!GRAPH.test(g)) throw new Error(`invalid graph name ${JSON.stringify(g)}`);
      return (
        `SELECT CASE WHEN EXISTS (SELECT 1 FROM ag_catalog.ag_graph WHERE name = '${g}') THEN 'graph ${g}: there' ` +
        `ELSE (SELECT 'graph ${g}: made' FROM ag_catalog.create_graph('${g}')) END;`
      );
    })
    .join("\n")
    .concat("\n");
}

/** As og in fabric-db: both roles take this install's passwords. */
export function fabricRolesSql(adminScram: string, queryScram: string, queryRole = "og_fabric_service"): string {
  return [
    `ALTER ROLE "og" PASSWORD ${verifier(adminScram)};`,
    `ALTER ROLE ${role(queryRole)} PASSWORD ${verifier(queryScram)};`,
    "",
  ].join("\n");
}

/** The image's own AGE install, for a volume made before it had AGE (idempotent; age-supabase install-age.sh). */
export const AGE_INSTALL_SQL_FILE = "/docker-entrypoint-initdb.d/migrations/99999999999999_age.sql";

// ---------------------------------------------------------------------------------- database preparation

/** `docker compose exec -T <service> <args…>` with `input` on standard input; resolves standard output. */
export type ExecInService = (service: string, args: string[], options?: { input?: string }) => Promise<string>;

async function retry<T>(attempts: number, delayMs: number, fn: () => Promise<T>): Promise<T> {
  let last: unknown = null;
  for (let i = 1; i <= attempts; i++) {
    try {
      return await fn();
    } catch (err) {
      last = err;
      if (i < attempts) await new Promise((r) => setTimeout(r, delayMs));
    }
  }
  throw last;
}

export interface AgeDbOptions {
  user: string;
  password: string;
  graphs: readonly string[];
  attempts?: number;
  delayMs?: number;
}

/**
 * The login role and the fixed graphs. 127.0.0.1 inside the image is `trust` (its pg_hba.conf), so
 * no password is needed to get in; the role's own password is only ever sent as a verifier.
 */
export async function prepareAgeDb(exec: ExecInService, options: AgeDbOptions, log?: LogFn): Promise<string[]> {
  const attempts = options.attempts ?? 15;
  const delayMs = options.delayMs ?? 2_000;
  const admin = ["psql", "-X", "-At", "-v", "ON_ERROR_STOP=1", "-h", "127.0.0.1", "-U", "supabase_admin"];
  const has = await retry(attempts, delayMs, () =>
    exec("age-db", [...admin, "-d", "postgres", "-c", "SELECT count(*) FROM pg_database WHERE datname = 'graph'"]),
  );
  if (has.trim() !== "1") {
    log?.("info", "age.install", { reason: "no graph database in this volume" });
    await exec("age-db", [...admin, "-q", "-d", "postgres", "-f", AGE_INSTALL_SQL_FILE]);
  }
  await retry(attempts, delayMs, () =>
    exec("age-db", [...admin, "-q", "-d", "graph"], {
      input: ageRoleSql(options.user, scramSha256Verifier(options.password)),
    }),
  );
  const made = await exec(
    "age-db",
    ["psql", "-X", "-At", "-v", "ON_ERROR_STOP=1", "-h", "127.0.0.1", "-U", options.user, "-d", "graph"],
    { input: ageGraphsSql(options.graphs) },
  );
  const lines = made.split("\n").map((l) => l.trim()).filter(Boolean);
  log?.("info", "age.graphs", { graphs: lines });
  return lines;
}

/** fabric-db's roles take this install's passwords (its local socket is `trust`). */
export async function prepareFabricDb(
  exec: ExecInService,
  secrets: Pick<AgeFabricSecrets, "fabricDbPassword" | "fabricQueryPassword">,
  options: { attempts?: number; delayMs?: number } = {},
): Promise<void> {
  const input = fabricRolesSql(
    scramSha256Verifier(secrets.fabricDbPassword),
    scramSha256Verifier(secrets.fabricQueryPassword),
  );
  await retry(options.attempts ?? 15, options.delayMs ?? 2_000, () =>
    exec("fabric-db", ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-U", "og", "-d", "fabric"], { input }),
  );
}

// ---------------------------------------------------------------------------------- og-fabric

export interface CredentialsEntry {
  name: string;
  engine: string;
  credentials: string;
  resolved?: boolean;
  unresolved_reason?: string;
}

type FetchLike = (url: string, init?: RequestInit) => Promise<Response>;

export class FabricError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
  ) {
    super(message);
    this.name = "FabricError";
  }
}

/** og-fabric's API (service token) and its secrets channel (the per-boot internal token). */
export class FabricClient {
  constructor(
    readonly baseUrl: string,
    private readonly serviceToken: string,
    private readonly internalToken: string,
    private readonly fetchImpl: FetchLike = fetch,
  ) {}

  private async call(method: string, pathPart: string, init: { body?: unknown; internal?: boolean } = {}) {
    const headers: Record<string, string> = init.internal
      ? { "X-Og-Fabric-Internal-Token": this.internalToken }
      : { Authorization: `Bearer ${this.serviceToken}` };
    if (init.body !== undefined) headers["Content-Type"] = "application/json";
    const response = await this.fetchImpl(`${this.baseUrl}${pathPart}`, {
      method,
      headers,
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
    });
    if (response.status >= 400) {
      let code = "http_" + response.status;
      let message = `og-fabric ${method} ${pathPart.split("?")[0]} answered ${response.status}`;
      try {
        const body = (await response.json()) as { error?: { code?: string; message?: string } };
        if (body?.error?.code) code = body.error.code;
        if (body?.error?.message) message += `: ${body.error.message}`;
      } catch {
        /* no JSON body */
      }
      throw new FabricError(message, response.status, code);
    }
    return response;
  }

  async healthy(): Promise<boolean> {
    try {
      const r = await this.fetchImpl(`${this.baseUrl}/healthz`);
      return r.status === 200;
    } catch {
      return false;
    }
  }

  async waitHealthy(timeoutMs = 60_000, stepMs = 1_000): Promise<void> {
    const until = Date.now() + timeoutMs;
    while (Date.now() < until) {
      if (await this.healthy()) return;
      await new Promise((r) => setTimeout(r, stepMs));
    }
    throw new FabricError(`og-fabric at ${this.baseUrl} did not answer /healthz`, 503, "unavailable");
  }

  async credentials(): Promise<CredentialsEntry[]> {
    const r = await this.call("GET", "/api/credentials");
    return ((await r.json()) as { credentials: CredentialsEntry[] }).credentials ?? [];
  }

  /** Hands a keychain secret over; resolves the number of connector files written. */
  async putSecret(ref: string, secret: string): Promise<number> {
    if (!ref.startsWith("keychain:")) throw new FabricError("only keychain: references go over the channel", 400, "invalid");
    const r = await this.call("PUT", `/internal/secrets/${encodeURIComponent(ref)}`, { body: { secret }, internal: true });
    return Number(r.headers.get("X-Og-Fabric-Files") ?? "0");
  }

  async deleteSecret(ref: string): Promise<void> {
    await this.call("DELETE", `/internal/secrets/${encodeURIComponent(ref)}`, { internal: true });
  }
}

// ---------------------------------------------------------------------------------- datasource secrets

/** og-fabric's datasource names (core.py check_name). */
const DATASOURCE = /^[a-z_][a-z0-9_]{0,62}$/;

export function datasourceRef(name: string): string {
  if (!DATASOURCE.test(name) || name.startsWith("pg_") || name.startsWith("og_")) {
    throw new FabricError(`'${name}' cannot name a datasource`, 400, "invalid_name");
  }
  return `keychain:ds/${name}`;
}

/** Where the keychain keeps a reference's secret: a stable id the secret store accepts, whatever the ref holds. */
export function secretIdOfRef(ref: string): string {
  return `fabric.keychain.${createHash("sha256").update(ref, "utf8").digest("hex").slice(0, 40)}`;
}

/** The screen's password → the keychain → og-fabric's channel; the screen registers with the reference only. */
export async function keepDatasourceSecret(
  store: SecretStoreLike,
  client: FabricClient | null,
  name: string,
  password: string,
): Promise<{ credentials: string }> {
  const ref = datasourceRef(name);
  if (typeof password !== "string" || password.length === 0) {
    throw new FabricError("an empty password is not a secret: register without credentials", 400, "invalid");
  }
  await store.set(secretIdOfRef(ref), password, { keychain: true });
  if (client) await client.putSecret(ref, password);
  return { credentials: ref };
}

export async function forgetDatasourceSecret(
  store: SecretStoreLike,
  client: FabricClient | null,
  name: string,
): Promise<void> {
  const ref = datasourceRef(name);
  await store.remove(secretIdOfRef(ref));
  if (client) {
    try {
      await client.deleteSecret(ref);
    } catch (err) {
      if (!(err instanceof FabricError && err.status === 404)) throw err;
    }
  }
}

export interface Delivery {
  delivered: string[];
  /** datasources whose keychain secret this install does not hold: they fail until it is entered again */
  missing: string[];
}

/** At start: every keychain reference og-fabric lists gets its secret (the container was made this boot). */
export async function deliverKeychainSecrets(
  client: FabricClient,
  store: SecretStoreLike,
  log?: LogFn,
): Promise<Delivery> {
  const out: Delivery = { delivered: [], missing: [] };
  const done = new Map<string, boolean>();
  for (const entry of await client.credentials()) {
    const ref = entry.credentials;
    if (typeof ref !== "string" || !ref.startsWith("keychain:")) continue;
    if (!done.has(ref)) {
      const secret = await store.get(secretIdOfRef(ref));
      if (secret === null) {
        done.set(ref, false);
      } else {
        await client.putSecret(ref, secret);
        done.set(ref, true);
      }
    }
    (done.get(ref) ? out.delivered : out.missing).push(entry.name);
  }
  log?.(out.missing.length ? "warn" : "info", "fabric.keychain.delivered", {
    delivered: out.delivered.length,
    missing: out.missing,
  });
  return out;
}

// ---------------------------------------------------------------------------------- plaintext migration

export interface MigratedSecret {
  name: string;
  engine: string;
  ref: string;
  secret: string;
  status: "moved" | "exists";
}

/** og-fabric-migrate --keychain --secrets-out -: one JSON object per line, nothing else. */
export function parseMigrationLines(stdout: string): MigratedSecret[] {
  const out: MigratedSecret[] = [];
  for (const line of stdout.split("\n")) {
    const text = line.trim();
    if (!text) continue;
    let row: unknown;
    try {
      row = JSON.parse(text);
    } catch {
      throw new Error("fabric.migrate: a line on its standard output is not JSON");
    }
    const r = row as Partial<MigratedSecret>;
    if (
      typeof r.name !== "string" ||
      typeof r.ref !== "string" ||
      !r.ref.startsWith("keychain:") ||
      typeof r.secret !== "string" ||
      (r.status !== "moved" && r.status !== "exists")
    ) {
      throw new Error("fabric.migrate: a line is not {name, ref: keychain:…, secret, status}");
    }
    out.push({ name: r.name, engine: String(r.engine ?? ""), ref: r.ref, secret: r.secret, status: r.status });
  }
  return out;
}

export interface MigrationDeps {
  /** the default configuration's graph-db, published on the host (null: there is none running) */
  findV1(): Promise<{ hostPort: number } | null>;
  /** runs og-fabric-migrate in the fabric container with `env` added; never logs stdout (it holds secrets) */
  runMigrate(env: Record<string, string>, args: string[]): Promise<{ stdout: string; stderr: string; code: number }>;
  store: SecretStoreLike;
  /** written once every datasource moved: the migration is not tried again */
  markerFile: string;
  log?: LogFn;
}

export type MigrationOutcome =
  | { state: "done-before" }
  | { state: "no-v1" }
  | { state: "migrated"; moved: string[]; exists: string[]; complete: boolean };

export const MIGRATE_ARGS = [
  "python",
  "-m",
  "og_fabric_service.migrate",
  "--keychain",
  "--secrets-out",
  "-",
  "--fabric-url",
  "http://127.0.0.1:8404",
];

/**
 * Datasources the v1 engine keeps with an inline password (pg_user_mapping, so in its catalog and WAL)
 * → og-fabric with keychain references, once. The v1 side is left as it is. The DSN goes in the
 * environment, not on a command line.
 */
export async function migrateV1Plaintext(
  deps: MigrationDeps,
  v1: { user: string; password: string; database: string },
): Promise<MigrationOutcome> {
  if (fs.existsSync(deps.markerFile)) return { state: "done-before" };
  const found = await deps.findV1();
  if (!found) {
    deps.log?.("info", "fabric.migrate.skipped", { reason: "no v1 graph-db running" });
    return { state: "no-v1" };
  }
  const dsn =
    `postgresql://${encodeURIComponent(v1.user)}:${encodeURIComponent(v1.password)}` +
    `@host.docker.internal:${found.hostPort}/${encodeURIComponent(v1.database)}`;
  const result = await deps.runMigrate({ OG_FABRIC_MIGRATE_FROM: dsn }, MIGRATE_ARGS);
  if (result.code !== 0 && result.code !== 1) {
    deps.log?.("warn", "fabric.migrate.failed", { code: result.code, report: redact(result.stderr, [v1.password]) });
    return { state: "migrated", moved: [], exists: [], complete: false };
  }
  const rows = parseMigrationLines(result.stdout);
  for (const row of rows) await deps.store.set(secretIdOfRef(row.ref), row.secret, { keychain: true });
  const moved = rows.filter((r) => r.status === "moved").map((r) => r.name);
  const exists = rows.filter((r) => r.status === "exists").map((r) => r.name);
  const complete = result.code === 0;
  const report = redact(result.stderr, [v1.password, ...rows.map((r) => r.secret)]);
  if (complete) {
    fs.mkdirSync(path.dirname(deps.markerFile), { recursive: true });
    fs.writeFileSync(
      deps.markerFile,
      `${JSON.stringify({ at: new Date().toISOString(), moved, exists, report: report.split("\n").filter(Boolean) }, null, 2)}\n`,
      { encoding: "utf8", mode: 0o600 },
    );
  }
  deps.log?.(complete ? "info" : "warn", "fabric.migrate.done", { moved, exists, complete });
  return { state: "migrated", moved, exists, complete };
}

function redact(text: string, secrets: string[]): string {
  let out = text;
  for (const s of secrets) if (s) out = out.split(s).join("***");
  return out;
}
