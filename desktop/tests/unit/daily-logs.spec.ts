/**
 * 로그가 **날짜별 파일**로 남는가.
 *
 * ## 왜 바꿨나
 *
 * 전에는 `desktop.log` 하나에 5MB 씩 돌려썼다(`.1`~`.5`). 그러면 "어제 무슨
 * 일이 있었나" 를 물을 수가 없다 — 경계가 크기라서 날짜와 안 맞고, 바쁜 하루가
 * 조용한 한 주를 밀어낸다. 2026-09-28 설치 검증 기록이 다음 날 기동 로그와 같은
 * 파일에 섞여 있었고, 그 안에서 시각으로 눈대중해 찾아야 했다.
 *
 * ## 로컬 날짜로 나누는 것이 요점이다
 *
 * 줄 안의 `ts` 는 ISO(UTC)다. 그런데 파일을 찾는 사람은 "9월 29일 오전" 처럼
 * 자기 시계로 생각한다. UTC 로 나누면 **KST 오전 9시가 전날 파일에 들어간다** —
 * 오늘 아침 로그를 어제 파일에서 찾아야 한다는 뜻이다. 그래서 파일 이름은
 * 로컬 날짜다.
 */

import { expect, test } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { localDayKey, pruneOldDays, recycleIfFull, resolveDayFile } from "../../src/main/logging";

function tmpdir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), "robo-logs-"));
}

/** 그 날짜의 파일을 주어진 크기로 만든다. */
function seed(dir: string, name: string, bytes = 0): string {
  const file = path.join(dir, name);
  fs.writeFileSync(file, Buffer.alloc(bytes, 0x20));
  return file;
}

test.describe("파일 이름이 로컬 날짜다", () => {
  test("자정 직후와 자정 직전이 같은 날로 묶인다", () => {
    const day = "2026-09-29";
    expect(localDayKey(new Date(2026, 8, 29, 0, 0, 1))).toBe(day);
    expect(localDayKey(new Date(2026, 8, 29, 23, 59, 59))).toBe(day);
  });

  test("KST 오전은 전날로 가지 않는다 — UTC 로 나누면 그렇게 된다", () => {
    // 이 검사는 실행 환경의 시간대에 의존하지 않는다. `localDayKey` 가 로컬
    // 필드(getFullYear/getMonth/getDate)만 쓰는지를 보는 것이다.
    const morning = new Date(2026, 8, 29, 9, 30); // 로컬 9/29 09:30
    expect(localDayKey(morning)).toBe("2026-09-29");
    // 같은 순간을 UTC 로 자르면 시간대에 따라 하루가 밀린다. 그 값이
    // 파일 이름이 되면 안 된다.
    const utcCut = morning.toISOString().slice(0, 10);
    if (morning.getTimezoneOffset() < 0) {
      // 한국(UTC+9)처럼 동쪽이면 UTC 자름이 전날이 될 수 있다.
      expect(localDayKey(morning)).not.toBe(
        new Date(morning.getTime() - 24 * 3600_000).toISOString().slice(0, 10),
      );
    }
    expect(utcCut).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});

test.describe("한 날짜 안에서만 조각낸다", () => {
  test("파일이 없으면 조각 없는 이름을 쓴다", () => {
    const dir = tmpdir();
    expect(path.basename(resolveDayFile(dir, "2026-09-29"))).toBe("desktop-2026-09-29.log");
  });

  test("작은 파일이 있으면 이어 쓴다 — 새 조각을 만들지 않는다", () => {
    const dir = tmpdir();
    seed(dir, "desktop-2026-09-29.log", 1024);
    expect(path.basename(resolveDayFile(dir, "2026-09-29"))).toBe("desktop-2026-09-29.log");
  });

  test("한도를 넘었으면 다음 조각으로 간다", () => {
    const dir = tmpdir();
    seed(dir, "desktop-2026-09-29.log", 20 * 1024 * 1024);
    expect(path.basename(resolveDayFile(dir, "2026-09-29"))).toBe("desktop-2026-09-29-1.log");
  });

  test("조각이 여럿이면 마지막 빈자리를 찾는다", () => {
    const dir = tmpdir();
    const full = 20 * 1024 * 1024;
    seed(dir, "desktop-2026-09-29.log", full);
    seed(dir, "desktop-2026-09-29-1.log", full);
    seed(dir, "desktop-2026-09-29-2.log", 10);
    expect(path.basename(resolveDayFile(dir, "2026-09-29"))).toBe("desktop-2026-09-29-2.log");
  });

  test("다른 날짜 파일은 조각 계산에 끼지 않는다", () => {
    const dir = tmpdir();
    seed(dir, "desktop-2026-09-28.log", 20 * 1024 * 1024);
    expect(path.basename(resolveDayFile(dir, "2026-09-29"))).toBe("desktop-2026-09-29.log");
  });
});

test.describe("오래된 날짜만 지운다", () => {
  const now = new Date(2026, 8, 29, 10, 0);

  test("보존 기간 안은 남긴다", () => {
    const dir = tmpdir();
    seed(dir, "desktop-2026-09-29.log");
    seed(dir, "desktop-2026-09-01.log");
    const removed = pruneOldDays(dir, now, 30);
    expect(removed).toEqual([]);
    expect(fs.readdirSync(dir).sort()).toEqual([
      "desktop-2026-09-01.log",
      "desktop-2026-09-29.log",
    ]);
  });

  test("기간을 넘긴 것은 지운다 — 조각까지 함께", () => {
    const dir = tmpdir();
    seed(dir, "desktop-2026-07-01.log");
    seed(dir, "desktop-2026-07-01-3.log");
    seed(dir, "desktop-2026-09-29.log");
    const removed = pruneOldDays(dir, now, 30).sort();
    expect(removed).toEqual(["desktop-2026-07-01-3.log", "desktop-2026-07-01.log"]);
    expect(fs.readdirSync(dir)).toEqual(["desktop-2026-09-29.log"]);
  });

  test("경계 그 날짜는 남긴다 — 하루 차이로 지우면 사람이 놀란다", () => {
    const dir = tmpdir();
    seed(dir, "desktop-2026-08-30.log"); // now - 30일
    expect(pruneOldDays(dir, now, 30)).toEqual([]);
    expect(fs.readdirSync(dir)).toEqual(["desktop-2026-08-30.log"]);
  });

  // 여기가 이 검사의 핵심이다. 정리 대상을 잘못 넓히면 **남의 파일을 지운다.**
  test("우리 이름이 아닌 파일은 손대지 않는다", () => {
    const dir = tmpdir();
    const keep = [
      "desktop.log", // 옛 형식 — 과거 기록이다
      "desktop.log.1",
      "desktop-2026-09.log", // 날짜가 덜 찼다
      "desktop-not-a-date.log",
      "robo-2026-01-01.log", // 접두사가 다르다
      "notes.txt",
    ];
    for (const n of keep) seed(dir, n);
    expect(pruneOldDays(dir, now, 1)).toEqual([]);
    expect(fs.readdirSync(dir).sort()).toEqual([...keep].sort());
  });

  test("폴더가 없어도 던지지 않는다 — 로깅이 앱을 죽이면 안 된다", () => {
    expect(() => pruneOldDays(path.join(tmpdir(), "nope"), now, 30)).not.toThrow();
  });
});

/**
 * **조각을 다 쓰면 마지막 조각을 비운다** (2026-09-30).
 *
 * 예전에는 한도를 다 쓰면 마지막 조각에 **계속 이어 썼다** — "로그가 커지는 것보다
 * 로그를 잃는 것이 나쁘다" 는 이유였다. 그 문장이 틀렸음이 드러났다: main 프로세스의
 * EPIPE 로그 루프가 마지막 조각을 **1.18GB** 까지 키우고 하루치 로그가 1.6GB 가 됐다.
 * 보존이 30일이니 그런 날 몇 번이면 디스크가 찬다. 사고를 보는 데 필요한 것은
 * **마지막 부분**이므로, 최근 한 조각을 남기고 버리는 편이 낫다.
 */
test.describe("하루치 조각을 다 썼을 때", () => {
  test("한도를 넘은 파일은 비우고 표시를 남긴다", () => {
    const dir = tmpdir();
    const file = path.join(dir, "desktop-2026-09-30-19.log");
    fs.writeFileSync(file, "x".repeat(2048) + "\n");

    const bytes = recycleIfFull(file, 1024);

    const after = fs.readFileSync(file, "utf8");
    expect(after.length, "비우지 않았다 — 이 파일은 무한히 커진다").toBeLessThan(600);
    expect(bytes).toBe(Buffer.byteLength(after, "utf8"));
    const entry = JSON.parse(after.trim());
    expect(entry.event).toBe("logging.day_parts_exhausted");
    // 무엇을 버렸는지 남긴다 — 로그가 갑자기 짧아진 이유를 뒤에서 알 수 있어야 한다.
    expect(entry.data.discardedBytes).toBeGreaterThan(2000);
  });

  test("한도 아래면 손대지 않는다", () => {
    const dir = tmpdir();
    const file = path.join(dir, "desktop-2026-09-30-19.log");
    fs.writeFileSync(file, "keep me\n");

    expect(recycleIfFull(file, 1024)).toBe(8);
    expect(fs.readFileSync(file, "utf8")).toBe("keep me\n");
  });

  test("없는 파일은 0", () => {
    expect(recycleIfFull(path.join(tmpdir(), "nope.log"), 1024)).toBe(0);
  });
});
