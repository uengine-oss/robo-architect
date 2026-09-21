/**
 * 껐다 켜도, OS 를 재시작해도 같게 동작하는가 (spec 058 T038~T041 · US3).
 *
 * ## 이 검사가 있는 이유 — 2026-09-18 에 실제로 겪었다
 *
 * 기계가 재부팅됐다. Docker Desktop 을 켜자 `restart: unless-stopped` 인 것들이 **앱보다
 * 먼저** 스스로 돌아왔다 — 9개 중 8개. 그 상태에서 앱이 "안 떠 있으니 띄운다"로
 * 움직이면 중복이 생긴다.
 *
 * 그리고 **돌아오지 않은 것도 있었다.**
 *
 * ```
 * exit 127          사라진 호스트 경로를 바인드 마운트하고 있었다
 * 재시작 정책 없음   `docker run` 으로 손으로 띄운 것
 * ```
 *
 * 그래서 "라벨이 붙은 컨테이너가 있다"와 "그게 돌고 있다"는 다른 사실이다.
 */

import { expect, test } from "@playwright/test";

import { planAdoption, type OwnedContainer } from "../../src/main/stack-ownership";
import { reclaimBlockedPorts } from "../../src/main/docker-stack";
import { RuntimeRegistry } from "../../src/main/runtime-state";
import type { DockerStackPorts } from "../../src/main/docker-stack";
import type { ManagedServiceId } from "../../src/shared/runtime-contract";

const COMPONENTS: ReadonlyArray<{ id: ManagedServiceId; component: string }> = [
  { id: "graph", component: "graph-bolt" },
  { id: "analyzer", component: "analyzer" },
  { id: "gateway", component: "gateway" },
];

const container = (component: string, over: Partial<OwnedContainer> = {}): OwnedContainer => ({
  id: `id-${component}`,
  name: `robo-${component}-1`,
  component,
  running: true,
  health: "healthy",
  exitCode: 0,
  image: "uengine/x:1",
  ...over,
});

test.describe("이미 떠 있는 것을 이어받는다 (T039)", () => {
  test("전부 돌고 있으면 compose 를 부르지 않는다", () => {
    const plan = planAdoption(
      [container("graph-bolt"), container("analyzer"), container("gateway")],
      COMPONENTS,
    );
    expect(plan.adopt).toHaveLength(3);
    expect(plan.needsUp).toBe(false);
    expect(plan.unknown).toBe(false);
  });

  test("멈춰 있는 것은 이어받지 않고 다시 올린다 — exit 127 을 겪었다", () => {
    const plan = planAdoption(
      [
        container("graph-bolt"),
        container("analyzer", { running: false, exitCode: 127 }),
        container("gateway"),
      ],
      COMPONENTS,
    );
    expect(plan.adopt.map((c) => c.component).sort()).toEqual(["gateway", "graph-bolt"]);
    expect(plan.restart.map((c) => c.component)).toEqual(["analyzer"]);
    expect(plan.needsUp).toBe(true);
    expect(plan.reason).toContain("이어받습니다");
    expect(plan.reason).toContain("다시 올립니다");
  });

  test("컨테이너가 없는 서비스는 새로 띄운다", () => {
    const plan = planAdoption([container("graph-bolt")], COMPONENTS);
    expect(plan.missing.sort()).toEqual(["analyzer", "gateway"]);
    expect(plan.needsUp).toBe(true);
  });

  test("**못 물어봤으면 띄우지도 이어받지도 않는다**", () => {
    const plan = planAdoption(null, COMPONENTS);
    expect(plan.unknown).toBe(true);
    // 여기서 "없는 것 같으니 띄우자"로 가면 중복이 생긴다.
    expect(plan.needsUp).toBe(false);
    expect(plan.adopt).toHaveLength(0);
    expect(plan.reason).toContain("확인하지 못했");
  });

  test("이름이 겹치는 남의 컨테이너는 목록에 애초에 안 들어온다", () => {
    // 목록은 `label=org.uengine.robo.release=<id>` 로 걸러서 온다. 여기서는 그
    // 계약을 문서화한다 — 같은 component 이름이라도 라벨이 없으면 애초에 안 온다.
    const plan = planAdoption([container("analyzer")], COMPONENTS);
    expect(plan.adopt.map((c) => c.component)).toEqual(["analyzer"]);
    expect(plan.missing.sort()).toEqual(["gateway", "graph"]);
  });

  test("health 는 이어받기 판단에 쓰지 않는다", () => {
    // `unhealthy` 인데 돌고 있으면 이어받는다 — 준비 여부는 기능 프로브가 따로 잰다.
    const plan = planAdoption(
      [
        container("graph-bolt", { health: "unhealthy" }),
        container("analyzer", { health: "starting" }),
        container("gateway", { health: "none" }),
      ],
      COMPONENTS,
    );
    expect(plan.adopt).toHaveLength(3);
    expect(plan.needsUp).toBe(false);
  });
});

test.describe("묵은 포트를 되잡는다 (T040)", () => {
  const ports: DockerStackPorts = {
    graph: 38687,
    graphPg: 35432,
    analyzer: 38502,
    gateway: 38000,
    architect: 38001,
    pdf2bpmn: 38611,
  };

  test("전부 비어 있으면 그대로 쓴다 — 재부팅마다 포트가 바뀌면 안 된다", async () => {
    const result = await reclaimBlockedPorts(ports, {
      isFree: async () => true,
      pick: async () => 49999,
    });
    expect(result.changed).toEqual([]);
    expect(result.ports).toEqual(ports);
  });

  test("막힌 것만 바꾸고 **무엇이 바뀌었는지 알린다**", async () => {
    const result = await reclaimBlockedPorts(ports, {
      isFree: async (port) => port !== 38000,
      pick: async () => 49001,
    });
    // 조용히 바꾸면 옛 포트를 쥔 외부 도구가 "갑자기 안 된다"가 된다.
    expect(result.changed).toEqual([{ key: "gateway", from: 38000, to: 49001 }]);
    expect(result.ports.gateway).toBe(49001);
    expect(result.ports.graph).toBe(38687);
  });

  test("우리가 쥔 포트는 막혀 있어도 그대로 쓴다", async () => {
    // 이어받는 경우 우리 컨테이너가 그 포트를 쥐고 있다 — 그건 정상이다.
    const result = await reclaimBlockedPorts(ports, {
      heldByUs: [38687, 38000],
      isFree: async () => false,
      pick: async () => 49002,
    });
    expect(result.ports.graph).toBe(38687);
    expect(result.ports.gateway).toBe(38000);
    // 나머지는 막혀 있으니 바뀐다.
    expect(result.changed.map((c) => c.key).sort()).toEqual([
      "analyzer", "architect", "graphPg", "pdf2bpmn",
    ]);
  });

  test("새로 뽑은 포트끼리 겹치지 않는다", async () => {
    let next = 49010;
    const result = await reclaimBlockedPorts(ports, {
      isFree: async () => false,
      // 같은 번호를 두 번 주려 드는 뽑기. 겹치면 두 서비스가 같은 포트를 잡는다.
      pick: async () => (next++ % 2 === 0 ? 49100 : next),
    });
    const assigned = Object.values(result.ports);
    expect(new Set(assigned).size).toBe(assigned.length);
  });
});

test.describe("사용자가 내린 것은 되살리지 않는다 (T041)", () => {
  test("markStopped 는 failed 와 다르다", () => {
    const registry = new RuntimeRegistry();
    registry.register(["graph", "analyzer", "architect"]);
    registry.markStopped("graph", "사용자가 내렸습니다.");
    const graph = registry.snapshot().services.find((s) => s.id === "graph")!;
    expect(graph.state).toBe("stopped");
    expect(graph.stateReason).toContain("사용자가");
    // 무엇으로 판정했는지를 비운다 — 프로브 결과가 아니다.
    expect(graph.probeKind).toBeNull();
  });

  test("내릴 대상에서 architect 를 뺀다 — 호스트 프로세스다", () => {
    const registry = new RuntimeRegistry();
    registry.register(["graph", "analyzer", "architect"]);
    expect(registry.containerServiceIds().sort()).toEqual(["analyzer", "graph"]);
  });

  test("모르는 서비스 id 를 조용히 만들지 않는다 — 오타가 서비스가 된다", () => {
    const registry = new RuntimeRegistry();
    registry.register(["graph"]);
    expect(registry.knows("graph")).toBe(true);
    expect(registry.knows("analyzer")).toBe(false);
    registry.markStopped("analyzer", "x");
    expect(registry.snapshot().services).toHaveLength(1);
  });
});
