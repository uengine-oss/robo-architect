from __future__ import annotations

from api.platform.neo4j import get_session


def next_proposal_id() -> str:
    """PRO-NNN 형식의 다음 ID를 반환한다 (MAX+1 패턴)."""
    query = """
    MATCH (n:Proposal)
    WHERE n.id STARTS WITH 'PRO-'
    RETURN max(toInteger(substring(n.id, 4))) AS maxNum
    """
    with get_session() as session:
        result = session.run(query)
        record = result.single()
        max_num = record["maxNum"] if record and record["maxNum"] is not None else 0
    return f"PRO-{max_num + 1:03d}"
