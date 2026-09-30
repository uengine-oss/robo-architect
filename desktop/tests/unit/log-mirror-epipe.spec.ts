/**
 * **로그 미러가 앱을 세우지 못하게 한다** (2026-09-30).
 *
 * ## 무슨 일이 있었나
 *
 * 앱을 띄운 부모 프로세스(터미널·`Start-Process`)가 먼저 끝나면 물려받은 stdout
 * 이 끊긴다. 그 뒤 `console.log` 가 EPIPE 를 낸다. 여기까지는 2026-09-28 에 알고
 * `mirrorToConsole` 의 `try/catch` 로 막아 두었다. **그런데 그 예외가 catch 를
 * 지나쳤다** — 스택이 `writeSync → SyncWriteStream._write → writeOrBuffer →
 * Writable.write → console.log` 로 끝나며 `uncaughtException` 으로 올라왔다.
 *
 * 그러면 `consoleBroken` 이 켜지지 않는다. 그래서 **로그 한 줄마다 예외 하나**가
 * 생기고, 그 예외를 처리기가 다시 `log()` 로 적고, 그 `log()` 가 또 미러를 불러
 * 또 EPIPE 를 냈다.
 *
 *     15분     app.uncaught_exception 32,178줄 · 로그 파일 21MB
 *     main     한 코어 100% · responding=False
 *     결과      SSE 프록시가 스트림을 못 비워 **전체 탐색이 3번째 프로세스에서 멈췄다**
 *
 * 백엔드는 멀쩡했다. 로그 미러 하나가 인제스천을 세운 것이다.
 *
 * ## 그래서 무엇을 재나
 *
 * 방어가 셋이고 **하나만 빠져도 되돌아온다**. 아래 둘은 돌려서 재고(미러를 끌 수
 * 있는가 · 동기 예외가 새지 않는가), 처리기 쪽 셋은 소스로 잰다 — `index.ts` 는
 * `electron` 을 끌고 오므로 `runtime-graph-contract.spec.ts` 와 같은 방식이다.
 */

import fs from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

import {
  disableConsoleMirror,
  isConsoleMirrorDisabled,
  log,
  resetConsoleMirrorForTests,
} from "../../src/main/logging";

const desktopRoot = path.resolve(__dirname, "..", "..");
const indexSource = fs.readFileSync(path.join(desktopRoot, "src", "main", "index.ts"), "utf8");

/** `uncaughtException` 처리기 본문. */
function handlerBody(): string {
  const start = indexSource.indexOf('process.on("uncaughtException"');
  expect(start, "uncaughtException 처리기를 못 찾았다").toBeGreaterThan(0);
  const end = indexSource.indexOf("\n  });", start);
  expect(end).toBeGreaterThan(start);
  return indexSource.slice(start, end);
}

test.describe.serial("콘솔 미러", () => {
  // 모듈 상태를 공유한다 — 앞 검사가 끈 것을 되돌려야 다음 검사가 헛돌지 않는다.
  test.beforeEach(() => resetConsoleMirrorForTests());

  test("동기 예외는 호출자에게 새지 않는다", () => {
    const original = console.log;
    console.log = () => {
      const err: NodeJS.ErrnoException = new Error("EPIPE: broken pipe, write");
      err.code = "EPIPE";
      throw err;
    };
    try {
      // 던지면 이 검사가 실패한다. logsDir 이 아직 없어 파일 쓰기는 타지 않는다.
      log("info", "mirror.sync_throw_probe");
    } finally {
      console.log = original;
    }
  });

  test("끄면 더 이상 콘솔로 안 나간다 — 비동기 EPIPE 의 출구", () => {
    const original = console.log;
    const seen: string[] = [];
    console.log = (line?: unknown) => {
      seen.push(String(line));
    };
    try {
      log("info", "mirror.before_disable");
      expect(seen.length, "끄기 전에는 미러가 돌아야 한다").toBe(1);

      disableConsoleMirror();
      expect(isConsoleMirrorDisabled()).toBe(true);

      log("info", "mirror.after_disable");
      log("info", "mirror.after_disable_again");
      expect(seen.length, "끈 뒤에도 콘솔로 나갔다 — EPIPE 가 줄마다 다시 난다").toBe(1);
    } finally {
      console.log = original;
    }
  });
});

test.describe("uncaughtException 처리기", () => {
  test("EPIPE 는 기록하기 전에 미러를 끊는다", () => {
    const body = handlerBody();
    const cut = body.indexOf("disableConsoleMirror()");
    const write = body.indexOf("log(epipe");
    expect(cut, "EPIPE 경로에서 미러를 끊지 않는다 — 기록이 또 EPIPE 를 낸다").toBeGreaterThan(0);
    expect(write).toBeGreaterThan(0);
    expect(cut, "미러를 끊기 전에 기록한다 — 그 기록이 다시 여기로 온다").toBeLessThan(write);
  });

  test("같은 EPIPE 를 두 번 적지 않는다", () => {
    const body = handlerBody();
    expect(body, "반복 차단이 없다 — 21MB 를 다시 쌓는다").toMatch(/epipeSeen/);
    expect(body).toMatch(/epipeSeen\s*>\s*1/);
  });

  test("처리기 재진입을 막는다", () => {
    const body = handlerBody();
    expect(body, "기록 자체가 던지면 무한히 되돌아온다").toMatch(/if \(handling\) return/);
  });
});

test.describe("검사용 출구는 제품 코드에 없다", () => {
  test("resetConsoleMirrorForTests 를 src 가 부르지 않는다", () => {
    const srcDir = path.join(desktopRoot, "src");
    const callers: string[] = [];
    const walk = (dir: string): void => {
      for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
        const p = path.join(dir, e.name);
        if (e.isDirectory()) walk(p);
        else if (e.name.endsWith(".ts")) {
          const t = fs.readFileSync(p, "utf8");
          if (t.includes("resetConsoleMirrorForTests()")) callers.push(path.relative(srcDir, p));
        }
      }
    };
    walk(srcDir);
    // 정의한 자리(logging.ts)만 허용한다.
    expect(callers.filter((f) => f !== "main\\logging.ts" && f !== "main/logging.ts")).toEqual([]);
  });
});

test.describe("표준 스트림", () => {
  test("initLogging 이 stdout·stderr 의 error 를 받는다", () => {
    const loggingSource = fs.readFileSync(
      path.join(desktopRoot, "src", "main", "logging.ts"),
      "utf8",
    );
    expect(loggingSource, "guardStandardStreams 가 없다").toMatch(/function guardStandardStreams/);
    const init = loggingSource.slice(loggingSource.indexOf("export function initLogging"));
    expect(
      init.slice(0, init.indexOf("\n}")),
      "initLogging 이 스트림 방어를 걸지 않는다 — 비동기 error 가 uncaughtException 이 된다",
    ).toMatch(/guardStandardStreams\(\)/);
  });
});
