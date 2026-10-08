/**
 * 백엔드가 죽으면 **상한을 두고 되살린다** (STAB-1 ⒝).
 *
 * ## 무엇이 비어 있었나
 *
 * 10/1 저녁에 백엔드가 힙 손상(`0xC0000374`)으로 내려갔고, 그 뒤 앱은 **아무것도
 * 하지 않았다.** 화면은 되살아나지 않고, 사람이 껐다 켜야 했다.
 *
 * 그렇다고 무한히 되살리면 더 나쁘다 — 같은 이유로 계속 죽는 백엔드를 끝없이 다시
 * 띄우면 **로그만 채우고 원인을 가린다.** 그래서 판정은 셋이다.
 *
 * ```
 * ① 되살린다        창 안의 횟수가 상한 이하면
 * ② 멈춘다          넘으면 — 그리고 **왜 멈췄는지** 말한다
 * ③ 잊는다          창 밖의 옛 크래시는 세지 않는다
 * ```
 *
 * 판정을 순수 함수로 떼어 둔 이유가 여기 있다. 타이머와 spawn 에 섞여 있으면
 * **이 셋을 따로 잴 수 없다.**
 */

import { expect, test } from "@playwright/test";

import {
  CRASH_BACKOFF_MS,
  CRASH_RESTART_LIMIT,
  CRASH_WINDOW_MS,
  shouldRestartAfterCrash,
} from "../../src/main/backend";

const NOW = 1_700_000_000_000;

/** `n` 번째 크래시가 방금 일어난 상태의 이력. */
function justCrashed(times: number, spacingMs = 1_000): number[] {
  return Array.from({ length: times }, (_, i) => NOW - (times - 1 - i) * spacingMs);
}

test.describe("상한 안에서는 되살린다", () => {
  for (let n = 1; n <= CRASH_RESTART_LIMIT; n += 1) {
    test(`${n}번째 크래시는 되살린다`, () => {
      const v = shouldRestartAfterCrash(justCrashed(n), NOW);
      expect(v.restart).toBe(true);
      expect(v.recent).toBe(n);
    });
  }

  test("기다리는 시간이 뒤로 갈수록 길어진다 — 즉사하는 고장에 매달리지 않는다", () => {
    const waits = [1, 2, 3].map((n) => shouldRestartAfterCrash(justCrashed(n), NOW).waitMs);
    expect(waits).toEqual([...CRASH_BACKOFF_MS]);
    const [first, , third] = waits;
    // 값이 없으면 0 이 되어 `0 < 0` 으로 **떨어진다** — 통과로 새지 않는다.
    expect(first ?? 0).toBeLessThan(third ?? 0);
  });
});

test.describe("상한을 넘으면 멈춘다", () => {
  test(`${CRASH_RESTART_LIMIT + 1}번째는 안 되살린다`, () => {
    const v = shouldRestartAfterCrash(justCrashed(CRASH_RESTART_LIMIT + 1), NOW);
    expect(v.restart).toBe(false);
    expect(v.recent).toBe(CRASH_RESTART_LIMIT + 1);
  });

  test("한참 더 죽어도 판정은 그대로 '멈춘다' 다", () => {
    expect(shouldRestartAfterCrash(justCrashed(20), NOW).restart).toBe(false);
  });
});

test.describe("창 밖의 크래시는 **세지 않는다**", () => {
  test("어제 세 번 죽은 것이 오늘 한 번을 막지 않는다", () => {
    const old = [1, 2, 3].map((i) => NOW - CRASH_WINDOW_MS - i * 1_000);
    const v = shouldRestartAfterCrash([...old, NOW], NOW);
    expect(v.recent).toBe(1);
    expect(v.restart).toBe(true);
  });

  test("창 경계는 포함하지 않는다 — 정확히 창 길이만큼 지난 것은 밖이다", () => {
    const v = shouldRestartAfterCrash([NOW - CRASH_WINDOW_MS, NOW], NOW);
    expect(v.recent).toBe(1);
  });
});

test("크래시가 없으면 되살릴 일도 없다", () => {
  const v = shouldRestartAfterCrash([], NOW);
  expect(v.recent).toBe(0);
  expect(v.restart).toBe(true); // 판정 자체는 참이지만, 부를 일이 없다
  expect(v.waitMs).toBe(0);
});

test("창과 상한은 **밖에서 바꿀 수 있다** — 검사가 시계를 쥐려면 필요하다", () => {
  const v = shouldRestartAfterCrash(justCrashed(2), NOW, { limit: 1, windowMs: 5_000 });
  expect(v.restart).toBe(false);
});
