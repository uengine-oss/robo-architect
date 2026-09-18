"""분석이 설계를 지우지 않는가 — **내용으로** 확인한다 (spec 058 T036 · US2).

## 재는 방법

분석이 대상 graph 에 하는 파괴적 동작을 **원본 질의 그대로** 돌린다
(`robo-data-analyzer/graph/product_writer.py` 의 `_replace`). 다시 쓰지 않는다 —
재구현이 원본보다 옳으면 결함을 가린다.

    ① zz_ graph 둘을 만든다 (설계용 · 분석용)
    ② 설계용에 **설계 노드**(소유자 표시 없음)와 **분석 노드**(_owner='analyzer')를 둘 다 심는다
       — 실제 운영에서 한 graph 에 섞여 있을 수 있는 모양이다
    ③ 분석용에도 분석 노드를 심는다
    ④ 양쪽 내용을 **이름 목록으로** 떠 둔다 (개수가 아니다)
    ⑤ 분석용에 파괴적 질의를 돌린다
    ⑥ 분석용의 분석 노드가 **정말 사라졌는지** 본다
       — 안 사라졌으면 아무것도 증명하지 못한 것이다(exit 3)
    ⑦ 설계용이 **내용까지 그대로인지** 본다

## 폭발 반경도 같이 잰다

`--measure-blast-radius` 를 주면, **설계용 graph 에** 같은 질의를 돌려 무엇이 죽고
무엇이 사는지 센다. 검증 graph 에서만 돈다.

이것이 필요한 이유: 2026-09-18 에 읽어 보니 main 의 파괴적 질의는 `_owner='analyzer'`
로 **범위가 잡혀 있다.** 즉 분석이 설계 graph 를 가리켜도 설계 노드는 살아남는다 —
예전의 "설계가 통째로 지워진다"와 다르다. 말로 옮기기 전에 재서 확인한다.

## 안전

`zz_` 로 시작하는 graph 만 만들고 지운다. 치우기 실패도 검사 실패다.
**실사용 graph(`robo`·`analyzer_run`·`prj_*`)는 건드리지 않는다.**

## 종료 코드

    0  설계가 온전하다      1  설계가 변했다      3  못 쟀다
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PREFIX = "zz_"
DESIGN_GRAPH = "zz_iso_design"
ANALYSIS_GRAPH = "zz_iso_analysis"
OWNER = "analyzer"

# 분석 파이프라인의 파괴적 질의 **그대로**. 원본이 바뀌면 여기도 바뀌어야 하고,
# 그 사실을 아래 `assert_query_matches_source()` 가 확인한다.
WIPE_RELATIONSHIPS = """
MATCH ()-[relationship]-()
WHERE relationship._owner = '{owner}'
DELETE relationship
"""
WIPE_NODES = """
MATCH (node)
WHERE node._owner = '{owner}'
  AND NOT node:TABLE AND NOT node:COLUMN
DETACH DELETE node
"""

SOURCE = Path("robo-analyzer/robo-data-analyzer/graph/product_writer.py")


class Measured(Exception):
    """쟀는데 틀렸다."""


class Unmeasured(Exception):
    """못 쟀다 — 실패와 구분한다."""


def psql(container: str, user: str, database: str, sql: str) -> str:
    proc = subprocess.run(
        ["docker", "exec", "-i", container, "psql", "-U", user, "-d", database,
         "-v", "ON_ERROR_STOP=1", "-tAc", sql],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        tail = proc.stderr.strip().splitlines()[-1:] or [proc.stderr.strip()]
        raise Unmeasured(f"psql 실패: {tail[0][:120]}")
    return proc.stdout.strip()


def assert_query_matches_source(repo_root: Path) -> None:
    """**원본과 같은 질의를 쓰고 있는가.**

    여기 박아 둔 질의가 원본에서 떨어져 나가면, 이 검사는 실제로 도는 것과 다른 것을
    재면서 계속 초록을 낸다. 그게 이 저장소가 반복해 밟은 함정이다.
    """
    source = repo_root / SOURCE
    if not source.is_file():
        raise Unmeasured(f"원본을 못 찾았다: {source}")
    text = source.read_text(encoding="utf-8")
    if "DETACH DELETE node" not in text:
        raise Unmeasured("원본에 노드 삭제 질의가 없다 — 이 검사가 낡았다")
    # 범위 술어가 살아 있는지 본다. 이것이 없어지면 폭발 반경이 완전히 달라진다.
    if "_owner = $owner" not in text:
        raise Unmeasured(
            "원본의 삭제 질의에 `_owner = $owner` 범위가 없다 — "
            "폭발 반경이 바뀌었으니 이 검사를 다시 읽어야 한다"
        )


def cypher(container: str, user: str, database: str, graph: str, query: str) -> str:
    escaped = query.replace("'", "''")
    return psql(container, user, database, f"SELECT og_cypher('{graph}', $${query}$$)")


def names(container: str, user: str, database: str, graph: str, label: str) -> list[str]:
    """라벨별 **이름 목록**. 개수가 아니다 — 개수만 보면 이름이 바뀌어도 통과한다."""
    out = cypher(container, user, database, graph,
                 f"MATCH (n:{label}) RETURN n.name AS name ORDER BY n.name")
    found = re.findall(r'"name": "([^"]*)"', out)
    return sorted(found)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", default="robo-og-measure-graph-db-1")
    parser.add_argument("--user", default="robo")
    parser.add_argument("--database", default="robo")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--measure-blast-radius", action="store_true",
                        help="설계용 zz_ graph 에도 파괴적 질의를 돌려 무엇이 죽는지 센다")
    args = parser.parse_args(argv)

    for graph in (DESIGN_GRAPH, ANALYSIS_GRAPH):
        if not graph.startswith(PREFIX):
            print(f"'{PREFIX}' 로 시작하지 않는 graph: {graph}")
            return 3

    run = lambda graph, query: cypher(args.container, args.user, args.database, graph, query)
    look = lambda graph, label: names(args.container, args.user, args.database, graph, label)

    lines: list[str] = []
    verdict = 0
    try:
        assert_query_matches_source(Path(args.repo_root))
        lines.append("  ✓ 파괴적 질의가 원본과 같은 모양이다(범위 술어 포함)")

        for graph in (DESIGN_GRAPH, ANALYSIS_GRAPH):
            psql(args.container, args.user, args.database, f"SELECT og_create_graph('{graph}')")

        # 설계 graph: 설계 노드 + (섞여 있을 수 있는) 분석 노드
        design_names = [f"design_{i}" for i in range(4)]
        for name in design_names:
            run(DESIGN_GRAPH, f"CREATE (n:ZzDesign {{name:'{name}'}})")
        mixed_names = [f"mixed_{i}" for i in range(2)]
        for name in mixed_names:
            run(DESIGN_GRAPH, f"CREATE (n:ZzAnalyzed {{name:'{name}', _owner:'{OWNER}'}})")
        # 분석 graph: 분석 노드
        analysis_names = [f"analysis_{i}" for i in range(6)]
        for name in analysis_names:
            run(ANALYSIS_GRAPH, f"CREATE (n:ZzAnalyzed {{name:'{name}', _owner:'{OWNER}'}})")

        before_design = look(DESIGN_GRAPH, "ZzDesign")
        before_mixed = look(DESIGN_GRAPH, "ZzAnalyzed")
        before_analysis = look(ANALYSIS_GRAPH, "ZzAnalyzed")
        if before_design != sorted(design_names) or before_analysis != sorted(analysis_names):
            raise Unmeasured(
                f"심은 것이 들어가지 않았다 (설계 {before_design} · 분석 {before_analysis})"
            )
        lines.append(f"  ✓ 심음 — 설계 {len(before_design)}건 · 섞인 분석 {len(before_mixed)}건 "
                     f"· 분석 graph {len(before_analysis)}건")

        # ⑤ 분석 graph 에 파괴적 질의
        run(ANALYSIS_GRAPH, WIPE_RELATIONSHIPS.format(owner=OWNER).strip())
        run(ANALYSIS_GRAPH, WIPE_NODES.format(owner=OWNER).strip())

        # ⑥ **정말 지워졌는지** 먼저 본다. 안 지워졌으면 아무것도 증명하지 못했다.
        after_analysis = look(ANALYSIS_GRAPH, "ZzAnalyzed")
        if after_analysis:
            raise Unmeasured(
                f"파괴적 질의가 실제로 지우지 않았다 (분석 graph 에 {after_analysis} 남음) — "
                "이 상태로 '설계가 온전하다'고 말하면 아무것도 증명하지 못한 것이다"
            )
        lines.append("  ✓ 파괴적 질의가 실제로 돌았다 (분석 graph 의 분석 노드 0건)")

        # ⑦ 설계는 **내용까지** 그대로여야 한다
        after_design = look(DESIGN_GRAPH, "ZzDesign")
        if after_design != before_design:
            raise Measured(f"설계 내용이 변했다: {before_design} → {after_design}")
        lines.append(f"  ✓ 설계 내용이 그대로다 — {after_design}")

        if args.measure_blast_radius:
            lines.append("  · 폭발 반경 측정: 설계용 zz_ graph 에 같은 질의를 돌린다")
            run(DESIGN_GRAPH, WIPE_RELATIONSHIPS.format(owner=OWNER).strip())
            run(DESIGN_GRAPH, WIPE_NODES.format(owner=OWNER).strip())
            survived = look(DESIGN_GRAPH, "ZzDesign")
            killed = look(DESIGN_GRAPH, "ZzAnalyzed")
            lines.append(f"    설계 노드   {len(survived)}/{len(before_design)} 살아남음 — {survived}")
            lines.append(f"    분석 노드   {len(killed)}/{len(before_mixed)} 살아남음 — {killed or '전멸'}")
            if survived != before_design:
                raise Measured(
                    "분석 graph 를 설계 graph 로 가리키면 설계 노드까지 죽는다 — "
                    "범위 술어가 없거나 듣지 않는다"
                )
            lines.append("    → 범위 술어가 듣는다: 설계 노드는 살고 분석 노드만 죽는다")
    except Measured as exc:
        lines.append(f"  ✗ {exc}")
        verdict = 1
    except Unmeasured as exc:
        lines.append(f"  ? 못 쟀다: {exc}")
        verdict = 3

    # 치우기 — 실패해도 예외를 던지지 않고 남은 것을 보고한다
    leftovers: list[str] = []
    for graph in (DESIGN_GRAPH, ANALYSIS_GRAPH):
        try:
            psql(args.container, args.user, args.database, f"SELECT og_drop_graph('{graph}')")
        except Unmeasured as exc:
            leftovers.append(f"og_drop_graph({graph}): {exc}")
    try:
        left = psql(args.container, args.user, args.database,
                    f"SELECT count(*) FROM og_catalog.graph WHERE name IN ('{DESIGN_GRAPH}','{ANALYSIS_GRAPH}')")
        if left != "0":
            leftovers.append(f"graph 가 {left} 개 남았다")
    except Unmeasured as exc:
        leftovers.append(f"치운 뒤 확인 실패: {exc}")

    print("\n".join(lines) or "  (아무것도 못 했다)")
    if leftovers:
        print("\n치우기 실패 — 검사 실패로 친다:")
        for problem in leftovers:
            print(f"  ✗ {problem}")
        verdict = 3 if verdict == 3 else 1

    print("=" * 60)
    print({0: "설계가 온전하다", 1: "실패", 3: "못 쟀다"}[verdict])
    return verdict


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
