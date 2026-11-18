/**
 * api 프록시가 **무엇을 계속 붙잡아야 하는가**.
 *
 * `index.ts` 에서 떼어 둔다 — 그 파일은 불러오는 순간 Electron 부트스트랩
 * (`protocol.registerSchemesAsPrivileged`)이 돌아 검사에서 쓸 수 없다.
 * 판단만 따로 두면 검사가 Electron 없이 돌고, 이 규칙이 한 자리에 남는다.
 */

/**
 * 응답이 **헤더 뒤에도 계속 흐르는가.** 그런 것만 문서 전환 때까지 붙잡아 둔다.
 *
 * 이 앱에서 소켓을 오래 무는 것은 SSE(`text/event-stream`)다. 덤으로 chunked
 * 스트림도 같게 본다 — 길이를 모른 채 흐르는 것은 끊어 줄 주체가 필요하다.
 */
export function isStreamingResponse(response: {
  headers: { get(name: string): string | null };
}): boolean {
  const type = (response.headers.get("content-type") ?? "").toLowerCase();
  if (type.includes("text/event-stream")) return true;
  const encoding = (response.headers.get("transfer-encoding") ?? "").toLowerCase();
  return encoding.includes("chunked");
}

/**
 * 이보다 작은 요청 본문은 **버퍼로 받아 넘긴다**(바이트). 그 위는 스트림 그대로.
 * 한 화면이 보내는 JSON 은 수 KB 다 — 1 MiB 면 업로드만 스트림으로 남는다.
 */
export const BUFFER_BODY_MAX_BYTES = 1024 * 1024;

export type RequestBodyPlan = "none" | "buffer" | "stream";

/**
 * 요청 본문을 **어떻게 넘길지**.
 *
 * 2026-11-16 Accept 422: 렌더러는 멀쩡한 JSON 을 보냈는데 상류(FastAPI)가 본문
 * 검증에 실패했다 — 본문이 비어 도착했다는 뜻이다. 프록시가 `request.body`
 * (ReadableStream)를 `duplex:'half'` 로 그대로 흘리고 있었고, 원본
 * Content-Length 는 그대로 간다. 그래서 작은 본문은 다 읽어(arrayBuffer)
 * 길이가 확정된 바이트로 넘긴다.
 *
 *   - 본문 없음(GET·HEAD, 본문 스트림 없음)          → "none"
 *   - Content-Length 가 있고 한도 이하                 → "buffer"
 *   - Content-Length 없음 + 글 본문(JSON·text·form)      → "buffer"
 *       Chromium 이 protocol 처리기에 Content-Length 를 안 실어 줄 수 있다.
 *       그때 전부 스트림으로 두면 이 고침이 아무것도 안 고친다 — 글 본문은
 *       업로드가 아니므로 버퍼로 받는다.
 *   - Content-Length 없음(그 밖) 또는 한도 초과         → "stream" (큰 업로드)
 */
export function planRequestBody(request: {
  method: string;
  hasBody: boolean;
  headers: { get(name: string): string | null };
}): RequestBodyPlan {
  const method = request.method.toUpperCase();
  if (!request.hasBody || method === "GET" || method === "HEAD") return "none";
  const raw = request.headers.get("content-length");
  if (raw === null || raw.trim() === "") {
    return isTextualBody(request.headers.get("content-type")) ? "buffer" : "stream";
  }
  const length = Number(raw);
  if (!Number.isFinite(length) || length < 0) return "stream";
  return length <= BUFFER_BODY_MAX_BYTES ? "buffer" : "stream";
}

/** 업로드가 아닌 "글" 본문인가 — multipart·octet-stream 은 아니다. */
function isTextualBody(contentType: string | null): boolean {
  const t = (contentType ?? "").toLowerCase();
  return (
    t.includes("application/json") ||
    t.includes("+json") ||
    t.startsWith("text/") ||
    t.includes("application/x-www-form-urlencoded")
  );
}
