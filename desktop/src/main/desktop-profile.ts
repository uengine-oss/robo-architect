/**
 * 데스크톱 판의 **프로필** — `enterprise`(기본) 또는 `lite`.
 *
 * 판은 web · desktop 둘이다. lite 는 따로 앱·따로 브랜치가 아니라 desktop 판의 한
 * 프로필이고, 코드 경로는 하나다. 갈리는 것은 아래 자리뿐이며 전부 이 모듈을 거친다.
 *
 * ```
 *                    enterprise (기본)                 lite
 * 창                 단일 창 + 런처                     탭 창(셸 홈이 런처를 대신)
 * 언어               한국어 고정                         OS 언어 / 메뉴(영어 모드)
 * 런타임 매니페스트  schema 5 · authority·pdf2bpmn ·    schema 4 도 받음 · 그 둘 없음 ·
 *                    graphs · 이미지 tar 필수           graphs 없으면 기본값 · tar 없이 pull
 * 모델 키            credentialNames 비면 기동 중단     경고만(Claude 브리지가 대신)
 * compose            compose.yml                        + compose.lite.yml(pdf2bpmn 끔 · 브리지 키)
 * 그래프 비밀번호    볼륨 값 그대로                      기동 때 graph-db 역할 비밀번호를 맞춤
 * 호스트 백엔드      AUTH_BIND_CONNECTION=true(설치본)  Claude 브리지 env · 번들 연결의 그래프 = 프로젝트
 * ```
 *
 * ## 어디서 정하나 — 하나의 스위치
 *
 *   1. `ROBO_DESKTOP_PROFILE=lite|enterprise` — 개발 실행·시험이 강제할 때
 *   2. 설치본의 `package.json` 의 `roboDesktopProfile` — `electron-builder.lite.js` 가
 *      `extraMetadata` 로 굽는다. 설치한 사람이 환경변수를 만질 필요가 없다.
 *   3. 없으면 `enterprise` — **모르는 빌드를 느슨한 쪽으로 가정하지 않는다.**
 *
 * Electron 을 import 하지 않는다 — 단위 시험이 그대로 부를 수 있어야 한다.
 */

import fs from "node:fs";
import path from "node:path";

export type DesktopProfile = "enterprise" | "lite";

export const DESKTOP_PROFILE_ENV = "ROBO_DESKTOP_PROFILE";
export const DEFAULT_DESKTOP_PROFILE: DesktopProfile = "enterprise";

function pick(value: unknown): DesktopProfile | null {
  const s = String(value ?? "").trim().toLowerCase();
  return s === "lite" || s === "enterprise" ? s : null;
}

/** 굽힌 package.json 의 `roboDesktopProfile`. 컴파일된 파일은 `dist/main/main/` 에 있다. */
function packagedProfile(): DesktopProfile | null {
  try {
    const file = path.resolve(__dirname, "..", "..", "..", "package.json");
    return pick((JSON.parse(fs.readFileSync(file, "utf8")) as { roboDesktopProfile?: unknown }).roboDesktopProfile);
  } catch {
    return null;
  }
}

/** 순수 결정 — 시험이 출처를 갈아 끼운다. */
export function resolveDesktopProfile(
  env: NodeJS.ProcessEnv = process.env,
  packaged: () => DesktopProfile | null = packagedProfile,
): { profile: DesktopProfile; source: "env" | "package" | "default" } {
  const fromEnv = pick(env[DESKTOP_PROFILE_ENV]);
  if (fromEnv) return { profile: fromEnv, source: "env" };
  const fromPackage = packaged();
  if (fromPackage) return { profile: fromPackage, source: "package" };
  return { profile: DEFAULT_DESKTOP_PROFILE, source: "default" };
}

let cached: ReturnType<typeof resolveDesktopProfile> | null = null;

function resolved(): ReturnType<typeof resolveDesktopProfile> {
  if (!cached) cached = resolveDesktopProfile();
  return cached;
}

/** 이 프로세스의 프로필. 한 번 정하면 실행 중에 바뀌지 않는다. */
export function desktopProfile(): DesktopProfile {
  return resolved().profile;
}

export function desktopProfileSource(): "env" | "package" | "default" {
  return resolved().source;
}

export function isLiteProfile(): boolean {
  return desktopProfile() === "lite";
}
