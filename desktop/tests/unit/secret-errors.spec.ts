/**
 * 비밀 저장소를 못 열 때 **사람이 무엇을 할 수 있는가** (ENT-APP-002).
 *
 * ## 여기서 재는 것
 *
 * 이 오류는 고객이 실제로 만난다 — 재설치, PC 이전, Windows 계정 변경, 백업에
 * `Local State` 를 빠뜨린 경우. 2026-09-28 설치 검증에서 우리가 먼저 겪었고, 그때
 * 화면에 뜬 것은 드라이버 원문이었다.
 *
 *     Error while decrypting the ciphertext provided to safeStorage.decryptString.
 *
 * **이 문장으로는 아무도 고칠 수 없다.** 그래서 메시지가 넷을 갖추는지 잰다 —
 * 무엇이 잘못됐는지 · 왜 그런지 · 데이터는 어떤지 · 무엇을 해야 하는지.
 *
 * 특히 세 번째가 중요하다. "열 수 없다" 만 보면 사용자는 **데이터가 날아갔다고
 * 읽고** 앱을 지운다. 실제로는 볼륨이 멀쩡하다.
 */

import { expect, test } from "@playwright/test";

import { SecretUndecryptableError, buildMessage } from "../../src/main/secret-errors";

const ID = "runtime.docker.graph.password";
const FILE = "C:\\Users\\hong\\AppData\\Roaming\\robo-architect-desktop\\secrets\\x.bin";

test.describe("메시지가 사람을 움직일 수 있는가", () => {
  const message = buildMessage(ID, FILE);

  test("① 무엇이 — 어느 비밀인지 대고, 파일 위치를 준다", () => {
    expect(message).toContain(ID);
    expect(message).toContain(FILE);
  });

  test("② 왜 — 짚이는 상황을 댄다", () => {
    // 이 셋이 실제 원인의 거의 전부다. 하나라도 빠지면 자기 상황을 못 찾는다.
    expect(message).toContain("다시 설치");
    expect(message).toMatch(/PC.*계정|계정.*옮/);
    expect(message).toContain("Local State");
  });

  test("③ 데이터는 — **지워지지 않았다**고 분명히 말한다", () => {
    expect(message).toContain("데이터는 지워지지 않았습니다");
    expect(message).toContain("볼륨은 그대로");
  });

  test("④ 무엇을 — 복구 절차가 어디 있는지 가리킨다", () => {
    expect(message).toContain("app-operations.md");
  });

  test("드라이버 원문을 그대로 쓰지 않는다", () => {
    expect(message).not.toContain("safeStorage.decryptString");
    expect(message).not.toContain("ciphertext provided");
  });
});

test.describe("오류 객체", () => {
  test("code 로 가를 수 있다 — 문자열 비교에 기대지 않는다", () => {
    const error = new SecretUndecryptableError(ID, FILE);
    expect(error.code).toBe("secret_store.undecryptable");
    expect(error.name).toBe("SecretUndecryptableError");
    expect(error).toBeInstanceOf(Error);
  });

  test("원인을 버리지 않는다 — 진단은 로그에 남아야 한다", () => {
    const root = new Error("DPAPI 실패");
    const error = new SecretUndecryptableError(ID, FILE, root);
    expect(error.cause).toBe(root);
  });

  test("원인이 없으면 cause 를 만들지 않는다", () => {
    expect(new SecretUndecryptableError(ID, FILE).cause).toBeUndefined();
  });

  test("message 가 buildMessage 와 같다 — 두 곳에서 문장을 만들지 않는다", () => {
    expect(new SecretUndecryptableError(ID, FILE).message).toBe(buildMessage(ID, FILE));
  });
});
