#!/usr/bin/env node
/**
 * E2E of the age-fabric configuration (FABRIC-SPLIT.md 5 stage 4):
 *   datasource → sample → FK inference → FK edges in AGE → review,
 * plus the shell's part: the stack brought up by the app's own code (dist/main/main/docker-stack.js —
 * the same startDockerStack an Electron start runs), the source password kept as a keychain reference
 * and handed to og-fabric's channel, the v1 plaintext migration once, and a second boot (a new channel
 * token, the keychain secrets handed over again).
 *
 * Electron is not running: `electron` resolves to a stand-in whose app.getPath() is a scratch folder and
 * whose safeStorage is a reversible stand-in (not the OS keychain — that is the one thing not exercised).
 *
 *   npm run build   # dist/
 *   node tests/e2e-age-fabric/run.mjs --runtime <dir>/runtime --work <dir> [--keep]
 *
 * Containers (all removed at the end unless --keep): the stack as compose project ral-agefab, a sample
 * source ral-agefab-src (127.0.0.1:28881) and a v1 Ontological graph-db ral-agefab-v1 (127.0.0.1:28882)
 * labelled as compose project ral-agefab-v1's graph-db, holding one datasource with an inline password.
 */

import { execFileSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import fs from "node:fs";
import Module from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const desktop = path.resolve(here, "../..");
const dist = path.join(desktop, "dist/main/main");
const args = process.argv.slice(2);
const opt = (name, dflt) => {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : dflt;
};
const RUNTIME = path.resolve(opt("--runtime", ""));
const WORK = path.resolve(opt("--work", ""));
const KEEP = args.includes("--keep");
if (!opt("--runtime") || !opt("--work")) throw new Error("give --runtime <dir>/runtime --work <dir>");
const PROJECT = "ral-agefab";
const V1_PROJECT = "ral-agefab-v1";
const SRC = "ral-agefab-src";
const V1 = "ral-agefab-v1";
const SRC_PORT = 28881;
const V1_PORT = 28882;

const results = [];
let failures = 0;
function check(name, ok, detail = "") {
  results.push({ name, ok: !!ok, detail });
  if (!ok) failures++;
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? `  — ${detail}` : ""}`);
}
const sh = (cmd, a, o = {}) => execFileSync(cmd, a, { encoding: "utf8", stdio: ["pipe", "pipe", "pipe"], ...o }).trim();
const docker = (...a) => sh("docker", a);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ───────────────────────────────────────────── disk guard (Docker Desktop must not fill the disk)
function freeGiB() {
  const line = sh("df", ["-k", "/System/Volumes/Data"]).split("\n")[1];
  return Number(line.split(/\s+/)[3]) / 1024 / 1024;
}
const startFree = freeGiB();
if (startFree < 15) throw new Error(`only ${startFree.toFixed(1)} GiB free: stop (needs 15)`);

// ───────────────────────────────────────────── Electron stand-in
const userData = path.join(WORK, "userData");
fs.mkdirSync(userData, { recursive: true });
const sealed = new Set(); // plaintexts that went through safeStorage (to tell keychain from file mode)
const electronStub = {
  app: { getPath: () => userData, isPackaged: false, getVersion: () => "0.1.1", getName: () => "robo-e2e" },
  safeStorage: {
    isEncryptionAvailable: () => true,
    encryptString: (s) => {
      sealed.add(s);
      return Buffer.from("E2E-SEALED:" + Buffer.from(s, "utf8").toString("base64"));
    },
    decryptString: (b) => {
      const t = Buffer.from(b).toString("utf8");
      if (!t.startsWith("E2E-SEALED:")) throw new Error("not sealed by the stand-in");
      return Buffer.from(t.slice("E2E-SEALED:".length), "base64").toString("utf8");
    },
  },
  shell: { openPath: async () => "" },
  ipcMain: { handle() {} },
  webContents: { getAllWebContents: () => [] },
};
const require = Module.createRequire(import.meta.url);
const resolve0 = Module._resolveFilename;
Module._resolveFilename = function (request, ...rest) {
  return request === "electron" ? "electron-e2e-stub" : resolve0.call(this, request, ...rest);
};
require.cache["electron-e2e-stub"] = { id: "electron-e2e-stub", filename: "electron-e2e-stub", loaded: true, exports: electronStub, children: [] };

process.env.ROBO_DOCKER_RUNTIME_DIR = RUNTIME;
process.env.ROBO_COMPOSE_PROJECT = PROJECT;
process.env.ROBO_V1_COMPOSE_PROJECT = V1_PROJECT;
process.env.ROBO_PG_STATEMENT_TIMEOUT = "120s"; // the session's rule for Postgres containers
delete process.env.ROBO_SECRET_STORE;

const { initLogging } = require(path.join(dist, "logging.js"));
initLogging();
const secretStore = require(path.join(dist, "secret-store.js"));
const stack = require(path.join(dist, "docker-stack.js"));
const ags = require(path.join(dist, "age-fabric-stack.js"));
const neo4j = require("neo4j-driver");

const store = {
  get: secretStore.getSecret,
  set: (id, v, o) => secretStore.setSecret(id, v, o),
  remove: secretStore.deleteSecret,
};
const token = () => randomBytes(24).toString("base64url");

// ───────────────────────────────────────────── teardown
function teardown() {
  if (KEEP) {
    console.log(`left running (--keep): project ${PROJECT}, ${SRC}, ${V1}`);
    return;
  }
  const compose = path.join(RUNTIME, "compose.age-fabric.yml");
  try {
    // values do not matter for down; set them so compose does not warn about each
    const env = { ...process.env };
    for (const k of ["ROBO_IMAGE_GRAPH_DB", "ROBO_IMAGE_GRAPH_BOLT", "ROBO_IMAGE_FABRIC", "ROBO_IMAGE_FABRIC_DB", "ROBO_IMAGE_CATALOG",
      "ROBO_IMAGE_ANALYZER", "ROBO_IMAGE_PARSER", "ROBO_IMAGE_GATEWAY", "ROBO_IMAGE_WIREFRAME", "ROBO_RELEASE_ID", "ROBO_GRAPH_USER", "ROBO_GRAPH_DESIGN",
      "ROBO_GRAPH_ANALYSIS", "ROBO_NEO4J_PASSWORD", "ROBO_AGE_ADMIN_PASSWORD", "ROBO_FABRIC_DB_PASSWORD", "ROBO_FABRIC_QUERY_PASSWORD",
      "ROBO_FABRIC_SERVICE_TOKEN", "ROBO_FABRIC_INTERNAL_TOKEN"]) env[k] ??= "x";
    for (const k of ["ROBO_NEO4J_PORT", "ROBO_ANALYZER_PORT", "ROBO_GATEWAY_PORT", "ROBO_FABRIC_PORT", "ROBO_ARCHITECT_API_PORT",
      "ROBO_WIREFRAME_PORT"]) env[k] ??= "1";
    sh("docker", ["compose", "--project-name", PROJECT, "--file", compose, "down", "--volumes", "--timeout", "10"], { env });
  } catch (e) {
    console.log("compose down:", String(e.stderr || e.message).slice(0, 300));
  }
  for (const c of [V1, SRC]) {
    try {
      docker("rm", "-f", "-v", c);
    } catch {
      /* gone */
    }
  }
}

// ───────────────────────────────────────────── 0. throwaway source + v1 graph-db
const srcAdmin = token();
const roPassword = token();
const installGraphPassword = token(); // this install's graph password (v1 and AGE share it, as on one PC)
await secretStore.setSecret("runtime.docker.neo4j.password", installGraphPassword);

function pg(container, user, db, sql, extra = []) {
  return sh("docker", ["exec", "-i", container, "psql", "-X", "-At", "-v", "ON_ERROR_STOP=1", "-U", user, "-d", db, ...extra], {
    input: sql,
  });
}

async function waitPg(container, user, db) {
  for (let i = 0; i < 60; i++) {
    try {
      docker("exec", container, "pg_isready", "-q", "-h", "127.0.0.1", "-U", user, "-d", db);
      return;
    } catch {
      await sleep(1000);
    }
  }
  throw new Error(`${container} did not start`);
}

const summary = { started: new Date().toISOString(), freeGiBStart: +startFree.toFixed(1) };
try {
  for (const c of [SRC, V1]) {
    try {
      docker("rm", "-f", "-v", c);
    } catch {
      /* none */
    }
  }
  docker("run", "-d", "--name", SRC, "--memory", "256m", "-p", `127.0.0.1:${SRC_PORT}:5432`,
    "-e", "POSTGRES_USER=shop_admin", "-e", `POSTGRES_PASSWORD=${srcAdmin}`, "-e", "POSTGRES_DB=shopdb",
    "postgres:16-bookworm", "-c", "temp_file_limit=2GB", "-c", "statement_timeout=120s");
  await waitPg(SRC, "shop_admin", "shopdb");
  pg(SRC, "shop_admin", "shopdb", fs.readFileSync(path.join(here, "source.sql"), "utf8"), ["-q", "-v", `ro_password=${roPassword}`]);
  check("source: sample shop database (6 tables, 1 view, no declared FK)", pg(SRC, "shop_admin", "shopdb", "SELECT count(*) FROM shop.order_items") === "720");

  docker("run", "-d", "--name", V1, "--memory", "512m", "-p", `127.0.0.1:${V1_PORT}:5432`,
    "--label", `com.docker.compose.project=${V1_PROJECT}`, "--label", "com.docker.compose.service=graph-db",
    "-e", "POSTGRES_USER=robo", "-e", `POSTGRES_PASSWORD=${installGraphPassword}`, "-e", "POSTGRES_DB=robo",
    "-e", "OG_GRAPH_DESIGN=robo", "-e", "OG_GRAPH_ANALYSIS=analyzer_run",
    "uengine/ontological-db:lite-mac", "-c", "temp_file_limit=2GB", "-c", "statement_timeout=120s");
  await waitPg(V1, "robo", "robo");
  await sleep(3000);
  const v1Params = JSON.stringify({ host: "host.docker.internal", port: SRC_PORT, database: "shopdb", schema: "shop", user: "shop_ro", password: roPassword });
  pg(V1, "robo", "robo", `SELECT og_fabric('CREATE DATASOURCE legacy WITH ENGINE = ''postgres'', PARAMETERS = ${v1Params}');`);
  const v1Inline = pg(V1, "robo", "robo", "SELECT count(*) FROM pg_user_mapping m JOIN pg_foreign_server s ON s.oid = m.umserver WHERE s.srvname = 'og_ds_legacy' AND array_to_string(m.umoptions, ',') LIKE '%password=%'");
  check("v1: datasource legacy with its password inline in pg_user_mapping", v1Inline === "1");

  // ───────────────────────────────────────────── 1. first boot through the app's code
  let t0 = Date.now();
  const runtime = await stack.startDockerStack();
  summary.firstBootSeconds = Math.round((Date.now() - t0) / 1000);
  const ports = runtime.ports;
  check("startDockerStack (age-fabric) returned", runtime.projectName === PROJECT && ports.fabric > 0,
    `${summary.firstBootSeconds}s, project ${runtime.projectName}`);

  const ps = docker("compose", "--project-name", PROJECT, "ps", "--all", "--format", "{{.Service}}\t{{.State}}\t{{.Health}}\t{{.Ports}}")
    .split("\n").map((l) => l.split("\t"));
  const services = Object.fromEntries(ps.map(([s, st, h, p]) => [s, { state: st, health: h, ports: p }]));
  const expected = ["age-db", "age-bolt", "fabric-db", "fabric", "catalog", "analyzer", "parser", "gateway", "wireframe"];
  check("9 services up and healthy (wireframe included)", expected.every((s) => services[s]?.state === "running" && services[s]?.health === "healthy"),
    expected.map((s) => `${s}:${services[s]?.health}`).join(" "));
  const published = ps.map(([s, , , p]) => [s, p]).filter(([, p]) => p && /->/.test(p));
  check("host ports on 127.0.0.1 only (age-bolt, fabric, analyzer, gateway, wireframe)",
    published.every(([, p]) => p.split(",").filter((x) => x.includes("->")).every((x) => x.trim().startsWith("127.0.0.1:")))
      && published.map(([s]) => s).sort().join() === "age-bolt,analyzer,fabric,gateway,wireframe",
    published.map(([s, p]) => `${s} ${p}`).join("; "));
  const internal = ["graph", "fabric"].map((n) => docker("network", "inspect", `${PROJECT}_${n}`, "--format", "{{.Internal}}"));
  check("networks graph and fabric are internal", internal.every((x) => x === "true"), internal.join(","));
  const dbNets = docker("inspect", `${PROJECT}-fabric-db-1`, "--format", "{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}");
  check("fabric-db only on fabric (internal) + sources", dbNets.split(" ").filter(Boolean).sort().join() === `${PROJECT}_fabric,${PROJECT}_sources`, dbNets);
  const tmpfs = docker("exec", `${PROJECT}-fabric-db-1`, "sh", "-c", "grep ' /run/og-fabric/credentials ' /proc/mounts; stat -c '%a %u' /run/og-fabric/credentials");
  check("credentials folder is a tmpfs, 0700, uid 999", /tmpfs/.test(tmpfs) && /700 999/.test(tmpfs), tmpfs.replace(/\n/g, " | "));

  // Bolt: the AGE gateway, the fixed graphs
  const bolt = neo4j.driver(`bolt://127.0.0.1:${ports.neo4j}`, neo4j.auth.basic("robo", installGraphPassword));
  const info = await bolt.getServerInfo();
  check("Bolt agent is the AGE gateway", /age-bolt/.test(info.agent), info.agent);
  const graphs = [];
  for (const g of ["robo", "analyzer_run"]) {
    const s = bolt.session({ database: g });
    try {
      await s.run("MATCH (n) RETURN count(n) AS n");
      graphs.push(g);
    } finally {
      await s.close();
    }
  }
  check("graphs robo and analyzer_run exist (made at install, gateway makes none)", graphs.length === 2, graphs.join(","));
  const owners = pg(`${PROJECT}-age-db-1`, "supabase_admin", "graph", "SELECT string_agg(nspname || ':' || pg_get_userbyid(nspowner), ',' ORDER BY nspname) FROM pg_namespace WHERE nspname IN ('robo','analyzer_run')", ["-h", "127.0.0.1"]);
  check("robo owns its graphs", owners === "analyzer_run:robo,robo:robo", owners);
  const roleRow = pg(`${PROJECT}-age-db-1`, "supabase_admin", "graph", "SELECT rolsuper::text || rolbypassrls::text || (rolpassword LIKE 'SCRAM-SHA-256$%')::text FROM pg_authid WHERE rolname = 'robo'", ["-h", "127.0.0.1"]);
  check("role robo: not superuser, no BYPASSRLS, SCRAM verifier", roleRow === "falsefalsetrue", roleRow);

  // og-fabric, as a caller with the service token
  const serviceToken = await secretStore.getSecret("runtime.docker.fabric.service.token");
  const fabric = `http://127.0.0.1:${ports.fabric}`;
  const api = async (method, p, body, base = fabric, headers = {}) => {
    const r = await fetch(base + p, {
      method,
      headers: { Authorization: `Bearer ${serviceToken}`, ...(body ? { "Content-Type": "application/json" } : {}), ...headers },
      body: body ? JSON.stringify(body) : undefined,
    });
    let json = null;
    try {
      json = await r.json();
    } catch {
      /* empty */
    }
    return { status: r.status, json };
  };
  check("og-fabric refuses a call without its token", (await fetch(fabric + "/api/datasources")).status === 401);
  const internalWrong = await fetch(fabric + "/internal/secrets/keychain%3Ads%2Fx", {
    method: "PUT", headers: { Authorization: `Bearer ${serviceToken}`, "Content-Type": "application/json" },
    body: JSON.stringify({ secret: "x" }),
  });
  check("the secrets channel refuses the service token (needs the per-boot one)", internalWrong.status === 403);

  // ───────────────────────────────────────────── 2. the v1 plaintext migration (once, at that first boot)
  const marker = path.join(userData, "runtime", "age-fabric-migration.json");
  const markerJson = fs.existsSync(marker) ? JSON.parse(fs.readFileSync(marker, "utf8")) : null;
  check("migration ran once and marked it", markerJson?.moved?.includes("legacy"), JSON.stringify(markerJson?.moved));
  const legacy = await api("GET", "/api/datasources/legacy");
  check("legacy is in og-fabric with a keychain reference", legacy.status === 200 && legacy.json.credentials === "keychain:ds/legacy"
    && legacy.json.table_count === 7,
    `${legacy.status} ${legacy.json?.credentials} tables=${legacy.json?.table_count}`);
  const legacyId = ags.secretIdOfRef("keychain:ds/legacy");
  check("its secret is in the keychain store (safeStorage), equal to v1's",
    (await secretStore.getSecret(legacyId)) === roPassword && sealed.has(roPassword)
      && fs.existsSync(path.join(userData, "secrets", `${legacyId}.bin`)));
  const lq = await api("POST", "/api/query", { datasource: "legacy", query: "SELECT count(*) AS n FROM orders" });
  check("legacy answers through og-fabric", lq.status === 200 && Number(lq.json.rows?.[0]?.[0]) === 240, JSON.stringify(lq.json?.rows));
  check("v1 is left as it was", pg(V1, "robo", "robo", "SELECT count(*) FROM og_catalog.datasource") === "1");

  // ───────────────────────────────────────────── 3. a datasource the way the screen makes it
  const inline = await api("POST", "/api/datasources", { name: "shop_inline", engine: "postgres",
    parameters: { host: "localhost", port: SRC_PORT, database: "shopdb", schema: "shop", user: "shop_ro", password: roPassword } });
  check("an inline password is refused (403)", inline.status === 403 && inline.json?.error?.code === "inline_password_refused");
  const kept = await ags.keepDatasourceSecret(store, stack.getFabricClient(), "shop", roPassword);
  check("keepDatasourceSecret → keychain:ds/shop (what fabric:keepDatasourceSecret answers)", kept.credentials === "keychain:ds/shop");
  t0 = Date.now();
  const created = await api("POST", "/api/datasources", { name: "shop", engine: "postgres",
    parameters: { host: "localhost", port: SRC_PORT, database: "shopdb", schema: "shop", user: "shop_ro", credentials: kept.credentials } });
  check("register shop with the reference only (host localhost → host.docker.internal)", created.status === 201 && created.json.table_count === 7,
    `${created.status} tables=${created.json?.table_count} ${Date.now() - t0}ms`);
  const tables = await api("GET", "/api/datasources/shop/tables");
  const kinds = Object.fromEntries((tables.json?.tables ?? []).map((t) => [t.name, t.kind]));
  check("og-fabric lists the source's kinds (big_orders is a view)", kinds.big_orders === "view" && kinds.orders === "table", JSON.stringify(kinds));

  // ───────────────────────────────────────────── 4. sample (catalog through the API gateway)
  const gateway = `http://127.0.0.1:${ports.gateway}/api/gateway/robo`;
  const caps = await api("GET", "/system/capabilities", null, gateway);
  check("catalog: variant age-fabric, graph age, source service (probed)",
    caps.json?.variant === "age-fabric" && caps.json?.graph?.engine === "age" && caps.json?.source?.kind === "service"
      && caps.json?.source?.available === true && caps.json?.probed === true, JSON.stringify(caps.json?.notes));
  t0 = Date.now();
  const disc = await api("GET", "/tables/discovery?datasource=shop&sample_limit=3", null, gateway);
  const discTables = disc.json?.tables ?? [];
  const ordersSample = discTables.find((t) => (t.name ?? t.table_name) === "orders");
  check("sample: catalog discovery lists shop's tables with sample rows", disc.status === 200 && discTables.length === 7
    && (ordersSample?.sample_rows?.length ?? 0) === 3, `${disc.status} tables=${discTables.length} ${Date.now() - t0}ms`);
  summary.sampleRow = ordersSample?.sample_rows?.[0] ?? null;
  const fs1 = await api("GET", "/api/datasources/shop/tables/customers/sample?limit=2");
  check("sample: og-fabric sample endpoint", fs1.status === 200 && fs1.json?.data?.length === 2,
    `${fs1.status} ${JSON.stringify(fs1.json).slice(0, 300)}`);

  // ───────────────────────────────────────────── 5. the analyzer's TABLE / COLUMN nodes + one declared FK
  const cols = {
    regions: [["code", "text", true], ["name", "text", false]],
    customers: [["id", "integer", true], ["name", "text", false], ["region_code", "text", false], ["email", "text", false]],
    products: [["id", "integer", true], ["sku", "text", false], ["name", "text", false], ["price", "numeric", false]],
    orders: [["id", "integer", true], ["customer_id", "integer", false], ["ordered_at", "date", false], ["status", "text", false],
      ["coupon_id", "integer", false]],
    coupons: [["coupon_id", "integer", true], ["label", "text", false]],
    order_items: [["order_id", "integer", true], ["line_no", "integer", true], ["product_id", "integer", false], ["qty", "integer", false]],
  };
  const an = bolt.session({ database: "analyzer_run" });
  try {
    for (const [t, cs] of Object.entries(cols)) {
      await an.run("CREATE (t:TABLE {_owner: 'analyzer', datasource: 'shop', schema: 'shop', name: $t, table_type: 'BASE TABLE'})", { t });
      for (const [c, ty, pk] of cs) {
        await an.run(
          "MATCH (t:TABLE {_owner: 'analyzer', datasource: 'shop', name: $t}) " +
            "CREATE (t)-[:HAS_COLUMN]->(:COLUMN {_owner: 'analyzer', name: $c, data_type: $ty, nullable: $n, primary_key: $pk, unique: $pk})",
          { t, c, ty, n: !pk, pk },
        );
      }
    }
    await an.run(
      "MATCH (s:TABLE {_owner: 'analyzer', datasource: 'shop', name: 'orders'}), (t:TABLE {_owner: 'analyzer', datasource: 'shop', name: 'customers'}) " +
        "CREATE (s)-[:FK {_owner: 'analyzer', from_column: 'customer_id', to_column: 'id'}]->(t)",
    );
    const n = (await an.run("MATCH (t:TABLE {datasource: 'shop'}) RETURN count(t) AS n")).records[0].get("n").toNumber();
    check("analysis graph: 6 TABLE nodes (as the Analyzer writes them) + 1 declared FK", n === 6);
  } finally {
    await an.close();
  }

  // ───────────────────────────────────────────── 6. FK inference → FK edges in AGE
  t0 = Date.now();
  const inf = await api("POST", "/schema/infer-relationships", { datasources: ["shop"], persist: true }, gateway);
  summary.inferMs = Date.now() - t0;
  const pairs = (rows) => (rows ?? []).map((r) => `${r.child_table}.${r.child_column ?? (r.child_columns ?? []).join("+")}→${r.parent_table}.${r.parent_column ?? (r.parent_columns ?? []).join("+")}`);
  summary.inference = {
    status: inf.status, source: inf.json?.source, dialect: inf.json?.dialect, relation_kinds: inf.json?.relation_kinds,
    relationships: pairs(inf.json?.relationships), unverified: pairs(inf.json?.unverified), already: inf.json?.already,
    rejected: (inf.json?.rejected ?? []).length, checks: inf.json?.checks, queries: inf.json?.queries, persisted: inf.json?.persisted,
    ms: summary.inferMs,
  };
  console.log(JSON.stringify(summary.inference, null, 1));
  check("FK inference ran over og-fabric (sql, postgres, kinds from the source)",
    inf.status === 200 && inf.json.source === "sql" && inf.json.dialect === "postgres" && inf.json.relation_kinds === "source",
    `${inf.status} ${summary.inferMs}ms`);
  const want = ["shop.shop.order_items.order_id→shop.shop.orders.id", "shop.shop.order_items.product_id→shop.shop.products.id"];
  check("relinfer finds order_items → orders and → products", want.every((w) => summary.inference.relationships.includes(w)),
    summary.inference.relationships.join(" "));
  check("the declared FK (orders → customers) is known, not suggested again",
    JSON.stringify(inf.json?.already ?? []).includes("customer_id") && !summary.inference.relationships.some((r) => r.includes("orders.customer_id")));
  const an2 = bolt.session({ database: "analyzer_run" });
  let edges = [];
  try {
    const res = await an2.run(
      "MATCH (s:TABLE)-[r]->(t:TABLE) WHERE s.datasource = 'shop' AND type(r) IN ['FK', 'FK_CANDIDATE'] " +
        "RETURN type(r) AS type, s.name AS s, r.from_column AS fc, t.name AS t, r.to_column AS tc, r._owner AS owner, r.status AS status, r.inferred AS inferred " +
        "ORDER BY type, s, fc",
    );
    edges = res.records.map((x) => x.toObject());
  } finally {
    await an2.close();
  }
  summary.edgesAfterInference = edges;
  const inferredEdges = edges.filter((e) => e.type === "FK" && e.owner === "catalog");
  check("FK edges in AGE: catalog-owned, inferred, one per accepted relationship",
    inferredEdges.length === (inf.json?.persisted?.persisted ?? -1) && inferredEdges.length >= 2
      && inferredEdges.every((e) => e.inferred === true && e.status === "inferred"),
    `${inferredEdges.length} inferred, ${edges.filter((e) => e.type === "FK_CANDIDATE").length} candidates, ${edges.filter((e) => e.owner === "analyzer").length} declared`);

  // ───────────────────────────────────────────── 7. review
  const fk = await api("GET", "/schema/inferred-relationships?datasource=shop", null, gateway);
  summary.review = { declared: fk.json?.declared?.length, inferred: fk.json?.inferred?.length, review: (fk.json?.review ?? []).map((r) => `${r.from_table}.${r.from_columns}→${r.to_table}.${r.to_columns} (${r.review})`) };
  check("review lists: declared 1, inferred = the FK edges", fk.status === 200 && fk.json.declared.length === 1 && fk.json.inferred.length === inferredEdges.length,
    JSON.stringify(summary.review));
  const candidate = (fk.json?.review ?? []).find((r) => r.from_table === "orders" && (r.from_columns ?? []).includes("coupon_id"));
  check("review: the never-filled orders.coupon_id is left for a reviewer (FK_CANDIDATE)",
    !!candidate && candidate.to_table === "coupons" && edges.some((e) => e.type === "FK_CANDIDATE" && e.fc === "coupon_id"),
    JSON.stringify(summary.review.review));
  const missing = await api("POST", "/schema/inferred-relationships/accept", {
    datasource: "shop", from_schema: "shop", from_table: "orders", from_columns: ["status"],
    to_schema: "shop", to_table: "regions", to_columns: ["code"] }, gateway);
  check("review: accepting a candidate that is not there is 404", missing.status === 404, `${missing.status} ${JSON.stringify(missing.json)}`);
  if (candidate) {
    const ref = {
      datasource: candidate.from_datasource, from_schema: candidate.from_schema, from_table: candidate.from_table,
      from_columns: candidate.from_columns, to_schema: candidate.to_schema, to_table: candidate.to_table, to_columns: candidate.to_columns,
    };
    const acc = await api("POST", "/schema/inferred-relationships/accept", ref, gateway, { "X-User-Name": "e2e-reviewer" });
    const after = await api("GET", "/schema/inferred-relationships?datasource=shop", null, gateway);
    const accepted = (after.json?.inferred ?? []).find((r) => r.from_table === "orders" && r.kind === "accepted");
    const an3 = bolt.session({ database: "analyzer_run" });
    let inAge = [];
    try {
      inAge = (await an3.run("MATCH (s:TABLE {name: 'orders'})-[r]->(t:TABLE {name: 'coupons'}) RETURN type(r) AS type, r.status AS status, r.accepted_by AS by"))
        .records.map((x) => x.toObject());
    } finally {
      await an3.close();
    }
    summary.accepted = inAge;
    check("review: a person accepts it → an accepted FK in AGE, the candidate gone",
      acc.status === 200 && !!accepted && (after.json?.review ?? []).length === 0
        && inAge.length === 1 && inAge[0].type === "FK" && inAge[0].status === "accepted",
      `${acc.status} ${JSON.stringify(inAge)}`);
  }

  // ───────────────────────────────────────────── 8. second boot: new channel token, keychain secrets handed over again
  await stack.stopDockerStack();
  t0 = Date.now();
  const again = await stack.startDockerStack();
  summary.secondBootSeconds = Math.round((Date.now() - t0) / 1000);
  check("second boot: the saved state is read back — the same host ports",
    JSON.stringify(again.ports) === JSON.stringify(ports), `${JSON.stringify(ports)} → ${JSON.stringify(again.ports)}`);
  const fabric2 = `http://127.0.0.1:${again.ports.fabric}`;
  const creds = await api("GET", "/api/credentials", null, fabric2);
  const states = Object.fromEntries((creds.json?.credentials ?? []).map((c) => [c.name, c.resolved]));
  check("second boot: both keychain datasources resolved again (handed over from the keychain store)",
    states.shop === true && states.legacy === true, `${JSON.stringify(states)} ${summary.secondBootSeconds}s`);
  const q2 = await api("POST", "/api/query", { datasource: "shop", query: "SELECT count(*) FROM order_items WHERE product_id = ANY($1)", params: [[1, 2, 3]] }, fabric2);
  check("second boot: shop answers (with a parameter)", q2.status === 200 && Number(q2.json.rows?.[0]?.[0]) > 0, JSON.stringify(q2.json?.rows));
  const log = fs.readFileSync(path.join(userData, "logs", "desktop.log"), "utf8");
  check("migration not run again (marker)", (log.match(/fabric\.migrate\.done/g) ?? []).length === 1);
  const bolt2 = neo4j.driver(`bolt://127.0.0.1:${again.ports.neo4j}`, neo4j.auth.basic("robo", installGraphPassword));
  const s2 = bolt2.session({ database: "analyzer_run" });
  const kept2 = (await s2.run("MATCH (:TABLE)-[r:FK]->(:TABLE) RETURN count(r) AS n")).records[0].get("n").toNumber();
  await s2.close();
  await bolt2.close();
  check("second boot: the FK edges are still in AGE (volume kept)", kept2 === edges.filter((e) => e.type === "FK").length + (candidate ? 1 : 0), String(kept2));

  // ───────────────────────────────────────────── 9. secrets: where they must not be
  const containerEnv = expected.map((s) => docker("inspect", `${PROJECT}-${s}-1`, "--format", "{{json .Config.Env}}")).join("\n");
  check("the source password is in no container's environment", !containerEnv.includes(roPassword));
  const logs = docker("compose", "--project-name", PROJECT, "logs", "--no-color", "fabric", "catalog", "fabric-db", "age-db");
  check("the source password is in no service log and not in the shell's log", !logs.includes(roPassword) && !log.includes(roPassword)
    && !log.includes(installGraphPassword));
  const files = docker("exec", `${PROJECT}-fabric-db-1`, "sh", "-c", "ls -ln /run/og-fabric/credentials | tail -n +2");
  check("connector files in the tmpfs: one per keychain datasource, 0600, uid 999",
    files.split("\n").length === 2 && files.split("\n").every((l) => l.startsWith("-rw-------") && /\b999\b/.test(l)), files.replace(/\n/g, " | "));
  await bolt.close();

  // ───────────────────────────────────────────── 10. the default configuration is untouched
  // the regular release this branch sits on (BASE_REF, default the 0.1.4 release tag)
  const baseRef = process.env.BASE_REF || "release/lite-0.1.4";
  const atBase = (file) => sh("git", ["-C", desktop, "show", `${baseRef}:desktop/${file}`]);
  const sameCompose = atBase("runtime/compose.yml") === fs.readFileSync(path.join(desktop, "runtime/compose.yml"), "utf8").trimEnd();
  const sameTemplate = atBase("runtime/runtime-manifest.template.json")
    === fs.readFileSync(path.join(desktop, "runtime/runtime-manifest.template.json"), "utf8").trimEnd();
  const defEnv = { ...process.env };
  for (const k of ["ROBO_IMAGE_GRAPH_DB", "ROBO_IMAGE_GRAPH_BOLT", "ROBO_IMAGE_FABRIC", "ROBO_IMAGE_CATALOG", "ROBO_IMAGE_ANALYZER",
    "ROBO_IMAGE_PARSER", "ROBO_IMAGE_GATEWAY", "ROBO_IMAGE_WIREFRAME", "ROBO_RELEASE_ID", "ROBO_GRAPH_USER", "ROBO_GRAPH_DESIGN",
    "ROBO_GRAPH_ANALYSIS", "ROBO_NEO4J_PASSWORD"]) defEnv[k] = "x";
  for (const k of ["ROBO_NEO4J_PORT", "ROBO_GRAPH_PG_LOCAL_PORT", "ROBO_ANALYZER_PORT", "ROBO_GATEWAY_PORT", "ROBO_ARCHITECT_API_PORT",
    "ROBO_WIREFRAME_PORT"]) defEnv[k] = "1";
  const defServices = sh("docker", ["compose", "-p", "ral-agefab-default-check", "-f", path.join(desktop, "runtime/compose.yml"), "config", "--services"], { env: defEnv })
    .split("\n").sort().join(",");
  check(`default compose.yml and manifest template are byte-identical to ${baseRef}; it resolves to its 8 services`,
    sameCompose && sameTemplate && defServices === "analyzer,catalog,fabric,gateway,graph-bolt,graph-db,parser,wireframe", defServices);

  await stack.stopDockerStack();
} catch (err) {
  check("no unexpected error", false, String(err?.stack ?? err).slice(0, 1500));
} finally {
  teardown();
  summary.freeGiBEnd = +freeGiB().toFixed(1);
  summary.results = results;
  summary.passed = results.filter((r) => r.ok).length;
  summary.failed = failures;
  fs.writeFileSync(path.join(WORK, "result.json"), JSON.stringify(summary, null, 2) + "\n");
  console.log(`\n${summary.passed} passed, ${failures} failed — ${path.join(WORK, "result.json")}`);
  process.exit(failures ? 1 : 0);
}
