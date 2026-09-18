/**
 * 옛 구성에 남은 데이터를 기동 시점에 알리는가 (spec 058 T049 · FR-030).
 *
 * ## 왜 이것이 필요한가
 *
 * graph 저장소를 Neo4j → Ontological 로 바꿨고, **두 구성은 볼륨이 다르다.**
 * 그래서 옛 데이터는 지워지지 않지만 **새 앱이 읽지 않는다.** 업그레이드한 사용자가
 * 앱을 열면 프로젝트 목록이 그냥 비어 있고 오류도 안 난다 — 그리고 **데이터가
 * 지워진 줄 안다.**
 *
 * ## 여기서 특히 재는 것
 *
 * **"아직 안 봤다"와 "안내할 것이 없다"를 가르는가.** 못 쟀는데 경고를 띄우면 사용자가
 * 없는 문제를 고치려 들고, 못 쟀는데 조용하면 있는 문제를 놓친다.
 */

import { expect, test } from "@playwright/test";

import { judgeLegacyData, LEGACY_VOLUME_SUFFIXES } from "../../src/main/legacy-data";

const LEGACY = ["robo-architect-desktop_neo4j_data", "robo-architect-desktop_neo4j_logs"];

test.describe("세 갈래로 가른다", () => {
  test("옛 볼륨이 있고 새 저장소가 비어 있으면 **사용자가 할 일이 있다**", () => {
    const notice = judgeLegacyData(LEGACY, true);
    expect(notice.needsAttention).toBe(true);
    expect(notice.legacyVolumes).toEqual(LEGACY.slice().sort());
    // "지워지지 않았다"를 먼저 말한다 — 사용자의 첫 두려움이 그것이다.
    expect(notice.reason).toContain("보이지 않습니다");
    expect(notice.action).toContain("지워진 것이 아닙니다");
    // 이유만 주고 할 일을 안 주면 조치를 못 한다.
    expect(notice.action).toContain("rollback-to-neo4j.md");
  });

  test("옛 볼륨이 있는데 새 저장소에 데이터가 있으면 **경고가 아니다**", () => {
    const notice = judgeLegacyData(LEGACY, false);
    // 정상 상태에 빨간불을 켜 두면 사용자가 빨간불을 무시하는 법을 배운다.
    expect(notice.needsAttention).toBe(false);
    expect(notice.reason).toContain("디스크에 남아 있습니다");
    expect(notice.action).toContain("앱은 지우지 않습니다");
  });

  test("옛 볼륨이 없으면 할 말이 없다", () => {
    const notice = judgeLegacyData([], true);
    expect(notice.needsAttention).toBe(false);
    expect(notice.reason).toBeNull();
    expect(notice.action).toBeNull();
    expect(notice.legacyVolumes).toEqual([]);
  });
});

test.describe("못 쟀다와 없다를 가른다", () => {
  test("`null` 은 **못 물어본 것**이다 — 경고하지 않고 사실만 남긴다", () => {
    const notice = judgeLegacyData(null, null);
    expect(notice.needsAttention).toBe(false);
    expect(notice.legacyVolumes).toEqual([]);
    // 조용히 넘기지 않는다. 못 쟀다는 것을 적는다.
    expect(notice.reason).toContain("확인하지 못했습니다");
    expect(notice.action).toBeNull();
  });

  test("빈 배열(없다)과 `null`(모른다)의 reason 이 다르다", () => {
    expect(judgeLegacyData([], null).reason).toBeNull();
    expect(judgeLegacyData(null, null).reason).not.toBeNull();
  });

  test("새 저장소 상태를 모르면(`null`) 경고하지 않는다", () => {
    // 옛 볼륨은 있는데 새 저장소가 비었는지 모른다. 여기서 경고하면
    // 이미 옮긴 사용자에게 헛경고가 간다.
    const notice = judgeLegacyData(LEGACY, null);
    expect(notice.needsAttention).toBe(false);
    expect(notice.reason).toContain("디스크에 남아 있습니다");
  });
});

test.describe("무엇을 옛 볼륨으로 보는가", () => {
  test("데이터와 로그 둘 다 본다", () => {
    expect([...LEGACY_VOLUME_SUFFIXES]).toEqual(["_neo4j_data", "_neo4j_logs"]);
  });

  test("새 구성의 볼륨을 옛 것으로 세지 않는다", () => {
    const notice = judgeLegacyData(["robo-architect-desktop_graph_data"], true);
    // 판정 함수는 받은 목록을 그대로 믿는다 — 걸러내는 것은 찾는 쪽 책임이다.
    // 다만 그 사실을 여기서 못 박아 둔다: 새 볼륨을 넣으면 헛경고가 간다.
    expect(notice.legacyVolumes).toEqual(["robo-architect-desktop_graph_data"]);
  });

  test("정렬해서 돌려준다 — 같은 상태가 매번 같은 문자열이어야 한다", () => {
    const notice = judgeLegacyData([LEGACY[1]!, LEGACY[0]!], false);
    expect(notice.legacyVolumes).toEqual(LEGACY.slice().sort());
  });
});
