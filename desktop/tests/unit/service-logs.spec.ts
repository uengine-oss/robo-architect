/**
 * 로그를 화면에 띄우기 전에 **무엇을 가리는가** (spec 058 T067 · T028).
 *
 * ## 왜 이 검사가 있나
 *
 * 로그를 화면에 내보내는 것은 **노출면을 늘리는 일**이다. 그래서 가리는 규칙을 먼저
 * 정하고 여기에 걸었다. 규칙이 코드에만 있으면 다음 사람이 정규식 하나를 고치는
 * 순간 조용히 넓어지거나 좁아진다.
 *
 * ## 두 방향으로 다 틀릴 수 있다
 *
 * ```
 * 덜 가리면   비밀이 화면에 뜬다
 * 더 가리면   **로그가 쓸모를 잃는다** — 커밋 해시·컨테이너 id·포트·경로가
 *            진단의 근거인데 그게 `***` 로 바뀌면 아무것도 못 읽는다
 * ```
 *
 * 그래서 "가려야 하는 것" 과 "건드리면 안 되는 것" 을 **같은 수로** 둔다.
 */

import { expect, test } from "@playwright/test";

import {
  DEFAULT_TAIL,
  MAX_TAIL,
  isNotable,
  maskSecrets,
  normalizeTail,
  pickHighlights,
  planSource,
  readServiceLogs,
} from "../../src/main/service-logs";

// ---------------------------------------------------------------------------
// 가려야 하는 것
// ---------------------------------------------------------------------------

test("이름이 비밀스러운 키의 값은 **길이만** 남는다", () => {
  const masked = maskSecrets("connect: host=db port=5432 user=robo password=hunter2secret dbname=og");
  expect(masked).not.toContain("hunter2secret");
  expect(masked).toContain("password=***(13자)");
  // 같은 줄의 **진단에 필요한 것**은 그대로 있어야 한다
  expect(masked).toContain("host=db");
  expect(masked).toContain("port=5432");
  expect(masked).toContain("user=robo");
});

test("값의 **앞자리도 남기지 않는다** — 짧은 값은 앞자리가 곧 값이다", () => {
  const masked = maskSecrets("token=abc");
  expect(masked).toBe("token=***(3자)");
});

test("JSON 모양의 비밀도 가린다", () => {
  const masked = maskSecrets('{"event":"auth","data":{"api_key":"sk-live-abcdefghijkl","user":"test"}}');
  expect(masked).not.toContain("sk-live-abcdefghijkl");
  expect(masked).toContain('"user":"test"');
});

test("Bearer 토큰 · 모양이 뚜렷한 토큰 · 접속 문자열의 비밀번호", () => {
  expect(maskSecrets("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig")).toContain("Bearer ***");
  expect(maskSecrets("using ghp_0123456789abcdefghij for clone")).not.toContain("ghp_0123456789");
  const url = maskSecrets("dsn postgres://robo:verysecret@172.27.64.1:55432/og");
  expect(url).not.toContain("verysecret");
  expect(url).toContain("@172.27.64.1:55432/og"); // 주소는 남는다
});

// ---------------------------------------------------------------------------
// 건드리면 안 되는 것 — **넓게 가리면 로그가 죽는다**
// ---------------------------------------------------------------------------

test("커밋 해시와 컨테이너 id 는 **그대로** 둔다", () => {
  const line = "releaseId 0.1.0-wb50d7aaa-aec8aa7f2-s0aae44 image sha256:9f1e4599b715563ec59512a7ced1ab56";
  expect(maskSecrets(line)).toBe(line);
});

test("오류 줄의 내용은 깎지 않는다", () => {
  const line = 'INFO: 127.0.0.1:53138 - "GET /api/health HTTP/1.1" 401 Unauthorized';
  expect(maskSecrets(line)).toBe(line);
});

test("경로와 포트는 그대로 둔다", () => {
  const line = "listening on 0.0.0.0:8080 · profile file:///tmp/lo_profile";
  expect(maskSecrets(line)).toBe(line);
});

// ---------------------------------------------------------------------------
// 눈에 걸릴 줄 — 오류만이 아니다
// ---------------------------------------------------------------------------

test("**끝난 이유**도 고른다 — 10/7 의 답이 거기였다", () => {
  // 그날 pdf2bpmn 의 답은 오류가 아니라 이 두 줄이었다.
  expect(isNotable("INFO:     Shutting down")).toBe(true);
  expect(isNotable("INFO:     Application shutdown complete.")).toBe(true);
  expect(isNotable("ERROR: connection refused")).toBe(true);
  expect(isNotable('"GET /api/health HTTP/1.1" 503 Service Unavailable')).toBe(true);
  // 평범한 진행 줄은 고르지 않는다 — 전부 고르면 고른 것이 아니다
  expect(isNotable("INFO:     Started server process [1]")).toBe(false);
  expect(isNotable("INFO:     Waiting for application startup.")).toBe(false);
});

test("고른 줄은 **마지막 것들**이다 — 원인은 보통 끝에 있다", () => {
  const lines = [...Array(30)].map((_, i) => `error ${i}`);
  const picked = pickHighlights(lines, 5);
  expect(picked).toEqual(["error 25", "error 26", "error 27", "error 28", "error 29"]);
});

// ---------------------------------------------------------------------------
// 어디서 읽을 것인가 — 못 읽는 이유마다 **다른 말**
// ---------------------------------------------------------------------------

test("백엔드는 호스트 프로세스라 컨테이너를 찾지 않는다", () => {
  const plan = planSource({
    serviceId: "architect",
    candidates: [],
    present: [],
    owner: "app",
    dockerAvailable: true,
  });
  expect(plan.source).toBe("backend");
});

test("밖에서 도는 것은 **없다고 말한다** — 중앙 모드의 graph", () => {
  const plan = planSource({
    serviceId: "graph",
    candidates: ["p-graph-bolt-1"],
    present: [],
    owner: "external",
    dockerAvailable: true,
  });
  expect(plan.source).toBe("external");
  expect(plan.note).toContain("이 PC 가 띄운 것이 아닙니다");
});

test("도커가 꺼진 것과 컨테이너가 없는 것은 **다른 말**이다", () => {
  const down = planSource({
    serviceId: "parser",
    candidates: ["p-parser-1"],
    present: null,
    owner: "app",
    dockerAvailable: false,
  });
  expect(down.source).toBe("unavailable");
  expect(down.note).toContain("Docker");

  const missing = planSource({
    serviceId: "parser",
    candidates: ["p-parser-1"],
    present: ["p-gateway-1"],
    owner: "app",
    dockerAvailable: true,
  });
  expect(missing.source).toBe("unavailable");
  expect(missing.note).toContain("만들어지지 않아");
});

test("**멈춘 컨테이너도 읽는다** — 그게 가장 알고 싶은 자리다", () => {
  const plan = planSource({
    serviceId: "pdf2bpmn",
    candidates: ["p-pdf2bpmn-1"],
    present: ["p-pdf2bpmn-1"], // `docker ps -a` 라 멈춘 것도 들어 있다
    owner: "app",
    dockerAvailable: true,
  });
  expect(plan.source).toBe("container");
  expect(plan.containerName).toBe("p-pdf2bpmn-1");
});

// ---------------------------------------------------------------------------
// 모으기
// ---------------------------------------------------------------------------

test("줄 수 상한을 벗어나지 않는다", () => {
  expect(normalizeTail(undefined)).toBe(DEFAULT_TAIL);
  expect(normalizeTail(0)).toBe(1);
  expect(normalizeTail(9_999)).toBe(MAX_TAIL);
});

test("컨테이너 로그를 읽어 **가린 줄**과 고른 줄을 같이 준다", async () => {
  const logs = await readServiceLogs(
    {
      candidatesOf: () => ["p-pdf2bpmn-1"],
      ownerOf: () => "app",
      dockerAvailable: async () => true,
      presentContainers: async () => ["p-pdf2bpmn-1"],
      containerLogs: async () =>
        [
          "INFO:     Started server process [1]",
          "INFO:     config token=supersecretvalue",
          "INFO:     Shutting down",
        ].join("\n"),
      backendLines: async () => [],
    },
    "pdf2bpmn",
  );

  expect(logs.source).toBe("container");
  expect(logs.lines).toHaveLength(3);
  expect(logs.lines.join("\n")).not.toContain("supersecretvalue");
  expect(logs.highlights).toContain("INFO:     Shutting down");
});

test("백엔드는 앱 로그에서 읽고, **도커를 묻지 않는다**", async () => {
  let askedDocker = false;
  const logs = await readServiceLogs(
    {
      candidatesOf: () => ["never"],
      ownerOf: () => "app",
      dockerAvailable: async () => {
        askedDocker = true;
        return true;
      },
      presentContainers: async () => {
        askedDocker = true;
        return [];
      },
      containerLogs: async () => "",
      backendLines: async () => ["[INFO] 인증되지 않은 요청을 막았다."],
    },
    "architect",
  );

  expect(logs.source).toBe("backend");
  expect(logs.lines).toEqual(["[INFO] 인증되지 않은 요청을 막았다."]);
  expect(askedDocker, "호스트 프로세스인데 docker 를 물었다").toBe(false);
});

test("읽을 줄이 없으면 **왜 없는지** 말한다", async () => {
  const logs = await readServiceLogs(
    {
      candidatesOf: () => ["p-parser-1"],
      ownerOf: () => "app",
      dockerAvailable: async () => true,
      presentContainers: async () => ["p-parser-1"],
      containerLogs: async () => "",
      backendLines: async () => [],
    },
    "parser",
  );
  expect(logs.lines).toEqual([]);
  expect(logs.note).toContain("아직 아무것도 안 찍혔습니다");
});
