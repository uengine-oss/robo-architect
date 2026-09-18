/**
 * 프로브가 쓰는 낮은 수준 도구 (spec 058 T021).
 *
 * **전부 예외를 삼키지 않고 갈라서 돌려준다.** 09-17 에 프로브 안의 `try/except` 가
 * import 실패를 삼켜 조용히 빈 값을 냈고, 그것을 앱의 결함으로 두 번 기록할 뻔했다.
 * "연결이 안 된다"와 "응답이 왔는데 코드가 이상하다"는 다른 사실이다.
 */

import { execFile } from "node:child_process";
import net from "node:net";

import type { ProbeOutcome } from "../../shared/runtime-contract";

export const DEFAULT_TIMEOUT_MS = 3000;

export interface Reached {
  /** `"pass"` = 응답이 왔다(코드 판정은 호출자 몫) · `"error"` = 닿지 못했다. */
  outcome: Extract<ProbeOutcome, "pass" | "error">;
  detail: string;
  /** 응답이 온 경우의 HTTP 코드. */
  code?: number;
}

/**
 * HTTP 왕복. **4xx·5xx 도 "닿았다"다** — 서비스는 답한 것이다.
 *
 * 절대 코드로 판정하면 안 되는 자리가 있다. `/api/gateway/antlr/` 는 500 이 정상일
 * 수 있다(parser 직접 호출도 500 이므로). 그래서 여기서는 **코드를 판정하지 않고
 * 돌려준다.**
 */
export async function httpReach(url: string, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<Reached> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { signal: controller.signal, redirect: "manual" });
    return { outcome: "pass", detail: String(response.status), code: response.status };
  } catch (error) {
    return { outcome: "error", detail: reason(error) };
  } finally {
    clearTimeout(timer);
  }
}

/**
 * 포트가 답하는가.
 *
 * `nc -z` 와 셸의 `/dev/tcp` 를 쓰지 않는다 — 전자는 IPv6 바인딩에서 거짓 음성을 내고,
 * 후자는 `CMD-SHELL` 의 dash 에 아예 없다(09-17 에 멀쩡한 Bolt 가 unhealthy 로 떴다).
 */
export function portOpen(host: string, port: number, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    const done = (value: boolean) => {
      socket.destroy();
      resolve(value);
    };
    socket.setTimeout(timeoutMs);
    socket.once("connect", () => done(true));
    socket.once("timeout", () => done(false));
    socket.once("error", () => done(false));
    socket.connect(port, host);
  });
}

function run(command: string, args: string[], timeoutMs: number): Promise<{ code: number; out: string }> {
  return new Promise((resolve) => {
    execFile(command, args, { timeout: timeoutMs, encoding: "utf8" }, (error, stdout, stderr) => {
      const out = `${stdout ?? ""}${stderr ?? ""}`;
      // execFile 의 error.code 는 신호일 수도 있다. 숫자가 아니면 1 로 본다.
      const code = error ? (typeof (error as { code?: unknown }).code === "number" ? (error as { code: number }).code : 1) : 0;
      resolve({ code, out });
    });
  });
}

export async function dockerAvailable(): Promise<boolean> {
  const { code } = await run("docker", ["info", "--format", "{{.ServerVersion}}"], 10_000);
  return code === 0;
}

/**
 * 컨테이너 **안에서** HTTP 코드를 얻는다 — 호스트에 포트를 안 연 서비스를 재려고.
 *
 * 이미지마다 든 도구가 다르다. parser·gateway 는 Java 이미지라 `python` 이 없고
 * `curl` 이 있다(compose healthcheck 도 그쪽만 curl 을 쓴다). **둘 다 없으면 `fail`
 * 이 아니라 `error` 다** — 서비스가 안 되는 게 아니라 우리가 못 잰 것이다.
 */
export async function containerHttpReach(
  containerName: string,
  url: string,
  timeoutMs = 15_000,
): Promise<Reached> {
  const script =
    "import urllib.request,urllib.error,sys\n" +
    `try: print(urllib.request.urlopen('${url}',timeout=3).status)\n` +
    "except urllib.error.HTTPError as e: print(e.code)\n" +
    "except Exception as e: print('ERR:'+type(e).__name__); sys.exit(3)\n";
  const attempts: Array<[string, string[]]> = [
    ["docker", ["exec", containerName, "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "3", url]],
    ["docker", ["exec", containerName, "python", "-c", script]],
  ];
  const missing: string[] = [];
  for (const [command, args] of attempts) {
    const { code, out } = await run(command, args, timeoutMs);
    if (out.includes("executable file not found")) {
      missing.push(args[2] ?? "?");
      continue;
    }
    const text = out.trim();
    if (code !== 0 || text.startsWith("ERR:") || !/^\d{3}$/.test(text)) {
      return { outcome: "error", detail: text || `exit=${code}` };
    }
    return { outcome: "pass", detail: text, code: Number(text) };
  }
  return { outcome: "error", detail: `컨테이너에 잴 도구가 없다: ${missing.join(", ")}` };
}

/** 컨테이너 안에서 명령을 돌려 종료 코드를 본다. 파일 쓰기 가능 여부 같은 것. */
export async function containerExec(
  containerName: string,
  argv: string[],
  timeoutMs = 15_000,
): Promise<{ code: number; out: string }> {
  return run("docker", ["exec", containerName, ...argv], timeoutMs);
}

/**
 * 왜 닿지 못했는지.
 *
 * **이름만 남기면 쓸모가 없다.** `fetch` 는 연결 거부도 `TypeError` 로 던지고 이름에는
 * 아무 정보가 없다 — 2026-09-18 에 죽어 있는 서비스의 상세가 `TypeError` 한 단어로
 * 나왔고, 그것으로는 "포트가 안 열렸다"와 "주소가 틀렸다"를 가릴 수 없었다.
 * 원인 체인의 `code`(ECONNREFUSED·ENOTFOUND·…)까지 꺼낸다.
 */
function reason(error: unknown): string {
  if (!(error instanceof Error)) return "unknown";
  // AbortError 를 "타임아웃"으로 부른다 — 이름만 남기면 왜 끊겼는지 안 보인다.
  if (error.name === "AbortError") return "timeout";
  const codes: string[] = [];
  let cursor: unknown = error;
  for (let depth = 0; depth < 4 && cursor instanceof Error; depth += 1) {
    const code = (cursor as { code?: unknown }).code;
    if (typeof code === "string" && !codes.includes(code)) codes.push(code);
    cursor = (cursor as { cause?: unknown }).cause;
  }
  return codes.length > 0 ? `${error.name}(${codes.join("/")})` : error.name;
}
