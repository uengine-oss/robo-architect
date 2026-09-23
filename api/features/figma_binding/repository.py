"""Neo4j read/write helpers for FigmaBinding, StoryboardPageMapping, BindingHistoryEvent.

All Cypher goes through `api/platform/neo4j.get_session()` per Constitution I.
No domain logic here — service.py owns business rules.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
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
        # 두 문장이다 — 한 문장에 읽기 → 쓰기 → 읽기 를 섞지 않는다.
        #
        # 종전에는 MERGE 뒤에 `WITH m … OPTIONAL MATCH (c:Command …) FOREACH (…)`
        # 로 Command 를 이어 붙였다. 조건부 FOREACH 는 지원되지 않아 이 질의가
        # 통째로 구문 오류였고, 그래서 스토리보드↔Figma 페이지 매핑이 하나도
        # 저장되지 않았다.
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
            RETURN m
            """,
            bid=SINGLETON_ID,
            cid=command_id,
            newid=str(uuid.uuid4()),
            page_id=figma_page_id,
            page_name=figma_page_name,
        ).single()
        # Command 가 없으면 MATCH 가 0행이라 아무 일도 일어나지 않는다 —
        # 조건부 FOREACH 가 하던 일이 그대로 문장의 의미가 된다.
        session.run(
            """
            MATCH (m:StoryboardPageMapping {commandId: $cid})
            MATCH (c:Command {id: $cid})
            MERGE (m)-[:MAPS]->(c)
            """,
            cid=command_id,
        )
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
    # 경계 시각은 파이썬에서 만든다 — `duration()` 은 엔진에 없다.
    # `startedAt` 은 `_now_iso()` 가 쓰는 고정 폭 UTC ISO 문자열이라
    # 문자열 비교가 그대로 시간 순서다.
    cutoff = (datetime.now(timezone.utc)
              - timedelta(minutes=int(older_than_minutes))).strftime("%Y-%m-%dT%H:%M:%SZ")
    with get_session() as session:
        rec = session.run(
            """
            MATCH (r:SyncRun {status:'running'})
            WHERE r.startedAt < $cutoff
            SET r.status = 'aborted-binding-unreachable',
                r.finishedAt = datetime(),
                r.summary = coalesce(r.summary, '{}')
            RETURN collect(r.id) AS ids
            """,
            cutoff=cutoff,
        ).single()
        stale_ids = list(rec["ids"]) if rec and rec.get("ids") else []
        # 붙어 있던 lock 을 푼다. 해당 run 을 들고 있지 않으면 MATCH 가 0행이라
        # 아무 일도 없다 — 조건부 FOREACH 가 하던 일과 같다.
        if stale_ids:
            session.run(
                """
                UNWIND $ids AS rid
                MATCH (b:FigmaBinding {currentRunId: rid})
                SET b.currentRunId = null, b.currentRunHolder = null
                """,
                ids=stale_ids,
            )
    return len(stale_ids)


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
    """Populate the classifier's `neo4j_view` for many ids at once:
    `{ui_present: {id: bool}, storyboard_archived: {id: bool}}`.

    스토리보드 소속은 **`storyboard_resolver` 에 맡긴다.** 여기서 직접 걷지
    않는다. 예전에는 이 함수가 도달성 탐색을 인라인으로 다시 짰는데, 그것이
    바로 `resolve_storyboard_for_ui` 의 docstring 이 "재현하지 말라"고 적어둔
    모양이었다 — 관계 타입 제한이 아예 없는 `(u:UI)<-[*1..30]-(c:Command)` 에,
    `WITH` 를 거친 값을 다시 패턴 대상으로 여는 조합. 그쪽 측정으로 깊이 12 에서
    19.3초, 30 에서는 서버 임시 공간을 소진하고 죽었다. `/failures` 는 실패가
    1건만 있어도 이 경로로 들어오므로, 그때마다 앱이 통째로 멈췄다.

    같은 코드에 **조용한 오답**도 있었다. `UNWIND` 로 id 를 펼쳐 놓고 `WITH uid,
    c LIMIT 1` 을 걸었는데, Cypher 의 `LIMIT` 은 id 별이 아니라 **스트림 전체**에
    걸린다. 그래서 몇 건을 넘기든 "보관됨" 판정을 받을 수 있는 UI 는 언제나
    최대 한 건이었다. 분류기는 없는 키를 `retryable` 로 흘려보내므로(§
    `failure_classifier.classify`) 나머지는 재시도 가능으로 잘못 표시됐고,
    이것은 오류 없이 지나간다.
    """
    if not ui_ids:
        return {"ui_present": {}, "storyboard_archived": {}}

    from . import storyboard_resolver  # noqa: PLC0415  (순환 임포트 회피)

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

        # 보관된 스토리보드의 entry command 집합. 매핑 전체를 한 번에 읽는다 —
        # UI 마다 되묻지 않으려는 것이고, 행 수는 스토리보드 수라 작다.
        archived_commands = {
            r["commandId"]
            for r in session.run(
                """
                MATCH (m:StoryboardPageMapping)
                WHERE m.status = 'archived'
                RETURN m.commandId AS commandId
                """
            ).data()
            if r.get("commandId")
        }

    ui_present: dict[str, bool] = {r["id"]: bool(r.get("present")) for r in present_rows}

    storyboard_archived: dict[str, bool] = {}
    if archived_commands:
        # entry command 목록은 UI 마다 다시 뽑지 않고 한 번만 넘긴다 —
        # `resolve_storyboard_for_ui` 가 그러라고 열어둔 인자다.
        entry_commands = storyboard_resolver.list_entry_commands()
        for uid in ui_ids:
            if not ui_present.get(uid):
                continue  # 사라진 UI 는 분류기가 앞 단계에서 먼저 잡는다
            owner = storyboard_resolver.resolve_storyboard_for_ui(
                uid, entry_commands=entry_commands
            )
            storyboard_archived[uid] = bool(owner and owner in archived_commands)

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


# ─── 024: FigmaComponent (bound design-system catalog) ────────────────────


def upsert_figma_component(
    *,
    binding_file_key: str,
    figma_node_id: str,
    name: str,
    page_name: str,
    width_px: int,
    height_px: int,
    vlm_description: str,
    figma_key: str | None = None,
    figma_node_last_modified: str | None = None,
) -> dict[str, Any]:
    """Create or update a :FigmaComponent row for the singleton binding.

    Idempotent on (bindingFileKey, figmaNodeId). Sets scannedAt on every call so
    callers can detect stale rows for cleanup.
    """
    now = _now_iso()
    with get_session() as session:
        rec = session.run(
            """
            MATCH (b:FigmaBinding {id: $bid})
            MERGE (c:FigmaComponent {bindingFileKey: $fk, figmaNodeId: $nid})
            ON CREATE SET c.id = $newid
            SET c.name = $name,
                c.pageName = $page_name,
                c.widthPx = $w,
                c.heightPx = $h,
                c.vlmDescription = $desc,
                c.figmaKey = $fkey,
                c.figmaNodeLastModified = $last_mod,
                c.scannedAt = $now
            MERGE (b)-[:HAS_COMPONENT]->(c)
            RETURN c
            """,
            bid=SINGLETON_ID,
            fk=binding_file_key,
            nid=figma_node_id,
            newid=str(uuid.uuid4()),
            name=name,
            page_name=page_name,
            w=int(width_px or 0),
            h=int(height_px or 0),
            desc=vlm_description or "",
            fkey=figma_key,
            last_mod=figma_node_last_modified,
            now=now,
        ).single()
    return dict(rec["c"]) if rec else {}


def list_figma_components(
    binding_file_key: str | None = None,
) -> list[dict[str, Any]]:
    """Return all :FigmaComponent rows for a binding, name-sorted.

    When binding_file_key is None, returns components for the active binding.
    """
    if binding_file_key is None:
        b = get_active_binding()
        if not b:
            return []
        binding_file_key = b.get("figmaFileKey")
        if not binding_file_key:
            return []
    with get_session() as session:
        records = session.run(
            """
            MATCH (c:FigmaComponent {bindingFileKey: $fk})
            RETURN c
            ORDER BY c.pageName, c.name
            """,
            fk=binding_file_key,
        ).data()
    return [dict(r["c"]) for r in records]


def count_figma_components(binding_file_key: str | None = None) -> int:
    """Count :FigmaComponent rows for a binding. 0 if no binding."""
    if binding_file_key is None:
        b = get_active_binding()
        if not b:
            return 0
        binding_file_key = b.get("figmaFileKey")
        if not binding_file_key:
            return 0
    with get_session() as session:
        rec = session.run(
            "MATCH (c:FigmaComponent {bindingFileKey: $fk}) RETURN count(c) AS n",
            fk=binding_file_key,
        ).single()
    return int(rec["n"]) if rec else 0


def delete_figma_components(binding_file_key: str | None = None) -> int:
    """Hard-delete every :FigmaComponent for a binding. Returns count removed."""
    if binding_file_key is None:
        b = get_active_binding()
        if not b:
            return 0
        binding_file_key = b.get("figmaFileKey")
        if not binding_file_key:
            return 0
    with get_session() as session:
        rec = session.run(
            """
            MATCH (c:FigmaComponent {bindingFileKey: $fk})
            WITH c, count(c) AS n
            DETACH DELETE c
            RETURN n
            """,
            fk=binding_file_key,
        ).single()
    return int(rec["n"]) if rec else 0


def delete_stale_figma_components(
    binding_file_key: str, kept_figma_node_ids: list[str]
) -> int:
    """Delete components whose figmaNodeId is NOT in kept_figma_node_ids.

    Called at the tail of a scan to clean up rows for components that no
    longer exist in the source Figma file.
    """
    with get_session() as session:
        rec = session.run(
            """
            MATCH (c:FigmaComponent {bindingFileKey: $fk})
            WHERE NOT c.figmaNodeId IN $kept
            WITH c, count(c) AS n
            DETACH DELETE c
            RETURN n
            """,
            fk=binding_file_key,
            kept=list(kept_figma_node_ids or []),
        ).single()
    return int(rec["n"]) if rec else 0


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
