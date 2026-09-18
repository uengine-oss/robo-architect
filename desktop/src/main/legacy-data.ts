/**
 * 옛 구성에 남은 사용자 데이터를 **기동 시점에 알린다** (spec 058 T049 · FR-030).
 *
 * ## 조용히 빈 화면이 되면 안 된다
 *
 * graph 저장소를 Neo4j → Ontological 로 바꿨다. 두 구성은 **볼륨이 다르다.**
 *
 * ```
 * 옛 구성   <프로젝트>_neo4j_data · <프로젝트>_neo4j_logs
 * 새 구성   <프로젝트>_graph_data
 * ```
 *
 * 그래서 교체해도 옛 데이터는 **지워지지 않는다** — 다만 새 앱이 **읽지 않는다.**
 * 업그레이드한 사용자가 앱을 열면 프로젝트 목록이 그냥 비어 있다. 오류도 안 난다.
 * 그게 이 프로젝트에서 제일 흔한 실패 모양이고, 사용자는 **데이터가 지워진 줄 안다.**
 *
 * ## 세 갈래로 가른다
 *
 * ```
 * 옛 볼륨 있음 + 새 저장소 비어 있음   이관이 필요하다. **화면이 말해야 한다**
 * 옛 볼륨 있음 + 새 저장소에 데이터    옮겨진 뒤다. 옛 볼륨은 디스크만 차지한다
 * 옛 볼륨 없음                          할 말이 없다
 * 못 물어봤다                           **"필요 없다"가 아니다.** 모른다고 적는다
 * ```
 *
 * 마지막 갈래를 `needsAttention: false` 로 두는 이유: 못 쟀는데 경고를 띄우면 사용자가
 * 없는 문제를 고치려 든다. 다만 `reason` 에 못 쟀다는 사실을 남긴다.
 *
 * ## 지우지 않는다
 *
 * 옛 볼륨을 앱이 지우지 않는다. **거기에 사용자 데이터가 있다.** 무엇이 있는지
 * 알려 주고, 지우는 것은 사용자가 결정한다.
 */

import { execFile } from "node:child_process";

/** 옛 구성이 쓰던 볼륨 이름의 끝부분. compose 가 `<프로젝트>_` 를 앞에 붙인다. */
export const LEGACY_VOLUME_SUFFIXES = ["_neo4j_data", "_neo4j_logs"] as const;

/**
 * 계약은 `shared/runtime-contract.ts` 에 산다 — 렌더러가 같은 타입을 봐야 한다.
 *
 * ```
 * legacyVolumes      남아 있는 옛 볼륨
 * currentGraphEmpty  새 저장소가 비어 있는가. **못 쟀으면 null**
 * needsAttention     사용자가 지금 무언가 해야 하는가
 * reason             무엇이 어떤 상태인가. 비밀정보 금지
 * action             **사용자가 할 수 있는 일.** 이유만 주면 조치를 못 한다
 * ```
 */
export type { LegacyDataNotice } from "../shared/runtime-contract";
import type { LegacyDataNotice } from "../shared/runtime-contract";

export const NO_LEGACY_DATA: LegacyDataNotice = {
  legacyVolumes: [],
  currentGraphEmpty: null,
  needsAttention: false,
  reason: null,
  action: null,
};

/**
 * 순수 판정. 볼륨 목록과 "새 저장소가 비었는지"를 주면 무엇을 말할지 정한다.
 *
 * `volumes` 가 `null` 이면 **못 물어본 것**이다 — 빈 배열과 다르다.
 */
export function judgeLegacyData(
  volumes: string[] | null,
  currentGraphEmpty: boolean | null,
): LegacyDataNotice {
  if (volumes === null) {
    return {
      ...NO_LEGACY_DATA,
      currentGraphEmpty,
      // 못 쟀는데 경고하면 사용자가 없는 문제를 고치려 든다. 사실만 남긴다.
      reason: "옛 구성의 데이터가 남아 있는지 확인하지 못했습니다.",
    };
  }
  const legacyVolumes = [...volumes].sort();
  if (legacyVolumes.length === 0) {
    return { ...NO_LEGACY_DATA, currentGraphEmpty };
  }
  if (currentGraphEmpty === true) {
    return {
      legacyVolumes,
      currentGraphEmpty,
      needsAttention: true,
      reason:
        `이전 버전(Neo4j)의 데이터가 ${legacyVolumes.length}개 볼륨에 남아 있고 ` +
        "새 저장소는 비어 있습니다. 이전 프로젝트가 화면에 보이지 않습니다.",
      action:
        "데이터가 지워진 것이 아닙니다. 이관을 원하면 이전 버전으로 되돌려 내보낸 뒤 " +
        "새 버전에서 다시 가져오세요. 되돌리는 방법은 런타임 폴더의 " +
        "rollback-to-neo4j.md 에 있습니다.",
    };
  }
  return {
    legacyVolumes,
    currentGraphEmpty,
    // 이미 옮겨진 뒤다. 경고가 아니라 안내다 — 여기서 경고를 띄우면 정상 상태에
    // 빨간불이 계속 켜져 있고, 그러면 사용자가 빨간불을 무시하는 법을 배운다.
    needsAttention: false,
    reason: `이전 버전(Neo4j)의 볼륨 ${legacyVolumes.length}개가 디스크에 남아 있습니다.`,
    action:
      "새 저장소에 데이터가 있으므로 앱 동작에는 영향이 없습니다. " +
      "디스크를 되찾으려면 내용을 확인한 뒤 직접 지우세요(앱은 지우지 않습니다).",
  };
}

function run(args: string[], timeoutMs = 20_000): Promise<{ code: number; out: string }> {
  return new Promise((resolve) => {
    execFile("docker", args, { timeout: timeoutMs, encoding: "utf8" }, (error, stdout, stderr) => {
      const out = `${stdout ?? ""}${stderr ?? ""}`;
      const code = error
        ? typeof (error as { code?: unknown }).code === "number"
          ? (error as { code: number }).code
          : 1
        : 0;
      resolve({ code, out });
    });
  });
}

/**
 * 옛 볼륨을 찾는다. 못 물어봤으면 **빈 배열이 아니라 `null`**.
 *
 * 이름으로 찾는 것이 여기서는 맞다 — 볼륨에는 우리 라벨이 없고(compose 가 프로젝트
 * 라벨만 붙인다), 찾는 대상이 **정확히 그 이름 규약**이다. 그래도 프로젝트 이름
 * 접두사를 요구해 남의 `neo4j_data` 를 집지 않는다.
 */
export async function findLegacyVolumes(projectName: string): Promise<string[] | null> {
  const { code, out } = await run([
    "volume",
    "ls",
    "--filter",
    `label=com.docker.compose.project=${projectName}`,
    "--format",
    "{{.Name}}",
  ]);
  if (code !== 0) return null;
  const labelled = out
    .trim()
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  // 옛 구성의 볼륨에는 프로젝트 라벨이 붙어 있을 수도, 없을 수도 있다(만든 compose
  // 버전에 따라 다르다). 그래서 이름으로도 한 번 더 찾는다.
  const byName = await run(["volume", "ls", "--format", "{{.Name}}"]);
  if (byName.code !== 0) return null;
  const all = byName.out
    .trim()
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  const candidates = new Set<string>();
  for (const name of [...labelled, ...all]) {
    if (!name.startsWith(`${projectName}_`)) continue;
    if (LEGACY_VOLUME_SUFFIXES.some((suffix) => name.endsWith(suffix))) candidates.add(name);
  }
  return [...candidates].sort();
}
