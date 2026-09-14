"""Ontological 에서 **읽기 투영**이 진짜로 도는가.

세 갈래 모두 `enterprise-todo.md` §21 의 비호환 위에 있었다.

```
1  RETURN {...} AS 다른이름 … ORDER BY 다른이름.f   → 예외를 던진다
   (별칭이 원래 변수와 **같은 이름**이면 통과한다 — 그래서 여덟 곳 중 셋만 진짜였다)
3  collect(DISTINCT x {...}) 가 매치 없을 때        → [] 가 아니라 [{...: null}]
                                                      = **유령 한 개**
```

예외는 위에서 `except Exception` 이 먹고, 유령은 개수만 보면 그럴듯하다.
**둘 다 조용하다.** 그래서 여기서는 실제 그래프에 쓰고 **되읽는다**.

```
zz_ 로 시작하는 이름만 쓴다        실 프로젝트 graph 를 안 건드린다
끝나고 그 graph 만 지운다
```

    robo-architect/.venv/bin/python scripts/verify_og_read_projections.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
os.environ.setdefault("AUTH_JWT_SECRET", "verify-only-secret")
os.environ.setdefault("AUTH_ROLE_SECRET", "verify-only-role-secret")

G = "zz_verify_og_reads"
assert G.startswith("zz_"), "검사 graph 이름이 안전하지 않다"
os.environ["NEO4J_DATABASE"] = G

from api.platform import pg  # noqa: E402

_fail: list[str] = []
_n = 0


def check(label: str, got, want) -> None:
    global _n
    _n += 1
    ok = got == want
    print(f"{'ok ' if ok else 'FAIL'} {label}" + ("" if ok else f"\n     got={got!r}\n     want={want!r}"))
    if not ok:
        _fail.append(label)


def _drop() -> None:
    if any(r["name"] == G for r in pg.query("SELECT name FROM og_catalog.graph")):
        pg.query("SELECT og_drop_graph(%s)", (G,))


def run(q: str) -> list[dict]:
    return [r["og_cypher"] for r in pg.query("SELECT * FROM og_cypher(%s,%s)", (G, q))]


def main() -> int:
    from api.features.ingestion.event_storming.neo4j_client import Neo4jClient

    _drop()
    pg.query("SELECT og_create_graph(%s)", (G,))
    try:
        # Zeta 가 알파벳 뒤. 정렬이 실제로 도는지 가리려면 입력 순서와 달라야 한다.
        run("CREATE (:BoundedContext {id:'bcZ', name:'Zeta', userStoryIds:['US-FR-001']})")
        # 비어 있는 쪽도 둔다 — `[]` 와 `['[','\"',…]` 를 가르는 자리다.
        run("CREATE (:BoundedContext {id:'bcA', name:'Alpha', userStoryIds:[]})")
        # bcZ 에만 애그리거트. **bcA 는 일부러 비워 둔다** — 유령이 드러나는 자리다.
        run("MATCH (b:BoundedContext {id:'bcZ'}) "
            "CREATE (b)-[:HAS_AGGREGATE]->(:Aggregate {id:'aggZ', name:'Zulu', "
            "invariants:['잔액은 음수가 될 수 없다'], enumerations:['A','B'], valueObjects:['VO']})")
        run("MATCH (b:BoundedContext {id:'bcZ'}) "
            "CREATE (b)-[:HAS_AGGREGATE]->(:Aggregate {id:'aggA', name:'Able'})")
        # aggZ 에만 커맨드. aggA 는 커맨드 0개.
        run("MATCH (a:Aggregate {id:'aggZ'}) "
            "CREATE (a)-[:HAS_COMMAND]->(:Command {id:'cZ', name:'Zap'})")
        run("MATCH (a:Aggregate {id:'aggZ'}) "
            "CREATE (a)-[:HAS_COMMAND]->(:Command {id:'cA', name:'Ack'})")
        # cZ 만 이벤트를 낸다.
        run("MATCH (c:Command {id:'cZ'}) CREATE (c)-[:EMITS]->(:Event {id:'eZ', name:'Zapped'})")
        run("CREATE (:UserStory {id:'US-FR-002', action:'b'})")
        run("CREATE (:UserStory {id:'US-FR-001', action:'a'})")
        run("MATCH (u:UserStory {id:'US-FR-001'}), (b:BoundedContext {id:'bcZ'}) "
            "CREATE (u)-[:IMPLEMENTS]->(b)")

        cli = Neo4jClient()

        print("\n── BoundedContext ──────────────────────────────────────")
        # 예외를 던지면 여기서 터진다. 던지던 시절에는 호출부의 `except` 가
        # 먹어서 ctx.bounded_contexts 가 빈 채 다음 단계로 갔다.
        bcs = cli.get_all_bounded_contexts()
        check("두 개를 다 읽는다", len(bcs), 2)
        check("이름순으로 온다", [b["name"] for b in bcs], ["Alpha", "Zeta"])
        by = {b["name"]: b for b in bcs}
        # **유령**: 애그리거트가 없는 BC 가 {id:null,name:null} 한 개를 받았다.
        check("애그리거트 없는 BC 는 빈 목록", by["Alpha"]["aggregates"], [])
        check("있는 BC 는 두 개",
              sorted(a["name"] for a in by["Zeta"]["aggregates"]), ["Able", "Zulu"])

        # **배열이 맵 투영을 지나면 JSON 문자열이 된다.** 문자열도 순회가 되므로
        # 호출부는 글자를 하나씩 돌고, 오류는 안 난다. 다섯 글자짜리 id 목록이
        # 371개의 한 글자가 됐고 그 결과가 Command 0개였다.
        check("userStoryIds 가 list 로 온다", type(by["Zeta"]["userStoryIds"]).__name__, "list")
        check("내용이 온전하다", by["Zeta"]["userStoryIds"], ["US-FR-001"])
        check("빈 BC 는 빈 list", by["Alpha"]["userStoryIds"], [])

        print("\n── Aggregate ───────────────────────────────────────────")
        aggs = cli.get_aggregates_by_bc("bcZ")
        check("두 개를 다 읽는다", len(aggs), 2)
        check("이름순으로 온다", [a["name"] for a in aggs], ["Able", "Zulu"])
        agg_by = {a["name"]: a for a in aggs}
        check("커맨드 없는 애그리거트는 빈 목록", agg_by["Able"]["commands"], [])
        check("있는 쪽은 두 개",
              sorted(c["name"] for c in agg_by["Zulu"]["commands"]), ["Ack", "Zap"])
        # `enumerations`·`valueObjects` 는 호출부가 손으로 풀고 있었고
        # `invariants` 는 빠져 있었다 — 셋을 같이 잰다.
        for f, want in [("invariants", ["잔액은 음수가 될 수 없다"]),
                        ("enumerations", ["A", "B"]),
                        ("valueObjects", ["VO"])]:
            check(f"{f} 가 list 로 온다", agg_by["Zulu"][f], want)

        print("\n── Command ─────────────────────────────────────────────")
        cmds = cli.get_commands_by_aggregate("aggZ")
        check("두 개를 다 읽는다", len(cmds), 2)
        check("이름순으로 온다", [c["name"] for c in cmds], ["Ack", "Zap"])
        cmd_by = {c["name"]: c for c in cmds}
        check("이벤트 없는 커맨드는 빈 목록", cmd_by["Ack"]["emits"], [])
        check("있는 쪽은 한 개", [e["name"] for e in cmd_by["Zap"]["emits"]], ["Zapped"])

        print("\n── UserStory ───────────────────────────────────────────")
        uss = cli.get_all_user_stories()
        check("두 개를 다 읽는다", len(uss), 2)
        check("id 순으로 온다", [u["id"] for u in uss], ["US-FR-001", "US-FR-002"])
        us_by = {u["id"]: u for u in uss}
        check("연결 없는 US 는 빈 목록", us_by["US-FR-002"]["implemented_in"], [])
        check("있는 쪽은 라벨과 이름이 온다",
              us_by["US-FR-001"]["implemented_in"],
              [{"type": "BoundedContext", "name": "Zeta", "id": "bcZ"}])
    finally:
        _drop()
        print("\n일회용 graph 삭제")

    print(f"\n검사 {_n}종 — " + ("전부 통과" if not _fail else f"{len(_fail)}종 실패"))
    for f in _fail:
        print("  실패:", f)
    return 1 if _fail else 0


if __name__ == "__main__":
    sys.exit(main())
