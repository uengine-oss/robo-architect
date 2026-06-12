from __future__ import annotations

import os

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger


def reset_change_data() -> None:
    """기존 RequirementChange·ChangeSet 노드 전체 삭제 (RESET_CHANGE_DATA=true 시에만 실행)."""
    if os.getenv("RESET_CHANGE_DATA", "").lower() != "true":
        return

    SmartLogger.log(
        "WARN",
        "RESET_CHANGE_DATA=true: deleting all RequirementChange and ChangeSet nodes.",
        category="requirement_changes.migration.reset",
        params={},
    )

    with get_session() as session:
        session.run("MATCH (n:RequirementChange) DETACH DELETE n")
        session.run("MATCH (n:ChangeSet) DETACH DELETE n")

    SmartLogger.log(
        "INFO",
        "RequirementChange and ChangeSet nodes cleared.",
        category="requirement_changes.migration.reset_done",
        params={},
    )
