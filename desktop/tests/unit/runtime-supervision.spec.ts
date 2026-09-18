/**
 * 런타임 감독의 판정 규칙 (spec 058 T025 · US1).
 *
 * ## 여기서 재는 것
 *
 * **"떴다"를 "쓸 수 있다"로 읽지 않는가.** 09-17 실측이 이 스펙의 근거다 —
 * `compose up --wait` 가 8/8 healthy 를 보고한 상태에서 pdf2bpmn 은 `/healthz` 200 을
 * 내면서 생성 요청에 502 를 냈다.
 *
 * 순수 함수만 부른다 — Docker·네트워크·Electron 없이 돈다. 실제 프로브가 그 판정을
 * 내는지는 별도로 스택에 붙여 쟀다(done-v2 §79).
 */

import { expect, test } from "@playwright/test";

import {
  deriveCapabilities,
  type ManagedService,
  type ManagedServiceId,
  type ProbeResult,
  type ServiceState,
} from "../../src/shared/runtime-contract";
import {
  applyRestartBudget,
  changedServiceIds,
  decideState,
  deriveLegacyStatus,
} from "../../src/main/supervisor";

const probe = (
  serviceId: ManagedServiceId,
  kind: "health" | "capability",
  outcome: ProbeResult["outcome"],
  detail = "",
): ProbeResult => ({ serviceId, kind, outcome, detail, durationMs: 1 });

const service = (id: ManagedServiceId, state: ServiceState): ManagedService => ({
  id,
  owner: id === "architect" ? "app" : "app",
  displayName: id,
  state,
  stateReason: null,
  probeKind: null,
  lastProbeAt: null,
  lastProbeMs: null,
  restartCount: 0,
  restartGaveUpAt: null,
  version: null,
  endpoint: null,
});

test.describe("health 만 통과한 것은 ready 가 아니다", () => {
  test("기능 프로브가 있는데 아직 안 돌았으면 starting", () => {
    const decision = decideState({
      alive: true,
      health: probe("pdf2bpmn", "health", "pass", "200"),
      capability: null,
      hasCapabilityProbe: true,
    });
    expect(decision.state).toBe("starting");
    expect(decision.probeKind).toBe("health");
  });

  test("**healthz 200 + 자격증명 거부 = degraded** — 이 스펙의 이유다", () => {
    const decision = decideState({
      alive: true,
      health: probe("pdf2bpmn", "health", "pass", "200"),
      capability: probe("pdf2bpmn", "capability", "fail", "LLM 자격증명이 거부됨 (401)"),
      hasCapabilityProbe: true,
    });
    // ready 면 화면이 "쓸 수 있다"고 거짓말한다. failed 면 살아 있는 서비스를 다 막는다.
    expect(decision.state).toBe("degraded");
    expect(decision.probeKind).toBe("capability");
    expect(decision.stateReason).toContain("401");
  });

  test("기능 프로브까지 통과하면 ready — 그리고 무엇으로 통과했는지 남는다", () => {
    const decision = decideState({
      alive: true,
      health: probe("graph", "health", "pass", "bolt open"),
      capability: probe("graph", "capability", "pass", "graph 'robo' 조회됨"),
      hasCapabilityProbe: true,
    });
    expect(decision.state).toBe("ready");
    expect(decision.probeKind).toBe("capability");
  });

  test("기능 프로브가 없는 서비스는 health 로 ready 가 되지만 probeKind 에 그 사실이 남는다", () => {
    const decision = decideState({
      alive: true,
      health: probe("fabric", "health", "pass", "200"),
      capability: null,
      hasCapabilityProbe: false,
    });
    expect(decision.state).toBe("ready");
    expect(decision.probeKind).toBe("health");
  });
});

test.describe("error 를 fail 로 뭉치지 않는다", () => {
  test("기능을 못 쟀으면 degraded 가 아니라 starting", () => {
    const decision = decideState({
      alive: true,
      health: probe("analyzer", "health", "pass", "200"),
      capability: probe("analyzer", "capability", "error", "ROBO_LLM_CONFIG 가 없어 재지 못함"),
      hasCapabilityProbe: true,
    });
    // 못 쟀는데 degraded 로 부르면 **모르는 것을 아는 척하는 것**이고, 사용자가
    // 멀쩡한 서비스를 고치려 든다.
    expect(decision.state).toBe("starting");
    expect(decision.stateReason).toContain("확인하지 못했습니다");
  });

  test("health 를 못 쟀으면 failed 가 아니라 starting", () => {
    const decision = decideState({
      alive: null,
      health: probe("catalog", "health", "error", "ECONNREFUSED"),
      capability: null,
      hasCapabilityProbe: false,
    });
    expect(decision.state).toBe("starting");
  });

  test("물리적으로 죽은 것은 프로브보다 강한 사실이다", () => {
    const decision = decideState({
      alive: false,
      health: probe("parser", "health", "pass", "200"),
      capability: probe("parser", "capability", "pass", "/data 쓰기 가능"),
      hasCapabilityProbe: true,
    });
    expect(decision.state).toBe("failed");
  });
});

test.describe("되살리기 한계", () => {
  test("한계에 닿으면 stopped 이고 사람이 할 일이 문구에 있다", () => {
    const decision = applyRestartBudget(
      { state: "failed", stateReason: "죽었습니다.", probeKind: "health" },
      3,
      3,
    );
    expect(decision.state).toBe("stopped");
    expect(decision.stateReason).toContain("직접 다시 시도");
  });

  test("한계 전에는 failed 그대로", () => {
    const decision = applyRestartBudget(
      { state: "failed", stateReason: "죽었습니다.", probeKind: "health" },
      1,
      3,
    );
    expect(decision.state).toBe("failed");
  });
});

test.describe("기능 상태는 서비스에서 파생된다", () => {
  const all = (state: ServiceState) =>
    (["graph", "architect", "analyzer", "catalog", "parser", "gateway", "pdf2bpmn"] as ManagedServiceId[])
      .map((id) => service(id, state));

  test("전부 ready 면 전부 available", () => {
    const capabilities = deriveCapabilities(all("ready"));
    expect(capabilities.every((capability) => capability.state === "available")).toBe(true);
    expect(capabilities.every((capability) => capability.blockedReason === null)).toBe(true);
  });

  test("pdf2bpmn 만 degraded 면 **BPMN 생성만** degraded — 나머지는 계속 쓸 수 있다", () => {
    const services = all("ready").map((s) =>
      s.id === "pdf2bpmn" ? { ...s, state: "degraded" as ServiceState } : s,
    );
    const capabilities = deriveCapabilities(services);
    const bpmn = capabilities.find((capability) => capability.id === "bpmn-generation")!;
    expect(bpmn.state).toBe("degraded");
    expect(bpmn.blockedReason).not.toBeNull();
    // **막는 것만 재면 전부 막아 놓고도 통과한다.** 반대쪽을 같이 본다.
    const design = capabilities.find((capability) => capability.id === "design")!;
    expect(design.state).toBe("available");
    const analysis = capabilities.find((capability) => capability.id === "legacy-analysis")!;
    expect(analysis.state).toBe("available");
  });

  test("analyzer 가 죽으면 레거시 탐색만 못 쓴다", () => {
    const services = all("ready").map((s) =>
      s.id === "analyzer" ? { ...s, state: "failed" as ServiceState } : s,
    );
    const capabilities = deriveCapabilities(services);
    expect(capabilities.find((c) => c.id === "legacy-analysis")!.state).toBe("unavailable");
    expect(capabilities.find((c) => c.id === "design")!.state).toBe("available");
  });

  test("기동 중과 실패를 **다른 문구로** 말한다", () => {
    const starting = deriveCapabilities(
      all("ready").map((s) => (s.id === "graph" ? { ...s, state: "starting" as ServiceState } : s)),
    ).find((c) => c.id === "design")!;
    const failed = deriveCapabilities(
      all("ready").map((s) => (s.id === "graph" ? { ...s, state: "failed" as ServiceState } : s)),
    ).find((c) => c.id === "design")!;
    expect(starting.state).toBe("unavailable");
    expect(failed.state).toBe("unavailable");
    // 같은 상태여도 사용자가 할 일이 다르다. 같은 문구를 주면 잘못된 조치를 한다.
    expect(starting.blockedReason).not.toBe(failed.blockedReason);
    expect(starting.blockedReason).toContain("기동 중");
  });

  test("상태를 아예 모르는 서비스가 있으면 통과로 치지 않는다", () => {
    // graph 를 목록에서 빼 버린다 — 재지 못한 것이다.
    const services = all("ready").filter((s) => s.id !== "graph");
    const design = deriveCapabilities(services).find((c) => c.id === "design")!;
    expect(design.state).toBe("unavailable");
    expect(design.blockedReason).toContain("확인하지 못한");
  });
});

test.describe("하위 호환 status 는 파생된다", () => {
  test("architect ready + 나머지 정상 → ready", () => {
    const services = [service("architect", "ready"), service("graph", "ready")];
    expect(deriveLegacyStatus(services)).toBe("ready");
  });

  test("architect 가 아직인데 컨테이너는 떴으면 starting-backend", () => {
    const services = [service("architect", "starting"), service("graph", "ready")];
    expect(deriveLegacyStatus(services)).toBe("starting-backend");
  });

  test("컨테이너가 아직이면 starting-db", () => {
    const services = [service("architect", "starting"), service("graph", "starting")];
    expect(deriveLegacyStatus(services)).toBe("starting-db");
  });

  test("architect 가 죽으면 fatal", () => {
    expect(deriveLegacyStatus([service("architect", "failed")])).toBe("fatal");
  });
});

test.describe("무엇이 바뀌었는지만 알린다", () => {
  test("안 바뀌면 빈 목록 — 같은 값을 5초마다 밀지 않는다", () => {
    const before = [service("graph", "ready"), service("analyzer", "ready")];
    expect(changedServiceIds(before, before.map((s) => ({ ...s })))).toEqual([]);
  });

  test("바뀐 것만 나온다", () => {
    const before = [service("graph", "ready"), service("analyzer", "ready")];
    const after = [service("graph", "ready"), service("analyzer", "degraded")];
    expect(changedServiceIds(before, after)).toEqual(["analyzer"]);
  });

  test("이유만 바뀌어도 알린다 — 같은 상태라도 사용자가 할 일이 달라진다", () => {
    const before = [{ ...service("graph", "degraded"), stateReason: "A" }];
    const after = [{ ...service("graph", "degraded"), stateReason: "B" }];
    expect(changedServiceIds(before, after)).toEqual(["graph"]);
  });
});
