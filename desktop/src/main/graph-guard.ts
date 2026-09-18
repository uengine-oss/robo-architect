/**
 * 설계 graph 와 분석 graph 가 갈려 있는가 (spec 058 T033 · US2).
 *
 * ## 왜 기동 시점에 보나
 *
 * 분석은 **대상 graph 를 통째로 비우고 다시 쓴다.** 두 graph 가 같으면 첫 분석에서
 * 설계가 사라진다 — 실제로 한 번 날렸다. 분석을 누른 뒤에 막으면 늦다: 누르는 순간
 * 지워진다.
 *
 * ## 빈 graph 로 판정하지 않는다
 *
 * **데이터가 없으면 지워져도 티가 안 난다.** 그리고 두 이름이 같은 저장소를 가리켜도
 * 양쪽 조회가 0 건으로 똑같이 나온다 — 빈 상태에서는 갈려 있는지 아닌지 알 수 없다.
 *
 * 그래서 "분리됐다"와 "분리를 증명했다"를 가른다.
 *
 * ```
 * evidence "content"   양쪽에서 서로 다른 내용이 나왔다 — 실제로 갈려 있다
 * evidence "names"     이름이 다르고 양쪽 조회가 돌았다. 내용으로는 확인 못 했다
 *                      **갓 설치한 상태가 정상적으로 여기다. 막지 않는다**
 * separated false      이름이 같거나 한쪽이 조회되지 않는다 → 분석을 잠근다
 * ```
 *
 * ## 쓰지 않는다
 *
 * 증명을 만들려고 **표식을 심지 않는다.** 기동할 때마다 사용자 graph 에 쓰는 것은
 * 그 자체로 위험하고, 되돌리기가 실패하면 쓰레기가 남는다. 심어서 확인하는 것은
 * 검증 스크립트(`scripts/verify_graph_isolation.py`)의 몫이고, 그쪽은 `zz_` graph 만
 * 쓴다.
 */

import type { GraphGuard } from "../shared/runtime-contract";

/** graph 이름 규칙 — `ontological-db/docker/runtime/10-ontological-init.sh` 와 같은 식. */
const GRAPH_NAME = /^[A-Za-z_][A-Za-z0-9_]{0,62}$/;

export interface GraphNames {
  design: string | null | undefined;
  analysis: string | null | undefined;
}

/**
 * 이름만으로 내릴 수 있는 판정. **연결 없이 돈다** — 설정이 틀린 것은 저장소를
 * 띄우기 전에 알 수 있고, 그게 가장 싼 자리다.
 *
 * `null` 을 돌려주면 "이름으로는 결론 못 냄"이고, 호출자가 조회까지 해 본다.
 */
export function inspectNames(names: GraphNames): GraphGuard | null {
  const design = (names.design ?? "").trim();
  const analysis = (names.analysis ?? "").trim();
  const base = { designGraph: design || null, analysisGraph: analysis || null };

  if (!design || !analysis) {
    return {
      ...base,
      separated: false,
      evidence: null,
      // 한쪽이 비면 분석이 **설정에 없는 쪽**으로 폴백한다 — 그 폴백이 설계 graph 다.
      reason: "설계 graph 와 분석 graph 이름이 둘 다 설정되어 있어야 합니다.",
    };
  }
  for (const [label, value] of [["설계", design], ["분석", analysis]] as const) {
    if (!GRAPH_NAME.test(value)) {
      return {
        ...base,
        separated: false,
        evidence: null,
        reason: `${label} graph 이름이 규칙에 맞지 않습니다: '${value}'`,
      };
    }
  }
  if (design === analysis) {
    return {
      ...base,
      separated: false,
      evidence: null,
      reason: `두 이름이 같습니다('${design}'). 분석은 대상 graph 를 비우고 다시 씁니다.`,
    };
  }
  return null; // 이름은 괜찮다. 실제로 조회되는지는 호출자가 본다.
}

/** 한 graph 를 조회한 결과. 호출자가 드라이버로 채운다. */
export interface GraphSample {
  /** 조회가 돌았는가. 건수는 판정에 안 쓴다 — 0 건도 정상이다. */
  reachable: boolean;
  /** 못 돌았으면 그 이유. */
  error?: string;
  /**
   * 내용의 지문. 같은 저장소를 두 이름으로 가리키면 **반드시 같다.**
   * 다르면 갈려 있다는 증거다. 양쪽이 같아도 "같은 저장소"라고 단정하지 않는다 —
   * 둘 다 비었을 때 자연히 같아지기 때문이다.
   */
  fingerprint: string;
  /** 비어 있는가. 비었으면 내용으로는 아무것도 증명 못 한다. */
  empty: boolean;
}

/**
 * 이름 판정 + 조회 결과 → 최종 판정.
 *
 * 순수 함수다. 드라이버를 부르는 쪽과 판정하는 쪽을 나눠 둔 이유는, 판정을 **연결
 * 없이** 검사할 수 있어야 하기 때문이다.
 */
export function judgeGuard(
  names: GraphNames,
  design: GraphSample,
  analysis: GraphSample,
): GraphGuard {
  const byName = inspectNames(names);
  if (byName) return byName;

  const base = {
    designGraph: (names.design ?? "").trim() || null,
    analysisGraph: (names.analysis ?? "").trim() || null,
  };

  const unreachable = [
    ["설계", design],
    ["분석", analysis],
  ].filter(([, sample]) => !(sample as GraphSample).reachable) as Array<[string, GraphSample]>;

  if (unreachable.length > 0) {
    return {
      ...base,
      // **조회가 안 되는 것을 "분리됐다"로 읽지 않는다.** 없는 graph 를 가리키면
      // 분석이 그걸 만들고 비운다 — 어디를 비울지 모르는 상태다.
      separated: false,
      evidence: null,
      reason: unreachable
        .map(([label, sample]) => `${label} graph 를 읽지 못했습니다: ${sample.error ?? "이유 불명"}`)
        .join(" "),
    };
  }

  if (design.fingerprint === analysis.fingerprint && !design.empty && !analysis.empty) {
    // 둘 다 내용이 있는데 지문이 같다 — 같은 저장소를 두 이름으로 보고 있을 수 있다.
    // 단정하지 않고 **막는다.** 여기서 틀려서 여는 쪽의 손해가 훨씬 크다.
    return {
      ...base,
      separated: false,
      evidence: "content",
      reason:
        "두 graph 의 내용이 완전히 같습니다. 같은 저장소를 두 이름으로 가리키고 있을 수 있습니다.",
    };
  }

  if (design.empty && analysis.empty) {
    return {
      ...base,
      // 이름이 다르고 양쪽이 조회된다 — 설정은 맞다. **다만 증명한 것은 아니다.**
      // 갓 설치한 상태가 정상적으로 여기이므로 막지 않는다.
      separated: true,
      evidence: "names",
      reason: "두 graph 가 모두 비어 있어 내용으로는 확인하지 못했습니다(설정은 분리되어 있습니다).",
    };
  }

  return { ...base, separated: true, evidence: "content", reason: null };
}

// ---------------------------------------------------------------------------
// 실제 조회 — Bolt 로 지문을 뜬다
// ---------------------------------------------------------------------------

export interface GraphProbeConnection {
  uri: string;
  user: string;
  /** **detail·reason 에 절대 싣지 않는다.** */
  password: string;
}

/**
 * 한 graph 의 지문을 뜬다. **쓰지 않는다.**
 *
 * 지문은 라벨별 건수다 — 같은 저장소를 두 이름으로 가리키면 반드시 같고, 갈려 있으면
 * (양쪽에 뭔가 있는 한) 거의 반드시 다르다. 전체 건수만 쓰면 3 대 3 같은 우연에
 * 속는다.
 *
 * `CALL db.labels()` 를 쓰지 않는다 — 저장소마다 있는 것이 다르다. 라벨 없는 스캔으로
 * 라벨을 모아 세는 편이 어디서나 돈다.
 */
export async function sampleGraph(
  connection: GraphProbeConnection,
  graph: string,
): Promise<GraphSample> {
  let driverModule: typeof import("neo4j-driver");
  try {
    driverModule = await import("neo4j-driver");
  } catch {
    return { reachable: false, error: "neo4j 드라이버 없음", fingerprint: "", empty: true };
  }
  const driver = driverModule.default.driver(
    connection.uri,
    driverModule.auth.basic(connection.user, connection.password),
  );
  try {
    const session = driver.session({ database: graph });
    try {
      const result = await session.run(
        "MATCH (n) WITH labels(n) AS ls UNWIND ls AS l " +
          "RETURN l AS label, count(*) AS c ORDER BY label",
      );
      const parts = result.records.map(
        (record) => `${record.get("label")}:${String(record.get("c"))}`,
      );
      const total = await session.run("MATCH (n) RETURN count(n) AS c");
      const count = Number(total.records[0]?.get("c") ?? 0);
      return {
        reachable: true,
        // 라벨이 없는 노드도 있을 수 있어 전체 건수를 함께 넣는다.
        fingerprint: `n=${count}|${parts.join(",")}`,
        empty: count === 0,
      };
    } finally {
      await session.close();
    }
  } catch (error) {
    const text = error instanceof Error ? error.message : String(error);
    return {
      reachable: false,
      // 첫 줄만, 90자까지. 드라이버 예외에 자격증명은 안 들어가지만 그래도 자른다.
      error: text.split("\n")[0]?.slice(0, 90),
      fingerprint: "",
      empty: true,
    };
  } finally {
    await driver.close();
  }
}

/** 기동 시점에 한 번 부르는 것. 이름이 틀렸으면 **연결도 안 해 본다.** */
export async function evaluateGraphGuard(
  names: GraphNames,
  connection: GraphProbeConnection | null,
): Promise<GraphGuard> {
  const byName = inspectNames(names);
  if (byName) return byName;
  const design = (names.design ?? "").trim();
  const analysis = (names.analysis ?? "").trim();
  if (!connection || !connection.password) {
    return {
      designGraph: design,
      analysisGraph: analysis,
      // **못 쟀다고 "분리됐다"고 하지 않는다.** 그렇다고 이름이 맞는데 막을 이유도
      // 없으므로 `separated` 는 이름 판정을 따르고, `evidence: null` 로 "확인 못 함"을
      // 남긴다.
      separated: true,
      evidence: null,
      reason: "저장소에 연결할 수 없어 내용으로 확인하지 못했습니다(이름은 분리되어 있습니다).",
    };
  }
  const [designSample, analysisSample] = await Promise.all([
    sampleGraph(connection, design),
    sampleGraph(connection, analysis),
  ]);
  return judgeGuard(names, designSample, analysisSample);
}
