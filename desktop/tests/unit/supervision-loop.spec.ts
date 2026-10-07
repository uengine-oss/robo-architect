/**
 * 프로브를 **주기적으로 돌리는 것** (spec 058 T018).
 *
 * ## 2026-10-07 에 잰 것
 *
 * 프로브(`probes/`)와 판정(`supervisor.ts`)은 다 있었는데 **돌려 주는 쪽이
 * 없었다** — `RuntimeRegistry.applyProbe` 의 호출자가 저장소 전체에서 0개였다.
 * 그래서 `snapshot().services` 는 언제나 빈 배열이고, `buildRuntimeState()` 은
 * "등록이 비어 있으면 신규 필드를 안 싣는다" 로 빠진다. **설계는 서비스 9개를
 * 따로 보는데 동작은 백엔드 상태 하나**였다.
 *
 * 그래서 이 검사는 "돈다" 가 아니라 **"무엇을 언제 돌리나"** 를 센다 —
 *
 * ```
 * ① 주기가 갈린다        health 5초 · capability 60초 (비싼 것을 자주 돌리지 않는다)
 * ② 겹쳐 돌리지 않는다    느린 프로브가 1초 틱마다 쌓이면 컨테이너를 때린다
 * ③ 모르면 모른다고 한다  컨테이너 목록을 못 얻은 것과 "죽었다" 는 다른 사실이다
 * ④ 바뀐 것만 남긴다      5초마다 같은 줄을 쓰면 로그가 그것으로 덮인다
 * ```
 *
 * ③이 가장 중요하다. `alive: false` 는 `decideState` 가 **가장 강한 근거**로 받아
 * 프로브를 보지도 않고 `failed` 로 만든다. 모르는 것을 `false` 로 넘기면 도커가
 * 꺼진 순간 멀쩡한 서비스 9개가 전부 "실행 중이 아닙니다" 가 된다.
 */

import { expect, test } from "@playwright/test";

import {
  CAPABILITY_INTERVAL_MS,
  HEALTH_INTERVAL_MS,
  aliveFrom,
  duePlan,
  probeKey,
  startSupervision,
} from "../../src/main/supervision";
import type { ManagedServiceId, ProbeKind, ProbeResult } from "../../src/shared/runtime-contract";

/** 왜 그렇게 돼야 하는지를 **실패 메시지에 남긴다** — 기존 검사들의 `expect` 를 쓴다. */
const expectEqual = (actual: unknown, want: unknown, why?: string) =>
  expect(actual, why).toEqual(want);
const expectBe = (actual: unknown, want: unknown, why?: string) =>
  expect(actual, why).toBe(want);
const throwFail = (why: string): never => {
  throw new Error(why);
};

const IDS = ["architect", "graph", "pdf2bpmn"] as ManagedServiceId[];
const withCapability = new Set<string>(["graph", "pdf2bpmn"]);
const hasCapability = (id: ManagedServiceId) => withCapability.has(id);

// ── ① 주기 ─────────────────────────────────────────────────────────────────

test("처음에는 전부 돈다 — 한 번도 안 돈 것은 기다리지 않는다", () => {
  const plan = duePlan(IDS, new Map(), 1_000, { hasCapability });
  expectEqual(plan.map((d) => probeKey(d.id, d.kind)).sort(),
    [
      "architect:health",
      "graph:capability",
      "graph:health",
      "pdf2bpmn:capability",
      "pdf2bpmn:health",
    ],
  );
});

test("기능 프로브가 없는 서비스는 capability 를 안 돌린다", () => {
  const plan = duePlan(["architect"] as ManagedServiceId[], new Map(), 0, { hasCapability });
  expectEqual(plan, [{ id: "architect", kind: "health" }]);
});

test("health 는 5초, capability 는 60초 — 중간 시각에는 health 만 돈다", () => {
  const start = 10_000;
  const last = new Map<string, number>([
    ["graph:health", start],
    ["graph:capability", start],
  ]);
  const ids = ["graph"] as ManagedServiceId[];

  expectEqual(duePlan(ids, last, start + 4_999, { hasCapability }), [], "5초 전에는 아무것도");
  expectEqual(duePlan(ids, last, start + HEALTH_INTERVAL_MS, { hasCapability }),
    [{ id: "graph", kind: "health" }],
    "5초에는 health 만",
  );
  expectEqual(duePlan(ids, last, start + CAPABILITY_INTERVAL_MS, { hasCapability }).map((d) => d.kind).sort(),
    ["capability", "health"],
    "60초에는 둘 다",
  );
});

// ── ② 겹침 ─────────────────────────────────────────────────────────────────

test("돌고 있는 프로브는 다시 계획하지 않는다", () => {
  const plan = duePlan(["graph"] as ManagedServiceId[], new Map(), 0, {
    hasCapability,
    inflight: new Set(["graph:capability"]),
  });
  expectEqual(plan, [{ id: "graph", kind: "health" }]);
});

// ── ③ 살아 있는가 — 모르는 것을 아는 척하지 않는다 ─────────────────────────

test("컨테이너 목록이 비면 **모른다**(null) — 죽었다가 아니다", () => {
  expectBe(aliveFrom([], ["robo-graph-bolt-1"]), null);
});

test("후보 이름이 목록에 있으면 살아 있다", () => {
  expectBe(aliveFrom(["robo-graph-bolt-1", "robo-architect-1"], ["robo-graph-bolt-1"]), true);
});

test("후보 둘 중 하나만 돌아도 살아 있다 — 구성마다 이름이 다르다", () => {
  expectBe(aliveFrom(["robo-neo4j-1"], ["robo-graph-bolt-1", "robo-neo4j-1"]), true);
});

test("목록은 얻었고 그 이름이 없으면 죽은 것이다", () => {
  expectBe(aliveFrom(["robo-architect-1"], ["robo-pdf2bpmn-1"]), false);
});

test("이름이 **비슷한 것**이 돌고 있으면 모른다 — 우리가 이름을 틀렸을 수 있다", () => {
  // compose 프로젝트 이름이 달라지면 접두사가 바뀐다. 그때 `false` 라고 말하면
  // 멀쩡한 서비스를 "실행 중이 아닙니다" 로 덮는다.
  expectBe(aliveFrom(["other-pdf2bpmn-1"], ["robo-pdf2bpmn-1"]), null);
});

// ── ④ 한 바퀴 — 적용과 기록 ────────────────────────────────────────────────

interface Applied {
  id: ManagedServiceId;
  alive: boolean | null;
  health: ProbeResult | null;
  capability: ProbeResult | null;
}

function harness(options: { running?: string[]; probe?: (id: ManagedServiceId, kind: ProbeKind) => ProbeResult } = {}) {
  const applied: Applied[] = [];
  const logs: { event: string; params: Record<string, unknown> }[] = [];
  const registered: ManagedServiceId[][] = [];
  let changedOnce = false;
  const result = (id: ManagedServiceId, kind: ProbeKind): ProbeResult => ({
    serviceId: id,
    kind,
    outcome: "pass",
    detail: "200",
    durationMs: 1,
  });
  const supervision = startSupervision<{ tag: string }>(
    {
      ids: () => ["graph"] as ManagedServiceId[],
      hasCapability: () => true,
      context: async () => ({ tag: "ctx" }),
      probe: async (_ctx, id, kind) => (options.probe ?? result)(id, kind),
      running: async () => options.running ?? ["robo-graph-bolt-1"],
      alive: (_ctx, _id, running) => aliveFrom(running, ["robo-graph-bolt-1"]),
      apply: (id, facts) => applied.push({ id, ...facts }),
      register: (ids) => registered.push(ids),
      changed: () => {
        if (changedOnce) return [];
        changedOnce = true;
        return [{ id: "graph" as ManagedServiceId, state: "ready", stateReason: null }];
      },
      log: (_level, event, params) => logs.push({ event, params }),
      now: () => 0,
    },
    { autostart: false },
  );
  return { supervision, applied, logs, registered };
}

test("한 틱이 등록하고, 프로브를 돌리고, 결과를 한 번에 적용한다", async () => {
  const h = harness();
  await h.supervision.tick();

  expectEqual(h.registered, [["graph"]], "볼 서비스를 먼저 등록한다");
  expectBe(h.applied.length, 1, "health·capability 를 **합쳐 한 번** 적용한다");
  const facts = h.applied[0]!;
  expectBe(facts.alive, true);
  expectBe(facts.health?.kind, "health");
  expectBe(facts.capability?.kind, "capability");
});

test("바뀐 것만 기록한다 — 두 번째 틱은 조용하다", async () => {
  const h = harness();
  await h.supervision.tick();
  const first = h.logs.filter((l) => l.event === "runtime.service.state");
  expectBe(first.length, 1);
  expectBe(first[0]!.params.service, "graph");

  // `now()` 가 0 에 묶여 있으니 두 번째 틱에는 돌릴 것이 없다 — 간격이 지키는 자리다.
  await h.supervision.tick();
  expectBe(h.logs.filter((l) => l.event === "runtime.service.state").length,
    1,
    "5초가 안 지났으면 다시 재지도, 쓰지도 않는다",
  );
});

test("설정을 모르면 아무것도 하지 않는다 — 추측해서 재지 않는다", async () => {
  const applied: Applied[] = [];
  const supervision = startSupervision<{ tag: string }>(
    {
      ids: () => ["graph"] as ManagedServiceId[],
      hasCapability: () => true,
      context: async () => null, // 스택이 아직 안 떴다
      probe: async () => {
        throw new Error("설정이 없는데 프로브를 돌렸다");
      },
      running: async () => [],
      alive: () => null,
      apply: (id, facts) => applied.push({ id, ...facts }),
      register: () => throwFail("등록도 하지 않는다"),
      changed: () => [],
      log: () => {},
      now: () => 0,
    },
    { autostart: false },
  );
  await supervision.tick();
  expectEqual(applied, []);
});

test("프로브 하나가 터져도 **틱은 끝난다** — 말하고 넘어간다", async () => {
  let calls = 0;
  let clock = 0;
  const logs: string[] = [];
  const applied: ManagedServiceId[] = [];
  const supervision = startSupervision<{ tag: string }>(
    {
      ids: () => ["graph", "architect"] as ManagedServiceId[],
      hasCapability: () => false,
      context: async () => ({ tag: "ctx" }),
      probe: async (_ctx, id) => {
        calls += 1;
        if (id === "graph") throw new Error("boom");
        return { serviceId: id, kind: "health", outcome: "pass", detail: "200", durationMs: 1 };
      },
      running: async () => [],
      alive: () => null,
      apply: (id) => applied.push(id),
      register: () => {},
      changed: () => [],
      log: (_level, event) => logs.push(event),
      now: () => clock,
    },
    { autostart: false },
  );

  await supervision.tick();
  // **다른 서비스는 그대로 판정된다** — 한 프로브의 사고가 틱을 끊지 않는다.
  expectEqual(applied.sort(), ["architect", "graph"], "둘 다 적용된다");
  expectBe(logs.includes("runtime.supervision.probe_failed"), true, "터진 것을 말한다");

  clock += HEALTH_INTERVAL_MS;
  await supervision.tick();
  expectBe(calls, 4, "다음 주기에 다시 잰다");
});

// ── ⑤ 배선 — **설치본에서 두 서비스를 잘못 적었다** (2026-10-07) ───────────
//
// 감독을 처음 붙여 구워 보니 10개 중 둘이 `failed` 로 찍혔다. 둘 다 코드가 아니라
// **배선이 틀린 것**이었고, 로그가 그 자리를 그대로 말해 줬다 —
//
//   graph      "bolt closed (172.27.64.1)"      호스트는 중앙인데 **포트가 이 PC 것**(59006)
//   architect  "컨테이너/프로세스가 실행 중이 아닙니다"  **호스트 프로세스**를 `docker ps` 로 찾았다
//
// 둘 다 `index.ts` 의 배선이라 단위 검사로 돌릴 수 없다(electron 을 끌고 온다).
// 그래서 **그 두 줄이 그대로 있는지**를 소스에서 본다. 투박하지만, 조용히
// 되돌아가는 것이 실제로 있었던 일이다.

import fs from "node:fs";
import path from "node:path";

const INDEX_TS = fs.readFileSync(
  path.resolve(__dirname, "../../src/main/index.ts"),
  "utf8",
);

test("중앙 모드에서는 **중앙의 bolt 포트**로 잰다", () => {
  expectBe(
    /graph:\s*topology\.mode === "central" \? topology\.boltPort : runtime\.ports\.graph/.test(
      INDEX_TS,
    ),
    true,
    "그래프 포트가 다시 이 PC 의 스택 값으로 돌아갔다 — 중앙에서 늘 bolt closed 가 된다",
  );
});

test("백엔드의 생존은 **pid** 로 본다 — 컨테이너 목록에 없다", () => {
  expectBe(
    /if \(id === "architect"\) return getRuntimeBackend\(\)\.pid !== null/.test(INDEX_TS),
    true,
    "호스트 프로세스를 docker ps 로 찾으면 멀쩡한 백엔드가 failed 가 된다",
  );
});
