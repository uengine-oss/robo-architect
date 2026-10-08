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
  // 오류
  /\b(error|errno|exception|traceback|fatal|critical|panic|segfault)\b/i,
  /\b(refused|denied|unauthorized|forbidden|timed?\s*out|timeout|unreachable)\b/i,
  /\b(fail(ed|ure)?)\b/i,
  /\bHTTP\/\d(\.\d)?"?\s+(4\d\d|5\d\d)\b/,
  // **끝난 이유** — 10/7 의 답이 여기였다
  /\b(shutting down|shutdown complete|stopping|stopped|terminated|killed|exit(ed|ing)?|oom)\b/i,
  // 자격·설정
  /\b(invalid|missing|not found|no such)\b/i,
];

export function isNotable(line: string): boolean {
  return NOTABLE.some((pattern) => pattern.test(line));
}

/** 전문에서 눈에 걸릴 줄만. **마지막 것들**을 우선한다 — 원인은 보통 끝에 있다. */
export function pickHighlights(lines: string[], limit = 12): string[] {
  const hits = lines.filter(isNotable);
  return hits.slice(Math.max(0, hits.length - limit));
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
  /** `docker logs --tail` 의 출력(stdout+stderr 합본). */
  containerLogs(containerName: string, tail: number): Promise<string>;
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
    raw = splitLines(await deps.containerLogs(plan.containerName, tail));
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

function splitLines(out: string): string[] {
  return out
    .split(/\r?\n/)
    .map((line) => line.replace(/\s+$/, ""))
    .filter((line) => line.length > 0);
}
