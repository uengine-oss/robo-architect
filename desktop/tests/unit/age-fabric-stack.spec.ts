/**
 * Unit tests for the age-fabric configuration's shell side (src/main/runtime-variant.ts,
 * src/main/age-fabric-stack.ts). No Docker, no Electron, no og-fabric: `docker compose exec`, the
 * keychain and og-fabric's HTTP are fakes. The real round trip is tests/e2e-age-fabric/run.mjs.
 */

import { expect, test } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import {
  ageGraphsSql,
  ageRoleSql,
  datasourceRef,
  deliverKeychainSecrets,
  ensureAgeFabricSecrets,
  FabricClient,
  FabricError,
  fabricRolesSql,
  forgetDatasourceSecret,
  keepDatasourceSecret,
  migrateV1Plaintext,
  parseMigrationLines,
  prepareAgeDb,
  prepareFabricDb,
  scramSha256Verifier,
  secretIdOfRef,
  SECRET_IDS,
  type ExecInService,
  type SecretStoreLike,
} from "../../src/main/age-fabric-stack";
import {
  composeProjectName,
  deployVariantOf,
  requiredImageKeys,
  servicesOf,
} from "../../src/main/runtime-variant";

/** A secret store that remembers which values went to the keychain. */
function memoryStore(initial: Record<string, string> = {}) {
  const values = new Map(Object.entries(initial));
  const keychain = new Set<string>();
  const store: SecretStoreLike = {
    get: async (id) => values.get(id) ?? null,
    set: async (id, value, options) => {
      values.set(id, value);
      if (options?.keychain) keychain.add(id);
      else keychain.delete(id);
    },
    remove: async (id) => {
      values.delete(id);
      keychain.delete(id);
    },
  };
  return { store, values, keychain };
}

/** og-fabric's API and channel as a fetch. */
function fakeFabric(credentials: Array<{ name: string; engine: string; credentials: string; resolved?: boolean }>) {
  const calls: Array<{ method: string; url: string; headers: Record<string, string>; body?: unknown }> = [];
  const kept = new Map<string, string>();
  const fetchImpl = async (url: string, init: RequestInit = {}) => {
    const headers = (init.headers ?? {}) as Record<string, string>;
    const body = init.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method: init.method ?? "GET", url, headers, body });
    const u = new URL(url);
    if (u.pathname === "/healthz") return new Response(JSON.stringify({ status: "ok" }), { status: 200 });
    if (u.pathname.startsWith("/internal/secrets/")) {
      if (headers["X-Og-Fabric-Internal-Token"] !== "internal-0123456789abcdef") {
        return new Response(JSON.stringify({ error: { code: "forbidden", message: "the channel needs its token" } }), {
          status: 403,
        });
      }
      const ref = decodeURIComponent(u.pathname.slice("/internal/secrets/".length));
      if (init.method === "PUT") kept.set(ref, body.secret);
      else kept.delete(ref);
      return new Response(null, { status: 204, headers: { "X-Og-Fabric-Files": "1" } });
    }
    if (headers.Authorization !== "Bearer service-0123456789abcdef") {
      return new Response(JSON.stringify({ error: { code: "unauthorized" } }), { status: 401 });
    }
    if (u.pathname === "/api/credentials") return new Response(JSON.stringify({ credentials }), { status: 200 });
    return new Response(JSON.stringify({ error: { code: "not_found" } }), { status: 404 });
  };
  const client = new FabricClient(
    "http://127.0.0.1:1",
    "service-0123456789abcdef",
    "internal-0123456789abcdef",
    fetchImpl as unknown as typeof fetch,
  );
  return { client, calls, kept };
}

test.describe("runtime variant", () => {
  test("a manifest without deployVariant is the default configuration, unchanged", () => {
    expect(deployVariantOf(undefined)).toBe("ontological");
    expect(deployVariantOf("ontological")).toBe("ontological");
    expect(deployVariantOf("age-fabric")).toBe("age-fabric");
    expect(() => deployVariantOf("neo4j")).toThrow(/deployVariant/);
    expect(requiredImageKeys("ontological")).toEqual([
      "graphDb", "graphBolt", "analyzer", "catalog", "fabric", "parser", "gateway",
    ]);
    expect(requiredImageKeys("age-fabric")).toContain("fabricDb");
    expect(servicesOf("ontological")).toEqual({ db: "graph-db", bolt: "graph-bolt", fabricDb: null });
    expect(servicesOf("age-fabric")).toEqual({ db: "age-db", bolt: "age-bolt", fabricDb: "fabric-db" });
  });

  test("project names: the default stays robo-architect-desktop, age-fabric runs beside it", () => {
    expect(composeProjectName("ontological", undefined)).toBe("robo-architect-desktop");
    expect(composeProjectName("ontological", "Bad Name")).toBe("robo-architect-desktop");
    expect(composeProjectName("age-fabric", undefined)).toBe("robo-architect-desktop-age");
    expect(composeProjectName("age-fabric", "ral-agefab")).toBe("ral-agefab");
  });
});

test.describe("secrets and SQL", () => {
  test("SCRAM-SHA-256 verifier matches PostgreSQL's (the age-supabase script's Python)", () => {
    const salt = Buffer.from(Array.from({ length: 16 }, (_, i) => i));
    expect(scramSha256Verifier("abcdefghijklmnop_-12", salt)).toBe(
      "SCRAM-SHA-256$4096:AAECAwQFBgcICQoLDA0ODw==$HDux64x26bNLso8W0ykOz6LkKVHvIL0aIBcmaxMDg6Y=:" +
        "lYPR779122b0dE+UqPIu8/bukrwRPDHlFoF1dDwUm+s=",
    );
    expect(scramSha256Verifier("abcdefghijklmnop_-12")).not.toBe(scramSha256Verifier("abcdefghijklmnop_-12"));
    expect(() => scramSha256Verifier("short")).toThrow();
    expect(() => scramSha256Verifier("abcdefghijklmnop'; DROP")).toThrow();
  });

  test("install secrets are made once and kept", async () => {
    const { store, values, keychain } = memoryStore();
    const first = await ensureAgeFabricSecrets(store);
    const again = await ensureAgeFabricSecrets(store);
    expect(again).toEqual(first);
    expect(new Set(Object.values(first)).size).toBe(4);
    expect([...values.keys()].sort()).toEqual(Object.values(SECRET_IDS).sort());
    expect(keychain.size).toBe(0); // infrastructure secrets follow the store's own mode
  });

  test("SQL takes only names and verifiers", () => {
    const v = scramSha256Verifier("abcdefghijklmnop_-12");
    const sql = ageRoleSql("robo", v);
    expect(sql).toContain(`PASSWORD '${v}'`);
    expect(sql).toContain("\\gexec");
    expect(sql).toContain('GRANT CONNECT, CREATE ON DATABASE "graph" TO "robo"');
    expect(sql).not.toContain("abcdefghijklmnop_-12");
    expect(() => ageRoleSql("robo; drop", v)).toThrow();
    expect(() => ageRoleSql("robo", "plain-password")).toThrow();
    expect(ageGraphsSql(["robo", "analyzer_run"])).toContain("create_graph('analyzer_run')");
    expect(() => ageGraphsSql(["x'); DROP"])).toThrow();
    expect(fabricRolesSql(v, v)).toContain('ALTER ROLE "og_fabric_service" PASSWORD');
  });

  test("prepareAgeDb: AGE install only when the graph database is missing, role before graphs", async () => {
    const calls: Array<{ service: string; args: string[]; input?: string }> = [];
    let first = true;
    const exec: ExecInService = async (service, args, options) => {
      calls.push({ service, args, input: options?.input });
      if (args.includes("-c")) {
        if (first) {
          first = false;
          throw new Error("the database system is starting up"); // retried
        }
        return "0\n";
      }
      if (args.includes("robo") && args.includes("graph") && !args.includes("supabase_admin")) {
        return "graph robo: made\ngraph analyzer_run: there\n";
      }
      return "";
    };
    const lines = await prepareAgeDb(exec, {
      user: "robo",
      password: "abcdefghijklmnop_-12",
      graphs: ["robo", "analyzer_run"],
      delayMs: 1,
    });
    expect(lines).toEqual(["graph robo: made", "graph analyzer_run: there"]);
    expect(calls.map((c) => c.args.at(-1))).toEqual([
      "SELECT count(*) FROM pg_database WHERE datname = 'graph'",
      "SELECT count(*) FROM pg_database WHERE datname = 'graph'",
      "/docker-entrypoint-initdb.d/migrations/99999999999999_age.sql",
      "graph",
      "graph",
    ]);
    expect(calls[3]!.input).toContain("ALTER ROLE \"robo\"");
    expect(calls[4]!.args).toContain("robo"); // the graphs are made as robo, so robo owns them
    expect(calls.every((c) => c.service === "age-db")).toBe(true);
    expect(JSON.stringify(calls)).not.toContain("abcdefghijklmnop_-12");
  });

  test("prepareFabricDb sends verifiers, not passwords", async () => {
    const inputs: string[] = [];
    await prepareFabricDb(
      async (service, _args, options) => {
        expect(service).toBe("fabric-db");
        inputs.push(options?.input ?? "");
        return "";
      },
      { fabricDbPassword: "fabricdbpassword_0123", fabricQueryPassword: "fabricquerypassword_0123" },
    );
    expect(inputs[0]).toContain("SCRAM-SHA-256$4096:");
    expect(inputs[0]).not.toContain("fabricdbpassword_0123");
    expect(inputs[0]).not.toContain("fabricquerypassword_0123");
  });
});

test.describe("datasource passwords: keychain → og-fabric channel", () => {
  test("keep: the keychain, then the channel; the screen gets the reference only", async () => {
    const { store, values, keychain } = memoryStore();
    const fabric = fakeFabric([]);
    const out = await keepDatasourceSecret(store, fabric.client, "erp", "pw with 'quotes' #1");
    expect(out).toEqual({ credentials: "keychain:ds/erp" });
    const id = secretIdOfRef("keychain:ds/erp");
    expect(values.get(id)).toBe("pw with 'quotes' #1");
    expect(keychain.has(id)).toBe(true); // safeStorage, whatever the store's file mode
    expect(fabric.kept.get("keychain:ds/erp")).toBe("pw with 'quotes' #1");
    const put = fabric.calls.find((c) => c.method === "PUT")!;
    expect(put.url).toBe("http://127.0.0.1:1/internal/secrets/keychain%3Ads%2Ferp");
    expect(put.headers.Authorization).toBeUndefined(); // the channel token, not the service token
    await expect(keepDatasourceSecret(store, fabric.client, "pg_erp", "x")).rejects.toThrow(FabricError);
    await expect(keepDatasourceSecret(store, fabric.client, "Erp-1", "x")).rejects.toThrow(FabricError);
    await expect(keepDatasourceSecret(store, fabric.client, "erp", "")).rejects.toThrow(FabricError);
    expect(datasourceRef("wms_2")).toBe("keychain:ds/wms_2");

    await forgetDatasourceSecret(store, fabric.client, "erp");
    expect(values.has(id)).toBe(false);
    expect(fabric.kept.has("keychain:ds/erp")).toBe(false);
  });

  test("at start every keychain reference is handed over; one this install lacks is reported", async () => {
    const { store } = memoryStore({
      [secretIdOfRef("keychain:ds/erp")]: "erp-secret",
      [secretIdOfRef("keychain:shared/one")]: "shared-secret",
    });
    const fabric = fakeFabric([
      { name: "erp", engine: "postgres", credentials: "keychain:ds/erp", resolved: false },
      { name: "a", engine: "postgres", credentials: "keychain:shared/one", resolved: false },
      { name: "b", engine: "mysql", credentials: "keychain:shared/one", resolved: false },
      { name: "lost", engine: "postgres", credentials: "keychain:ds/lost", resolved: false },
      { name: "server", engine: "postgres", credentials: "vault:secret/fabric/x#password", resolved: true },
      { name: "dev", engine: "postgres", credentials: "inline", resolved: true },
    ]);
    const events: string[] = [];
    const out = await deliverKeychainSecrets(fabric.client, store, (level, event) => events.push(`${level} ${event}`));
    expect(out).toEqual({ delivered: ["erp", "a", "b"], missing: ["lost"] });
    expect([...fabric.kept.entries()]).toEqual([
      ["keychain:ds/erp", "erp-secret"],
      ["keychain:shared/one", "shared-secret"],
    ]);
    expect(fabric.calls.filter((c) => c.method === "PUT")).toHaveLength(2); // a shared reference once
    expect(events).toEqual(["warn fabric.keychain.delivered"]);
  });

  test("a wrong channel token is an error, not a silent skip", async () => {
    const fabric = fakeFabric([{ name: "erp", engine: "postgres", credentials: "keychain:ds/erp" }]);
    const wrong = new FabricClient("http://127.0.0.1:1", "service-0123456789abcdef", "not-the-token", (fabric.client as any).fetchImpl);
    const { store } = memoryStore({ [secretIdOfRef("keychain:ds/erp")]: "s" });
    await expect(deliverKeychainSecrets(wrong, store)).rejects.toMatchObject({ status: 403, code: "forbidden" });
  });
});

test.describe("plaintext migration from v1 (og-fabric-migrate --keychain)", () => {
  const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), "ral-agefab-"));

  test("the secrets go to the keychain, the marker only when every one moved", async () => {
    const dir = tmp();
    try {
      const { store, values, keychain } = memoryStore();
      const env: Array<Record<string, string>> = [];
      const outcome = await migrateV1Plaintext(
        {
          findV1: async () => ({ hostPort: 51698 }),
          runMigrate: async (extra) => {
            env.push(extra);
            return {
              code: 0,
              stdout:
                JSON.stringify({ name: "erp", engine: "postgres", ref: "keychain:ds/erp", secret: "s3cret", status: "moved" }) +
                "\n" +
                JSON.stringify({ name: "crm", engine: "postgres", ref: "keychain:ds/crm", secret: "other", status: "exists" }) +
                "\n",
              stderr: "moved   erp (postgres) → keychain:ds/erp, 3 tables\nexists  crm …\n",
            };
          },
          store,
          markerFile: path.join(dir, "runtime", "age-fabric-migration.json"),
        },
        { user: "robo", password: "v1-pass/word", database: "robo" },
      );
      expect(outcome).toEqual({ state: "migrated", moved: ["erp"], exists: ["crm"], complete: true });
      expect(env[0]!.OG_FABRIC_MIGRATE_FROM).toBe("postgresql://robo:v1-pass%2Fword@host.docker.internal:51698/robo");
      expect(values.get(secretIdOfRef("keychain:ds/erp"))).toBe("s3cret");
      expect(keychain.has(secretIdOfRef("keychain:ds/crm"))).toBe(true);
      const marker = fs.readFileSync(path.join(dir, "runtime", "age-fabric-migration.json"), "utf8");
      expect(marker).not.toContain("s3cret");
      expect(fs.statSync(path.join(dir, "runtime", "age-fabric-migration.json")).mode & 0o777).toBe(0o600);
      // once
      const again = await migrateV1Plaintext(
        { findV1: async () => { throw new Error("not asked"); }, runMigrate: async () => { throw new Error("not run"); }, store,
          markerFile: path.join(dir, "runtime", "age-fabric-migration.json") },
        { user: "robo", password: "x", database: "robo" },
      );
      expect(again).toEqual({ state: "done-before" });
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });

  test("no v1 stack: nothing run, nothing marked; a partial run is tried again next start", async () => {
    const dir = tmp();
    try {
      const { store } = memoryStore();
      const marker = path.join(dir, "m.json");
      expect(
        await migrateV1Plaintext(
          { findV1: async () => null, runMigrate: async () => { throw new Error("not run"); }, store, markerFile: marker },
          { user: "robo", password: "x", database: "robo" },
        ),
      ).toEqual({ state: "no-v1" });
      const partial = await migrateV1Plaintext(
        {
          findV1: async () => ({ hostPort: 1 }),
          runMigrate: async () => ({
            code: 1,
            stdout: JSON.stringify({ name: "erp", engine: "postgres", ref: "keychain:ds/erp", secret: "a", status: "moved" }) + "\n",
            stderr: "FAIL    wms: 502 …",
          }),
          store,
          markerFile: marker,
        },
        { user: "robo", password: "x", database: "robo" },
      );
      expect(partial).toEqual({ state: "migrated", moved: ["erp"], exists: [], complete: false });
      expect(fs.existsSync(marker)).toBe(false);
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });

  test("only well-formed secret lines are taken", () => {
    expect(() => parseMigrationLines("moved erp\n")).toThrow(/not JSON/);
    expect(() => parseMigrationLines(JSON.stringify({ name: "x", ref: "vault:a/b#c", secret: "s", status: "moved" }))).toThrow();
    expect(parseMigrationLines("\n")).toEqual([]);
  });
});

test.describe("runtime profile (what the screen names)", () => {
  test("age-fabric names Apache AGE and og-fabric; the default keeps its old words", async () => {
    const { profileOf } = await import("../../src/main/runtime-variant");
    expect(profileOf("age-fabric")).toEqual({
      id: "age-fabric", label: "Apache AGE + og-fabric", graph: "Apache AGE", fabric: "og-fabric", containers: 8,
    });
    const base = profileOf("ontological");
    expect(base.graph).toBe("Ontological");
    expect(base.containers).toBe(7);
  });
});
