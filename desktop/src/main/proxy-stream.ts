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
