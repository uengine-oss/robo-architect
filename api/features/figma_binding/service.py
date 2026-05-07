"""Business logic for figma_binding feature 016.

Endpoints in router.py thin-wrap these functions. SmartLogger events fire at
phase boundaries per Constitution VII.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator, Callable

from fastapi import HTTPException

from api.platform.observability.smart_logger import SmartLogger

from . import plugin_messages, repository, storyboard_resolver
from ._figma_validate import validate_file


# Plugin call timeouts. The lower bound is set by Figma plugin sandbox's
# setInterval throttling: when the plugin window isn't actively focused (the
# common case during bulk ingestion — the user's looking at the ingestion
# panel, not the plugin), polling drops from 3 s to ~60 s. Any timeout < 60 s
# raced ahead of the plugin's next poll and produced false-positive
# "응답 시간 초과" — observed in 016 end-to-end testing. Padding ~30 s on top
# of the 60 s poll cadence covers the plugin's processing time
# (figma.createPage is fast; CREATE_FRAME_IN_PAGE walks the sceneGraph and
# can take a few seconds on a large frame).
_CREATE_PAGE_TIMEOUT = 90.0
_CREATE_FRAME_TIMEOUT = 120.0


# ─── Helpers ──────────────────────────────────────────────────────────────


def _to_response(binding: dict[str, Any]) -> dict[str, Any]:
    counts = repository.count_storyboard_mappings_by_status()
    return {
        "id": binding.get("id", "singleton"),
        "figmaFileKey": binding.get("figmaFileKey"),
        "figmaFileName": binding.get("figmaFileName"),
        "connectedBy": binding.get("connectedBy"),
        "connectedAt": binding.get("connectedAt"),
        "lastSyncAt": binding.get("lastSyncAt"),
        "status": binding.get("status", "active"),
        "storyboardCounts": counts,
    }


# ─── Lifecycle ────────────────────────────────────────────────────────────


def get_active_binding_response() -> dict[str, Any] | None:
    b = repository.get_active_binding()
    if not b:
        return None
    return _to_response(b)


async def connect_binding(
    *, figma_file_key: str, api_token: str, actor: str
) -> dict[str, Any]:
    """Validate file via Figma REST then persist the singleton binding."""
    SmartLogger.log(
        "INFO",
        f"figma_binding.connect.start file_key={figma_file_key}",
        category="figma_binding.connect",
    )

    # Reject if an active binding already exists.
    existing = repository.get_active_binding()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="이미 다른 Figma 다큐먼트가 바인딩되어 있습니다. 먼저 해제하거나 /replace를 사용하세요.",
        )

    meta = await validate_file(figma_file_key, api_token)
    if not meta.get("ok"):
        repository.append_history_event_no_binding(
            event_type="validate_failure",
            actor=actor,
            figma_file_key=figma_file_key,
            payload={"error": meta.get("error", "")},
        )
        SmartLogger.log(
            "WARN",
            f"figma_binding.validate failed: {meta.get('error')}",
            category="figma_binding.validate",
        )
        raise HTTPException(
            status_code=400,
            detail=f"Figma 파일에 접근할 수 없습니다: {meta.get('error', '')}",
        )

    binding = repository.upsert_binding(
        figma_file_key=figma_file_key,
        figma_file_name=meta.get("fileName") or "Untitled",
        connected_by=actor,
    )
    repository.append_history_event(
        event_type="connect",
        actor=actor,
        figma_file_key=figma_file_key,
        payload={"fileName": meta.get("fileName")},
    )
    SmartLogger.log(
        "INFO",
        f"figma_binding.connect.done file_key={figma_file_key}",
        category="figma_binding.connect",
    )
    return _to_response(binding)


def disconnect_binding(*, actor: str) -> None:
    SmartLogger.log("INFO", "figma_binding.disconnect.start", category="figma_binding.disconnect")
    existing = repository.get_active_binding()
    if not existing:
        return  # idempotent no-op
    repository.mark_binding_status("disconnected")
    repository.append_history_event(
        event_type="disconnect",
        actor=actor,
        figma_file_key=existing.get("figmaFileKey"),
    )
    SmartLogger.log("INFO", "figma_binding.disconnect.done", category="figma_binding.disconnect")


async def replace_binding(
    *, figma_file_key: str, api_token: str, actor: str
) -> dict[str, Any]:
    SmartLogger.log("INFO", f"figma_binding.replace.start new_file_key={figma_file_key}", category="figma_binding.replace")

    existing = repository.get_active_binding()
    # Validate the new file FIRST — never archive prior state if the new file is bad.
    meta = await validate_file(figma_file_key, api_token)
    if not meta.get("ok"):
        repository.append_history_event_no_binding(
            event_type="validate_failure",
            actor=actor,
            figma_file_key=figma_file_key,
            payload={"phase": "replace", "error": meta.get("error", "")},
        )
        raise HTTPException(
            status_code=400,
            detail=f"Figma 파일에 접근할 수 없습니다: {meta.get('error', '')}",
        )

    if existing:
        # Archive prior mappings and append a 'replace' event before swapping the binding row.
        archived = repository.archive_all_active_mappings()
        # v1.2 / FR-019b clean-up: figmaSyncStatus on every :UI describes the
        # last push attempt against the *previous* binding's file. After a
        # replace those values are meaningless — null them so the UI doesn't
        # surface stale "Figma 동기화 실패" badges that point at a file the
        # architect just disconnected from. The persistent figmaFileKey /
        # figmaNodeId / figmaPageId columns stay so US4's "from previous
        # binding" badge still works (T055).
        cleared_count = repository.clear_ui_sync_status_for_binding_replace()
        repository.append_history_event(
            event_type="replace",
            actor=actor,
            figma_file_key=existing.get("figmaFileKey"),
            payload={
                "previousFileKey": existing.get("figmaFileKey"),
                "previousFileName": existing.get("figmaFileName"),
                "newFileKey": figma_file_key,
                "archivedMappings": archived,
                "uiSyncStatusCleared": cleared_count,
            },
        )

    binding = repository.upsert_binding(
        figma_file_key=figma_file_key,
        figma_file_name=meta.get("fileName") or "Untitled",
        connected_by=actor,
    )
    repository.append_history_event(
        event_type="connect",
        actor=actor,
        figma_file_key=figma_file_key,
        payload={"fileName": meta.get("fileName"), "via": "replace"},
    )
    SmartLogger.log("INFO", f"figma_binding.replace.done new_file_key={figma_file_key}", category="figma_binding.replace")
    return _to_response(binding)


# ─── History ─────────────────────────────────────────────────────────────


def get_history(limit: int = 50) -> list[dict[str, Any]]:
    return repository.list_history_events(limit=limit)


# ─── Storyboards listing (US2 read-only) ─────────────────────────────────


def list_storyboards() -> list[dict[str, Any]]:
    """Union of (a) entry commands present in the model and (b) currently-mapped
    storyboards. Each row carries display name, step count, and mapping info if any.
    """
    entry_commands = storyboard_resolver.list_entry_commands()
    mappings_by_cid = {
        m["commandId"]: m for m in repository.list_storyboard_mappings(status=None)
    }

    out: list[dict[str, Any]] = []
    seen_cids: set[str] = set()

    for ec in entry_commands:
        cid = ec["id"]
        seen_cids.add(cid)
        m = mappings_by_cid.get(cid)
        out.append({
            "commandId": cid,
            "displayName": ec.get("displayName") or ec.get("name") or cid,
            "stepCount": storyboard_resolver.get_step_count_for_storyboard(cid),
            "mapping": (
                {
                    "figmaPageId": m["figmaPageId"],
                    "figmaPageName": m["figmaPageName"],
                    "status": m["status"],
                }
                if m
                else None
            ),
        })

    # Mappings whose entry command is gone — render them at the bottom as archive-eligible.
    for cid, m in mappings_by_cid.items():
        if cid in seen_cids:
            continue
        out.append({
            "commandId": cid,
            "displayName": m.get("figmaPageName") or cid,  # last cached
            "stepCount": None,
            "mapping": {
                "figmaPageId": m["figmaPageId"],
                "figmaPageName": m["figmaPageName"],
                "status": m["status"],
            },
        })

    return out


# ─── Storyboard ↔ Figma page sync (US2: T030, T032) ─────────────────────


async def _ensure_page_for_command(
    *,
    file_key: str,
    command_id: str,
    display_name: str,
    on_event: Callable[[str, dict], None] | None = None,
) -> dict[str, Any]:
    """Ensure a Figma page exists for one entry command. Side-effect: writes /
    refreshes the :StoryboardPageMapping. Returns one of:

      {action: 'created', commandId, figmaPageId, figmaPageName}
      {action: 'reused',  commandId, figmaPageId, figmaPageName}
      {action: 'renamed', commandId, figmaPageId, figmaPageName, oldName}
      {action: 'unreachable', commandId, error}

    Never raises plugin errors — they're packaged into the unreachable result.
    """
    existing = repository.get_mapping_by_command_id(command_id)
    if existing and existing.get("status") == "active":
        # Reuse. If the entry command's display name changed, update the
        # cached figmaPageName (FR-008 first half — local→Figma rename
        # itself is deferred per research D5).
        if existing.get("figmaPageName") != display_name:
            old = existing.get("figmaPageName")
            repository.update_mapping_cached_name(command_id, display_name)
            if on_event:
                on_event("renamed", {"commandId": command_id, "oldName": old, "newName": display_name})
            return {
                "action": "renamed",
                "commandId": command_id,
                "figmaPageId": existing["figmaPageId"],
                "figmaPageName": display_name,
                "oldName": old,
            }
        if on_event:
            on_event("reused", {"commandId": command_id, "figmaPageId": existing["figmaPageId"]})
        return {
            "action": "reused",
            "commandId": command_id,
            "figmaPageId": existing["figmaPageId"],
            "figmaPageName": existing["figmaPageName"],
        }

    # No active mapping → create the page in Figma.
    msg = plugin_messages.build_create_page(display_name)
    try:
        ack = await plugin_messages.send_and_wait(file_key, msg, _CREATE_PAGE_TIMEOUT)
    except plugin_messages.PluginNotConnectedError as e:
        SmartLogger.log(
            "WARN",
            f"figma_binding.sync_storyboards.unreachable command_id={command_id}: plugin not connected",
            category="figma_binding.sync_storyboards.unreachable",
            params={"commandId": command_id, "fileKey": e.file_key},
        )
        return {"action": "unreachable", "commandId": command_id, "error": "Figma 플러그인이 연결되어 있지 않습니다."}
    except asyncio.TimeoutError:
        SmartLogger.log(
            "WARN",
            f"figma_binding.sync_storyboards.unreachable command_id={command_id}: plugin timeout",
            category="figma_binding.sync_storyboards.unreachable",
        )
        return {"action": "unreachable", "commandId": command_id, "error": "Figma 플러그인 응답 시간 초과."}

    if not ack.get("ok") or not ack.get("figmaPageId"):
        err = ack.get("error") or "Figma 페이지 생성에 실패했습니다."
        return {"action": "unreachable", "commandId": command_id, "error": err}

    figma_page_id = ack["figmaPageId"]
    figma_page_name = ack.get("figmaPageName") or display_name
    repository.upsert_storyboard_mapping(
        command_id=command_id,
        figma_page_id=figma_page_id,
        figma_page_name=figma_page_name,
    )
    if on_event:
        on_event("created", {
            "commandId": command_id,
            "figmaPageId": figma_page_id,
            "figmaPageName": figma_page_name,
        })
    return {
        "action": "created",
        "commandId": command_id,
        "figmaPageId": figma_page_id,
        "figmaPageName": figma_page_name,
    }


def _archive_orphaned_mappings(active_command_ids: set[str]) -> list[str]:
    """Mark mappings whose commandId is no longer an entry command as archived.
    Returns the list of archived commandIds.
    """
    out: list[str] = []
    for m in repository.list_storyboard_mappings(status="active") or []:
        if m["commandId"] not in active_command_ids:
            repository.archive_storyboard_mapping(m["commandId"])
            out.append(m["commandId"])
    return out


async def sync_storyboards(
    *,
    actor: str,
    on_event: Callable[[str, dict], None] | None = None,
) -> dict[str, Any]:
    """Full FR-006 sync: ensure one Figma page per current entry command.
    Reuses by stable mapping ID; renames where the entry command's display
    name changed; archives mappings whose entry command no longer exists.
    """
    binding = repository.get_active_binding()
    if not binding:
        raise HTTPException(status_code=404, detail="바인딩된 Figma 다큐먼트가 없습니다.")

    file_key = binding["figmaFileKey"]
    SmartLogger.log(
        "INFO",
        f"figma_binding.sync_storyboards.start file_key={file_key}",
        category="figma_binding.sync_storyboards",
    )

    entries = storyboard_resolver.list_entry_commands()
    created: list[dict[str, Any]] = []
    reused: list[dict[str, Any]] = []
    renamed: list[dict[str, Any]] = []
    unreachable: list[dict[str, Any]] = []

    for ec in entries:
        result = await _ensure_page_for_command(
            file_key=file_key,
            command_id=ec["id"],
            display_name=ec.get("displayName") or ec.get("name") or ec["id"],
            on_event=on_event,
        )
        action = result.pop("action", None)
        if action == "created":
            created.append(result)
        elif action == "reused":
            reused.append(result)
        elif action == "renamed":
            renamed.append(result)
        elif action == "unreachable":
            unreachable.append(result)

    archived = _archive_orphaned_mappings({ec["id"] for ec in entries})
    if archived:
        SmartLogger.log(
            "INFO",
            f"figma_binding.sync_storyboards.archived count={len(archived)}",
            category="figma_binding.page_archived",
            params={"archivedCommandIds": archived},
        )

    if not unreachable:
        repository.update_last_sync_at()
    else:
        repository.mark_binding_status("unreachable")

    repository.append_history_event(
        event_type="sync_storyboards",
        actor=actor,
        figma_file_key=file_key,
        payload={
            "created": [c["commandId"] for c in created],
            "reused": [c["commandId"] for c in reused],
            "renamed": [c["commandId"] for c in renamed],
            "archived": archived,
            "unreachable": [c["commandId"] for c in unreachable],
        },
    )
    SmartLogger.log(
        "INFO",
        f"figma_binding.sync_storyboards.done created={len(created)} reused={len(reused)} renamed={len(renamed)} archived={len(archived)} unreachable={len(unreachable)}",
        category="figma_binding.sync_storyboards",
    )

    return {
        "created": created,
        "reused": reused,
        "renamed": renamed,
        "archived": archived,
        "unreachable": unreachable,
    }


async def sync_storyboards_stream(
    *, actor: str
) -> AsyncGenerator[tuple[str, dict[str, Any]], None]:
    """SSE-friendly variant of sync_storyboards. Yields (event_name, payload)
    tuples that the router translates into `event:`/`data:` lines.
    """
    queue: asyncio.Queue = asyncio.Queue()

    def _emit(name: str, payload: dict[str, Any]) -> None:
        queue.put_nowait((name, payload))

    async def _run():
        try:
            summary = await sync_storyboards(actor=actor, on_event=_emit)
            queue.put_nowait(("done", summary))
        except HTTPException as e:
            queue.put_nowait(("error", {"detail": e.detail, "status": e.status_code}))
        except Exception as e:  # noqa: BLE001
            queue.put_nowait(("error", {"detail": str(e)}))
        finally:
            queue.put_nowait(("__terminator__", {}))

    task = asyncio.create_task(_run())
    try:
        while True:
            name, payload = await queue.get()
            if name == "__terminator__":
                break
            yield name, payload
    finally:
        if not task.done():
            task.cancel()


# ─── Storyboard sync subset (FR-019b helper, T081) ───────────────────────


async def sync_storyboards_for_ids(
    ui_ids: list[str],
    *,
    on_event: Callable[[str, dict], None] | None = None,
) -> dict[str, Any]:
    """Slimmer variant of `sync_storyboards`: ensures pages only for the
    storyboards owning the given UI nodes. Used by the bulk ingestion bridge
    (`bulk_sync.sync_batch`) so we don't re-sync unrelated storyboards on
    every batch.

    Returns:
        {
          "pagesCreated":  [{commandId, figmaPageId, figmaPageName}, ...],
          "pagesReused":   [...],
          "pagesRenamed":  [...],
          "orphanUis":     [uiId, ...],   # UIs not reachable from any entry command
          "unreachable":   [{commandId, error}, ...],  # plugin-level failures
          "uiToPageId":    {uiId: figmaPageId, ...},   # convenience map for callers
        }

    Never raises HTTPException — the bulk path needs to keep going on partial
    failures (FR-020). The caller decides what to do with `orphanUis` /
    `unreachable`.
    """
    binding = repository.get_active_binding()
    if not binding:
        return {
            "pagesCreated": [],
            "pagesReused": [],
            "pagesRenamed": [],
            "orphanUis": list(ui_ids),
            "unreachable": [],
            "uiToPageId": {},
        }

    file_key = binding["figmaFileKey"]

    # Step 1: resolve each UI's owning storyboard (entry command id).
    ui_to_command: dict[str, str | None] = {}
    for uid in ui_ids:
        ui_to_command[uid] = storyboard_resolver.resolve_storyboard_for_ui(uid)
    orphan_uis = [uid for uid, cid in ui_to_command.items() if cid is None]
    needed_command_ids = {cid for cid in ui_to_command.values() if cid}

    if not needed_command_ids:
        return {
            "pagesCreated": [],
            "pagesReused": [],
            "pagesRenamed": [],
            "orphanUis": orphan_uis,
            "unreachable": [],
            "uiToPageId": {},
        }

    # Step 2: ensure a Figma page exists for each needed entry command.
    created: list[dict[str, Any]] = []
    reused: list[dict[str, Any]] = []
    renamed: list[dict[str, Any]] = []
    unreachable: list[dict[str, Any]] = []
    cmd_to_page_id: dict[str, str] = {}

    for cid in needed_command_ids:
        display_name = storyboard_resolver.get_command_display_name(cid) or cid
        result = await _ensure_page_for_command(
            file_key=file_key,
            command_id=cid,
            display_name=display_name,
            on_event=on_event,
        )
        action = result.pop("action", None)
        if action in ("created", "reused", "renamed"):
            cmd_to_page_id[cid] = result["figmaPageId"]
            if action == "created":
                created.append(result)
            elif action == "reused":
                reused.append(result)
            else:
                renamed.append(result)
        elif action == "unreachable":
            unreachable.append(result)

    ui_to_page_id = {
        uid: cmd_to_page_id[cid]
        for uid, cid in ui_to_command.items()
        if cid and cid in cmd_to_page_id
    }

    return {
        "pagesCreated": created,
        "pagesReused": reused,
        "pagesRenamed": renamed,
        "orphanUis": orphan_uis,
        "unreachable": unreachable,
        "uiToPageId": ui_to_page_id,
    }


# ─── Per-UI Figma frame push (US3 simplified slice for FR-019b) ─────────


async def push_frame_for_ui(
    ui_id: str,
    *,
    figma_page_id: str,
    on_event: Callable[[str, dict], None] | None = None,
) -> dict[str, Any]:
    """Send the UI's existing sceneGraph to Figma as a new top-level frame in
    the given page. Used by the bulk ingestion bridge — `on_conflict='overwrite'`
    is implicit (the bulk path just overwrites; per-node generation flows
    through a different helper that handles the FR-012 prompt).

    Returns one of:
      {ok: True,  uiId, figmaPageId, figmaNodeId, figmaFrameName}
      {ok: False, uiId, errorKo}

    Never raises — failures package as `ok=False` so the caller (bulk_sync)
    can record per-UI status without halting the batch.
    """
    binding = repository.get_active_binding()
    if not binding:
        return {"ok": False, "uiId": ui_id, "errorKo": "바인딩된 Figma 다큐먼트가 없습니다."}

    file_key = binding["figmaFileKey"]

    # Read the UI's name + sceneGraph from Neo4j.
    from api.platform.neo4j import get_session as _get_session  # noqa: PLC0415

    with _get_session() as session:
        rec = session.run(
            """
            MATCH (u:UI {id: $uid})
            RETURN coalesce(u.displayName, u.name) AS name,
                   u.sceneGraph AS sceneGraph
            """,
            uid=ui_id,
        ).single()
    if not rec:
        return {"ok": False, "uiId": ui_id, "errorKo": f"UI 노드를 찾을 수 없습니다 (id={ui_id})."}

    raw_sg = rec.get("sceneGraph")
    if not raw_sg:
        return {"ok": False, "uiId": ui_id, "errorKo": "이 UI 노드에는 아직 sceneGraph가 없습니다."}

    import json as _json  # noqa: PLC0415
    try:
        scene_graph = _json.loads(raw_sg) if isinstance(raw_sg, str) else raw_sg
    except _json.JSONDecodeError:
        return {"ok": False, "uiId": ui_id, "errorKo": "UI sceneGraph 데이터가 손상되었습니다."}

    frame_name = rec.get("name") or "Wireframe"
    msg = plugin_messages.build_create_frame_in_page(
        figma_page_id=figma_page_id,
        frame_name=frame_name,
        scene_graph=scene_graph,
    )

    if on_event:
        on_event("figma_sync.start", {"uiId": ui_id, "uiName": frame_name})

    try:
        ack = await plugin_messages.send_and_wait(file_key, msg, _CREATE_FRAME_TIMEOUT)
    except plugin_messages.PluginNotConnectedError:
        err = "Figma 플러그인이 연결되어 있지 않습니다."
        if on_event:
            on_event("figma_sync.failed", {"uiId": ui_id, "errorKo": err})
        return {"ok": False, "uiId": ui_id, "errorKo": err}
    except asyncio.TimeoutError:
        err = "Figma 플러그인 응답 시간 초과."
        if on_event:
            on_event("figma_sync.failed", {"uiId": ui_id, "errorKo": err})
        return {"ok": False, "uiId": ui_id, "errorKo": err}

    if not ack.get("ok") or not ack.get("figmaNodeId"):
        err = ack.get("error") or "Figma 프레임 생성에 실패했습니다."
        if on_event:
            on_event("figma_sync.failed", {"uiId": ui_id, "errorKo": err})
        return {"ok": False, "uiId": ui_id, "errorKo": err}

    result = {
        "ok": True,
        "uiId": ui_id,
        "figmaPageId": ack.get("figmaPageId") or figma_page_id,
        "figmaNodeId": ack["figmaNodeId"],
        "figmaFrameName": ack.get("figmaFrameName") or frame_name,
    }
    if on_event:
        on_event("figma_sync.ok", {
            "uiId": ui_id,
            "figmaPageId": result["figmaPageId"],
            "figmaNodeId": result["figmaNodeId"],
        })
    return result


# ─── Bidirectional sync (RA → Figma update, Figma → RA pull) ────────────


async def update_frame_for_ui(ui_id: str) -> dict[str, Any]:
    """RA → Figma in-place update: send the UI's *current* sceneGraph to the
    plugin, which clears the existing frame's children and re-renders.
    Requires the UI already has figmaNodeId (i.e., was previously pushed).

    Returns:
        {ok: True,  uiId, figmaNodeId, figmaFrameName, nodesCreated, nodesFailed}
        {ok: False, uiId, errorKo}
    """
    binding = repository.get_active_binding()
    if not binding:
        return {"ok": False, "uiId": ui_id, "errorKo": "바인딩된 Figma 다큐먼트가 없습니다."}
    file_key = binding["figmaFileKey"]

    from api.platform.neo4j import get_session as _get_session  # noqa: PLC0415
    with _get_session() as session:
        rec = session.run(
            """
            MATCH (u:UI {id: $uid})
            RETURN u.figmaNodeId AS fnid, u.sceneGraph AS sg, coalesce(u.displayName, u.name) AS name
            """,
            uid=ui_id,
        ).single()
    if not rec:
        return {"ok": False, "uiId": ui_id, "errorKo": f"UI 노드를 찾을 수 없습니다 (id={ui_id})."}
    figma_node_id = rec.get("fnid")
    if not figma_node_id:
        return {"ok": False, "uiId": ui_id, "errorKo": "이 UI 는 아직 Figma 에 푸시된 적이 없습니다 (figmaNodeId 없음)."}
    raw_sg = rec.get("sg")
    if not raw_sg:
        return {"ok": False, "uiId": ui_id, "errorKo": "UI 에 sceneGraph 가 없습니다."}

    import json as _json  # noqa: PLC0415
    try:
        scene_graph = _json.loads(raw_sg) if isinstance(raw_sg, str) else raw_sg
    except _json.JSONDecodeError:
        return {"ok": False, "uiId": ui_id, "errorKo": "sceneGraph 데이터가 손상되었습니다."}

    msg = plugin_messages.build_update_frame(figma_node_id, scene_graph)
    try:
        ack = await plugin_messages.send_and_wait(file_key, msg, _CREATE_FRAME_TIMEOUT)
    except plugin_messages.PluginNotConnectedError:
        return {"ok": False, "uiId": ui_id, "errorKo": "Figma 플러그인이 연결되어 있지 않습니다."}
    except asyncio.TimeoutError:
        return {"ok": False, "uiId": ui_id, "errorKo": "Figma 플러그인 응답 시간 초과."}

    if not ack.get("ok"):
        return {"ok": False, "uiId": ui_id, "errorKo": ack.get("error") or "Figma 프레임 업데이트 실패"}

    repository.mark_ui_sync_ok(ui_id, page_id=binding.get("figmaPageId") or "", node_id=figma_node_id)
    return {
        "ok": True,
        "uiId": ui_id,
        "figmaNodeId": ack.get("figmaNodeId") or figma_node_id,
        "figmaFrameName": ack.get("figmaFrameName") or rec.get("name"),
        "nodesCreated": ack.get("nodesCreated"),
        "nodesFailed": ack.get("nodesFailed"),
    }


async def pull_frame_via_plugin(ui_id: str) -> dict[str, Any]:
    """Figma → RA pull: ask the plugin for the current state of the UI's
    linked Figma frame, convert the returned tree to a SerializedSceneGraph,
    and persist it on the UI node.

    No Figma REST API token needed — uses the plugin transport.
    """
    binding = repository.get_active_binding()
    if not binding:
        return {"ok": False, "uiId": ui_id, "errorKo": "바인딩된 Figma 다큐먼트가 없습니다."}
    file_key = binding["figmaFileKey"]

    from api.platform.neo4j import get_session as _get_session  # noqa: PLC0415
    with _get_session() as session:
        rec = session.run(
            """
            MATCH (u:UI {id: $uid})
            RETURN u.figmaNodeId AS fnid, coalesce(u.displayName, u.name) AS name
            """,
            uid=ui_id,
        ).single()
    if not rec:
        return {"ok": False, "uiId": ui_id, "errorKo": f"UI 노드를 찾을 수 없습니다 (id={ui_id})."}
    figma_node_id = rec.get("fnid")
    if not figma_node_id:
        return {"ok": False, "uiId": ui_id, "errorKo": "이 UI 는 Figma 에 연결되어 있지 않습니다."}

    msg = plugin_messages.build_export_frame_by_id(figma_node_id)
    try:
        ack = await plugin_messages.send_and_wait(file_key, msg, _CREATE_FRAME_TIMEOUT)
    except plugin_messages.PluginNotConnectedError:
        return {"ok": False, "uiId": ui_id, "errorKo": "Figma 플러그인이 연결되어 있지 않습니다."}
    except asyncio.TimeoutError:
        return {"ok": False, "uiId": ui_id, "errorKo": "Figma 플러그인 응답 시간 초과."}

    if not ack.get("ok") or not ack.get("frameData"):
        return {"ok": False, "uiId": ui_id, "errorKo": ack.get("error") or "Figma 프레임 데이터를 받지 못했습니다."}

    # Convert plugin's frame tree to a SerializedSceneGraph using the
    # existing 009-era converter (same one used by /export-result endpoint).
    from api.features.ingestion.figma_plugin_ws import _figma_export_to_scene_graph  # noqa: PLC0415

    # Diagnostic: count what the plugin actually sent.
    frame_data = ack["frameData"]
    def _count(n):
        c = 1
        for ch in (n.get("children") or []):
            c += _count(ch)
        return c
    def _types(n, acc):
        acc[n.get("type", "?")] = acc.get(n.get("type", "?"), 0) + 1
        for ch in (n.get("children") or []):
            _types(ch, acc)
        return acc
    types = _types(frame_data, {})
    SmartLogger.log(
        "INFO",
        f"figma_binding.pull_frame received frameData ui={ui_id} total={_count(frame_data)} types={types}",
        category="figma_binding.pull_frame.diag",
        params={"uiId": ui_id, "totalNodes": _count(frame_data), "byType": types},
    )

    scene_graph = _figma_export_to_scene_graph(frame_data)
    if not scene_graph or not scene_graph.get("nodes"):
        return {"ok": False, "uiId": ui_id, "errorKo": "Figma 프레임을 sceneGraph 로 변환하지 못했습니다."}

    import json as _json  # noqa: PLC0415
    sg_str = _json.dumps(scene_graph, ensure_ascii=False)

    with _get_session() as session:
        session.run(
            """
            MATCH (u:UI {id: $uid})
            SET u.sceneGraph = $sg, u.updatedAt = datetime()
            """,
            uid=ui_id,
            sg=sg_str,
        )

    return {
        "ok": True,
        "uiId": ui_id,
        "figmaNodeId": figma_node_id,
        "figmaFrameName": ack.get("figmaFrameName"),
        "nodeCount": len(scene_graph.get("nodes") or {}),
        "sceneGraph": sg_str,  # so frontend can update local state without a re-fetch
    }
