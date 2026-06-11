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
        chg_result = session.run(
            "MATCH (n:RequirementChange) WITH count(n) AS cnt DETACH DELETE (n) RETURN cnt"
        )
        chg_count = chg_result.single()
        chg_deleted = chg_count["cnt"] if chg_count else 0

        cs_result = session.run(
            "MATCH (n:ChangeSet) WITH count(n) AS cnt DETACH DELETE (n) RETURN cnt"
        )
        cs_count = cs_result.single()
        cs_deleted = cs_count["cnt"] if cs_count else 0

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
