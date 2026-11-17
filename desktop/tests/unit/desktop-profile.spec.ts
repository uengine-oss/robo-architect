/**
 * desktop 판의 프로필 스위치 (desktop-profile.ts).
 *
 * 기본값이 **enterprise** 인 것이 이 검사의 요점이다 — 모르는 빌드를 느슨한 쪽(lite:
 * 키 없이 뜨고, 로그인 묶음을 안 거는 판)으로 가정하면 납품본이 조용히 lite 로 돈다.
 */

import { expect, test } from "@playwright/test";

import { DESKTOP_PROFILE_ENV, resolveDesktopProfile } from "../../src/main/desktop-profile";

const none = () => null;

test.describe("resolveDesktopProfile", () => {
  test("아무것도 없으면 enterprise 다", () => {
    expect(resolveDesktopProfile({}, none)).toEqual({ profile: "enterprise", source: "default" });
  });

  test("환경변수가 굽힌 값을 이긴다", () => {
    expect(resolveDesktopProfile({ [DESKTOP_PROFILE_ENV]: "lite" }, () => "enterprise")).toEqual({
      profile: "lite",
      source: "env",
    });
    expect(resolveDesktopProfile({ [DESKTOP_PROFILE_ENV]: " Enterprise " }, () => "lite").profile).toBe(
      "enterprise",
    );
  });

  test("굽힌 package.json 값을 읽는다(electron-builder.lite.js 의 extraMetadata)", () => {
    expect(resolveDesktopProfile({}, () => "lite")).toEqual({ profile: "lite", source: "package" });
  });

  test("모르는 값은 무시하고 다음 출처로 간다", () => {
    expect(resolveDesktopProfile({ [DESKTOP_PROFILE_ENV]: "posco" }, none).profile).toBe("enterprise");
    expect(resolveDesktopProfile({ [DESKTOP_PROFILE_ENV]: "" }, () => "lite").profile).toBe("lite");
  });
});
