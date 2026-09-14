"""구조화 US 문서 — 파싱부터 **저장까지** 검사.

단위 검사(`api/features/ingestion/tests/test_user_story_format.py`)는 파서가
무엇을 읽는지만 잰다. 그것만으로는 **배선이 끊겨도 통과한다** — 실제로 그랬다.

    GeneratedUserStory 에 필드를 더하고 upsert 에 컬럼을 더했는데,
    페이즈가 bulk 행을 **손으로 조립**해서 값이 영영 안 왔다.

모델에 필드를 더하는 것만으로는 안 따라온다. 그래서 여기서는 **그래프에 실제로
쓰고 되읽는다.**

**안전장치**

```
zz_ 로 시작하는 이름만 쓴다        실 프로젝트 graph 를 안 건드린다
끝나고 그 graph 만 지운다          이름을 두 번 확인한다
NEO4J_DATABASE 를 이 프로세스에서만 바꾼다
```

    robo-architect/.venv/bin/python scripts/verify_user_story_format.py
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

G = "zz_verify_us_format"
assert G.startswith("zz_"), "검사 graph 이름이 안전하지 않다"
os.environ["NEO4J_DATABASE"] = G

from api.platform import pg  # noqa: E402

FIXTURE = ROOT / "api/features/ingestion/tests/fixtures/posco_user_stories.md"

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


def main() -> int:
    from api.features.ingestion.event_storming.neo4j_client import Neo4jClient
    from api.features.ingestion.user_story_format import (
        looks_like_user_story_document,
        parse_user_story_document,
        to_generated_user_stories,
    )

    text = FIXTURE.read_text(encoding="utf-8")

    print("\n── 감지 ────────────────────────────────────────────────")
    check("구조화 문서를 알아본다", looks_like_user_story_document(text), True)
    # **이쪽이 더 중요하다.** 기존 문서가 새 길로 새면 LLM 을 안 거쳐 빈 결과가
    # 되고, 그건 조용하다.
    for label, sample in [
        ("보통 요구사항 문서", "# 요구사항\n회원은 이름으로 가입한다.\n"),
        ("코드 분석 입력(BL)", "BL[1] 인증을 수행한다\nBL[2] 이력을 적재한다\n"),
        ("옛 ID 체계", "##### [US-001] 회원 가입\n"),
    ]:
        check(f"{label} 는 기존 경로로", looks_like_user_story_document(sample), False)

    print("\n── 파싱 ────────────────────────────────────────────────")
    doc = parse_user_story_document(text)
    check("스토리 수", len(doc.stories), 8)
    check("목록과 명세가 안 어긋난다",
          (doc.listed_without_spec, doc.spec_without_listing), ([], []))

    print("\n── 저장 (실제 그래프) ──────────────────────────────────")
    _drop()
    pg.query("SELECT og_create_graph(%s)", (G,))
    try:
        stories = to_generated_user_stories(doc)
        # **페이즈가 조립하는 행을 그대로 흉내 낸다.** 여기가 끊겼던 자리다.
        rows = [
            {
                "id": u.id, "role": u.role, "action": u.action, "benefit": u.benefit,
                "priority": u.priority, "status": "draft", "ui_description": "x",
                "display_name": u.displayName, "source_screen_name": None,
                "source_unit_id": None, "sequence": u.sequence,
                "acceptance_criteria": list(u.acceptance_criteria),
                "epic_id": getattr(u, "epic_id", None),
                "epic_name": getattr(u, "epic_name", None),
                "tasks": list(getattr(u, "tasks", []) or []),
            }
            for u in stories
        ]
        Neo4jClient().bulk_create_user_stories(rows, session_id="zzsess", phase="verify")

        read = {
            r["og_cypher"]["id"]: r["og_cypher"]
            for r in pg.query(
                "SELECT * FROM og_cypher(%s,%s)",
                (G, "MATCH (u:UserStory) RETURN u.id AS id, u.epicId AS e, "
                    "u.epicName AS en, u.taskIds AS t, u.displayName AS d"),
            )
        }
        check("여덟 개가 다 저장됐다", len(read), 8)
        # **ID 를 다시 매기지 않는다** — 이 기능의 이유다.
        check("문서의 ID 가 그대로 남는다",
              sorted(read), sorted([u.id for u in stories]))
        check("에픽이 저장된다", read["US-FR-001"]["e"], "EP-001")
        check("에픽 이름도", read["US-FR-001"]["en"], "인사 의사결정 및 평가 지원 자동화")
        check("태스크가 저장된다", read["US-FR-001"]["t"],
              ["US-FR-001-TASK-001", "US-FR-001-TASK-002", "US-FR-001-TASK-003"])
        check("문서의 스토리명이 남는다",
              read["US-FR-001"]["d"], "시뮬레이션 기반 인력계획 수립")
        check("접두사 ID 도 그대로", read["PROJ-US-FR-020"]["e"], "EP-006")
        # 비기능은 태스크 0개가 정상. "없다"와 "안 저장됐다"를 가른다.
        check("비기능은 태스크 0개", read["US-NFR-001"]["t"], [])
        check("비기능도 에픽은 있다", read["US-NFR-001"]["e"], "EP-007")

        print("\n── 다시 써도 안 지워진다 ───────────────────────────────")
        # 같은 프로젝트를 LLM 경로로 재인제스천하면 에픽·태스크가 **비어서**
        # 온다. 그때 덮으면 조용히 사라진다.
        blank = [
            {**r, "epic_id": None, "epic_name": None, "tasks": []} for r in rows
        ]
        Neo4jClient().bulk_create_user_stories(blank, session_id="zzsess", phase="verify")
        again = pg.query(
            "SELECT * FROM og_cypher(%s,%s)",
            (G, "MATCH (u:UserStory {id:'US-FR-001'}) RETURN u.epicId AS e, u.taskIds AS t"),
        )[0]["og_cypher"]
        check("빈 값이 에픽을 안 덮는다", again["e"], "EP-001")
        check("빈 값이 태스크를 안 덮는다", len(again["t"] or []), 3)

        print("\n── Feature 연결 (US 를 에픽 묶음에 붙인다) ────────────")
        # **다섯 프로젝트 전부 0건이었다.** 오류도 로그도 없었다 —
        # `OPTIONAL MATCH` + 그 변수의 `DELETE` 가 Ontological 에서 매치가
        # 없을 때 행을 0개로 만들어, 뒤따르는 MERGE 가 아예 안 돌았다.
        # 첫 인제스천에서는 US 에 붙은 Feature 가 없으니 **항상** 그 경우다.
        cli = Neo4jClient()
        pg.query("SELECT * FROM og_cypher(%s,%s)", (G, "CREATE (:Feature {id:'zzF-1'})"))
        pg.query("SELECT * FROM og_cypher(%s,%s)", (G, "CREATE (:Feature {id:'zzF-2'})"))

        check("처음 붙이면 True",
              cli.link_user_story_to_feature("US-FR-001", "zzF-1",
                                             source="llm", respect_manual=True), True)
        linked = pg.query(
            "SELECT * FROM og_cypher(%s,%s)",
            (G, "MATCH (:Feature)-[r:HAS_USER_STORY]->(:UserStory) RETURN count(r) AS c"),
        )[0]["og_cypher"]["c"]
        check("연결이 실제로 생긴다", linked, 1)

        cli.link_user_story_to_feature("US-FR-001", "zzF-2", source="llm", respect_manual=True)
        after = pg.query(
            "SELECT * FROM og_cypher(%s,%s)",
            (G, "MATCH (f:Feature)-[:HAS_USER_STORY]->(:UserStory) RETURN collect(f.id) AS f"),
        )[0]["og_cypher"]["f"]
        # US 는 Feature 하나에만 속한다 — 옛 연결이 안 지워지면 둘이 된다.
        check("옮기면 옛 연결이 지워진다", after, ["zzF-2"])

        pg.query("SELECT * FROM og_cypher(%s,%s)",
                 (G, "MATCH (:Feature)-[r:HAS_USER_STORY]->(:UserStory) SET r.source='manual'"))
        check("사람이 붙인 것은 안 덮는다",
              cli.link_user_story_to_feature("US-FR-001", "zzF-1",
                                             source="llm", respect_manual=True), False)
    finally:
        _drop()
        print("\n일회용 graph 삭제")

    print(f"\n검사 {_n}종 — " + ("전부 통과" if not _fail else f"{len(_fail)}종 실패"))
    for f in _fail:
        print("  실패:", f)
    return 1 if _fail else 0


if __name__ == "__main__":
    sys.exit(main())
