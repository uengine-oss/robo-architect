"""
038 RequirementChange / ChangeSet 노드 초기화 스크립트.

spec FR-015: 마이그레이션 없이 기존 CHG/CS 노드를 전체 삭제.
수동 실행: python -m api.features.proposal_lifecycle.services.migration
"""

from __future__ import annotations

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger


def reset_change_data() -> dict:
    """RequirementChange 및 ChangeSet 노드를 모두 삭제하고 삭제 건수를 반환한다."""
    with get_session() as session:
        # 집계 WITH 를 쓰기 앞에 두지 않는다 — 세고 지우는 두 문장으로 나눈다.
        chg_count = session.run(
            "MATCH (n:RequirementChange) RETURN count(n) AS cnt"
        ).single()
        chg_deleted = chg_count["cnt"] if chg_count else 0
        if chg_deleted:
            session.run("MATCH (n:RequirementChange) DETACH DELETE n")

        cs_count = session.run("MATCH (n:ChangeSet) RETURN count(n) AS cnt").single()
        cs_deleted = cs_count["cnt"] if cs_count else 0
        if cs_deleted:
            session.run("MATCH (n:ChangeSet) DETACH DELETE n")

    SmartLogger.log(
        "INFO",
        f"038 migration: deleted {chg_deleted} RequirementChange nodes, {cs_deleted} ChangeSet nodes",
        category="proposal_lifecycle.migration.done",
        params={"chg_deleted": chg_deleted, "cs_deleted": cs_deleted},
    )
    print(f"Deleted {chg_deleted} RequirementChange nodes, {cs_deleted} ChangeSet nodes")
    return {"chg_deleted": chg_deleted, "cs_deleted": cs_deleted}


if __name__ == "__main__":
    reset_change_data()
