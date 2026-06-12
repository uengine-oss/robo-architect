from __future__ import annotations

from api.platform.neo4j import get_session


def next_change_id() -> str:
    """CHG-NNN 형식의 다음 ID를 반환한다 (MAX+1 패턴)."""
    query = """
    MATCH (n:RequirementChange)
    WHERE n.id STARTS WITH 'CHG-'
    RETURN max(toInteger(substring(n.id, 4))) AS maxNum
    """
    with get_session() as session:
        result = session.run(query)
        record = result.single()
        max_num = record["maxNum"] if record and record["maxNum"] is not None else 0
    return f"CHG-{max_num + 1:03d}"


def next_changeset_id() -> str:
    """CS-NNN 형식의 다음 ChangeSet ID를 반환한다."""
    query = """
    MATCH (n:ChangeSet)
    WHERE n.id STARTS WITH 'CS-'
    RETURN max(toInteger(substring(n.id, 3))) AS maxNum
    """
    with get_session() as session:
        result = session.run(query)
        record = result.single()
        max_num = record["maxNum"] if record and record["maxNum"] is not None else 0
    return f"CS-{max_num + 1:03d}"
