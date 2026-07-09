"""047 — 분석된 그래프(소스) 목록 조회(FR-003).

system DB 의 SHOW DATABASES 로 후보를 얻어, 각 DB 에 오퍼레이션(FUNCTION/PROCEDURE…)이
있는지 프로브해 분석 그래프만 반환한다. SHOW DATABASES 불가 시 설정된 단일 DB 로 폴백
(research D4). analyzer 그래프는 읽기 전용.
"""
from __future__ import annotations

from api.platform.neo4j import ANALYZER_NEO4J_DATABASE, get_session
from api.platform.observability.smart_logger import SmartLogger

_OP_COUNT = (
    "MATCH (n) WHERE n:FUNCTION OR n:PROCEDURE OR n:METHOD OR n:TRIGGER "
    "RETURN count(n) AS c"
)


def _probe(names: list[str]) -> list[dict]:
    out: list[dict] = []
    for db in names:
        try:
            with get_session(database=db) as s:
                c = s.run(_OP_COUNT).single()["c"]
        except Exception:
            continue
        if c and c > 0:
            out.append({"db": db, "operationCount": c, "label": db})
    return sorted(out, key=lambda x: (-x["operationCount"], x["db"]))


def list_sources() -> list[dict]:
    """분석 그래프(오퍼레이션>0)를 가진 DB 목록. 없으면 빈 배열."""
    try:
        with get_session(database="system") as s:
            names = sorted({r["name"] for r in s.run("SHOW DATABASES")
                            if r["name"] and r["name"] != "system"})
    except Exception as e:
        SmartLogger.log("WARN", f"reverse sources SHOW DATABASES 실패, 단일 폴백: {e}",
                        category="proposal_lifecycle.reverse.sources_fallback")
        fallback = ANALYZER_NEO4J_DATABASE or "neo4j"
        return _probe([fallback])
    return _probe(names)
