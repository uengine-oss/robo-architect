/**
 * 체크섬으로 잠근 `.env` 를 **환경변수가 이기는 것**을 잡는가.
 *
 * ## 2026-09-29 에 이 PC 가 정확히 그 상태였다
 *
 * ```
 * architect/app/.env  (sha256 고정)   AUTH_DEV_LOGIN_ENABLED=false
 * Windows 사용자 환경변수              AUTH_DEV_LOGIN_ENABLED=true
 * 서버가 화면에 답한 값                devLogin.enabled: true
 * ```
 *
 * 파일은 한 글자도 안 바뀌었으므로 `runtime.environment.verified` 는 7개 전부
 * 통과했다. 그런데도 SSO 를 안 거치고 아이디·비밀번호로 들어갈 수 있었다.
 * 백엔드가 `load_dotenv()` 를 기본값(`override=False`)으로 부르기 때문이다 —
 * **이미 프로세스 환경에 있는 값이 잠긴 파일을 이긴다.**
 *
 * ## 왜 경고가 아니라 중단인가
 *
 * 열려 있어도 증상이 없다. 로그인 화면은 정상으로 뜨고, 개발용 칸이 하나 더
 * 보일 뿐이다. 증상이 없는 우회는 발견되지 않는다. 그래서 기동 시점에 이름을
 * 대고 멈춘다 — `runtime.credentials_missing` 과 같은 급으로 다룬다.
 *
 * ## 이 검사가 진짜 잡는지부터 본다
 *
 * 마지막 `describe` 가 **일부러 틀린 조건**들을 넣는다. 통과해야 하는 경우까지
 * 막아 버리면(예: 릴리스가 스스로 개발용 로그인을 켠 경우) 이 가드는 켜자마자
 * 꺼진다.
 */

import { expect, test } from "@playwright/test";

import { assertAuthPostureNotOverridden } from "../../src/main/docker-stack";
import type { RuntimeManifest } from "../../src/main/docker-stack";

const VAR = "AUTH_DEV_LOGIN_ENABLED";
const ENFORCE = "AUTH_ENFORCE";

/** 이 가드가 보는 필드만 담은 최소 매니페스트. 나머지는 읽지 않는다. */
function manifest(over: Partial<RuntimeManifest> = {}): RuntimeManifest {
  return {
    releaseId: "0.1.0-test",
    authEnforced: true,
    authProvider: "posco",
    ...over,
  } as RuntimeManifest;
}

/** 환경변수를 이 검사 안에서만 바꾼다 — 남기면 다음 검사가 이유 없이 붉어진다. */
function withEnv<T>(vars: Record<string, string | undefined>, body: () => T): T {
  const before = new Map<string, { had: boolean; value?: string }>();
  for (const [name, value] of Object.entries(vars)) {
    before.set(name, {
      had: Object.prototype.hasOwnProperty.call(process.env, name),
      value: process.env[name],
    });
    if (value === undefined) delete process.env[name];
    else process.env[name] = value;
  }
  try {
    return body();
  } finally {
    for (const [name, prev] of before) {
      if (prev.had) process.env[name] = prev.value;
      else delete process.env[name];
    }
  }
}

/** 개발용 로그인 변수만 건드리는 흔한 경우. 나머지는 비워 둔다. */
function withVar<T>(value: string | undefined, body: () => T): T {
  return withEnv({ [VAR]: value, [ENFORCE]: undefined }, body);
}

test.describe("납품본의 인증 자세를 환경변수로 뒤집으면 멈춘다", () => {
  test("켜져 있으면 던진다", () => {
    withVar("true", () => {
      expect(() => assertAuthPostureNotOverridden(manifest())).toThrow(
        /runtime\.auth_posture_override/,
      );
    });
  });

  for (const v of ["1", "TRUE", "  yes  ", "on", "On"]) {
    test(`'${v}' 도 켜진 것으로 본다`, () => {
      withVar(v, () => {
        expect(() => assertAuthPostureNotOverridden(manifest())).toThrow(
          /runtime\.auth_posture_override/,
        );
      });
    });
  }

  // `AUTH_ENFORCE=false` 는 개발용 로그인보다 **더 큰 구멍**이다 — 문을 통째로
  // 없앤다. 처음 만든 가드는 이걸 안 봤다.
  for (const v of ["false", "0", "no", "off", "OFF"]) {
    test(`${ENFORCE}='${v}' 로 강제를 끈 것도 잡는다`, () => {
      withEnv({ [ENFORCE]: v, [VAR]: undefined }, () => {
        expect(() => assertAuthPostureNotOverridden(manifest())).toThrow(
          /runtime\.auth_posture_override/,
        );
      });
    });
  }

  test("둘이 함께 켜져 있으면 둘 다 이름을 댄다", () => {
    withEnv({ [ENFORCE]: "false", [VAR]: "true" }, () => {
      let message = "";
      try {
        assertAuthPostureNotOverridden(manifest());
      } catch (err) {
        message = err instanceof Error ? err.message : String(err);
      }
      expect(message).toContain(ENFORCE);
      expect(message).toContain(VAR);
    });
  });

  test("메시지가 무엇을·왜·어떻게 를 다 말한다", () => {
    withVar("true", () => {
      let message = "";
      try {
        assertAuthPostureNotOverridden(manifest());
      } catch (err) {
        message = err instanceof Error ? err.message : String(err);
      }
      // ① 무엇이 잘못됐는지 — 변수 이름을 댄다.
      expect(message).toContain(VAR);
      // ② 왜 이게 문제인지 — 체크섬이 못 막는 이유.
      expect(message).toContain(".env");
      // ③ 무엇을 하면 되는지 — 붙여 쓸 수 있는 명령.
      expect(message).toContain("SetEnvironmentVariable");
      // ④ 그 뒤 필요한 것 — 환경변수는 재로그인해야 반영된다.
      expect(message).toMatch(/로그아웃|재로그인/);
      // ⑤ 막기만 하면 사람이 갈 곳이 없다 — 사내망 밖에서 밟는 길을 댄다.
      expect(message).toContain("internal-test");
    });
  });
});

test.describe("이름 붙은 예외는 통과시킨다", () => {
  // `robo.ps1` 이 이미 정한 원칙 — 문제는 끌 수 있다는 것이 아니라
  // **이름 없는 예외가 납품으로 새는 것**이다. 여기서 막아 버리면 사내망 밖에서
  // 화면을 밟을 방법이 아예 없어지고, 그러면 누군가 가드를 지운다.
  test("internal-test 채널에서는 막지 않는다", () => {
    withEnv({ [ENFORCE]: "false", [VAR]: "true" }, () => {
      expect(() =>
        assertAuthPostureNotOverridden(manifest({ releaseChannel: "internal-test" })),
      ).not.toThrow();
    });
  });

  test("채널이 없으면 delivery 로 본다 — 모르는 빌드를 느슨하게 보지 않는다", () => {
    withVar("true", () => {
      expect(() =>
        assertAuthPostureNotOverridden(manifest({ releaseChannel: undefined })),
      ).toThrow(/runtime\.auth_posture_override/);
    });
  });

  test("엉뚱한 채널 이름도 delivery 로 본다", () => {
    withVar("true", () => {
      expect(() =>
        assertAuthPostureNotOverridden(manifest({ releaseChannel: "dev" })),
      ).toThrow(/runtime\.auth_posture_override/);
    });
  });
});

test.describe("일부러 틀린 조건을 넣어 과잉 차단이 아닌지 본다", () => {
  test("변수가 없으면 통과한다", () => {
    withVar(undefined, () => {
      expect(() => assertAuthPostureNotOverridden(manifest())).not.toThrow();
    });
  });

  test("빈 문자열은 켜진 것이 아니다", () => {
    withVar("", () => {
      expect(() => assertAuthPostureNotOverridden(manifest())).not.toThrow();
    });
  });

  test(`${ENFORCE}='true' 는 당연히 통과한다 — 뒤집은 게 아니다`, () => {
    withEnv({ [ENFORCE]: "true", [VAR]: undefined }, () => {
      expect(() => assertAuthPostureNotOverridden(manifest())).not.toThrow();
    });
  });

  test(`${ENFORCE}='' 는 "지운 흔적" 으로 본다`, () => {
    withEnv({ [ENFORCE]: "", [VAR]: undefined }, () => {
      expect(() => assertAuthPostureNotOverridden(manifest())).not.toThrow();
    });
  });

  test("'false' 는 당연히 통과한다", () => {
    withVar("false", () => {
      expect(() => assertAuthPostureNotOverridden(manifest())).not.toThrow();
    });
  });

  test("사내 인증이 아닌 릴리스는 건드리지 않는다", () => {
    withVar("true", () => {
      expect(() =>
        assertAuthPostureNotOverridden(manifest({ authProvider: "none" })),
      ).not.toThrow();
      expect(() =>
        assertAuthPostureNotOverridden(manifest({ authEnforced: false })),
      ).not.toThrow();
    });
  });

  test("옛 매니페스트(필드 없음)에서는 검사하지 않는다", () => {
    withVar("true", () => {
      expect(() =>
        assertAuthPostureNotOverridden(
          manifest({ authEnforced: undefined, authProvider: undefined }),
        ),
      ).not.toThrow();
    });
  });

  test("릴리스가 스스로 켠 경우는 막지 않는다 — 파일은 체크섬이 덮는다", () => {
    // `.env` 에 true 가 구워졌다면 그건 굽는 쪽의 결정이다. 이 가드가 보는 것은
    // **프로세스 환경으로 덮어쓴 경우**뿐이라, 변수가 없으면 통과해야 한다.
    withVar(undefined, () => {
      expect(() => assertAuthPostureNotOverridden(manifest())).not.toThrow();
    });
  });
});
