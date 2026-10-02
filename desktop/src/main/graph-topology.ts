/**
 * 그래프 저장소가 **어디 있는가** (ENT-DEPLOY-001 · 배포 모델 A).
 *
 * ## 왜 별도 파일인가
 *
 * `docker-stack.ts` 는 `electron` 을 끌고 온다(`app`·`safeStorage`). 그래서 그 안에
 * 두면 이 판정을 단위 테스트로 부를 수 없고, 소스 문자열을 읽어 재는 우회 검사밖에
 * 남지 않는다. 이 파일은 순수 함수만 두어 **실제로 불러서** 잰다.
 *
 * ## 두 배치 모델
 *
 *     bundled   DB 까지 이 PC 안. 1인 도구. 지금까지의 동작.
 *     central   DB 는 사내 서버 한 대, PC 는 나머지 컨테이너만.
 *
 * Electron 이 앱을 PC 로 내려보내면서 **프로젝트 공유가 깨졌다** — 프로젝트·권한·
 * 공유가 모두 그래프 저장소에 살기 때문이다. central 이 그것을 되돌린다.
 */

export interface GraphPorts {
  /** 번들 Bolt 게이트웨이를 이 PC 에 발행한 포트. */
  graph: number;
  /** 번들 Postgres 를 이 PC 에 발행한 포트. */
  graphPg: number;
}

/**
 * 판정 결과.
 *
 * **합타입이다.** `host: string | null` 한 필드로 두면 central 경로에서 `host!` 를
 * 쓰게 되고, 그 `!` 가 나중에 틀려도 컴파일러가 말해 주지 않는다.
 */
export type GraphTopology =
  | { mode: "bundled"; host: null; boltPort: number; pgPort: number }
  | { mode: "central"; host: string; boltPort: number; pgPort: number };

/** 그래프에 붙을 실제 주소. 두 모드에서 뜻이 같다. */
export interface GraphEndpoint {
  host: string;
  boltPort: number;
  pgPort: number;
}

/** 번들 모드에서 그래프가 사는 곳. 이 PC 안이다. */
export const LOOPBACK = "127.0.0.1";

export const DEFAULT_BOLT_PORT = 7687;
export const DEFAULT_PG_PORT = 5432;

/**
 * 이 주소를 **컨테이너도 쓴다** — 그래서 루프백이면 못 쓴다.
 *
 * `ROBO_GRAPH_HOST` 는 호스트 백엔드만 보는 값이 아니다. 같은 값이 compose 를 타고
 * 컨테이너 8개에 그대로 들어간다(`fabric`·`catalog`·`analyzer`). 컨테이너 안에서
 * `127.0.0.1` 은 **자기 자신**이라, Bolt 에 못 붙어 `fabric` 이 서고 앱은 그냥
 * "시작할 수 없다" 만 말한다 — 2026-10-02 에 그 화면을 실제로 봤고, **아무 설명이
 * 없었다.**
 *
 * `host.docker.internal` 도 답이 아니다. 컨테이너에서는 풀리지만 **호스트에서는
 * 안 풀려서** 이번엔 백엔드가 못 붙는다. 양쪽이 같이 닿는 주소여야 한다 — Windows
 * 에서는 WSL 가상 스위치 주소(`172.x.x.1` 꼴)가 그것이다.
 *
 * 쓸 수 없는 이유를 돌려준다. 쓸 수 있으면 `null`.
 */
export function unreachableFromContainers(host: string): string | null {
  const name = host.trim().toLowerCase().replace(/^\[|\]$/g, "");
  if (!name) return null; // 빈 값은 호출부가 따로 거절한다.
  if (name === "localhost" || name.endsWith(".localhost")) {
    return "localhost 는 컨테이너 안에서 컨테이너 자신을 가리킨다";
  }
  if (name === "::1" || name === "0:0:0:0:0:0:0:1") {
    return "::1 은 컨테이너 안에서 컨테이너 자신을 가리킨다";
  }
  if (/^127\./.test(name)) {
    return `${host} 는 컨테이너 안에서 컨테이너 자신을 가리킨다`;
  }
  if (name === "0.0.0.0" || name === "::") {
    return `${host} 는 '모든 주소' 라는 뜻이고 붙을 대상이 아니다`;
  }
  if (name === "host.docker.internal") {
    return "host.docker.internal 은 컨테이너에서만 풀린다 — 호스트 백엔드가 못 붙는다";
  }
  return null;
}

function positiveInt(raw: string | undefined, fallback: number): number {
  const value = Number.parseInt((raw ?? "").trim(), 10);
  return Number.isInteger(value) && value > 0 && value <= 65535 ? value : fallback;
}

/**
 * 이 PC 가 어느 모델로 도는가.
 *
 * **왜 환경변수로 정하나.** 이 판정은 Compose 를 띄우기 **전에** 필요하다. 런처의
 * 연결 선택 화면은 스택이 뜬 뒤에 나오므로 거기서 고를 수 없다 — 배포 모델은 설치
 * 시점에 정해지는 것이고 사용자가 매번 고르는 것이 아니다.
 *
 * 기본은 `bundled` 다. **아무것도 설정하지 않으면 지금까지와 똑같이 동작한다.**
 */
export function graphTopology(env: NodeJS.ProcessEnv = process.env): GraphTopology {
  const boltPort = positiveInt(env.ROBO_GRAPH_BOLT_PORT, DEFAULT_BOLT_PORT);
  const pgPort = positiveInt(env.ROBO_GRAPH_PG_PORT, DEFAULT_PG_PORT);
  if ((env.ROBO_GRAPH_MODE ?? "").trim().toLowerCase() !== "central") {
    return { mode: "bundled", host: null, boltPort, pgPort };
  }
  const host = (env.ROBO_GRAPH_HOST ?? "").trim();
  if (!host) {
    // 빈 값으로 넘기면 compose 가 `bolt://:7687` 을 만들고 컨테이너는 그대로 뜬다.
    // **조용히 틀린 주소를 쓰는 대신 여기서 멈춘다.**
    throw new Error(
      "runtime.graph_host_missing: ROBO_GRAPH_MODE=central 인데 ROBO_GRAPH_HOST 가 없다. " +
        "중앙 그래프 서버의 주소를 지정하라 (예: 10.10.0.5). " +
        "서버는 compose.central-db.yml 로 띄운다",
    );
  }
  const unreachable = unreachableFromContainers(host);
  if (unreachable) {
    // 기동 전에 멈춘다. 이 값으로 띄우면 `fabric` 이 설명 없이 죽고, 사람은
    // 도커를 의심한다 — **고칠 수 있는 말**을 여기서 한 번 하는 것이 전부다.
    throw new Error(
      `runtime.graph_host_unreachable: ROBO_GRAPH_HOST=${host} 로는 중앙 DB 에 붙을 수 없다. ` +
        `${unreachable}. 이 주소는 **컨테이너 8개에도 그대로** 들어가므로 ` +
        "호스트와 컨테이너가 **둘 다** 닿는 주소여야 한다. " +
        "다른 PC 라면 그 서버의 LAN 주소를, 이 PC 에 서버를 띄웠다면 " +
        "WSL 가상 스위치 주소(ipconfig 의 vEthernet (WSL) IPv4, 172.x.x.1 꼴)를 쓴다",
    );
  }
  return { mode: "central", host, boltPort, pgPort };
}

/**
 * 그래프에 **어디로** 붙는가.
 *
 * bundled 면 이 PC 의 발행 포트(실행마다 달라진다), central 이면 사내 서버의 주소와
 * 포트다. 호출자는 두 모드를 구별하지 않고 이 값만 쓴다 — 구별을 여러 곳에 흩으면
 * 한 곳이 빠지고, **빠진 곳은 로컬을 가리켜서 조용히 자기만의 저장소를 쓴다.**
 */
export function graphEndpoint(ports: GraphPorts, topology: GraphTopology): GraphEndpoint {
  if (topology.mode === "central") {
    return { host: topology.host, boltPort: topology.boltPort, pgPort: topology.pgPort };
  }
  return { host: LOOPBACK, boltPort: ports.graph, pgPort: ports.graphPg };
}
