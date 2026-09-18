/**
 * 감독 상태를 모으는 곳 (spec 058 T034).
 *
 * ## 여기서 재는 것
 *
 * **모은 값이 파생값을 오염시키지 않는가.** `capabilities` 와 하위 호환 `status` 는
 * 저장하지 않고 매번 계산한다 — 두 곳에 같은 사실을 두면 어긋난다.
 *
 * 그리고 **가드가 서비스 상태와 독립인가.** 전부 ready 여도 두 graph 가 같으면
 * 분석을 열면 안 된다.
 */

import { expect, test } from "@playwright/test";

import { RuntimeRegistry } from "../../src/main/runtime-state";
import type { GraphGuard, ManagedServiceId, ProbeResult } from "../../src/shared/runtime-contract";

const probe = (
  serviceId: ManagedServiceId,
  kind: "health" | "capability",
  outcome: ProbeResult["outcome"],
  detail = "",
): ProbeResult => ({ serviceId, kind, outcome, detail, durationMs: 7 });

const ALL: ManagedServiceId[] = [
  "graph", "analyzer", "catalog", "parser", "gateway", "pdf2bpmn", "architect",
];

function readyRegistry(): RuntimeRegistry {
  const registry = new RuntimeRegistry();
  registry.register(ALL);
  for (const id of ALL) {
    registry.applyProbe(id, {
      alive: true,
      health: probe(id, "health", "pass", "200"),
      capability: probe(id, "capability", "pass", "ok"),
      hasCapabilityProbe: true,
    });
  }
  return registry;
}

test.describe("등록 전에는 아무것도 주장하지 않는다", () => {
  test("빈 등록이면 서비스도 기능도 비어 있다", () => {
    const snapshot = new RuntimeRegistry().snapshot();
    expect(snapshot.services).toEqual([]);
    // **기능을 파생하지만 전부 unavailable 이다** — 상태를 모르니 열 수 없다.
    expect(snapshot.capabilities.every((c) => c.state === "unavailable")).toBe(true);
    expect(snapshot.capabilities[0]?.blockedReason).toContain("확인하지 못한");
  });

  test("dockerAvailable 은 못 쟀을 때 null 이다 — false 가 아니다", () => {
    const snapshot = new RuntimeRegistry().snapshot();
    // false 로 두면 기동 초반에 "도커를 설치하세요"가 잘못 뜬다.
    expect(snapshot.dockerAvailable).toBeNull();
  });

  test("등록만 하면 pending 이고 아직 판정이 없다", () => {
    const registry = new RuntimeRegistry();
    registry.register(["graph"]);
    const service = registry.snapshot().services[0]!;
    expect(service.state).toBe("pending");
    expect(service.probeKind).toBeNull();
    expect(service.lastProbeAt).toBeNull();
  });
});

test.describe("프로브 결과를 상태로 옮긴다", () => {
  test("기능까지 통과하면 ready 이고 **무엇으로** 판정했는지 남는다", () => {
    const snapshot = readyRegistry().snapshot();
    const graph = snapshot.services.find((s) => s.id === "graph")!;
    expect(graph.state).toBe("ready");
    expect(graph.probeKind).toBe("capability");
    expect(graph.lastProbeMs).toBe(7);
    expect(graph.lastProbeAt).not.toBeNull();
  });

  test("healthz 는 통과하는데 자격증명이 거부되면 degraded", () => {
    const registry = readyRegistry();
    registry.applyProbe("pdf2bpmn", {
      alive: true,
      health: probe("pdf2bpmn", "health", "pass", "200"),
      capability: probe("pdf2bpmn", "capability", "fail", "LLM 자격증명이 거부됨 (401)"),
      hasCapabilityProbe: true,
    });
    const snapshot = registry.snapshot();
    expect(snapshot.services.find((s) => s.id === "pdf2bpmn")!.state).toBe("degraded");
    // **BPMN 생성만** 막힌다. 나머지는 계속 쓸 수 있다.
    expect(snapshot.capabilities.find((c) => c.id === "bpmn-generation")!.state).toBe("degraded");
    expect(snapshot.capabilities.find((c) => c.id === "design")!.state).toBe("available");
  });

  test("endpoint·version 은 프로브가 덮지 않는다", () => {
    const registry = readyRegistry();
    registry.setEndpoint("graph", "bolt://127.0.0.1:38687", "local-0917");
    registry.applyProbe("graph", {
      alive: true,
      health: probe("graph", "health", "pass"),
      capability: probe("graph", "capability", "pass"),
      hasCapabilityProbe: true,
    });
    const graph = registry.snapshot().services.find((s) => s.id === "graph")!;
    expect(graph.endpoint).toBe("bolt://127.0.0.1:38687");
    expect(graph.version).toBe("local-0917");
  });
});

test.describe("가드는 서비스 상태와 독립이다 (T034)", () => {
  const guard = (over: Partial<GraphGuard>): GraphGuard => ({
    designGraph: "robo",
    analysisGraph: "analyzer_run",
    separated: true,
    evidence: "content",
    reason: null,
    ...over,
  });

  test("전부 ready 여도 분리가 깨졌으면 분석이 안 열린다", () => {
    const registry = readyRegistry();
    registry.setGraphGuard(guard({ separated: false, reason: "두 이름이 같습니다('robo')." }));
    const snapshot = registry.snapshot();
    expect(snapshot.services.every((s) => s.state === "ready")).toBe(true);
    expect(snapshot.capabilities.find((c) => c.id === "legacy-analysis")!.state).toBe("unavailable");
    // 파생값이므로 스냅샷마다 다시 계산된다 — 가드를 고치면 곧바로 반영된다.
    registry.setGraphGuard(guard({}));
    expect(
      registry.snapshot().capabilities.find((c) => c.id === "legacy-analysis")!.state,
    ).toBe("available");
  });

  test("하위 호환 status 는 저장하지 않고 파생된다", () => {
    const registry = readyRegistry();
    expect(registry.snapshot().legacyStatus).toBe("ready");
    registry.applyProbe("architect", {
      alive: false,
      health: null,
      capability: null,
      hasCapabilityProbe: false,
    });
    expect(registry.snapshot().legacyStatus).toBe("fatal");
  });
});

test.describe("바뀐 것만 알린다", () => {
  test("같은 프로브를 다시 넣으면 빈 목록", () => {
    const registry = readyRegistry();
    const before = registry.snapshot().services;
    registry.applyProbe("graph", {
      alive: true,
      health: probe("graph", "health", "pass", "200"),
      capability: probe("graph", "capability", "pass", "ok"),
      hasCapabilityProbe: true,
    });
    expect(registry.diff(before)).toEqual([]);
  });

  test("상태가 바뀌면 그것만 나온다", () => {
    const registry = readyRegistry();
    const before = registry.snapshot().services;
    registry.applyProbe("analyzer", {
      alive: false,
      health: null,
      capability: null,
      hasCapabilityProbe: true,
    });
    expect(registry.diff(before)).toEqual(["analyzer"]);
  });
});

test.describe("되살리기 기록", () => {
  test("시도 횟수와 포기 시각을 남긴다", () => {
    const registry = readyRegistry();
    registry.noteRestart("analyzer", false);
    registry.noteRestart("analyzer", true);
    const analyzer = registry.snapshot().services.find((s) => s.id === "analyzer")!;
    expect(analyzer.restartCount).toBe(2);
    expect(analyzer.restartGaveUpAt).not.toBeNull();
  });
});
