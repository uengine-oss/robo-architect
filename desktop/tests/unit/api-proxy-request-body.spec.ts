/**
 * app:// 프록시가 요청 본문을 **어떻게 넘기나** (2026-11-16 Accept 422).
 *
 * 렌더러는 `{comment, forceAcceptWithFailures}` JSON 을 보냈는데 FastAPI 가 본문
 * 검증(422)에 실패했다 — 본문이 비어 도착했다. 프록시는 `request.body` 스트림을
 * `duplex:'half'` 로 흘리고 있었다. 작은 본문은 버퍼로 받아 넘긴다.
 *
 *   ① GET·HEAD·본문 없음 → none
 *   ② Content-Length 가 있고 작다 → buffer
 *   ③ 크다 → stream (업로드)
 *   ④ Content-Length 없음: JSON·text·form → buffer, multipart·octet → stream
 *   ⑤ 이상한 Content-Length 는 stream 으로(터지지 않는다)
 */

import { expect, test } from "@playwright/test";

import { BUFFER_BODY_MAX_BYTES, planRequestBody } from "../../src/main/proxy-stream";

const req = (method: string, headers: Record<string, string>, hasBody = true) => ({
  method,
  hasBody,
  headers: { get: (n: string) => headers[n.toLowerCase()] ?? null },
});

test("본문 없는 요청은 none", () => {
  expect(planRequestBody(req("GET", {}, false))).toBe("none");
  expect(planRequestBody(req("GET", { "content-length": "10" }))).toBe("none");
  expect(planRequestBody(req("head", {}))).toBe("none");
  expect(planRequestBody(req("POST", {}, false))).toBe("none");
});

test("작은 JSON POST(Accept) 는 버퍼로 넘긴다", () => {
  const accept = req("POST", {
    "content-type": "application/json",
    "content-length": "52",
  });
  expect(planRequestBody(accept)).toBe("buffer");
  expect(planRequestBody(req("PUT", { "content-length": "0" }))).toBe("buffer");
  expect(
    planRequestBody(req("POST", { "content-length": String(BUFFER_BODY_MAX_BYTES) })),
  ).toBe("buffer");
});

test("큰 업로드는 스트림 그대로", () => {
  expect(
    planRequestBody(
      req("POST", {
        "content-type": "multipart/form-data; boundary=x",
        "content-length": String(BUFFER_BODY_MAX_BYTES + 1),
      }),
    ),
  ).toBe("stream");
});

test("Content-Length 가 없으면 글 본문만 버퍼, 나머지는 스트림", () => {
  expect(planRequestBody(req("POST", { "content-type": "application/json" }))).toBe("buffer");
  expect(planRequestBody(req("POST", { "content-type": "text/plain;charset=UTF-8" }))).toBe(
    "buffer",
  );
  expect(
    planRequestBody(req("POST", { "content-type": "application/x-www-form-urlencoded" })),
  ).toBe("buffer");
  expect(
    planRequestBody(req("POST", { "content-type": "multipart/form-data; boundary=x" })),
  ).toBe("stream");
  expect(planRequestBody(req("POST", { "content-type": "application/octet-stream" }))).toBe(
    "stream",
  );
  expect(planRequestBody(req("POST", {}))).toBe("stream");
});

test("이상한 Content-Length 는 스트림으로 둔다", () => {
  expect(planRequestBody(req("POST", { "content-length": "abc" }))).toBe("stream");
  expect(planRequestBody(req("POST", { "content-length": "-1" }))).toBe("stream");
  expect(planRequestBody(req("POST", { "content-length": " " }))).toBe("stream");
});
