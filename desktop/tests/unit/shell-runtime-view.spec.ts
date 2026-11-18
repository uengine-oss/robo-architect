/**
 * 홈(셸)이 ready **이후의** 서비스 상태를 읽는 법 (라이트 지적 A-3 ①).
 *
 * 감독은 ready 뒤에도 5초마다 재서 `runtime:onStatus` 로 민다. 홈은 그 값을 받아
 *   - 내려가면 상태 줄·경고 띠로 말하고
 *   - 회복하면 그 표시를 거두고
 *   - 컨테이너 하나 빠진 것을 **기동 화면으로 되돌아가는 것**으로 보이지 않는다
 * 판정은 main 이 했다 — 여기서는 그 값을 홈의 말로 옮기는 순수 함수만 잰다.
 */

import { createRequire } from "node:module";
import path from "node:path";

import { expect, test } from "@playwright/test";

const load = createRequire(__filename);
const view = load(path.resolve(__dirname, "../../resources/shell/runtime-view.js")) as {
  homeReady(status: string, services: unknown[], everReady: boolean): boolean;
  summarize(services: unknown[]): {
    tone: "ok" | "warn" | "bad";
    graphDown: boolean;
    names: string[];
    reason: string;
    headline: string;
  };
};

const svc = (id: string, state: string, extra: Record<string, unknown> = {}) => ({
  id,
  state,
  displayName: id === "graph" ? "그래프 DB" : id,
  stateReason: null,
  ...extra,
});

const allReady = [svc("architect", "ready"), svc("graph", "ready"), svc("fabric", "ready")];

test("전부 ready 면 아무것도 안 띄운다", () => {
  const sum = view.summarize(allReady);
  expect(sum.tone).toBe("ok");
  expect(sum.headline).toBe("");
  expect(sum.graphDown).toBe(false);
});

test("ready 뒤에 그래프 컨테이너가 내려가면 bad 이고 이름·이유를 말한다", () => {
  const down = [
    svc("architect", "ready"),
    svc("graph", "failed", { stateReason: "컨테이너/프로세스가 실행 중이 아닙니다." }),
    svc("fabric", "ready"),
  ];
  const sum = view.summarize(down);
  expect(sum.tone).toBe("bad");
  expect(sum.graphDown).toBe(true);
  expect(sum.names).toEqual(["그래프 DB"]);
  expect(sum.reason).toContain("실행 중이 아닙니다");
  expect(sum.headline).toContain("그래프 DB");
});

test("degraded 만 있으면 warn — 고장과 다른 말로", () => {
  const sum = view.summarize([svc("architect", "ready"), svc("fabric", "degraded")]);
  expect(sum.tone).toBe("warn");
  expect(sum.graphDown).toBe(false);
});

test("starting·pending 은 문제가 아니다 — 모르는 것을 고장이라 하지 않는다", () => {
  expect(view.summarize([svc("graph", "starting"), svc("fabric", "pending")]).tone).toBe("ok");
});

test("회복하면 표시가 거둬진다", () => {
  const before = view.summarize([svc("architect", "ready"), svc("graph", "failed")]);
  const after = view.summarize(allReady);
  expect(before.tone).toBe("bad");
  expect(after.tone).toBe("ok");
});

test.describe("homeReady — 컨테이너 하나 빠진 것은 기동 화면이 아니다", () => {
  test("status ready 면 준비됨", () => {
    expect(view.homeReady("ready", [], false)).toBe(true);
  });

  test("ready 를 본 적 없으면 파생 starting-db 는 기동 중", () => {
    expect(view.homeReady("starting-db", allReady, false)).toBe(false);
  });

  test("ready 를 본 뒤 컨테이너가 빠져 파생 status 가 starting-db 여도 백엔드가 살아 있으면 준비됨", () => {
    const down = [svc("architect", "ready"), svc("graph", "failed")];
    expect(view.homeReady("starting-db", down, true)).toBe(true);
  });

  test("백엔드가 죽으면 준비가 아니다", () => {
    expect(view.homeReady("fatal", [svc("architect", "failed")], true)).toBe(false);
    expect(view.homeReady("backend-crashed", allReady, true)).toBe(false);
    expect(view.homeReady("starting-db", [svc("architect", "failed")], true)).toBe(false);
  });
});
