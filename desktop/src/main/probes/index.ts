/**
 * 서비스별 기능 프로브 (spec 058 T021·T023·T024).
 *
 * 계약은 `specs/058-app-owned-runtime-supervision/contracts/service-capability-probes.md`.
 *
 * ## 이 파일이 하지 않는 것
 *
 * - **LLM 을 부르지 않는다.** 실제 BPMN 생성은 12.6초 걸리고 돈이 나간다. 자격증명
 *   유효성은 값싼 인증 호출로 잰다.
 * - **없는 경로를 지어내지 않는다.** 09-17 에 `/robo/health` 를 만들어 불렀다가 500 을
 *   보고 게이트웨이 결함으로 오독했다. 여기 적힌 경로는 전부 실제로 도는 것을 확인한
 *   것이다.
 * - **쓰기를 하지 않는다.** 단 하나 예외가 parser 인데, 파서는 작업 폴더를 비우고 다시
 *   쓰는 쪽이라 "쓸 수 있는가"가 곧 기능이다 — 그래서 자기 이름으로 된 임시 파일
 *   하나를 만들고 지운다.
 */

import type {
  ManagedServiceId,
  ProbeKind,
  ProbeOutcome,
  ProbeResult,
} from "../../shared/runtime-contract";
import {
  containerExec,
  containerHttpReach,
  httpReach,
  portOpen,
} from "./net";

/** 프로브가 알아야 할 것 전부. **비밀번호는 여기로만 온다 — 로그·detail 로 안 나간다.** */
export interface ProbeContext {
  /** compose 프로젝트 이름. 컨테이너 이름을 만드는 데 쓴다. */
  projectName: string;
  ports: {
    graph: number;
    analyzer: number;
    gateway: number;
    architect: number;
    pdf2bpmn: number;
  };
  graph: {
    user: string;
    /** **detail 에 절대 싣지 않는다.** */
    password: string;
    design: string;
    analysis: string;
  };
}

/**
 * 프로브 id → compose 서비스 이름 후보.
 *
 * **같지 않다.** 저장소는 컨테이너가 둘(`graph-db` + `graph-bolt`)인데 앱이 보는 것은
 * Bolt 하나이고, 되돌아간 Neo4j 구성에서는 그냥 `neo4j` 다. 한 이름으로 못 박으면 다른
 * 구성에서 조용히 "컨테이너 없음"이 된다 — 후보를 순서대로 본다.
 */
export const COMPOSE_SERVICE_CANDIDATES: Partial<Record<ManagedServiceId, string[]>> = {
  graph: ["graph-bolt", "neo4j"],
};

export function containerNames(context: ProbeContext, id: ManagedServiceId): string[] {
  const candidates = COMPOSE_SERVICE_CANDIDATES[id] ?? [id];
  return candidates.map((name) => `${context.projectName}-${name}-1`);
}

type Probe = (context: ProbeContext) => Promise<Omit<ProbeResult, "serviceId" | "kind" | "durationMs">>;

interface ProbePair {
  health: Probe;
  capability?: Probe;
}

const ok = (detail: string) => ({ outcome: "pass" as ProbeOutcome, detail });
const no = (detail: string) => ({ outcome: "fail" as ProbeOutcome, detail });
const cannot = (detail: string) => ({ outcome: "error" as ProbeOutcome, detail });
const later = (detail: string) => ({ outcome: "skipped" as ProbeOutcome, detail });

// ---------------------------------------------------------------------------
// graph — 저장소 (T022 는 이미 닫혔다. 같은 판정을 여기로 옮긴다)
// ---------------------------------------------------------------------------

const graphProbes: ProbePair = {
  async health(context) {
    return (await portOpen("127.0.0.1", context.ports.graph))
      ? ok("bolt open")
      : no("bolt closed");
  },
  async capability(context) {
    if (!(await portOpen("127.0.0.1", context.ports.graph))) {
      return later("bolt 가 안 열려 있어 재지 않음");
    }
    if (!context.graph.user || !context.graph.design) {
      return cannot("graph 사용자·이름이 없어 재지 못함");
    }
    if (!context.graph.password) {
      return cannot("graph 비밀번호가 없어 재지 못함");
    }
    // **포트 열림으로 판정하지 않는다.** bolt 핸드셰이크는 성공하는데 그 graph 가
    // 없으면 조회에서야 `DatabaseNotFound` 가 난다 — 런처 연결 테스트가 통과하고
    // 화면이 전부 500 이 되던 그 증상이다.
    let driverModule: typeof import("neo4j-driver");
    try {
      driverModule = await import("neo4j-driver");
    } catch {
      return cannot("neo4j 드라이버 없음 — 재지 못함");
    }
    const driver = driverModule.default.driver(
      `bolt://127.0.0.1:${context.ports.graph}`,
      driverModule.auth.basic(context.graph.user, context.graph.password),
    );
    try {
      const session = driver.session({ database: context.graph.design });
      try {
        // **건수는 판정에 안 쓴다.** 갓 만든 graph 는 0 건이 정상이다. 질의가
        // 돌았는지가 판정이다 — 0 건을 실패로 보면 정상 부재를 고장으로 읽는다.
        await session.run("MATCH (n) RETURN count(n) AS c");
      } finally {
        await session.close();
      }
      return ok(`graph '${context.graph.design}' 조회됨`);
    } catch (error) {
      return no(`graph '${context.graph.design}' 질의 실패: ${firstLine(error)}`);
    } finally {
      await driver.close();
    }
  },
};

// ---------------------------------------------------------------------------
// gateway — **절대 코드로 판정하지 않는다** (T023)
// ---------------------------------------------------------------------------

const gatewayProbes: ProbePair = {
  async health(context) {
    const reached = await httpReach(`http://127.0.0.1:${context.ports.gateway}/actuator/health`);
    if (reached.outcome === "error") return cannot(reached.detail);
    return reached.code === 200 ? ok("200") : no(`actuator=${reached.detail}`);
  },
  async capability(context) {
    // 판정 기준은 **"직접 호출과 같은 코드인가"** 다. `/api/gateway/antlr/` 가 500 이어도
    // parser 직접이 500 이면 라우팅은 정상이다(09-17 에 이걸 결함으로 오독했다).
    const via = await httpReach(`http://127.0.0.1:${context.ports.gateway}/api/gateway/antlr/`);
    if (via.outcome === "error") return cannot(`게이트웨이 도달 불가: ${via.detail}`);
    const direct = await firstReachable(
      containerNames(context, "parser"),
      "http://127.0.0.1:8081/antlr/",
    );
    if (direct.outcome === "error") return cannot(`parser 직접 호출 불가: ${direct.detail}`);
    return via.detail === direct.detail
      ? ok(`게이트웨이 ${via.detail} == 직접 ${direct.detail}`)
      : no(`게이트웨이 ${via.detail} != 직접 ${direct.detail}`);
  },
};

// ---------------------------------------------------------------------------
// pdf2bpmn — **이 스펙 전체의 근거 실험 자리** (T024)
// ---------------------------------------------------------------------------

const pdf2bpmnProbes: ProbePair = {
  async health(context) {
    const reached = await httpReach(`http://127.0.0.1:${context.ports.pdf2bpmn}/healthz`);
    if (reached.outcome === "error") return cannot(reached.detail);
    return reached.code === 200 ? ok("200") : no(`healthz=${reached.detail}`);
  },
  async capability(context) {
    // 09-17 실측: `/healthz` 200 인 상태에서 자격증명이 틀리면 생성이 502, 맞으면
    // 진짜 BPMN(9.6KB)이 나왔다. **healthz 는 준비의 근거가 아니다.**
    //
    // 그래서 여기서는 **설정된 LLM 엔드포인트에 값싼 인증 호출**을 한다 —
    // 실제 생성은 쓰지 않는다(12.6초·비용).
    const health = await httpReach(`http://127.0.0.1:${context.ports.pdf2bpmn}/healthz`);
    if (health.outcome === "error" || health.code !== 200) {
      return later("healthz 가 200 이 아니라 재지 않음");
    }
    const names = containerNames(context, "pdf2bpmn");
    const script =
      "import os,sys,json,urllib.request,urllib.error\n"
      + "base=(os.environ.get('OPENAI_BASE_URL') or os.environ.get('LLM_API_BASE') or '').rstrip('/')\n"
      + "key=os.environ.get('OPENAI_API_KEY') or os.environ.get('LLM_API_KEY') or ''\n"
      // 설정이 아예 없으면 **못 잰 것**이다. 없다고 "안 된다"로 부르지 않는다.
      + "if not base or not key: print('NOCONF'); sys.exit(0)\n"
      + "req=urllib.request.Request(base+'/models', headers={'Authorization':'Bearer '+key})\n"
      + "try: urllib.request.urlopen(req,timeout=8); print('200')\n"
      + "except urllib.error.HTTPError as e: print(e.code)\n"
      + "except Exception as e: print('ERR:'+type(e).__name__)\n";
    for (const name of names) {
      const { out } = await containerExec(name, ["python", "-c", script], 20_000);
      const text = out.trim().split("\n").pop()?.trim() ?? "";
      if (out.includes("No such container") || out.includes("is not running")) continue;
      if (text === "NOCONF") return cannot("LLM 엔드포인트·키 설정이 없어 재지 못함");
      if (text === "200") return ok("LLM 자격증명 유효");
      if (/^(401|403)$/.test(text)) {
        // **여기가 이 스펙의 이유다.** healthz 는 200 인데 일할 수 없는 상태.
        return no(`LLM 자격증명이 거부됨 (${text}) — healthz 는 200 이다`);
      }
      if (/^\d{3}$/.test(text)) return cannot(`LLM 엔드포인트가 ${text} — 판정 못 함`);
      return cannot(text || "출력 없음");
    }
    return cannot("pdf2bpmn 컨테이너를 못 찾음");
  },
};

// ---------------------------------------------------------------------------
// 나머지
// ---------------------------------------------------------------------------

function httpHealth(port: (context: ProbeContext) => number, path: string): Probe {
  return async (context) => {
    const reached = await httpReach(`http://127.0.0.1:${port(context)}${path}`);
    // **도달했으면 pass 다.** 절대 코드로 판정하지 않는다 — FastAPI 루트가 404 를
    // 내는 것은 정상이고, 그것도 "서비스가 답했다"는 사실이다.
    return reached.outcome === "error" ? cannot(reached.detail) : ok(reached.detail);
  };
}

function containerHealth(id: ManagedServiceId, url: string): Probe {
  return async (context) => {
    const reached = await firstReachable(containerNames(context, id), url);
    return reached.outcome === "error" ? cannot(reached.detail) : ok(reached.detail);
  };
}

const analyzerProbes: ProbePair = {
  health: httpHealth((context) => context.ports.analyzer, "/"),
  async capability(context) {
    // 분석 실행에는 `ROBO_LLM_CONFIG`·`ROBO_LLM_API_KEY` 가 필요하다. 없으면
    // **화면·API 는 뜨고 분석만 실패한다** — 그 실패를 기동 시점에 드러낸다.
    //
    // LLM 을 부르지 않는다. 설정 파일이 실제로 읽히는지까지만 본다(로더가 필수 필드를
    // 검증하므로, 읽히면 최소한 형식은 맞는 것이다).
    const script =
      "import os,sys\n"
      + "name=os.environ.get('ROBO_LLM_CONFIG','')\n"
      + "key=os.environ.get('ROBO_LLM_API_KEY','')\n"
      + "if not name: print('NOCONF'); sys.exit(0)\n"
      + "if not key: print('NOKEY'); sys.exit(0)\n"
      + "sys.path.insert(0,'/app')\n"
      // **설정 로더의 자리가 판마다 다르다.** main 은 `llm/configs/`, 이식 전 브랜치는
      // `shared/llm/`. 둘 다 없으면 **fail 이 아니라 error 다** — 서비스가 안 되는 게
      // 아니라 우리가 이 이미지에서 잴 방법을 모르는 것이다. 2026-09-18 에 옛 이미지를
      // 상대로 이걸 `fail` 로 냈다.
      + "load=None\n"
      + "for mod in ('llm.configs.config_loader','shared.llm.config_loader'):\n"
      + "    try:\n"
      + "        load=__import__(mod, fromlist=['load_llm_config']).load_llm_config; break\n"
      + "    except Exception: pass\n"
      + "if load is None: print('NOLOADER'); sys.exit(0)\n"
      + "try: print('OK:'+load(name).provider)\n"
      + "except Exception as e: print('BAD:'+str(e).splitlines()[0][:80])\n";
    for (const name of containerNames(context, "analyzer")) {
      const { out } = await containerExec(name, ["python", "-c", script], 20_000);
      if (out.includes("No such container") || out.includes("is not running")) continue;
      const text = out.trim().split("\n").pop()?.trim() ?? "";
      if (text === "NOCONF") return cannot("ROBO_LLM_CONFIG 가 없어 재지 못함");
      if (text === "NOKEY") return no("ROBO_LLM_API_KEY 가 비어 있어 분석이 실패한다");
      if (text === "NOLOADER") return cannot("이 이미지에서 LLM 설정 로더를 못 찾아 재지 못함");
      if (text.startsWith("OK:")) return ok(`LLM 설정 읽힘 (${text.slice(3)})`);
      if (text.startsWith("BAD:")) return no(`LLM 설정을 못 읽는다: ${text.slice(4)}`);
      return cannot(text || "출력 없음");
    }
    return cannot("analyzer 컨테이너를 못 찾음");
  },
};

const parserProbes: ProbePair = {
  health: containerHealth("parser", "http://127.0.0.1:8081/"),
  async capability(context) {
    // 파서는 작업 폴더를 **비우고 다시 쓴다.** 쓸 수 없으면 분석이 조용히 빈다.
    // 자기 이름으로 된 파일 하나를 만들고 **반드시 지운다.**
    const marker = "/data/.robo-probe-write";
    for (const name of containerNames(context, "parser")) {
      const { code, out } = await containerExec(
        name,
        ["sh", "-c", `touch ${marker} && rm -f ${marker} && echo WRITABLE`],
        15_000,
      );
      if (out.includes("No such container") || out.includes("is not running")) continue;
      if (code === 0 && out.includes("WRITABLE")) return ok("/data 쓰기 가능");
      return no(`/data 에 쓸 수 없다: ${out.trim().split("\n")[0]?.slice(0, 80) ?? `exit=${code}`}`);
    }
    return cannot("parser 컨테이너를 못 찾음");
  },
};

const PROBES: Partial<Record<ManagedServiceId, ProbePair>> = {
  graph: graphProbes,
  gateway: gatewayProbes,
  analyzer: analyzerProbes,
  parser: parserProbes,
  pdf2bpmn: pdf2bpmnProbes,
  catalog: { health: containerHealth("catalog", "http://127.0.0.1:5503/robo/check-data/") },
  fabric: { health: containerHealth("fabric", "http://127.0.0.1:8404/health") },
  mindsdb: { health: containerHealth("mindsdb", "http://127.0.0.1:47334/api/status") },
  architect: { health: httpHealth((context) => context.ports.architect, "/api/health") },
};

export function probedServiceIds(): ManagedServiceId[] {
  return Object.keys(PROBES) as ManagedServiceId[];
}

export function hasCapabilityProbe(id: ManagedServiceId): boolean {
  return Boolean(PROBES[id]?.capability);
}

export async function runProbe(
  context: ProbeContext,
  id: ManagedServiceId,
  kind: ProbeKind,
): Promise<ProbeResult> {
  const pair = PROBES[id];
  const probe = kind === "health" ? pair?.health : pair?.capability;
  const started = Date.now();
  if (!probe) {
    return {
      serviceId: id,
      kind,
      outcome: "error",
      detail: `${kind} 프로브가 없다`,
      durationMs: 0,
    };
  }
  try {
    const result = await probe(context);
    return { serviceId: id, kind, ...result, durationMs: Date.now() - started };
  } catch (error) {
    // **프로브가 터진 것은 fail 이 아니라 error 다.** 뭉치면 "재지 못한 것"이
    // "안 되는 것"이 된다.
    return {
      serviceId: id,
      kind,
      outcome: "error",
      detail: `프로브 예외: ${firstLine(error)}`,
      durationMs: Date.now() - started,
    };
  }
}

async function firstReachable(names: string[], url: string) {
  let last = { outcome: "error" as const, detail: "컨테이너를 못 찾음" };
  for (const name of names) {
    const reached = await containerHttpReach(name, url);
    if (reached.outcome === "pass") return reached;
    if (!reached.detail.includes("No such container") && !reached.detail.includes("is not running")) {
      last = { outcome: "error", detail: reached.detail };
    }
  }
  return last;
}

function firstLine(error: unknown): string {
  const text = error instanceof Error ? error.message : String(error);
  return text.split("\n")[0]?.slice(0, 90) ?? "unknown";
}
