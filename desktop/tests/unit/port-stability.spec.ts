/**
 * **포트가 기동마다 바뀌지 않는다** (2026-09-30).
 *
 * ## 조용한 고장이었다
 *
 * 포트는 `docker-state.json` 에 저장되고 다음 기동에 물려받도록 설계돼 있었다.
 * 그런데 그 상태를 읽는 자리가 이렇게 검사했다 —
 *
 *     const ports = Object.values(parsed.ports);
 *     if (ports.length !== 6 || …) return null;
 *
 * **포트는 7개다**(`graphPg` 가 나중에 늘었다). 그래서 이 함수는 **언제나 null 을
 * 돌려주었고**, 저장된 포트는 쓰인 적이 없다. 기동마다 전부 새로 뽑혔다.
 *
 * 앱은 잘 뜨고 포트가 바뀌는 것은 화면에 안 나오므로 아무도 몰랐다. 드러난 경로는
 * **Figma 플러그인**이다: 플러그인에 손으로 적어 둔 `http://127.0.0.1:50065` 가
 * 재기동마다 죽은 주소가 되고, 화면에는 원인을 알 수 없는 `Failed to fetch` 만 떴다.
 * 사내망이면 방화벽 규칙도 같이 무효가 된다.
 *
 * ## 여기서 재는 것
 *
 *   ① 저장된 7개를 **그대로** 물려받는다 — 개수를 세지 않는다
 *   ② releaseId 가 달라도 물려받는다 — 포트는 릴리스의 속성이 아니다
 *   ③ 빠진 키만 새로 뽑을 수 있게, 없는 것은 없다고 답한다
 *   ④ 못 쓰는 값(범위 밖·정수 아님·중복)은 버린다
 *
 * ①이 핵심이다. 키 개수를 세는 검사는 포트가 또 늘면 같은 방식으로 죽는다 —
 * 그래서 이 검사는 `PORT_KEYS` 를 소스에서 가져와 쓴다.
 */

import { expect, test } from "@playwright/test";

import { PORT_KEYS, reusablePorts } from "../../src/main/docker-stack";

function saved(ports: Record<string, unknown>, extra: Record<string, unknown> = {}) {
  return { schemaVersion: 5, releaseId: "0.1.0-w1-a1-s1", ports, ...extra };
}

/** 키마다 서로 다른 포트를 붙인 온전한 파일. */
function everyPort(): Record<string, number> {
  const out: Record<string, number> = {};
  PORT_KEYS.forEach((key, i) => {
    out[key] = 59000 + i;
  });
  return out;
}

test.describe("저장된 포트를 물려받는다", () => {
  test("키를 다 채운 파일은 그대로 돌려준다", () => {
    const ports = everyPort();
    const got = reusablePorts(saved(ports));
    expect(Object.keys(got).sort()).toEqual([...PORT_KEYS].sort());
    for (const key of PORT_KEYS) expect(got[key]).toBe(ports[key]);
  });

  test("포트 개수가 늘어도 깨지지 않는다", () => {
    // 개수를 세던 옛 코드가 죽은 자리다. 키를 하나 더 붙여도 알던 것은 다 살아야 한다.
    const got = reusablePorts(saved({ ...everyPort(), somethingNew: 59100 }));
    expect(Object.keys(got).sort()).toEqual([...PORT_KEYS].sort());
  });

  test("releaseId 가 달라도 물려받는다 — 업그레이드가 주소를 바꾸지 않는다", () => {
    const got = reusablePorts(saved(everyPort(), { releaseId: "0.1.0-w9-a9-s9" }));
    expect(Object.keys(got)).toHaveLength(PORT_KEYS.length);
  });

  test("schemaVersion 이 달라도 포트는 포트다", () => {
    const got = reusablePorts(saved(everyPort(), { schemaVersion: 1 }));
    expect(Object.keys(got)).toHaveLength(PORT_KEYS.length);
  });
});

test.describe("못 쓰는 값은 버린다", () => {
  test("빠진 키는 없다고 답한다 — 부르는 쪽이 그것만 새로 뽑는다", () => {
    const ports = everyPort();
    delete ports.architect;
    const got = reusablePorts(saved(ports));
    expect(got.architect).toBeUndefined();
    expect(got.graph).toBe(ports.graph);
  });

  test("범위 밖·정수 아님·문자열을 버린다", () => {
    const got = reusablePorts(saved({
      ...everyPort(), graph: 80, graphPg: 70000, analyzer: 59001.5, gateway: "59002",
    }));
    for (const key of ["graph", "graphPg", "analyzer", "gateway"]) {
      expect(got[key as keyof typeof got], `${key} 를 물려받았다`).toBeUndefined();
    }
    expect(got.architect).toBeDefined();
  });

  test("같은 포트가 두 서비스에 적혀 있으면 둘째를 버린다", () => {
    // 하나는 반드시 못 뜬다. 물려받으면 그 고장을 그대로 재현한다.
    const got = reusablePorts(saved({ ...everyPort(), gateway: 59000 }));
    expect(got.graph).toBe(59000);
    expect(got.gateway).toBeUndefined();
  });

  test("이상한 입력에 던지지 않는다", () => {
    for (const bad of [null, undefined, 3, "x", {}, { ports: null }, { ports: 7 }, []]) {
      expect(reusablePorts(bad)).toEqual({});
    }
  });
});
