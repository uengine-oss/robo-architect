/**
 * 샌드박스 preload 가 **상대 경로를 require 하지 않는가**.
 *
 * ## 2026-09-18 ~ 09-29, 11일 동안 IPC 가 죽어 있었다
 *
 * 이 preload 는 `sandbox: true` 로 뜬다(`src/main/index.ts`). 샌드박스 preload 의
 * `require` 는 `electron` 과 일부 내장 모듈만 해소하고 **상대 경로는 못 찾는다.**
 * 그래서 값 import 하나가 브리지를 통째로 죽인다.
 *
 * `bba8be6` 이 이 파일 **최초의 값 import** 로 `RUNTIME_CHANNELS` 를 들여왔다.
 * 그 전에는 전부 `import type` 이라 tsc 가 지웠고 `require("electron")` 하나뿐이었다.
 * 그 뒤로 패키지 앱은 이렇게 죽었다 —
 *
 *     Unable to load preload script: …\app.asar\dist\preload\preload\index.js
 *     Error: module not found: ../shared/runtime-contract
 *
 * **증상이 없었다.** `window.robo` 가 없으면 화면은 자기를 웹 SPA 로 알고 런처를
 * 건너뛴다. HTTP 는 `app://` 프록시로 멀쩡히 흐르므로 화면은 정상으로 보인다.
 * 렌더러 콘솔을 파일로 받기 시작한 09-29 에야 드러났다.
 *
 * ## 그래서 무엇을 재는가
 *
 * 타입 사본을 맞춰 두는 것(`preload/index.ts` 의 `_channelsAreExact`)은 **그
 * 상수 하나만** 지킨다. 다음에 누가 다른 모듈에서 값을 가져오면 같은 사고가
 * 반복된다. 그래서 **컴파일 결과에 상대 require 가 하나도 없는지** 본다.
 *
 * 소스가 아니라 `dist` 를 보는 것이 요점이다 — `import type` 은 지워지므로
 * 소스만 읽으면 지워질 것과 남을 것을 구별할 수 없다.
 */

import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const PRELOAD_JS = path.join(__dirname, "..", "..", "dist", "preload", "preload", "index.js");

/** 샌드박스 preload 에서 해소되는 것. 이 목록 밖은 전부 실패 사유다. */
const ALLOWED = new Set(["electron"]);

function requires(source: string): string[] {
  const found = new Set<string>();
  for (const m of source.matchAll(/require\(\s*["'`]([^"'`]+)["'`]\s*\)/g)) {
    found.add(m[1]!);
  }
  return [...found].sort();
}

test.describe("preload 는 샌드박스에서 살아남는 형태여야 한다", () => {
  test("컴파일 결과가 존재한다 — 없으면 이 검사는 아무것도 못 지킨다", () => {
    expect(
      fs.existsSync(PRELOAD_JS),
      `먼저 \`npm run build\` 가 필요하다: ${PRELOAD_JS}`,
    ).toBe(true);
  });

  test("상대 경로를 require 하지 않는다", () => {
    const source = fs.readFileSync(PRELOAD_JS, "utf8");
    const relative = requires(source).filter((r) => r.startsWith("."));
    expect(
      relative,
      "샌드박스 preload 는 상대 require 를 해소하지 못한다 — 값 import 를 " +
        "`import type` 으로 바꾸거나, 값을 이 파일 안에 두고 타입으로 묶어라 " +
        "(`preload/index.ts` 의 RUNTIME_CHANNELS 참고)",
    ).toEqual([]);
  });

  test("허용된 모듈만 require 한다", () => {
    const source = fs.readFileSync(PRELOAD_JS, "utf8");
    const unexpected = requires(source).filter((r) => !ALLOWED.has(r));
    expect(unexpected, `허용 목록: ${[...ALLOWED].join(", ")}`).toEqual([]);
  });

  test("그래도 electron 은 써야 한다 — 빈 파일이 통과하면 안 된다", () => {
    // 이 검사가 없으면 preload 를 통째로 비워도 위 둘이 통과한다.
    const source = fs.readFileSync(PRELOAD_JS, "utf8");
    expect(requires(source)).toContain("electron");
    expect(source).toContain("contextBridge");
  });
});

test.describe("검사 자체가 동작하는가", () => {
  // 일부러 틀린 입력을 넣어 잡히는지부터 본다.
  test("상대 require 가 있으면 잡아낸다", () => {
    const bad = 'const x = require("../shared/runtime-contract");';
    expect(requires(bad).filter((r) => r.startsWith("."))).toEqual([
      "../shared/runtime-contract",
    ]);
  });

  test("공백·따옴표 변형도 잡는다", () => {
    const bad = "require( './a' ) require(`../b`) require(\"electron\")";
    expect(requires(bad)).toEqual(["../b", "./a", "electron"]);
  });
});
