/**
 * 그래프가 **어디 있는가** 의 판정 (ENT-DEPLOY-001 · 배포 모델 A).
 *
 * ## 여기서 재는 것
 *
 * 이 판정이 틀리면 나는 고장이 **조용하다.** 앱은 뜨고 화면도 뜨는데 저장소만 다른
 * 곳을 가리킨다 — 남이 만든 프로젝트가 "없는 프로젝트" 로 보이고, 오류는 안 난다.
 * 그래서 다음 셋을 실제로 불러서 잰다.
 *
 *   1. 아무것도 설정하지 않으면 **지금까지와 똑같다** (bundled · 루프백)
 *   2. central 인데 주소가 없으면 **멈춘다** — 빈 값으로 진행하지 않는다
 *   3. central 이면 Bolt 와 **Postgres 가 같이** 중앙을 가리킨다
 *
 * 3번이 이 항목의 본래 결함이다. `OG_PG_HOST` 만 루프백으로 남으면 설계는 중앙,
 * 사용자·프로젝트는 로컬이 되어 **반쪽만 공유된다.**
 */

import { expect, test } from "@playwright/test";

import {
  DEFAULT_BOLT_PORT,
  DEFAULT_PG_PORT,
  graphEndpoint,
  graphTopology,
} from "../../src/main/graph-topology";

/** 실행마다 달라지는 로컬 발행 포트. 중앙 모드에서는 쓰이지 않아야 한다. */
const LOCAL_PORTS = { graph: 49111, graphPg: 49222 };

test.describe("기본값은 bundled — 설정이 없으면 동작이 바뀌지 않는다", () => {
  test("빈 환경이면 bundled 다", () => {
    const topology = graphTopology({});
    expect(topology.mode).toBe("bundled");
    expect(topology.host).toBeNull();
  });

  test("bundled 끝점은 이 PC 의 발행 포트다", () => {
    const endpoint = graphEndpoint(LOCAL_PORTS, graphTopology({}));
    expect(endpoint).toEqual({
      host: "127.0.0.1",
      boltPort: LOCAL_PORTS.graph,
      pgPort: LOCAL_PORTS.graphPg,
    });
  });

  test("central 이 아닌 값은 bundled 로 읽는다", () => {
    for (const raw of ["", "  ", "bundled", "local", "CENTRALIZED", "0"]) {
      expect(graphTopology({ ROBO_GRAPH_MODE: raw }).mode, `ROBO_GRAPH_MODE=${raw}`).toBe("bundled");
    }
  });

  test("대소문자·공백은 무시한다 — `Central` 도 central 이다", () => {
    const topology = graphTopology({ ROBO_GRAPH_MODE: " Central ", ROBO_GRAPH_HOST: "10.10.0.5" });
    expect(topology.mode).toBe("central");
  });
});

test.describe("central 인데 주소가 없으면 멈춘다", () => {
  test("ROBO_GRAPH_HOST 가 없으면 던진다", () => {
    expect(() => graphTopology({ ROBO_GRAPH_MODE: "central" })).toThrow(
      /graph_host_missing/,
    );
  });

  test("공백만 있어도 없는 것으로 본다", () => {
    expect(() => graphTopology({ ROBO_GRAPH_MODE: "central", ROBO_GRAPH_HOST: "   " })).toThrow(
      /graph_host_missing/,
    );
  });

  test("오류 메시지가 무엇을 해야 하는지 말한다", () => {
    // 사람이 읽는 문장이다. "설정이 잘못됐습니다" 로는 아무도 고칠 수 없다.
    let message = "";
    try {
      graphTopology({ ROBO_GRAPH_MODE: "central" });
    } catch (error) {
      message = String(error);
    }
    expect(message).toContain("ROBO_GRAPH_HOST");
    expect(message).toContain("compose.central-db.yml");
  });
});

test.describe("central 이면 Bolt 와 Postgres 가 같이 중앙을 가리킨다", () => {
  const env = { ROBO_GRAPH_MODE: "central", ROBO_GRAPH_HOST: "10.10.0.5" };

  test("포트를 안 주면 표준 포트를 쓴다", () => {
    const topology = graphTopology(env);
    expect(topology).toEqual({
      mode: "central",
      host: "10.10.0.5",
      boltPort: DEFAULT_BOLT_PORT,
      pgPort: DEFAULT_PG_PORT,
    });
  });

  test("끝점이 로컬 발행 포트를 쓰지 않는다", () => {
    const endpoint = graphEndpoint(LOCAL_PORTS, graphTopology(env));
    expect(endpoint.host).toBe("10.10.0.5");
    // **이 두 줄이 본래 결함을 잡는다.** `OG_PG_*` 가 루프백으로 남아 있으면
    // pgPort 가 49222(로컬)로 나온다.
    expect(endpoint.boltPort).not.toBe(LOCAL_PORTS.graph);
    expect(endpoint.pgPort).not.toBe(LOCAL_PORTS.graphPg);
    expect(endpoint.pgPort).toBe(DEFAULT_PG_PORT);
  });

  test("포트를 주면 그것을 쓴다", () => {
    const endpoint = graphEndpoint(
      LOCAL_PORTS,
      graphTopology({ ...env, ROBO_GRAPH_BOLT_PORT: "17687", ROBO_GRAPH_PG_PORT: "15432" }),
    );
    expect(endpoint).toEqual({ host: "10.10.0.5", boltPort: 17687, pgPort: 15432 });
  });

  test("호스트명도 받는다 — IP 만이 아니다", () => {
    expect(graphTopology({ ...env, ROBO_GRAPH_HOST: "graph.posco.net" }).host).toBe(
      "graph.posco.net",
    );
  });
});

test.describe("못 쓸 포트 값은 표준 포트로 되돌린다", () => {
  // `Number.parseInt("abc")` 는 NaN 이고, 그것을 그대로 쓰면 `bolt://host:NaN` 이 된다.
  // 0 과 음수도 포트가 아니다. **빈 문자열이 0 이 되어 통과하던 자리**이기도 하다.
  for (const raw of ["", " ", "abc", "0", "-1", "70000", "7687abc7"]) {
    test(`ROBO_GRAPH_BOLT_PORT=${JSON.stringify(raw)} → ${DEFAULT_BOLT_PORT}`, () => {
      const topology = graphTopology({
        ROBO_GRAPH_MODE: "central",
        ROBO_GRAPH_HOST: "10.10.0.5",
        ROBO_GRAPH_BOLT_PORT: raw,
      });
      expect(topology.boltPort).toBe(DEFAULT_BOLT_PORT);
    });
  }

  test("앞뒤 공백이 붙은 숫자는 받는다", () => {
    expect(
      graphTopology({
        ROBO_GRAPH_MODE: "central",
        ROBO_GRAPH_HOST: "10.10.0.5",
        ROBO_GRAPH_BOLT_PORT: " 7688 ",
      }).boltPort,
    ).toBe(7688);
  });
});
