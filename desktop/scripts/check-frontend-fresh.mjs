#!/usr/bin/env node
// 설치본에 싣는 화면(frontend/dist)이 화면 소스의 마지막 커밋보다 **나중에** 빌드됐는지 본다.
//
// 화면은 이미지·런타임과 따로 빌드된다(scripts/release/README.md 0단계 — robo-lite-src/build/
// build-frontend.sh → frontend/dist). electron-builder 는 거기 있는 것을 그대로 싣는다. 그래서 소스를
// 받고 화면을 다시 빌드하지 않으면 **옛 화면이 새 버전 이름으로 나간다.** lite 0.1.6(2026-11-19)이
// 그랬다: 백엔드는 f5505d3 인데 화면은 그 전 14:08 빌드라, 화면 고침 둘(2f08e75 · 667066b)이 빠졌다.
//
// 비교: frontend/dist/index.html 의 수정 시각 vs `git log -1 --format=%ct -- frontend <화면 서브모듈>`.
// 커밋 시각은 받기(pull) 전이므로, 받은 뒤 빌드했으면 dist 가 항상 더 늦다.
// 일부러 넘기려면 ROBO_SKIP_FRONTEND_FRESH=1.
import { execFileSync } from "node:child_process";
import { existsSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const index = join(root, "frontend", "dist", "index.html");
const paths = ["frontend", "robo-analyzer/robo-data-frontend"];

if (process.env.ROBO_SKIP_FRONTEND_FRESH === "1") {
  console.warn("[frontend-fresh] ROBO_SKIP_FRONTEND_FRESH=1 — 건너뜀");
  process.exit(0);
}
if (!existsSync(index)) {
  console.error(`[frontend-fresh] ${index} 가 없다 — 화면을 먼저 빌드한다(robo-lite-src/build/build-frontend.sh)`);
  process.exit(1);
}

const out = execFileSync("git", ["-C", root, "log", "-1", "--format=%ct %h %s", "--", ...paths], { encoding: "utf8" }).trim();
if (!out) process.exit(0);
const [ct, hash, ...subject] = out.split(" ");
const committed = Number(ct) * 1000;
const built = statSync(index).mtimeMs;
if (built < committed) {
  const fmt = (ms) => new Date(ms).toISOString().replace("T", " ").slice(0, 19) + "Z";
  console.error(
    `[frontend-fresh] frontend/dist 가 옛 빌드다 — 빌드 ${fmt(built)} < 화면 커밋 ${hash} ${fmt(committed)} (${subject.join(" ")})\n` +
    "  화면을 다시 빌드한 뒤 굽는다: robo-lite-src/build/build-frontend.sh (scripts/release/README.md 0단계)",
  );
  process.exit(1);
}
console.log(`[frontend-fresh] ok — frontend/dist 가 ${hash} 뒤에 빌드됐다`);
