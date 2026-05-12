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


# ─── 020: Run lock ─────────────────────────────────────────────────────────


def try_acquire_run_lock(*, run_id: str, actor: str) -> bool:
    """Atomically claim the singleton binding's advisory lock for `run_id`.

    Returns True if acquired (binding active and currentRunId was null), False
    on contention (someone else holds it) or if the binding isn't active.
    """
    with get_session() as session:
        rec = session.run(
            """
            MATCH (b:FigmaBinding {id: $id})
            WHERE b.currentRunId IS NULL AND b.status = 'active'
            SET b.currentRunId = $rid,
                b.currentRunHolder = $actor
            RETURN b.currentRunId AS rid
            """,
            id=SINGLETON_ID,
            rid=run_id,
            actor=actor or "unknown",
        ).single()
    return bool(rec and rec.get("rid") == run_id)


def release_run_lock(*, run_id: str) -> None:
    """Release the lock held by `run_id`. No-op if the lock is held by a
    different run (defensive — protects against late releases clobbering a
    successor's lock).
    """
    with get_session() as session:
        session.run(
            """
            MATCH (b:FigmaBinding {id: $id, currentRunId: $rid})
            SET b.currentRunId = null,
                b.currentRunHolder = null
            """,
            id=SINGLETON_ID,
            rid=run_id,
        )


def get_current_lock_holder() -> dict[str, Any] | None:
    """If a run is currently in flight, return `{currentRunId, currentRunHolder}`."""
    with get_session() as session:
        rec = session.run(
            """
            MATCH (b:FigmaBinding {id: $id})
            WHERE b.currentRunId IS NOT NULL
            RETURN b.currentRunId AS rid, b.currentRunHolder AS holder
            """,
            id=SINGLETON_ID,
        ).single()
    if not rec:
        return None
    return {"currentRunId": rec["rid"], "currentRunHolder": rec.get("holder")}


# ─── 020: SyncRun ──────────────────────────────────────────────────────────


def create_sync_run(
    *,
    run_id: str,
    kind: str,
    binding_file_key: str,
    actor: str,
) -> dict[str, Any]:
    """Insert a `:SyncRun {status:'running'}` row and edge it to the binding."""
    now = _now_iso()
    with get_session() as session:
        rec = session.run(
            """
            MATCH (b:FigmaBinding {id: $bid})
            CREATE (r:SyncRun {
                id: $rid,
                kind: $kind,
                bindingFileKey: $fk,
                actor: $actor,
                startedAt: $now,
                status: 'running',
                summary: null,
                finishedAt: null
            })
            CREATE (r)-[:RUN_OF]->(b)
            RETURN r
            """,
            bid=SINGLETON_ID,
            rid=run_id,
            kind=kind,
            fk=binding_file_key,
            actor=actor or "unknown",
            now=now,
        ).single()
    return dict(rec["r"]) if rec else {}


def finalize_sync_run(
    *,
    run_id: str,
    status: str,
    summary: dict[str, Any] | None = None,
) -> None:
    """Move a running :SyncRun to a terminal state and freeze its summary map."""
    with get_session() as session:
        session.run(
            """
            MATCH (r:SyncRun {id: $rid})
            WHERE r.status = 'running'
            SET r.status = $status,
                r.finishedAt = $now,
                r.summary = $summary
            """,
            rid=run_id,
            status=status,
            now=_now_iso(),
            summary=json.dumps(summary, ensure_ascii=False) if summary else None,
        )


def list_sync_runs(
    *,
    limit: int = 20,
    include_previous_binding: bool = True,
    current_file_key: str | None = None,
) -> list[dict[str, Any]]:
    """Most-recent runs first. When include_previous_binding is False and
    current_file_key is provided, only runs whose bindingFileKey matches are
    returned.
    """
    limit = max(1, min(int(limit or 20), 100))
    with get_session() as session:
        if include_previous_binding or not current_file_key:
            records = session.run(
                """
                MATCH (r:SyncRun)
                RETURN r
                ORDER BY r.startedAt DESC
                LIMIT $lim
                """,
                lim=limit,
            ).data()
        else:
            records = session.run(
                """
                MATCH (r:SyncRun)
                WHERE r.bindingFileKey = $fk
                RETURN r
                ORDER BY r.startedAt DESC
                LIMIT $lim
                """,
                fk=current_file_key,
                lim=limit,
            ).data()

    out: list[dict[str, Any]] = []
    for rec in records:
        n = rec["r"]
        d = dict(n)
        if d.get("summary"):
            try:
                d["summary"] = json.loads(d["summary"])
            except Exception:
                pass
        out.append(d)
    return out


def get_sync_run(run_id: str) -> dict[str, Any] | None:
    with get_session() as session:
        rec = session.run(
            "MATCH (r:SyncRun {id: $rid}) RETURN r",
            rid=run_id,
        ).single()
    if not rec:
        return None
    d = dict(rec["r"])
    if d.get("summary"):
        try:
            d["summary"] = json.loads(d["summary"])
        except Exception:
            pass
    return d


def release_stale_locks(older_than_minutes: int = 30) -> int:
    """Recovery hook: any :SyncRun stuck in 'running' for > N minutes plus its
    associated binding lock are released. Returns count of runs reset.
    """
    with get_session() as session:
        rec = session.run(
            """
            MATCH (r:SyncRun {status:'running'})
            WHERE datetime(r.startedAt) < datetime() - duration({minutes: $m})
            WITH r
            OPTIONAL MATCH (b:FigmaBinding {currentRunId: r.id})
            SET r.status = 'aborted-binding-unreachable',
                r.finishedAt = datetime(),
                r.summary = coalesce(r.summary, '{}')
            FOREACH (bb IN CASE WHEN b IS NULL THEN [] ELSE [b] END |
                SET bb.currentRunId = null, bb.currentRunHolder = null
            )
            RETURN count(r) AS n
            """,
            m=int(older_than_minutes),
        ).single()
    return int(rec["n"]) if rec else 0


# ─── 020: Failures (extension of 016 v1.2 store) ──────────────────────────


def list_failures_with_binding_key() -> list[dict[str, Any]]:
    """Every :UI {figmaSyncStatus:'failed'} with the fields needed by the
    classifier — superset of 016's list_failed_sync_uis (adds the file-key
    snapshot needed for "이전 바인딩" detection).
    """
    with get_session() as session:
        result = session.run(
            """
            MATCH (u:UI)
            WHERE u.figmaSyncStatus = 'failed'
            RETURN u.id AS id,
                   coalesce(u.displayName, u.name, '') AS displayName,
                   u.figmaSyncLastError AS lastError,
                   toString(u.figmaSyncLastAttemptAt) AS lastAttemptAt,
                   u.figmaSyncBindingFileKey AS bindingFileKey
            ORDER BY u.figmaSyncLastAttemptAt DESC
            """
        )
        return [
            {
                "uiId": r["id"],
                "displayName": r["displayName"],
                "lastErrorKr": r["lastError"],
                "lastAttemptAt": r["lastAttemptAt"],
                "figmaSyncBindingFileKey": r.get("bindingFileKey"),
            }
            for r in result
            if r and r.get("id")
        ]


def fetch_classifier_view(ui_ids: list[str]) -> dict[str, Any]:
    """One-shot Cypher to populate the classifier's `neo4j_view` for many ids
    at once: `{ui_present: {id: bool}, storyboard_archived: {id: bool}}`.
    """
    if not ui_ids:
        return {"ui_present": {}, "storyboard_archived": {}}

    with get_session() as session:
        # Which UI ids still exist
        present_rows = session.run(
            """
            UNWIND $ids AS uid
            OPTIONAL MATCH (u:UI {id: uid})
            RETURN uid AS id, (u IS NOT NULL) AS present
            """,
            ids=ui_ids,
        ).data()

        # Owning-storyboard archived check: a UI is "owned by an archived
        # storyboard" when the BFS-resolved entry-command's
        # :StoryboardPageMapping.status = 'archived'.
        archived_rows = session.run(
            """
            UNWIND $ids AS uid
            OPTIONAL MATCH (u:UI {id: uid})<-[*1..30]-(c:Command)
            WHERE c IS NOT NULL AND NOT EXISTS { (:Policy)-[:INVOKES]->(c) }
            WITH uid, c LIMIT 1
            OPTIONAL MATCH (m:StoryboardPageMapping {commandId: c.id})
            RETURN uid AS id,
                   coalesce(m.status, 'active') = 'archived' AS archived
            """,
            ids=ui_ids,
        ).data()

    ui_present: dict[str, bool] = {r["id"]: bool(r.get("present")) for r in present_rows}
    storyboard_archived: dict[str, bool] = {
        r["id"]: bool(r.get("archived")) for r in archived_rows
    }
    return {"ui_present": ui_present, "storyboard_archived": storyboard_archived}


def update_ui_sync_binding_file_key(ui_id: str, file_key: str | None) -> None:
    """Stamp the active binding's file key onto the :UI alongside figmaSync*
    writes. Called by extended bulk_sync / push paths so the classifier's
    "이전 바인딩" check has data to compare against.
    """
    with get_session() as session:
        session.run(
            """
            MATCH (u:UI {id: $uid})
            SET u.figmaSyncBindingFileKey = $fk
            """,
            uid=ui_id,
            fk=file_key,
        )


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
