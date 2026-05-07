"""Neo4j read/write helpers for FigmaBinding, StoryboardPageMapping, BindingHistoryEvent.

All Cypher goes through `api/platform/neo4j.get_session()` per Constitution I.
No domain logic here — service.py owns business rules.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from api.platform.neo4j import get_session


SINGLETON_ID = "singleton"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─── FigmaBinding ─────────────────────────────────────────────────────────


def get_active_binding() -> dict[str, Any] | None:
    """Return the singleton binding if status != 'disconnected', else None."""
    with get_session() as session:
        rec = session.run(
            """
            MATCH (b:FigmaBinding {id: $id})
            WHERE b.status <> 'disconnected'
            RETURN b
            """,
            id=SINGLETON_ID,
        ).single()
        if not rec:
            return None
        node = rec["b"]
        return _binding_node_to_dict(node)


def get_any_binding_record() -> dict[str, Any] | None:
    """Return the singleton binding regardless of status (for replace/upsert flows)."""
    with get_session() as session:
        rec = session.run(
            "MATCH (b:FigmaBinding {id: $id}) RETURN b",
            id=SINGLETON_ID,
        ).single()
        if not rec:
            return None
        return _binding_node_to_dict(rec["b"])


def upsert_binding(
    *,
    figma_file_key: str,
    figma_file_name: str,
    connected_by: str,
) -> dict[str, Any]:
    """Create or replace the singleton binding row to a fresh active state.

    Resets `status` to 'active', updates `connectedAt`/`connectedBy` to now,
    clears `lastSyncAt`. Existing `:StoryboardPageMapping` rows are NOT touched
    here — caller (service.replace_binding) is responsible for archiving them.
    """
    now = _now_iso()
    with get_session() as session:
        rec = session.run(
            """
            MERGE (b:FigmaBinding {id: $id})
            SET b.figmaFileKey = $file_key,
                b.figmaFileName = $file_name,
                b.connectedBy = $connected_by,
                b.connectedAt = $now,
                b.lastSyncAt = null,
                b.status = 'active'
            RETURN b
            """,
            id=SINGLETON_ID,
            file_key=figma_file_key,
            file_name=figma_file_name,
            connected_by=connected_by,
            now=now,
        ).single()
    return _binding_node_to_dict(rec["b"])


def mark_binding_status(status: str) -> None:
    """Set status to 'active' | 'unreachable' | 'disconnected' on the singleton."""
    with get_session() as session:
        session.run(
            "MATCH (b:FigmaBinding {id: $id}) SET b.status = $status",
            id=SINGLETON_ID,
            status=status,
        )


def update_last_sync_at() -> None:
    with get_session() as session:
        session.run(
            "MATCH (b:FigmaBinding {id: $id}) SET b.lastSyncAt = $now",
            id=SINGLETON_ID,
            now=_now_iso(),
        )


# ─── StoryboardPageMapping ────────────────────────────────────────────────


def list_storyboard_mappings(status: str | None = "active") -> list[dict[str, Any]]:
    """Return mappings attached to the active binding. Pass status=None to include archived."""
    cypher = """
        MATCH (b:FigmaBinding {id: $id})-[:MAPS_STORYBOARD]->(m:StoryboardPageMapping)
        """
    if status is not None:
        cypher += "WHERE m.status = $status\n"
    cypher += "RETURN m ORDER BY m.figmaPageName"

    with get_session() as session:
        records = session.run(cypher, id=SINGLETON_ID, status=status).data()
    return [_mapping_node_to_dict(r["m"]) for r in records]


def get_mapping_by_command_id(command_id: str) -> dict[str, Any] | None:
    with get_session() as session:
        rec = session.run(
            "MATCH (m:StoryboardPageMapping {commandId: $cid}) RETURN m",
            cid=command_id,
        ).single()
        if not rec:
            return None
        return _mapping_node_to_dict(rec["m"])


def upsert_storyboard_mapping(
    *,
    command_id: str,
    figma_page_id: str,
    figma_page_name: str,
) -> dict[str, Any]:
    """Create or update a mapping. Attaches MAPS_STORYBOARD edge to the active
    binding and MAPS edge to the Command if it exists.
    """
    now = _now_iso()
    with get_session() as session:
        rec = session.run(
            """
            MATCH (b:FigmaBinding {id: $bid})
            MERGE (m:StoryboardPageMapping {commandId: $cid})
            ON CREATE SET m.id = $newid,
                          m.lastRenameAt = null
            SET m.figmaPageId = $page_id,
                m.figmaPageName = $page_name,
                m.status = 'active'
            MERGE (b)-[:MAPS_STORYBOARD]->(m)
            WITH m
            OPTIONAL MATCH (c:Command {id: $cid})
            FOREACH (cc IN CASE WHEN c IS NULL THEN [] ELSE [c] END |
                MERGE (m)-[:MAPS]->(cc)
            )
            RETURN m
            """,
            bid=SINGLETON_ID,
            cid=command_id,
            newid=str(uuid.uuid4()),
            page_id=figma_page_id,
            page_name=figma_page_name,
        ).single()
    return _mapping_node_to_dict(rec["m"])


def update_mapping_cached_name(command_id: str, new_name: str) -> None:
    now = _now_iso()
    with get_session() as session:
        session.run(
            """
            MATCH (m:StoryboardPageMapping {commandId: $cid})
            SET m.figmaPageName = $new_name,
                m.lastRenameAt = $now
            """,
            cid=command_id,
            new_name=new_name,
            now=now,
        )


def archive_storyboard_mapping(command_id: str) -> None:
    with get_session() as session:
        session.run(
            "MATCH (m:StoryboardPageMapping {commandId: $cid}) SET m.status = 'archived'",
            cid=command_id,
        )


def archive_all_active_mappings() -> int:
    """Bulk-archive all currently-active mappings (used by replace flow). Returns count."""
    with get_session() as session:
        rec = session.run(
            """
            MATCH (m:StoryboardPageMapping {status: 'active'})
            SET m.status = 'archived'
            RETURN count(m) AS n
            """
        ).single()
    return int(rec["n"]) if rec else 0


def count_storyboard_mappings_by_status() -> dict[str, int]:
    with get_session() as session:
        rec = session.run(
            """
            MATCH (b:FigmaBinding {id: $id})-[:MAPS_STORYBOARD]->(m:StoryboardPageMapping)
            RETURN m.status AS status, count(m) AS n
            """,
            id=SINGLETON_ID,
        ).data()
    out = {"active": 0, "archived": 0}
    for r in rec:
        s = r.get("status") or "active"
        out[s] = int(r.get("n") or 0)
    return out


# ─── BindingHistoryEvent ─────────────────────────────────────────────────


def append_history_event(
    *,
    event_type: str,
    actor: str,
    figma_file_key: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Append-only audit log. Always succeeds (best-effort)."""
    with get_session() as session:
        session.run(
            """
            MATCH (b:FigmaBinding {id: $bid})
            CREATE (e:BindingHistoryEvent {
                id: $eid,
                eventType: $etype,
                actor: $actor,
                at: $now,
                figmaFileKey: $fk,
                payload: $payload
            })
            CREATE (e)-[:LOGGED]->(b)
            """,
            bid=SINGLETON_ID,
            eid=str(uuid.uuid4()),
            etype=event_type,
            actor=actor or "unknown",
            now=_now_iso(),
            fk=figma_file_key,
            payload=json.dumps(payload, ensure_ascii=False) if payload else None,
        )


def append_history_event_no_binding(
    *,
    event_type: str,
    actor: str,
    figma_file_key: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Append a history event when no binding exists yet (e.g. validate_failure
    on the very first connect attempt). The event is created free-standing,
    without a :LOGGED edge — readers should not assume that edge is present.
    """
    with get_session() as session:
        session.run(
            """
            CREATE (e:BindingHistoryEvent {
                id: $eid,
                eventType: $etype,
                actor: $actor,
                at: $now,
                figmaFileKey: $fk,
                payload: $payload
            })
            """,
            eid=str(uuid.uuid4()),
            etype=event_type,
            actor=actor or "unknown",
            now=_now_iso(),
            fk=figma_file_key,
            payload=json.dumps(payload, ensure_ascii=False) if payload else None,
        )


def list_history_events(limit: int = 50) -> list[dict[str, Any]]:
    """Return the most recent history events newest-first."""
    limit = max(1, min(int(limit or 50), 500))
    with get_session() as session:
        records = session.run(
            """
            MATCH (e:BindingHistoryEvent)
            RETURN e
            ORDER BY e.at DESC
            LIMIT $lim
            """,
            lim=limit,
        ).data()
    out: list[dict[str, Any]] = []
    for r in records:
        n = r["e"]
        d = dict(n)
        if d.get("payload"):
            try:
                d["payload"] = json.loads(d["payload"])
            except Exception:
                pass
        out.append(d)
    return out


# ─── UI sync status (v1.2 / FR-019b / FR-020) ────────────────────────────


def mark_ui_sync_ok(ui_id: str, *, page_id: str, node_id: str) -> None:
    """Mark a :UI as Figma-synced. Clears figmaSyncLastError and stamps the
    attempt time. Also writes figmaPageId / figmaNodeId so downstream readers
    have one consistent source of truth for the linked frame.
    """
    with get_session() as session:
        session.run(
            """
            MATCH (u:UI {id: $uid})
            SET u.figmaSyncStatus = 'ok',
                u.figmaSyncLastError = null,
                u.figmaSyncLastAttemptAt = datetime(),
                u.figmaPageId = $page_id,
                u.figmaNodeId = $node_id
            """,
            uid=ui_id,
            page_id=page_id,
            node_id=node_id,
        )


def mark_ui_sync_failed(ui_id: str, *, error_ko: str) -> None:
    """Mark a :UI's last Figma push attempt as failed. Leaves any prior
    figmaPageId / figmaNodeId in place — they may still describe the previous
    successful push, and FR-020 retry only clears them on a fresh success.
    """
    with get_session() as session:
        session.run(
            """
            MATCH (u:UI {id: $uid})
            SET u.figmaSyncStatus = 'failed',
                u.figmaSyncLastError = $err,
                u.figmaSyncLastAttemptAt = datetime()
            """,
            uid=ui_id,
            err=error_ko,
        )


def list_failed_sync_uis() -> list[dict[str, Any]]:
    """Every :UI currently flagged figmaSyncStatus='failed', most recently
    attempted first. Used by the FR-020 retry endpoint when called with no
    explicit uiIds list, and by the FrameEditor banner for cross-session
    visibility.
    """
    with get_session() as session:
        result = session.run(
            """
            MATCH (u:UI)
            WHERE u.figmaSyncStatus = 'failed'
            RETURN u.id AS id,
                   coalesce(u.displayName, u.name) AS name,
                   u.figmaSyncLastError AS error,
                   toString(u.figmaSyncLastAttemptAt) AS lastAttemptAt
            ORDER BY u.figmaSyncLastAttemptAt DESC
            """,
        )
        return [
            {
                "uiId": r["id"],
                "name": r["name"],
                "errorKo": r["error"],
                "lastAttemptAt": r["lastAttemptAt"],
            }
            for r in result
            if r and r.get("id")
        ]


def clear_ui_sync_status_for_binding_replace() -> int:
    """When the architect replaces the active binding, every :UI's sync state
    against the old file becomes meaningless. This nulls the v1.2 status
    triple (figmaSyncStatus / figmaSyncLastError / figmaSyncLastAttemptAt) on
    every :UI. The persistent figmaFileKey / figmaNodeId / figmaPageId are
    deliberately *not* touched here — those remain so DesignBindingBadge can
    still render "from previous binding" per US4 (T055). Returns the count
    of nodes touched for observability.
    """
    with get_session() as session:
        result = session.run(
            """
            MATCH (u:UI)
            WHERE u.figmaSyncStatus IS NOT NULL
            SET u.figmaSyncStatus = null,
                u.figmaSyncLastError = null,
                u.figmaSyncLastAttemptAt = null
            RETURN count(u) AS n
            """
        )
        rec = result.single()
        return int(rec["n"]) if rec and rec.get("n") is not None else 0


# ─── helpers ──────────────────────────────────────────────────────────────


def _binding_node_to_dict(node: Any) -> dict[str, Any]:
    """Convert a Neo4j node to a plain dict, normalizing datetime fields."""
    if node is None:
        return {}
    d = dict(node)
    for k in ("connectedAt", "lastSyncAt"):
        if k in d and d[k] is not None and not isinstance(d[k], str):
            d[k] = str(d[k])
    return d


def _mapping_node_to_dict(node: Any) -> dict[str, Any]:
    if node is None:
        return {}
    d = dict(node)
    for k in ("lastRenameAt",):
        if k in d and d[k] is not None and not isinstance(d[k], str):
            d[k] = str(d[k])
    return d
