/**
 * 설치본 런타임의 **graph 배선 계약** (spec 058 T076 · T077).
 *
 * ## 왜 소스를 읽어서 재나
 *
 * `docker-stack.ts` 와 `connections.ts` 는 `electron` 을 끌고 온다(`app`·`safeStorage`).
 * 그래서 이 검사는 함수를 부르는 대신 **파일들이 서로 맞는지**를 본다. 여기서 나는
 * 고장은 전부 "파일 A 가 쓰는 이름을 파일 B 가 안 준다" 모양이고, 그건 실행 시점에
 * 조용하다 — compose 는 없는 변수를 **빈 문자열**로 채우고 컨테이너는 그대로 뜬다.
 *
 * ## 규칙을 다시 짜지 않는다
 *
 * `validateDatabase` 의 정규식은 **소스에서 뽑아서 그대로 돌린다**. 검사 쪽에 규칙을
 * 다시 쓰면 재구현이 원본보다 옳아져서 결함을 가린다(이 저장소가 밟은 적 있다).
 */

import fs from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

const desktopRoot = path.resolve(__dirname, "..", "..");
const read = (...p: string[]) => fs.readFileSync(path.join(desktopRoot, ...p), "utf8");

const composeSource = read("runtime", "compose.yml");
const stackSource = read("src", "main", "docker-stack.ts");
const backendSource = read("src", "main", "backend.ts");
const connectionsSource = read("src", "main", "launcher", "connections.ts");
const manifest = JSON.parse(read("runtime", "runtime-manifest.template.json"));

/** `composeEnvironment()` 본문이 내보내는 변수 이름들. */
function emittedComposeVars(): Set<string> {
  const start = stackSource.indexOf("function composeEnvironment(");
  expect(start, "composeEnvironment() 를 못 찾았다 — 이름이 바뀌었으면 이 검사도 고쳐라").toBeGreaterThan(0);
  const end = stackSource.indexOf("\n}", start);
  const body = stackSource.slice(start, end);
  return new Set([...body.matchAll(/^\s{4}(ROBO_[A-Z0-9_]+):/gm)].map((m) => m[1]!));
}

test.describe("compose ↔ docker-stack 변수 계약", () => {
  test("compose.yml 이 쓰는 ROBO_* 를 앱이 전부 준다", () => {
    const used = new Set([...composeSource.matchAll(/\$\{(ROBO_[A-Z0-9_]+)\}/g)].map((m) => m[1]!));
    expect(used.size).toBeGreaterThan(10);
    const missing = [...used].filter((name) => !emittedComposeVars().has(name)).sort();
    // 없는 변수는 compose 에서 **빈 문자열**이 된다. 이미지 이름이 비면 실패가 보이지만
    // graph 이름이 비면 조용히 엉뚱한 곳을 읽는다.
    expect(missing, `compose 가 쓰는데 앱이 안 주는 변수: ${missing.join(", ")}`).toEqual([]);
  });

  test("저장소는 Ontological 이다 — 옛 Neo4j 이미지 변수는 남아 있지 않다", () => {
    expect(composeSource).not.toContain("ROBO_IMAGE_NEO4J");
    expect(composeSource).toContain("${ROBO_IMAGE_GRAPH_DB}");
    expect(composeSource).toContain("${ROBO_IMAGE_GRAPH_BOLT}");
  });
});

test.describe("설계 graph 와 분석 graph 를 가른다", () => {
  const graphNamePattern = /^[A-Za-z_][A-Za-z0-9_]{0,62}$/;

  test("매니페스트 템플릿의 두 graph 이름이 다르다", () => {
    // 같으면 첫 분석에서 설계가 사라진다. analyzer 는 대상 graph 를 통째로 비운다.
    expect(manifest.graphs.design).not.toBe(manifest.graphs.analysis);
    for (const key of ["user", "design", "analysis"] as const) {
      expect(graphNamePattern.test(manifest.graphs[key]), `graphs.${key}`).toBe(true);
    }
  });

  test("매니페스트 템플릿이 docker-stack 의 스키마 버전·이미지 목록과 맞는다", () => {
    const declared = Number(/const MANIFEST_SCHEMA_VERSION = (\d+);/.exec(stackSource)![1]);
    expect(manifest.schemaVersion).toBe(declared);
    const required = [...stackSource.matchAll(/^\s{4}"(graphDb|graphBolt|mindsdb|analyzer|catalog|fabric|parser|gateway|pdf2bpmn)",$/gm)]
      .map((m) => m[1]!);
    expect(required.length).toBeGreaterThan(0);
    for (const name of required) {
      expect(manifest.images[name], `images.${name}`).toBeTruthy();
      expect(manifest.imageIds[name], `imageIds.${name}`).toBeTruthy();
    }
  });

  test("compose 의 analyzer 는 분석 graph 를 받는다 — 설계 graph 가 아니다", () => {
    const analyzer = composeSource.slice(
      composeSource.indexOf("\n  analyzer:"),
      composeSource.indexOf("\n  parser:"),
    );
    expect(analyzer.length).toBeGreaterThan(100);
    expect(analyzer).toContain("NEO4J_DATABASE: ${ROBO_GRAPH_ANALYSIS}");
    expect(analyzer).not.toContain("NEO4J_DATABASE: ${ROBO_GRAPH_DESIGN}");
  });

  test("호스트 백엔드도 분석 graph 를 따로 받는다", () => {
    // 예전에는 `ROBO_NEO4J_DATABASE`(= 설계) 로 덮었다. Community 에서는 그게 유일한
    // 구성이었지만, 이제 갈라져 있으므로 덮으면 설계가 지워진다.
    expect(backendSource).toContain(
      "ANALYZER_NEO4J_DATABASE:\n      process.env.ROBO_ANALYZER_NEO4J_DATABASE",
    );
    expect(stackSource).toContain(
      "process.env.ROBO_ANALYZER_NEO4J_DATABASE = manifest.graphs.analysis;",
    );
  });
});

test.describe("연결 저장이 graph 이름을 받아들인다", () => {
  test("validateDatabase 의 실제 정규식이 두 graph 이름을 통과시킨다", () => {
    // 소스에서 **그대로 뽑아** 돌린다. 여기 규칙을 다시 쓰면 검사만 옳아진다.
    const literal = /if \(!(\/\^.*?\/)\.test\(db\)\)/.exec(connectionsSource);
    expect(literal, "validateDatabase 의 정규식 리터럴을 못 찾았다").not.toBeNull();
    // eslint-disable-next-line no-new-func
    const pattern = new Function(`return ${literal![1]}`)() as RegExp;
    for (const key of ["design", "analysis"] as const) {
      const name = manifest.graphs[key];
      expect(pattern.test(name), `validateDatabase 가 graphs.${key}='${name}' 를 거부한다`).toBe(true);
    }
  });
});
