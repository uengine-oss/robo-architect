/**
 * 옛 두 채널이 안 깨졌는가 (spec 058 T020).
 *
 * ## 왜 이 검사가 있나
 *
 * 058 은 `RuntimeState` 를 **서비스 배열로 넓혔다.** 그러면서 지키기로 한 것이
 * 하나다 — **기존 필드를 지우지도, 뜻을 바꾸지도 않는다.** 두 채널을 지금 쓰는
 * 자리가 있기 때문이다.
 *
 * ```
 * app:getRuntimeState    ClaudeCodeTerminal.vue · workspace.api.js ·
 *                        FigmaBindingModal.vue — 셋 다 **backendPort** 로
 *                        백엔드 주소를 만든다. 이 필드가 없으면 화면이
 *                        "Analyzer 로드 중…" 에서 멎는다(9/29 에 본 그 모양)
 * app:onBackendStatus    runtime.store.js 가 058 전부터 듣던 유일한 구독
 * ```
 *
 * 깨지는 방식이 조용하다 — 필드가 하나 빠지면 타입은 `undefined` 로 통과하고,
 * 증상은 **한참 뒤 다른 화면**에서 난다. 그래서 두 자리를 **코드에서 견준다.**
 *
 * ## 무엇을 근거로 하는가
 *
 * 타입은 런타임에 사라지므로 `RuntimeState` 를 객체로 검사할 수 없다. 그래서
 * 소스를 읽어 **`buildRuntimeState()` 가 실제로 싣는 키**와 **푸시하는 필드**를
 * 센다. 적재 쪽에서 쓰는 방식과 같다(`test_replace_covers_every_label.py`).
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { RuntimeRegistry } from "../../src/main/runtime-state";
import type { ManagedServiceId, ProbeResult } from "../../src/shared/runtime-contract";

const SRC = join(__dirname, "..", "..", "src");
const indexSource = readFileSync(join(SRC, "main", "index.ts"), "utf8");
const contractSource = readFileSync(join(SRC, "shared", "ipc-contract.ts"), "utf8");

/** 058 **전부터** 있던 필수 필드. 하나라도 빠지면 옛 렌더러가 조용히 깨진다. */
const LEGACY_FIELDS = [
  "appVersion",
  "backendPort",
  "boltPort",
  "backendPid",
  "neo4jPid",
  "status",
  "dataSource",
  "dataDir",
  "updateState",
];

/** `buildRuntimeState()` 의 본문만 떼어 본다 — 다른 함수의 같은 이름에 속지 않게. */
function buildRuntimeStateBody(): string {
  const start = indexSource.indexOf("function buildRuntimeState()");
  expect(start, "buildRuntimeState() 가 index.ts 에 없다").toBeGreaterThan(-1);
  const end = indexSource.indexOf("\n}", start);
  expect(end, "buildRuntimeState() 의 끝을 못 찾았다").toBeGreaterThan(start);
  return indexSource.slice(start, end);
}

test("app:getRuntimeState 핸들러가 그대로 등록돼 있다", () => {
  expect(indexSource).toContain('registerHandler("app:getRuntimeState"');
  expect(contractSource).toContain('"app:getRuntimeState"');
});

test("옛 필수 필드가 **하나도 빠지지 않았다**", () => {
  const body = buildRuntimeStateBody();
  const missing = LEGACY_FIELDS.filter((field) => !new RegExp(`\\b${field}\\s*:`).test(body));
  expect(missing, `buildRuntimeState() 가 안 싣는 옛 필드: ${missing.join(", ")}`).toEqual([]);
});

test("058 신규 필드는 **옛 필드를 밀어내지 않고** 더해진다", () => {
  const body = buildRuntimeStateBody();
  // 신규 필드는 base 를 펼친 뒤에 붙는다. `...base` 가 없으면 옛 필드가 사라진다.
  expect(body).toContain("...base");
  for (const field of ["services", "capabilities", "graphGuard"]) {
    expect(body, `058 필드 ${field} 가 안 실린다`).toContain(`${field}:`);
  }
});

test("app:onBackendStatus 가 **status·backendPort·boltPort** 를 그대로 싣는다", () => {
  expect(contractSource).toContain('"app:onBackendStatus"');
  const start = contractSource.indexOf("interface BackendStatusEvent");
  const body = contractSource.slice(start, contractSource.indexOf("}", start));
  for (const field of ["status", "backendPort", "boltPort"]) {
    expect(body, `BackendStatusEvent 에 ${field} 가 없다`).toContain(field);
  }
});

test("`status` 는 **파생값으로 남아** 옛 뜻을 유지한다", () => {
  // 감독이 붙어도 `status` 가 사라지면 안 되고, 모르는 값을 돌려줘도 안 된다 —
  // 옛 렌더러는 이 여덟 말만 안다.
  const known = new Set([
    "initializing",
    "starting-db",
    "starting-backend",
    "ready",
    "backend-crashed",
    "db-crashed",
    "restarting",
    "fatal",
  ]);

  const ids: ManagedServiceId[] = ["graph", "architect", "analyzer"];
  const probe = (
    serviceId: ManagedServiceId,
    kind: "health" | "capability",
    outcome: ProbeResult["outcome"],
  ): ProbeResult => ({ serviceId, kind, outcome, detail: "", durationMs: 1 });

  // 아무것도 안 쟨 상태 · 전부 ready · 하나 실패 — 세 경우 모두 옛 말이어야 한다.
  const registry = new RuntimeRegistry();
  registry.register(ids);
  expect(known.has(registry.snapshot().legacyStatus)).toBe(true);

  for (const id of ids) {
    registry.applyProbe(id, { alive: true, probes: [probe(id, "health", "pass")] });
  }
  expect(known.has(registry.snapshot().legacyStatus)).toBe(true);

  registry.applyProbe("analyzer", { alive: false, probes: [probe("analyzer", "health", "fail")] });
  expect(known.has(registry.snapshot().legacyStatus)).toBe(true);
});
