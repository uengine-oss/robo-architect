/**
 * **백엔드 stdout 의 인코딩 계약** (2026-09-30).
 *
 * ## 왜 이걸 재나
 *
 * `backend.ts` 는 stdout 을 `buf.toString()` 으로 읽는다 — Node 의 기본은 **UTF-8**
 * 이다. 그런데 한국어 Windows 에서 파이프에 붙은 python 의 기본 인코딩은 `cp949`
 * 다. 둘이 어긋나면 **두 가지가 같이 터진다**:
 *
 *   1. 로그의 한글이 전부 `U+FFFD` 로 깨진다 — 사고 났을 때 읽을 것이 없어진다.
 *   2. `cp949` 에 없는 글자(`—` U+2014 등)를 담은 로그 한 줄이 `print()` 에서
 *      `UnicodeEncodeError` 를 던져 **그 요청을 죽인다**.
 *
 * 2026-09-30 에 실제로 그랬다: 문서 업로드 인제스천이 Phase 1 **성공 직후** 매번
 * 죽었고, 죽인 것은 성공을 알리는 INFO 한 줄이었다("facade produced Phase 1
 * bundle — using it"). 앱을 셸에서 띄우면 그 셸의 `PYTHONUTF8` 을 물려받아 우연히
 * 살아나므로 **개발 중에는 절대 안 보인다** — 깨끗하게 설치해서 띄운 PC 에서만 난다.
 *
 * ## 왜 소스를 읽어서 재나
 *
 * `backend.ts` 는 `electron` 을 끌고 온다. 그래서 `runtime-graph-contract.spec.ts`
 * 와 같은 방식으로 **파일이 서로 맞는지**를 본다. 여기서 나는 고장은 실행 시점에
 * 조용하다 — 백엔드는 정상으로 뜨고, 문서 인제스천만 죽는다.
 */

import fs from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

const desktopRoot = path.resolve(__dirname, "..", "..");
const backendSource = fs.readFileSync(
  path.join(desktopRoot, "src", "main", "backend.ts"),
  "utf8",
);

/** 백엔드에 넘기는 `env` 리터럴 본문. */
function spawnEnvBody(): string {
  const start = backendSource.indexOf("const env: NodeJS.ProcessEnv = {");
  expect(
    start,
    "spawn 에 넘기는 env 리터럴을 못 찾았다 — 모양이 바뀌었으면 이 검사도 고쳐라",
  ).toBeGreaterThan(0);
  const end = backendSource.indexOf("\n  };", start);
  expect(end).toBeGreaterThan(start);
  return backendSource.slice(start, end);
}

test.describe("백엔드 stdout 인코딩", () => {
  test("python 을 UTF-8 로 띄운다", () => {
    const env = spawnEnvBody();
    expect(env, 'PYTHONUTF8 를 안 준다 — cp949 로 떨어지면 로그가 요청을 죽인다').toMatch(
      /PYTHONUTF8:\s*"1"/,
    );
    expect(env, "PYTHONIOENCODING 을 안 준다").toMatch(/PYTHONIOENCODING:\s*"utf-8"/);
  });

  test("읽는 쪽은 UTF-8 로 디코딩한다 — 주는 쪽과 같아야 한다", () => {
    // `buf.toString()` 은 인자 없으면 UTF-8. 다른 인코딩을 명시하면 위 env 와
    // 어긋나므로 같이 고쳐야 한다.
    const decoders = [...backendSource.matchAll(/buf\.toString\(([^)]*)\)/g)].map(
      (m) => m[1]!.trim(),
    );
    expect(decoders.length, "stdout/stderr 디코딩 지점을 못 찾았다").toBeGreaterThanOrEqual(2);
    for (const arg of decoders) {
      expect(
        arg === "" || /^["']utf-?8["']$/i.test(arg),
        `buf.toString(${arg}) — env 의 PYTHONIOENCODING 과 어긋난다`,
      ).toBe(true);
    }
  });

  test("개발 경로도 같은 env 를 쓴다", () => {
    // packaged / development 로 갈리는 건 executable·args 뿐이고 env 는 하나다.
    // 둘로 갈라지면 개발 중에만 살아나는 결함이 다시 생긴다.
    const count = [...backendSource.matchAll(/const env: NodeJS\.ProcessEnv = \{/g)].length;
    expect(count, "env 리터럴이 둘 이상이다 — 갈라지면 한쪽만 고쳐진다").toBe(1);
  });
});
