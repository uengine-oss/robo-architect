/**
 * **앱의 프로브를 그대로 돌리는** 명령줄 껍데기 (spec 058 T032).
 *
 * ## 왜 껍데기인가 — 판정을 두 번 짜지 않는다
 *
 * `scripts/probe_runtime.py` 는 앱에 프로브가 없던 동안 쓰던 측정 도구다. 둘을 나란히
 * 두면 **재구현이 원본보다 옳아져서 결함을 가린다** — 이 저장소가 실제로 밟은 함정이다.
 * 그래서 판정의 권위는 `src/main/probes/` 하나에 두고, 검증 스크립트는 이 껍데기를
 * 통해 **그것을** 부른다.
 *
 * ## 비밀정보
 *
 * 비밀번호는 **인자로 받지 않는다** — `ps` 와 셸 기록에 남는다.
 * `ROBO_NEO4J_PASSWORD` 로 받고, 출력(`detail`)에도 싣지 않는다(프로브의 계약).
 *
 * 사용:
 *   node scripts/probe-runtime.mjs --project robo-og-measure --bolt 38687 \
 *        --gateway 38000 --analyzer 38502 --pdf2bpmn 38611 \
 *        --graph-user robo --graph-name robo [--json]
 *
 * 종료 코드: 0 전부 pass · 1 fail 있음 · 3 못 쟀다(error 있고 fail 없음)
 */

import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);

// 빌드 산출물을 쓴다. 없으면 **조용히 다른 것을 재지 않고** 무엇을 해야 하는지 말한다.
const built = path.join(here, "..", "dist", "main", "main", "probes", "index.js");
let probes;
try {
  probes = require(built);
} catch {
  console.error(`빌드 산출물이 없다: ${built}\n  먼저 \`npm run build\` 를 돌려라.`);
  process.exit(3);
}

const argv = process.argv.slice(2);
const flag = (name) => {
  const index = argv.indexOf(`--${name}`);
  return index >= 0 && index + 1 < argv.length ? argv[index + 1] : undefined;
};
const json = argv.includes("--json");

const required = ["project", "bolt", "gateway", "analyzer", "pdf2bpmn", "graph-user", "graph-name"];
const missing = required.filter((name) => flag(name) === undefined);
if (missing.length > 0) {
  console.error(`빠진 인자: ${missing.map((n) => `--${n}`).join(", ")}`);
  process.exit(3);
}

const context = {
  projectName: flag("project"),
  ports: {
    graph: Number(flag("bolt")),
    analyzer: Number(flag("analyzer")),
    gateway: Number(flag("gateway")),
    // architect 는 호스트 프로세스다. 안 주면 닿지 않는 포트로 두고 error 가 나게 한다 —
    // **없는 것을 pass 로 만들지 않는다.**
    architect: Number(flag("architect") ?? 0) || 1,
    pdf2bpmn: Number(flag("pdf2bpmn")),
  },
  graph: {
    user: flag("graph-user"),
    password: process.env.ROBO_NEO4J_PASSWORD ?? process.env.OG_PASSWORD ?? "",
    design: flag("graph-name"),
    analysis: flag("graph-analysis") ?? "",
  },
};

const results = [];
for (const id of probes.probedServiceIds()) {
  const kinds = probes.hasCapabilityProbe(id) ? ["health", "capability"] : ["health"];
  for (const kind of kinds) {
    const result = await probes.runProbe(context, id, kind);
    results.push({
      service_id: result.serviceId,
      kind: result.kind,
      outcome: result.outcome,
      detail: result.detail,
      duration_ms: result.durationMs,
    });
  }
}

if (json) {
  // `--json` 은 기계가 읽는 출력이다. 사람용 요약은 stderr 로 보낸다 — 같은 스트림에
  // 섞으면 받는 쪽의 파싱이 깨지고, 증상이 "프로브를 못 읽었다"로 보인다.
  process.stdout.write(`${JSON.stringify(results, null, 2)}\n`);
} else {
  const mark = { pass: "✓", fail: "✗", error: "!", skipped: "-" };
  for (const r of results) {
    console.log(`  ${mark[r.outcome]} ${r.service_id.padEnd(9)} ${r.kind.padEnd(11)} ${r.outcome.padEnd(8)} ${r.detail}`);
  }
}

const count = (outcome) => results.filter((r) => r.outcome === outcome).length;
console.error(
  `\npass ${count("pass")} · fail ${count("fail")} · error ${count("error")} · skipped ${count("skipped")}`,
);
// **error 를 fail 과 다르게 센다.** 뭉치면 "재지 못한 것"이 "안 되는 것"이 된다.
process.exit(count("fail") > 0 ? 1 : count("error") > 0 ? 3 : 0);
