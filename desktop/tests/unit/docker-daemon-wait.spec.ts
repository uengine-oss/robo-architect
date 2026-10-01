/**
 * 도커 엔진을 **기다린다** — 한 번 물어보고 포기하지 않는다.
 *
 * ## 이 검사가 있는 이유 — 2026-10-01 에 실제로 겪었다
 *
 * 도커 엔진이 재시작되는 사이에 앱이 떴다. 그때는 `docker info` 가 이렇게 끝난다 —
 *
 * ```
 * failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine
 * ```
 *
 * 파이프가 아예 없으므로 **15초 타임아웃도 안 쓰고 1초 만에** 실패한다. 앱은 그
 * 한 번으로 `fatal` 이 됐고, 13초 뒤 `app.backend_start_failed` 를 남긴 뒤
 * **아무것도 더 하지 않았다.** 엔진은 46초 뒤 멀쩡히 올라왔는데 앱은 죽은 채로
 * 남아 사람이 다시 띄워야 했다.
 *
 * 도커 데스크톱은 로그인 직후나 엔진 재시작 뒤 30~90초가 보통이다.
 * **그 창을 못 견디면 "껐다 켜면 되는" 실패를 사람에게 떠넘기는 것이다.**
 *
 * 여기서 재는 것 —
 *   ① 늦게 올라오는 엔진을 기다렸다가 성공한다
 *   ② 기다리는 동안 잠든 시간이 실제로 들어간다 (바쁜 대기가 아니다)
 *   ③ 끝내 안 오면 **얼마나 기다렸는지와 원인**을 담아 실패한다
 *   ④ 처음부터 떠 있으면 기다리지 않는다
 */

import { expect, test } from "@playwright/test";

import { awaitDockerDaemon } from "../../src/main/docker-stack";

/** 시계와 잠을 가짜로 — 검사가 2분을 기다리지 않는다. */
function fakeClock() {
  let t = 0;
  const slept: number[] = [];
  return {
    now: () => t,
    sleep: async (ms: number) => {
      slept.push(ms);
      t += ms;
    },
    slept,
    advance: (ms: number) => {
      t += ms;
    },
  };
}

const PIPE_ERROR =
  "docker.command_failed: docker info --format: failed to connect to the docker " +
  "API at npipe:////./pipe/dockerDesktopLinuxEngine";

test("늦게 올라오는 엔진을 기다렸다가 성공한다", async () => {
  const clock = fakeClock();
  let calls = 0;
  const probe = async () => {
    calls += 1;
    if (calls < 15) throw new Error(PIPE_ERROR);   // 약 45초 동안 없다
    return "27.0.3";
  };

  const result = await awaitDockerDaemon(probe, {
    now: clock.now,
    sleep: clock.sleep,
  });

  expect(calls).toBe(15);
  expect(result.attempts).toBe(15);
  // ② 바쁜 대기가 아니다 — 시도 사이에 실제로 잠든다.
  expect(clock.slept.length).toBe(14);
  expect(clock.slept.every((ms) => ms === 3_000)).toBe(true);
  expect(result.waitedMs).toBe(42_000);
});

test("처음부터 떠 있으면 기다리지 않는다", async () => {
  const clock = fakeClock();
  const result = await awaitDockerDaemon(async () => "27.0.3", {
    now: clock.now,
    sleep: clock.sleep,
  });
  expect(result.attempts).toBe(1);
  expect(clock.slept.length).toBe(0);
  expect(result.waitedMs).toBe(0);
});

test("끝내 안 오면 얼마나 기다렸는지와 원인을 담아 실패한다", async () => {
  const clock = fakeClock();
  let calls = 0;
  const probe = async () => {
    calls += 1;
    throw new Error(PIPE_ERROR);
  };

  await expect(
    awaitDockerDaemon(probe, { waitMs: 30_000, now: clock.now, sleep: clock.sleep }),
  ).rejects.toThrow(/docker\.daemon_unavailable: 30초 기다렸지만/);

  // 원인을 삼키지 않는다 — 파이프가 없다는 말이 그대로 실려야 사람이 안다.
  await expect(
    awaitDockerDaemon(probe, { waitMs: 0, now: clock.now, sleep: clock.sleep }),
  ).rejects.toThrow(/dockerDesktopLinuxEngine/);

  // 30초 창에서 3초 간격이면 10번 안쪽이다 — 무한히 두드리지 않는다.
  expect(calls).toBeLessThanOrEqual(12);
});
