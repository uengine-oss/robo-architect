/**
 * 프로젝트 의도(그린필드/브라운필드)를 어디에 어떻게 남기나 (라이트 지적 C-5 ⑩).
 *
 * 자리: DesktopSettings 의 **선택 칸** `projectTypes` (그래프 이름 → 의도).
 *   - 없던 파일을 읽어도 칸을 만들지 않는다 — 기존 설정과의 비교가 흔들리지 않게
 *   - 어휘 밖의 값은 버린다 — DDD 마법사가 모르는 값을 기본값으로 받지 않게
 */

import { expect, test } from "@playwright/test";

import { cleanProjectTypes, defaultSettings, migrateSettingsIfNeeded } from "../../src/main/launcher/settings-migrate";
import { normalizeProjectType, rememberProjectType } from "../../src/main/launcher/projects";

test("의도 어휘만 받는다", () => {
  expect(normalizeProjectType("greenfield")).toBe("greenfield");
  expect(normalizeProjectType("brownfield")).toBe("brownfield");
  expect(normalizeProjectType("legacy")).toBeNull();
  expect(normalizeProjectType(undefined)).toBeNull();
});

test("의도를 적은 새 설정 — 다른 프로젝트 칸은 지키고, 원본은 안 바꾼다", () => {
  const base = { ...defaultSettings(), projectTypes: { shop: "greenfield" as const } };
  const next = rememberProjectType(base, "erp", "brownfield");
  expect(next.projectTypes).toEqual({ shop: "greenfield", erp: "brownfield" });
  expect(base.projectTypes).toEqual({ shop: "greenfield" });
  expect(rememberProjectType(base, "erp", null)).toBe(base);
});

test("v2 파일에 칸이 없으면 만들지 않는다(migrated 도 안 켠다)", () => {
  const raw = JSON.parse(JSON.stringify(defaultSettings()));
  const result = migrateSettingsIfNeeded(raw);
  expect(result.migrated).toBe(false);
  expect("projectTypes" in result.settings).toBe(false);
});

test("v2 파일의 칸은 읽을 때 살아남고, 어휘 밖 값은 버린다", () => {
  const raw = { ...JSON.parse(JSON.stringify(defaultSettings())), projectTypes: { erp: "brownfield", x: "??" } };
  const result = migrateSettingsIfNeeded(raw);
  expect(result.settings.projectTypes).toEqual({ erp: "brownfield" });
  expect(cleanProjectTypes({ a: 1 })).toBeNull();
  expect(cleanProjectTypes(null)).toBeNull();
});
