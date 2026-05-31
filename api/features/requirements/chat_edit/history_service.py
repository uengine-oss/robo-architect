"""Generic edit-history + per-item conversation log (035).

Spec 033 gave User Stories an `(:UserStory)-[:HAS_HISTORY]->(:EditHistory)`
trail. Conversational editing extends this to ANY requirement node (Epic /
Feature / UserStory) — the `HAS_HISTORY` relationship is label-agnostic — and
enriches each entry with the chat `source`, the NL `feedback`, and the agent's
`rationale`, so the collaborative History records not just *what* changed but
*why* and *who* decided it.

The running conversation (including proposals the user rejected) is also kept
as a JSON `chatEditLog` array on the node, so the decision process survives.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from api.features.requirements.requirements_contracts import (
    ChatEditLogEntry,
    EditHistoryItemDTO,
)


def record_history(
    session,
    node_id: str,
    *,
    source: str,
    changes: dict,
    actor: Any = None,
    feedback: str = "",
    rationale: str = "",
) -> Optional[str]:
    """Append an EditHistory entry to any requirement node; return its id."""
    row = session.run(
        """
        MATCH (n {id: $id})
        CREATE (h:EditHistory {
            id: randomUUID(), timestamp: datetime(),
            userName: $user_name, userEmail: $user_email,
            source: $source, feedback: $feedback, rationale: $rationale,
            changes: $changes_json
        })
        CREATE (n)-[:HAS_HISTORY]->(h)
        RETURN h.id AS id
        """,
        id=node_id,
        user_name=getattr(actor, "name", None) or "unknown",
        user_email=getattr(actor, "email", None) or "unknown",
        source=source,
        feedback=feedback or "",
        rationale=rationale or "",
        changes_json=json.dumps(changes or {}, ensure_ascii=False),
    ).single()
    return row["id"] if row else None


def fetch_history(session, node_id: str, limit: int = 50) -> list[EditHistoryItemDTO]:
    rows = session.run(
        """
        MATCH (n {id: $id})-[:HAS_HISTORY]->(h:EditHistory)
        RETURN h.id AS id, h.timestamp AS timestamp,
               h.userName AS userName, h.userEmail AS userEmail,
               h.changes AS changes, h.source AS source,
               h.feedback AS feedback, h.rationale AS rationale
        ORDER BY h.timestamp DESC
        LIMIT $limit
        """,
        id=node_id,
        limit=limit,
    ).data()
    return [_to_dto(r) for r in rows]


def append_chat_log(session, node_id: str, entry: ChatEditLogEntry) -> None:
    """Append one conversation turn to the node's `chatEditLog` JSON array."""
    row = session.run(
        "MATCH (n {id: $id}) RETURN n.chatEditLog AS log", id=node_id
    ).single()
    log = []
    if row and row["log"]:
        try:
            log = json.loads(row["log"])
        except (ValueError, TypeError):
            log = []
    log.append(entry.model_dump())
    session.run(
        "MATCH (n {id: $id}) SET n.chatEditLog = $log",
        id=node_id,
        log=json.dumps(log, ensure_ascii=False),
    )


def fetch_chat_log(session, node_id: str) -> list[ChatEditLogEntry]:
    row = session.run(
        "MATCH (n {id: $id}) RETURN n.chatEditLog AS log", id=node_id
    ).single()
    if not row or not row["log"]:
        return []
    try:
        raw = json.loads(row["log"])
    except (ValueError, TypeError):
        return []
    return [ChatEditLogEntry(**e) for e in raw]


def _to_dto(row: dict) -> EditHistoryItemDTO:
    ts = row.get("timestamp")
    if ts is None:
        ts_str = ""
    elif hasattr(ts, "iso_format"):
        ts_str = ts.iso_format()
    elif hasattr(ts, "isoformat"):
        ts_str = ts.isoformat()
    else:
        ts_str = str(ts)
    changes_raw = row.get("changes") or "{}"
    if isinstance(changes_raw, str):
        try:
            changes = json.loads(changes_raw)
        except (ValueError, TypeError):
            changes = {}
    else:
        changes = changes_raw
    return EditHistoryItemDTO(
        id=row.get("id") or "",
        timestamp=ts_str,
        userName=row.get("userName") or "unknown",
        userEmail=row.get("userEmail") or "unknown",
        changes=changes,
        source=row.get("source"),
        feedback=row.get("feedback") or None,
        rationale=row.get("rationale") or None,
    )
