/**
 * 붙잡힌 요청 수가 **누적 요청 수**가 되어 있었다 (2026-10-01 실측).
 *
 * ## 무엇이 있었나
 *
 * main 의 api 프록시는 요청마다 `AbortController` 를 집합에 넣는다. 문서가
 * 통째로 사라지는 하드 리로드에서는 렌더러가 취소해 줄 수 없으니, main 이
 * 대신 끊어 주려는 장치다.
 *
 * 그런데 **끝난 요청도 집합에 남겼다.** SSE 가 헤더 뒤에도 본문을 흘리기
 * 때문인데, 그 예외를 모든 응답에 적용한 셈이다. 그 결과 —
 *
 * ```
 * 00:49  inflight 0
 * 04:10  inflight 651
 * 08:09  inflight 192 (앱을 다시 띄운 뒤 또 오르는 중)   최대 860
 * ```
 *
 * 한 번도 안 내려왔다. 로그 옆 주석은 *"6 에 가까워지면 stalled 가 곧 뜬다"* 라고
 * 말하는데(Chromium 의 호스트당 연결 한도), 860 에서는 **아무 뜻이 없다.**
 * 측정 수단이 거짓말을 하면 그 자리를 다시 못 본다.
 *
 * ## 여기서 재는 것
 *
 *   ① SSE 는 계속 붙잡는다 — 소켓을 무는 장본인이다
 *   ② 보통 응답은 놓는다 — 끝났으면 끊어 줄 것이 없다
 *   ③ 길이를 모른 채 흐르는 것(chunked)도 붙잡는다
 *   ④ 헤더가 없거나 이상해도 터지지 않는다
 */

import { expect, test } from "@playwright/test";

import { isStreamingResponse } from "../../src/main/proxy-stream";

const res = (headers: Record<string, string>) => ({
  headers: { get: (n: string) => headers[n.toLowerCase()] ?? null },
});

test("SSE 는 계속 붙잡는다", () => {
  expect(isStreamingResponse(res({ "content-type": "text/event-stream" }))).toBe(true);
  // charset 이 붙어서 온다 — 정확히 같은 문자열로 비교하면 놓친다.
  expect(
    isStreamingResponse(res({ "content-type": "text/event-stream; charset=utf-8" })),
  ).toBe(true);
});

test("끝난 보통 응답은 놓는다", () => {
  for (const type of [
    "application/json",
    "application/json; charset=utf-8",
    "text/html",
    "application/octet-stream",
  ]) {
    expect(isStreamingResponse(res({ "content-type": type }))).toBe(false);
  }
});

test("길이를 모른 채 흐르는 것도 붙잡는다", () => {
  expect(
    isStreamingResponse(
      res({ "content-type": "application/json", "transfer-encoding": "chunked" }),
    ),
  ).toBe(true);
});

test("헤더가 없어도 터지지 않는다", () => {
  expect(isStreamingResponse(res({}))).toBe(false);
  expect(isStreamingResponse(res({ "content-type": "" }))).toBe(false);
});
