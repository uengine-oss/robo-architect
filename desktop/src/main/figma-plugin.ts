/**
 * Figma 플러그인 묶음을 **사용자가 쓸 수 있는 자리에 꺼내 준다.**
 *
 * ## 왜 필요한가
 *
 * 설치본 사용자 PC 에는 저장소가 없다. 2026-11-12 에 포스코 웹 판에서 그대로 밟았다 —
 * 체크아웃 폴더의 `manifest.json` 을 Figma 에 Import 하면
 *
 *     Unable to load code: ENOENT … figma-plugin\dist\plugin.js
 *
 * 로 죽는다. `manifest.json` 의 `"main": "dist/plugin.js"` 는 **빌드 산출물**이라
 * 저장소에 없고, 사용자 PC 에는 그것을 구울 bun 도 없다. 그래서 굽는 쪽이 묶어 싣고
 * (`electron-builder.yml` 의 `extraResources` · `npm run build:figma`),
 * 앱이 꺼내 준다.
 *
 * ## 왜 설치 폴더가 아니라 userData 인가
 *
 * Figma 는 Import 한 **그 경로**를 기억한다. 설치 폴더(`resources/figma-plugin`)를
 * 그대로 고르게 하면 앱을 지우거나 업데이트가 폴더를 갈아치울 때 플러그인이
 * 사라진다 — Figma 에는 "플러그인이 없다" 로만 보인다. 그래서 앱 데이터
 * (`userData/figma-plugin`)로 복사하고 **그 자리**를 열어 준다. 이 자리는
 * `deleteAppDataOnUninstall: false` 라 앱을 지워도 남는다.
 *
 * 부를 때마다 덮어쓴다 — 앱을 업데이트하면 새 플러그인으로 조용히 갱신된다
 * (파일 둘 · 100KB 미만이라 값이 싸다).
 */

import { app, shell } from "electron";
import fs from "node:fs";
import path from "node:path";

/** 묶음에 든 파일 — manifest 의 `main` 과 같은 자리를 지킨다. */
const FILES = ["manifest.json", path.join("dist", "plugin.js")] as const;

/**
 * 묶음의 원본 자리.
 *
 * 개발: `<repo>/figma-plugin` (desktop 의 한 단계 위)
 * 설치본: `<app>/resources/figma-plugin` (electron-builder extraResources)
 */
export function resolveFigmaPluginSource(): string {
  const dev = path.resolve(app.getAppPath(), "..", "figma-plugin");
  if (fs.existsSync(path.join(dev, "manifest.json"))) return dev;
  return path.join(process.resourcesPath, "figma-plugin");
}

/** 꺼내 놓는 자리 — 앱을 지워도 남는다(Figma 가 이 경로를 기억한다). */
export function figmaPluginUserDir(): string {
  return path.join(app.getPath("userData"), "figma-plugin");
}

/**
 * 묶음을 userData 로 복사하고 그 폴더를 연다.
 *
 * @returns 사용자가 Figma 에서 고를 `manifest.json` 이 있는 폴더.
 * @throws 묶음이 없으면(= 이 판을 구울 때 `build:figma` 가 안 돌았다) 던진다.
 *         조용히 빈 폴더를 열면 사용자가 Figma 에서 원인 모를 실패를 본다.
 */
export async function revealFigmaPlugin(): Promise<{ dir: string }> {
  const src = resolveFigmaPluginSource();
  const missing = FILES.filter((rel) => !fs.existsSync(path.join(src, rel)));
  if (missing.length > 0) {
    throw new Error(
      `Figma 플러그인 묶음이 이 판에 없습니다 (${missing.join(", ")}) — ` +
        `굽는 쪽에서 npm run build:figma 가 돌지 않았습니다.`,
    );
  }

  const dir = figmaPluginUserDir();
  for (const rel of FILES) {
    const to = path.join(dir, rel);
    fs.mkdirSync(path.dirname(to), { recursive: true });
    fs.copyFileSync(path.join(src, rel), to);
  }

  // openPath 는 실패를 **던지지 않고** 문자열로 돌려준다 — 비어 있어야 성공이다.
  const problem = await shell.openPath(dir);
  if (problem) throw new Error(`폴더를 열지 못했습니다: ${problem}`);
  return { dir };
}
