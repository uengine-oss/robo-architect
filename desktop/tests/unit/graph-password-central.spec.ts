/**
 * 중앙 모드에서 **비밀번호를 어디서 받는가** (2026-10-02).
 *
 * ## 왜 이 검사가 있나 — 중앙 모드가 한 번도 못 돌던 이유
 *
 * 앱은 두 모드에서 같은 길로 비밀번호를 얻었다 — 이 PC 가 만들어 DPAPI 에 넣어 둔
 * 난수다. bundled 는 볼륨도 이 PC 것이라 맞는다. **중앙은 아니다.** 서버는
 * `compose.central-db.yml` 을 돌린 사람이 정한 값을 쓰고, PC 마다 다른 난수를
 * 서버가 맞춰 줄 길은 없다.
 *
 * 그래서 호스트·포트만 중앙을 가리키고 자격은 이 PC 것이었다. 켜 봤다면
 * **인증 실패로 끝났을 것**이다 — 실제로 로그 38회가 전부 bundled 였다.
 *
 * 여기서 재는 것 —
 *   ① 중앙 모드는 서버가 준 값을 그대로 쓴다
 *   ② 없으면 **멈춘다.** 무엇을 넣어야 하는지 말한다
 *   ③ 공백만 있는 것은 없는 것이다 (그대로 쓰면 빈 비밀번호로 붙는다)
 *   ④ bundled 는 건드리지 않는다 — 이 변수를 봐서는 안 된다
 */

import { expect, test } from "@playwright/test";

import { graphPassword } from "../../src/main/docker-stack";

const central = { mode: "central" as const, host: "10.10.0.5", boltPort: 7687, pgPort: 5432 };

test.afterEach(() => {
  delete process.env.ROBO_GRAPH_PASSWORD;
});

test("중앙 모드는 서버가 준 값을 쓴다", async () => {
  process.env.ROBO_GRAPH_PASSWORD = "server-chosen-value";
  expect(await graphPassword(central)).toBe("server-chosen-value");
});

test("없으면 무엇을 넣어야 하는지 말하고 멈춘다", async () => {
  await expect(graphPassword(central)).rejects.toThrow(/ROBO_GRAPH_PASSWORD/);
  await expect(graphPassword(central)).rejects.toThrow(/compose\.central-db\.yml/);
});

test("공백만 있는 것은 없는 것이다", async () => {
  process.env.ROBO_GRAPH_PASSWORD = "   ";
  await expect(graphPassword(central)).rejects.toThrow(/graph_password_missing/);
});

test("앞뒤 공백은 떼고 쓴다 — 복사·붙여넣기로 들어온다", async () => {
  process.env.ROBO_GRAPH_PASSWORD = "  server-chosen-value\n";
  expect(await graphPassword(central)).toBe("server-chosen-value");
});
