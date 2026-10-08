/**
 * 도커가 **있는가 · 없는가 · 모르는가** (spec 058 T030).
 *
 * ## 왜 이 검사가 있나
 *
 * 2026-10-08 에 세었다 — `RuntimeRegistry.setDockerAvailable` 의 **호출자가 0개**였다.
 * 그래서 `dockerAvailable` 은 언제나 `null` 이었고, 화면의 "도커를 준비하세요" 안내는
 * **뜰 수가 없었다.** T030 이 "지금은 패널이 한 줄로 말한다" 고 적혀 있었는데,
 * 그 한 줄조차 나올 수 없는 상태였다.
 *
 * 이 저장소에서 **같은 모양을 다섯 번째**로 본다 — 프로브(호출자 0) ·
 * `serviceId` 를 받고도 안 쓰는 핸들러 · 호출자 0인 `/docx-normalization/status` ·
 * 잡는 쪽이 0개인 `PgUnavailable` · 그리고 이것.
 *
 * ## 두 방향으로 다 틀릴 수 있다
 *
 * ```
 * 안 적으면    꺼져 있는데 **아무 안내도 안 나온다**(지금까지가 그랬다)
 * 넘겨 적으면  데몬이 그 순간 바빴을 뿐인데 **멀쩡한 PC 에 "도커를 실행하세요"** 가 뜬다
 * ```
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { decideDockerAvailability } from "../../src/main/supervision";
import { RuntimeRegistry } from "../../src/main/runtime-state";

test("`docker ps` 가 되면 **있다**", () => {
  expect(decideDockerAvailability(true, true)).toBe(true);
  // info 를 묻지 않았어도(= false 로 넘겨도) ps 가 됐으면 있는 것이다.
  expect(decideDockerAvailability(true, false)).toBe(true);
});

test("둘 다 안 되면 **없다** — 그때만 안내를 띄운다", () => {
  expect(decideDockerAvailability(false, false)).toBe(false);
});

test("ps 는 실패했지만 info 가 되면 **모른다**", () => {
  // 데몬이 그 순간 바빴을 뿐이다. 여기서 `false` 로 떨어뜨리면 멀쩡한 PC 에
  // "Docker Desktop 을 실행하세요" 가 뜬다 — 058 이 세운 규칙을 깨는 자리다.
  expect(decideDockerAvailability(false, true)).toBeNull();
});

test("스냅샷이 그 셋을 **그대로** 들고 간다", () => {
  const registry = new RuntimeRegistry();
  registry.register(["parser"]);

  // 처음은 **모른다** — 아직 아무것도 안 쟨 상태다.
  expect(registry.snapshot().dockerAvailable).toBeNull();

  registry.setDockerAvailable(false);
  expect(registry.snapshot().dockerAvailable).toBe(false);

  registry.setDockerAvailable(true);
  expect(registry.snapshot().dockerAvailable).toBe(true);

  registry.setDockerAvailable(null);
  expect(registry.snapshot().dockerAvailable).toBeNull();
});

test("**배선이 남아 있는가** — 호출자가 0개로 돌아가지 않게", () => {
  // 이 검사가 없으면 그 한 줄을 지워도 아무도 모른다. 지워진 뒤의 증상은
  // "안내가 안 뜬다" 이고, 그건 **아무 오류도 내지 않는다**.
  const source = readFileSync(join(__dirname, "..", "..", "src", "main", "index.ts"), "utf8");
  expect(source).toContain("setDockerAvailable(");
  expect(source).toContain("decideDockerAvailability(");
  // 같은 `docker ps` 로 적는다 — 틱마다 `docker info` 를 또 돌리면 데몬을 때린다.
  expect(source).toContain("listRunningContainers()");
});
