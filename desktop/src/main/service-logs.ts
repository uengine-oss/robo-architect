/**
 * 고장 난 서비스의 **로그를 그 자리에서 읽게** 한다 (spec 058 US1 · T028 의 남은 반).
 *
 * ## 왜 필요한가
 *
 * 패널은 이미 이름과 이유를 말한다 — "LLM 자격증명이 거부됨 (401)". 그런데 그다음
 * 한 걸음이 없었다: 버튼이 **탐색기로 로그 폴더를 열 뿐**이었고(`openDiagnostics` 는
 * `serviceId` 를 받고도 쓰지 않았다), 받는 사람은 도커를 모르고 물어볼 사람이 없다.
 * 폴더를 열어 줘도 **어느 파일의 어느 줄**인지 모른다.
 *
 * 2026-10-07 저녁에 그 간격이 그대로 드러났다 — pdf2bpmn 이 `ready` 뒤에 내려가
 * 감독이 `failed` 로 바꿨고, **왜** 는 `docker logs` 를 사람이 쳐서야 나왔다
 * ("Shutting down" · "Application shutdown complete" — 사용자가 알림을 시험하려고
 * 내린 것이었다). 그 줄이 화면에 있었으면 **묻지 않고도** 알았다.
 *
 * ## 갈래가 셋이다 — 서비스마다 로그가 있는 자리가 다르다
 *
 * ```
 * 컨테이너 8개   `docker logs --tail N <이름>` (stdout+stderr)
 * architect     **호스트 프로세스**다. 컨테이너가 없으니 앱 로그의
 *               `backend.stdout`·`backend.stderr` 줄을 모은다
 * graph         중앙 모드에서는 **밖에서 돈다**(`owner: "external"`) — 우리가 띄운
 *               것이 아니라 로그가 없다. **없다고 말하는 것**이 맞는 답이다
 * ```
 *
 * ## 비밀 값은 가린다
 *
 * 로그를 화면에 띄우는 것은 **노출면을 늘리는 일**이다(058 T067). 그래서 규칙을
 * 먼저 정하고, 그 규칙을 단위 검사로 건다.
 *
 * ```
 * ① 이름이 비밀스러운 키의 값   password·secret·token·key·authorization·cookie·dsn
 *                           → `***(12자)` — **길이만** 남긴다(지문도 안 남긴다)
 * ② Bearer 토큰              `Bearer ***`
 * ③ 모양이 뚜렷한 토큰         `sk-…` · `ghp_…` · `xox?-…` · JWT(`eyJ…`)
 * ④ 접속 문자열의 비밀번호      `scheme://user:***@host`
 * ```
 *
 * **긴 16진 문자열은 가리지 않는다.** 커밋 해시·컨테이너 id 가 거기 들어가고, 그것이
 * 진단의 근거다. 넓게 가리면 로그가 쓸모를 잃는다 — 가리는 범위도 **좁게** 둔다.
 *
 * ## 판정은 여기서 하지 않는다
 *
 * 어떤 줄이 "중요한가" 는 열어 보는 사람이 정한다. 여기서는 **눈에 먼저 걸릴 줄**을
 * 골라 위로 올릴 뿐이고(`highlights`), 전문은 그대로 같이 준다. 오류만 고르지 않는
 * 이유는 위의 10/7 사례다 — 그때 답은 오류가 아니라 **"끝났다" 는 줄**이었다.
 */

import type { LogSource, ManagedServiceId, ServiceLogs } from "../shared/runtime-contract";

/** 한 번에 읽는 줄 수. 넘기면 화면이 멈추고, 적으면 원인이 잘린다. */
export const DEFAULT_TAIL = 200;
export const MAX_TAIL = 1000;

// ---------------------------------------------------------------------------
// 가리기
// ---------------------------------------------------------------------------

const SECRET_KEY = /(pass(word|wd)?|secret|token|api[_-]?key|key|authorization|auth|cookie|dsn)/i;

/** `key=value` · `key: value` · `"key":"value"` 의 **값만** 길이로 바꾼다. */
function maskKeyedValues(line: string): string {
  // "key":"value"  /  "key": "value"
  let out = line.replace(/"([A-Za-z0-9_.-]{2,40})"\s*:\s*"([^"]{1,4096})"/g, (whole, key, value) =>
    SECRET_KEY.test(key) && !alreadySafe(value) ? `"${key}":"${redact(value)}"` : whole,
  );
  // key=value  /  key: value   (공백·줄끝·따옴표·쉼표에서 끊는다)
  out = out.replace(
    /\b([A-Za-z0-9_.-]{2,40})\s*[=:]\s*("?)([^\s"',;]{1,4096})\2/g,
    (whole, key, quote, value) =>
      SECRET_KEY.test(key) && !alreadySafe(value)
        ? `${key}${whole.includes("=") ? "=" : ": "}${quote}${redact(value)}${quote}`
        : whole,
  );
  return out;
}

/** 이미 가려졌거나, 비밀이 아닌 표시(스킴 이름)인가. */
function alreadySafe(value: string): boolean {
  return value.startsWith("***") || AUTH_SCHEME_WORD.test(value);
}

/** 값을 **길이만** 남긴다. 앞자리도 안 남긴다 — 짧은 값은 앞자리가 곧 값이다. */
function redact(value: string): string {
  return `***(${value.length}자)`;
}

// 인증 스킴 뒤의 값. `Authorization` 키 규칙보다 **먼저** 돌아야 한다 — 안 그러면
// 스킴 이름("Bearer")이 값으로 잡혀 가려지고, 정작 **읽어야 할 표시**가 사라진다.
const AUTH_SCHEME_VALUE = /\b(Bearer|Basic|Digest|Token)\s+[A-Za-z0-9._~+/=-]{4,}/gi;
/** 스킴 이름 자체는 비밀이 아니다 — 위 규칙이 이미 그 뒤를 가렸다. */
const AUTH_SCHEME_WORD = /^(Bearer|Basic|Digest|Token)$/i;
const SHAPED_TOKEN = /\b(sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{8,}|xox[baprs]-[A-Za-z0-9-]{8,}|eyJ[A-Za-z0-9._-]{16,})/g;
const URL_PASSWORD = /\b([a-z][a-z0-9+.-]*:\/\/[^\s:/@]+):([^\s@]+)@/gi;

/**
 * 한 줄을 가린다. **좁게** 가린다 — 커밋 해시·컨테이너 id 같은 긴 16진 문자열은
 * 그대로 둔다(그게 진단의 근거다).
 */
export function maskSecrets(line: string): string {
  // **순서가 규칙의 일부다.** 모양이 뚜렷한 것을 먼저 가리고, 남은 것을 키 이름으로
  // 가린다. 거꾸로 하면 `Authorization: Bearer …` 에서 "Bearer" 가 값으로 잡힌다.
  let out = line.replace(AUTH_SCHEME_VALUE, (_whole, scheme) => `${scheme} ***`);
  out = out.replace(SHAPED_TOKEN, (token) => redact(token));
  out = out.replace(URL_PASSWORD, (_whole, head, password) => `${head}:${redact(password)}@`);
  return maskKeyedValues(out);
}

// ---------------------------------------------------------------------------
// 눈에 먼저 걸릴 줄
// ---------------------------------------------------------------------------

const NOTABLE = [
  // 오류.
  //
  // **낱말 경계를 쓰지 않는다.** 기술 로그의 말은 붙어서 온다 — 2026-10-08 실측:
  // `\bexception\b` 가 `NoResourceFoundException` 을 **못 잡아서** 스택 43줄을 든
  // 원인 줄이 안 뽑혔다(뽑힌 것은 그 위의 "Unhandled exception" 한 줄뿐이었다).
  // 같은 이유로 `IOError`·`SQLException`·`ConnectTimeout` 도 놓친다.
  /error|errno|exception|throwable|traceback|fatal|critical|panic|segfault/i,
  /refus|denied|unauthoriz|forbidden|timed?\s*out|timeout|unreachable/i,
  /fail(ed|ure|s|ing)?/i,
  /\bHTTP\/\d(\.\d)?"?\s+(4\d\d|5\d\d)\b/,
  // **끝난 이유** — 10/7 의 답이 여기였다.
  //
  // 어간으로 잡는다. 처음엔 `shutdown complete` 로 적었는데 실제 로그는
  // `Shutdown completed.` 였고 `complete\b` 가 **completed 를 못 잡았다**
  // (2026-10-08, parser 로그에서 걸렸다). 말끝은 서비스마다 다르다.
  /shut\s?down|shutting\s+down/i,
  /\b(stopp(ed|ing)|terminat\w*|kill(ed)?|aborted?|oom)\b/i,
  /\bexit(ed|ing|\s+code|\s+status)?\b/i,
  // 자격·설정
  /\b(invalid|missing|not found|no such)\b/i,
];

export function isNotable(line: string): boolean {
  return NOTABLE.some((pattern) => pattern.test(line));
}

/**
 * **앞이 잘린 덩이**인가 — 첫 줄이 이어짐 모양이면 머리(원인 줄)가 없다.
 *
 * `--tail 200` 은 스택 **중간을** 자른다. 그러면 남은 `at …` 들이 붙을 앞 줄을 못 찾아
 * 자기들끼리 한 덩이가 되고, 그 안의 클래스 이름 하나(`ErrorReportValve`) 때문에
 * **눈에 걸린 줄로 올라온다.** 2026-10-08 사용자 화면의 맨 위가 그것이었다 —
 *
 * ```
 * 05:42:22 	at org.apache.catalina.core.ApplicationFilterChain.doFilter(…)   ← 원인이 없다
 * ```
 *
 * 어제 낱말 경계를 뺀 고침(§161 ③)의 뒷면이다. 조각은 **원인을 말할 수 없으니**
 * 고를 때 뒤로 민다(전문에는 그대로 남는다).
 */
export function isSevered(chunk: string): boolean {
  const first = chunk.split("\n", 1)[0] ?? "";
  return CONTINUATION.test(first.replace(/^\d{2}:\d{2}:\d{2}\s/, ""));
}

/**
 * 전문에서 눈에 걸릴 줄만. **마지막 것들**을 우선한다 — 원인은 보통 끝에 있다.
 *
 * 앞이 잘린 조각은 **온전한 것이 하나라도 있으면** 빼고, 없으면 넣는다 — 조각뿐일 때
 * 아무것도 안 보여주면 "로그가 없다" 로 읽힌다(그건 거짓이다).
 */
export function pickHighlights(lines: string[], limit = 12): string[] {
  const hits = lines.filter(isNotable);
  const whole = hits.filter((chunk) => !isSevered(chunk));
  const chosen = whole.length > 0 ? whole : hits;
  return chosen.slice(Math.max(0, chosen.length - limit));
}

export function normalizeTail(tail: number | undefined): number {
  if (!Number.isFinite(tail as number)) return DEFAULT_TAIL;
  return Math.min(MAX_TAIL, Math.max(1, Math.trunc(tail as number)));
}

// ---------------------------------------------------------------------------
// 어디서 읽을 것인가
// ---------------------------------------------------------------------------

export interface LogSourcePlan {
  source: LogSource;
  containerName: string | null;
  note: string | null;
}

export interface PlanInput {
  serviceId: ManagedServiceId;
  /** 그 서비스의 compose 컨테이너 후보 이름. */
  candidates: string[];
  /** 지금 **있는** 컨테이너 이름(멈춘 것도 포함). 못 얻었으면 `null` = 모른다. */
  present: string[] | null;
  /** 앱 소유가 아니면 `"external"`. */
  owner: "app" | "external";
  dockerAvailable: boolean;
}

/**
 * 읽을 자리를 정한다. **못 읽는 경우마다 다른 말**을 준다 — "없다" 와 "모른다" 와
 * "밖에 있다" 는 사용자에게 전혀 다른 사실이다.
 */
export function planSource(input: PlanInput): LogSourcePlan {
  if (input.serviceId === "architect") {
    return { source: "backend", containerName: null, note: null };
  }
  if (input.owner === "external") {
    return {
      source: "external",
      containerName: null,
      note: "이 서비스는 이 PC 가 띄운 것이 아닙니다(중앙 모드). 로그는 그 기계에 있습니다.",
    };
  }
  if (!input.dockerAvailable) {
    return {
      source: "unavailable",
      containerName: null,
      note: "컨테이너 실행 환경(Docker)이 응답하지 않아 로그를 읽지 못했습니다.",
    };
  }
  // 멈춘 컨테이너의 로그도 읽어야 한다 — **그게 가장 알고 싶은 자리다.**
  const found = input.present
    ? input.candidates.find((name) => input.present!.includes(name))
    : input.candidates[0];
  if (!found) {
    return {
      source: "unavailable",
      containerName: null,
      note: "컨테이너가 아직 만들어지지 않아 로그가 없습니다.",
    };
  }
  return { source: "container", containerName: found, note: null };
}

// ---------------------------------------------------------------------------
// 모으기
// ---------------------------------------------------------------------------

export interface ReadDeps {
  candidatesOf(serviceId: ManagedServiceId): string[];
  ownerOf(serviceId: ManagedServiceId): "app" | "external";
  dockerAvailable(): Promise<boolean>;
  /** 멈춘 것까지 포함한 컨테이너 이름. 못 얻으면 `null`. */
  presentContainers(): Promise<string[] | null>;
  /** `docker logs -t --tail` 의 **갈라진 두 흐름**. 합치는 것은 이 모듈이 한다. */
  containerLogs(containerName: string, tail: number): Promise<{ stdout: string; stderr: string }>;
  /** 앱 로그에서 백엔드가 낸 줄만. */
  backendLines(tail: number): Promise<string[]>;
}

export async function readServiceLogs(
  deps: ReadDeps,
  serviceId: ManagedServiceId,
  tailInput?: number,
): Promise<ServiceLogs> {
  const tail = normalizeTail(tailInput);
  const owner = deps.ownerOf(serviceId);

  // **도커를 묻지 않아도 되는 둘을 먼저 가른다.** 호스트 프로세스와 밖에서 도는 것은
  // 컨테이너가 없으니, 거기서 `docker ps` 를 돌리면 아무 쓸모 없이 데몬을 때린다.
  let plan: LogSourcePlan;
  if (serviceId === "architect" || owner === "external") {
    plan = planSource({ serviceId, candidates: [], present: [], owner, dockerAvailable: true });
  } else {
    const dockerUp = await deps.dockerAvailable();
    plan = planSource({
      serviceId,
      candidates: deps.candidatesOf(serviceId),
      present: dockerUp ? await deps.presentContainers() : null,
      owner,
      dockerAvailable: dockerUp,
    });
  }

  let raw: string[] = [];
  if (plan.source === "container" && plan.containerName) {
    const streams = await deps.containerLogs(plan.containerName, tail);
    raw = mergeStreams(streams.stdout, streams.stderr, tail);
  } else if (plan.source === "backend") {
    raw = await deps.backendLines(tail);
  }

  const lines = raw.map(maskSecrets);
  return {
    serviceId,
    source: plan.source,
    containerName: plan.containerName,
    lines,
    highlights: pickHighlights(lines),
    note:
      plan.note ??
      (lines.length === 0 ? "로그에 남은 줄이 없습니다 — 아직 아무것도 안 찍혔습니다." : null),
  };
}

/** `2026-10-08T02:11:49.136248977Z ` 꼴 머리. `docker logs -t` 가 붙인다. */
const STAMPED = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d+)?Z\s?(.*)$/;

/**
 * 서비스가 **이미 시각을 찍고 있는가**.
 *
 * 2026-10-08 실측 — parser(Spring Boot)는 `04:08:11 Closing JPA …` 로 찍는다. 거기에
 * 우리 시각을 또 붙이면 `04:08:11 04:08:11 Closing JPA …` 가 된다(사용자가 화면에서
 * 그걸 봤다). 도커 시각은 **정렬에만** 쓰고, 보여줄 때는 겹치지 않게 한다.
 */
const SELF_CLOCKED = /^\d{2}:\d{2}:\d{2}([.,]\d+)?\s/;

/**
 * **앞 줄의 이어짐**인가 — 모양으로 가른다.
 *
 * 처음에는 "도커 시각이 없는 줄" 을 이어짐으로 봤다. 그런데 `-t` 는 **모든 줄에**
 * 시각을 붙인다 — 자바 스택의 `\tat org.apache…` 한 줄 한 줄이 각자 시각을 받는다.
 * 그래서 그 규칙은 컨테이너 로그에서 **한 번도 안 먹었고**, "Unhandled exception" 만
 * 뽑히고 **원인(스택)이 안 따라왔다**(2026-10-08, 사용자 화면).
 *
 * 이어짐은 시각의 문제가 아니라 **줄의 모양**이다.
 */
// `\s+` 가 탭도 먹는다 — 따로 적던 `\u0009` 는 **같은 것을 두 번** 적은 것이었다(지웠다).
const CONTINUATION = /^(\s+|at\s|Caused by:|Suppressed:|\.\.\.\s*\d+\s+more)/;

/**
 * **예외 이름만 적힌 줄**인가 — `org.…NoResourceFoundException: No static resource …`
 * 또는 `ValueError: boom`.
 *
 * 이 줄은 들여쓰기도 `at ` 도 없어서 이어짐이 아니다. 그래서 앞 줄과 떨어진다.
 * 그런데 실제 로그에서 **원인은 거의 늘 이 줄**이고, 그 앞 줄은 `Unhandled exception`
 * 처럼 **아무것도 안 말하는 머리**다 — 2026-10-08 사용자 화면에서 고른 줄 둘이 한
 * 사건이었고, 어느 것이 어느 것의 원인인지 안 보였다.
 *
 * 이름이 `:` 나 줄끝으로 끝나는 것만 본다 — 그래야 평범한 문장("ErrorHandler
 * started")을 안 집는다.
 */
const EXCEPTION_HEAD = /^(?:[\w$]+\.)*[A-Z][\w$]*(?:Exception|Error|Throwable)(?=\s*(?::|$))/;

/** 그 덩이가 **스택을 열어 둔 채** 끝났나 — 마지막 줄이 이어짐 모양이면 그렇다. */
function stackIsOpen(text: string): boolean {
  const lines = text.split("\n");
  return CONTINUATION.test(lines[lines.length - 1] ?? "");
}

/**
 * 두 흐름을 **시각으로** 합친다.
 *
 * ## 왜 — 이어 붙이면 시간이 뒤집힌다
 *
 * 2026-10-08 에 사용자가 화면에서 그걸 봤다. 방금 찍힌 `healthz 200` 네 줄 **아래에**
 * 한참 전의 "Started server process" 가 깔려 있었다. `docker logs` 가 stdout 과
 * stderr 를 갈라 주는데 우리가 `stdout + stderr` 로 이어 붙였기 때문이다
 * (실측: 접속 로그 109줄이 stdout · 기동 메시지 4줄이 stderr).
 *
 * 시각은 `HH:MM:SS` 로 짧게 남긴다. **앱 로그와 같은 UTC** 라 두 기록을 나란히 읽을
 * 수 있다 — "앱이 degraded 로 바꾼 그 시각에 컨테이너는 뭘 하고 있었나" 가 그걸로 붙는다.
 *
 * 시각이 없는 줄(여러 줄짜리 traceback 의 둘째 줄 이후)은 **앞 줄에 붙여** 둔다.
 * 따로 떼어 정렬하면 traceback 이 흩어져 못 읽는다.
 */
export function mergeStreams(stdout: string, stderr: string, limit = DEFAULT_TAIL): string[] {
  const rows: { at: string; order: number; text: string }[] = [];
  let order = 0;
  for (const chunk of [stdout, stderr]) {
    let last: { at: string; order: number; text: string } | null = null;
    for (const line of chunk.split(/\r?\n/)) {
      const trimmed = line.replace(/\s+$/, "");
      if (!trimmed) continue;
      const matched = STAMPED.exec(trimmed);
      const at = matched?.[1] ?? "";
      const body = matched ? (matched[2] ?? "") : trimmed;

      // 예외 이름 줄은 **앞의 머리에 붙인다** — 단 앞 줄이 오류를 말하고 있고,
      // 아직 한 줄뿐이거나(자바의 `Unhandled exception`) 스택을 열어 둔 채 끝났을
      // 때만(파이썬의 `Traceback …` + 들여쓴 줄들). 그래야 평범한 줄 뒤에 온
      // 예외가 **없던 인과를 만들지** 않는다.
      const joinsHead =
        last &&
        EXCEPTION_HEAD.test(body) &&
        isNotable(last.text) &&
        (!last.text.includes("\n") || stackIsOpen(last.text));

      if (last && (joinsHead || CONTINUATION.test(body))) {
        // **모양으로** 이어 붙인다 — 들여쓰기 · `at …` · `Caused by:` · `… N more`.
        // 도커가 그 줄에도 시각을 붙였는지는 상관없다(붙인다). 떼어 놓으면 스택이
        // 흩어지고, 그러면 "Unhandled exception" 만 보이고 **원인이 사라진다.**
        last.text += `\n${body}`;
        continue;
      }

      if (matched && at) {
        // 서비스가 **이미 시각을 찍고 있으면** 우리 것을 붙이지 않는다 — 안 그러면
        // `04:08:11 04:08:11 …` 이 된다. 도커 시각은 **정렬에만** 쓴다.
        const shown = SELF_CLOCKED.test(body) ? body : `${at.slice(11)} ${body}`;
        last = { at, order: order++, text: shown };
        rows.push(last);
      } else {
        // 시각이 아예 없는 로그(`-t` 없이 받은 것). **줄마다 한 줄**로 두고 순서만 지킨다 —
        // 여기서 이어 붙이면 로그 전체가 **한 덩이**가 된다(검사가 그걸 먼저 물었다).
        last = { at: "", order: order++, text: trimmed };
        rows.push(last);
      }
    }
  }
  // 시각이 같으면 **받은 순서**를 지킨다(정렬이 줄을 섞으면 읽는 순서가 깨진다).
  rows.sort((a, b) => (a.at === b.at ? a.order - b.order : a.at < b.at ? -1 : 1));
  const merged = rows.map((row) => row.text);
  return merged.slice(Math.max(0, merged.length - limit));
}
