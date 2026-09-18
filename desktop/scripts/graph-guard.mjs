/**
 * 설계·분석 graph 분리 판정을 **앱 코드로** 내린다 (spec 058 T035).
 *
 * `desktop/src/main/graph-guard.ts` 를 그대로 부르는 껍데기다. 판정을 파이썬으로 다시
 * 쓰면 재구현이 원본보다 옳아져 결함을 가린다.
 *
 * 비밀번호는 **인자로 받지 않는다** — `ROBO_NEO4J_PASSWORD`.
 *
 * 사용:
 *   node scripts/graph-guard.mjs --bolt 38687 --user robo --design robo --analysis analyzer_run
 *
 * 종료 코드: 0 분리됨 · 1 분리 안 됨 · 3 못 쟀다(evidence 가 null)
 */

import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const built = path.join(here, "..", "dist", "main", "main", "graph-guard.js");
let guardModule;
try {
  guardModule = require(built);
} catch {
  console.error(`빌드 산출물이 없다: ${built}\n  먼저 \`npm run build\` 를 돌려라.`);
  process.exit(3);
}

const argv = process.argv.slice(2);
const flag = (name) => {
  const index = argv.indexOf(`--${name}`);
  return index >= 0 && index + 1 < argv.length ? argv[index + 1] : undefined;
};

const missing = ["bolt", "user", "design", "analysis"].filter((n) => flag(n) === undefined);
if (missing.length > 0) {
  console.error(`빠진 인자: ${missing.map((n) => `--${n}`).join(", ")}`);
  process.exit(3);
}

const guard = await guardModule.evaluateGraphGuard(
  { design: flag("design"), analysis: flag("analysis") },
  {
    uri: `bolt://127.0.0.1:${flag("bolt")}`,
    user: flag("user"),
    password: process.env.ROBO_NEO4J_PASSWORD ?? process.env.OG_PASSWORD ?? "",
  },
);

if (argv.includes("--json")) {
  process.stdout.write(`${JSON.stringify(guard, null, 2)}\n`);
} else {
  console.log(`  설계 graph   ${guard.designGraph}`);
  console.log(`  분석 graph   ${guard.analysisGraph}`);
  console.log(`  분리됨       ${guard.separated}`);
  // **evidence 를 같이 찍는다.** `separated: true` 만 보고 "확인했다"고 읽으면
  // 빈 graph 를 증명으로 착각한다.
  console.log(`  근거         ${guard.evidence ?? "(확인 못 함)"}`);
  if (guard.reason) console.log(`  이유         ${guard.reason}`);
}

process.exit(guard.separated ? (guard.evidence === null ? 3 : 0) : 1);
