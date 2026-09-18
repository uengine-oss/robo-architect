/**
 * 설계 graph 와 분석 graph 분리 판정 (spec 058 T033·T034 · US2).
 *
 * ## 왜 이것이 P1 인가
 *
 * 분석은 **대상 graph 를 통째로 비우고 다시 쓴다.** 두 graph 가 같으면 첫 분석에서
 * 설계가 사라진다 — 실제로 한 번 날렸다.
 *
 * ## 여기서 특히 재는 것
 *
 * **"분리됐다"와 "분리를 증명했다"를 가르는가.** 빈 graph 로는 아무것도 증명하지
 * 못한다 — 데이터가 없으면 지워져도 티가 안 나고, 같은 저장소를 두 이름으로 가리켜도
 * 양쪽이 0 건으로 똑같이 나온다.
 */

import { expect, test } from "@playwright/test";

import { inspectNames, judgeGuard, type GraphSample } from "../../src/main/graph-guard";
import {
  deriveCapabilities,
  type GraphGuard,
  type ManagedService,
  type ManagedServiceId,
  type ServiceState,
} from "../../src/shared/runtime-contract";

const sample = (over: Partial<GraphSample> = {}): GraphSample => ({
  reachable: true,
  fingerprint: "n=0|",
  empty: true,
  ...over,
});

const service = (id: ManagedServiceId, state: ServiceState): ManagedService => ({
  id,
  owner: "app",
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

test.describe("이름만으로 막을 수 있는 것은 연결 전에 막는다", () => {
  test("두 이름이 같으면 분리가 아니다", () => {
    const guard = inspectNames({ design: "robo", analysis: "robo" })!;
    expect(guard.separated).toBe(false);
    expect(guard.reason).toContain("비우고");
  });

  test("공백 차이를 다른 이름으로 보지 않는다 — **이유까지 맞아야 한다**", () => {
    const guard = inspectNames({ design: "robo", analysis: " robo " })!;
    expect(guard.separated).toBe(false);
    // trim 을 빼도 막히기는 한다(이름 규칙이 공백을 거부하므로). 그러면 사용자는
    // "이름이 규칙에 안 맞는다"를 보고 이름을 고치려 든다 — **진짜 원인은 둘이 같은
    // 것이다.** 조치가 달라지므로 문구로 잰다.
    expect(guard.reason).toContain("같습니다");
    expect(guard.reason).not.toContain("규칙");
  });

  test("한쪽이 비어 있으면 분리가 아니다 — 폴백이 설계 graph 로 간다", () => {
    expect(inspectNames({ design: "robo", analysis: "" })!.separated).toBe(false);
    expect(inspectNames({ design: null, analysis: "analyzer_run" })!.separated).toBe(false);
  });

  test("경로 탈출 같은 이름은 거부한다 — 이름이 그대로 질의에 들어간다", () => {
    for (const bad of ["../etc", "robo;drop", "a b", "1robo"]) {
      expect(inspectNames({ design: bad, analysis: "analyzer_run" })!.separated, bad).toBe(false);
    }
  });

  test("이름이 멀쩡하면 이름만으로 결론 내지 않는다", () => {
    // `null` 은 "이름으로는 모르겠다" 다 — 실제로 조회해 봐야 한다.
    expect(inspectNames({ design: "robo", analysis: "analyzer_run" })).toBeNull();
  });
});

test.describe("빈 graph 로 증명하지 않는다", () => {
  test("둘 다 비었으면 분리는 인정하되 **증명은 아니다**", () => {
    const guard = judgeGuard(
      { design: "robo", analysis: "analyzer_run" },
      sample(),
      sample(),
    );
    // 갓 설치한 상태가 정상적으로 여기다 — 막으면 아무것도 못 한다.
    expect(guard.separated).toBe(true);
    // 그렇다고 "확인했다"고 하지 않는다.
    expect(guard.evidence).toBe("names");
    expect(guard.reason).toContain("확인하지 못");
  });

  test("양쪽에 서로 다른 내용이 있으면 **증명된다**", () => {
    const guard = judgeGuard(
      { design: "robo", analysis: "analyzer_run" },
      sample({ fingerprint: "n=3|BoundedContext:3", empty: false }),
      sample({ fingerprint: "n=7|FUNCTION:7", empty: false }),
    );
    expect(guard.separated).toBe(true);
    expect(guard.evidence).toBe("content");
    expect(guard.reason).toBeNull();
  });

  test("양쪽 내용이 완전히 같으면 **막는다** — 같은 저장소일 수 있다", () => {
    const guard = judgeGuard(
      { design: "robo", analysis: "analyzer_run" },
      sample({ fingerprint: "n=3|BoundedContext:3", empty: false }),
      sample({ fingerprint: "n=3|BoundedContext:3", empty: false }),
    );
    // 여기서 틀려서 여는 쪽의 손해가 훨씬 크다.
    expect(guard.separated).toBe(false);
    expect(guard.evidence).toBe("content");
  });

  test("한쪽만 비어 있으면 갈려 있는 것이다", () => {
    const guard = judgeGuard(
      { design: "robo", analysis: "analyzer_run" },
      sample({ fingerprint: "n=3|BoundedContext:3", empty: false }),
      sample(),
    );
    expect(guard.separated).toBe(true);
    expect(guard.evidence).toBe("content");
  });
});

test.describe("못 읽은 것을 분리로 읽지 않는다", () => {
  test("한쪽이 조회되지 않으면 막는다", () => {
    const guard = judgeGuard(
      { design: "robo", analysis: "analyzer_run" },
      sample(),
      sample({ reachable: false, error: "DatabaseNotFound" }),
    );
    // 없는 graph 를 가리키면 분석이 그걸 만들고 비운다 — 어디를 비울지 모르는 상태다.
    expect(guard.separated).toBe(false);
    expect(guard.evidence).toBeNull();
    expect(guard.reason).toContain("분석 graph 를 읽지 못했습니다");
  });

  test("양쪽 다 못 읽으면 둘 다 이유에 나온다", () => {
    const guard = judgeGuard(
      { design: "robo", analysis: "analyzer_run" },
      sample({ reachable: false, error: "AuthError" }),
      sample({ reachable: false, error: "DatabaseNotFound" }),
    );
    expect(guard.reason).toContain("설계 graph");
    expect(guard.reason).toContain("분석 graph");
  });
});

test.describe("분리가 깨지면 분석 기능이 기동 시점에 잠긴다 (T034)", () => {
  const allReady = (["graph", "analyzer", "catalog", "parser", "gateway", "architect", "pdf2bpmn"] as ManagedServiceId[])
    .map((id) => service(id, "ready"));

  const guard = (over: Partial<GraphGuard>): GraphGuard => ({
    designGraph: "robo",
    analysisGraph: "analyzer_run",
    separated: true,
    evidence: "content",
    reason: null,
    ...over,
  });

  test("서비스가 전부 ready 여도 분리가 깨졌으면 분석을 열지 않는다", () => {
    const capabilities = deriveCapabilities(
      allReady,
      guard({ separated: false, reason: "두 이름이 같습니다('robo')." }),
    );
    const analysis = capabilities.find((c) => c.id === "legacy-analysis")!;
    expect(analysis.state).toBe("unavailable");
    // 사용자가 무엇을 해야 하는지 말한다. "실패"만 말하면 조치를 못 한다.
    expect(analysis.blockedReason).toContain("지워집니다");
    expect(analysis.blockedReason).toContain("설정");
  });

  test("**분석만** 잠근다 — 설계·문서 업로드는 계속 쓸 수 있다", () => {
    const capabilities = deriveCapabilities(allReady, guard({ separated: false, reason: "x" }));
    expect(capabilities.find((c) => c.id === "design")!.state).toBe("available");
    expect(capabilities.find((c) => c.id === "document-ingestion")!.state).toBe("available");
    expect(capabilities.find((c) => c.id === "bpmn-generation")!.state).toBe("available");
  });

  test("분리가 성립하면 분석이 열린다 — 막는 것만 재면 전부 막아 놓고도 통과한다", () => {
    const capabilities = deriveCapabilities(allReady, guard({}));
    expect(capabilities.find((c) => c.id === "legacy-analysis")!.state).toBe("available");
  });

  test("증명이 'names' 뿐이어도 열린다 — 갓 설치한 상태를 막지 않는다", () => {
    const capabilities = deriveCapabilities(allReady, guard({ evidence: "names", reason: "비어 있음" }));
    expect(capabilities.find((c) => c.id === "legacy-analysis")!.state).toBe("available");
  });

  test("가드를 안 넘기면 예전대로 — 하위 호환", () => {
    const capabilities = deriveCapabilities(allReady);
    expect(capabilities.find((c) => c.id === "legacy-analysis")!.state).toBe("available");
  });
});
