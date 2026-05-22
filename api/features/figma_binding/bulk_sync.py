"""Bulk-with-binding bridge between requirements ingestion and figma_binding.

Called by `api/features/ingestion/workflow/phases/ui_wireframes.py` once per
ingestion batch (max 10 UIs at a time). For each batch:

    1. If no active :FigmaBinding → return immediately (binding-independent
       per FR-019: bulk just populates sceneGraph; no Figma writes attempted).

    2. Resolve each UI's owning storyboard and ensure a Figma page exists
       (`service.sync_storyboards_for_ids` — slimmer than the full FR-006
       sync because it only touches storyboards owned by THIS batch).

    3. For each UI in the batch, push its sceneGraph as a Figma frame into
       the resolved page (`service.push_frame_for_ui`). The bulk path always
       overwrites — clarification Q5 settled this: the architect's
       "기존 데이터 삭제하고 계속" confirmation at the upload modal IS the
       FR-012 prompt for bulk; per-node generation flows handle the prompt
       separately.

    4. Per-UI status flags on :UI nodes: `figmaSyncStatus`,
       `figmaSyncLastError`, `figmaSyncLastAttemptAt` (FR-020).

The function NEVER raises. Every failure mode (orphan UI, plugin
unreachable, plugin error, timeout) becomes:
    - one emitted `figma_sync.failed` event,
    - one Neo4j status flag write via `repository.mark_ui_sync_failed`.

That contract is what FR-020 hangs on: the ingestion stream keeps draining
even when a few UIs can't reach Figma, and the architect later finds the
failed list at FR-020's two surfaces (summary panel + Inspector badge) and
retries via `/api/figma-binding/retry-sync`.
"""

from __future__ import annotations

from typing import Any, Callable

from api.platform.observability.smart_logger import SmartLogger

from . import repository, service


# Event names mirror specs/016-figma-document-binding/contracts/rest-api.md
# § Ingestion stream new events (FR-019b) — same shape as the dedicated
# /retry-sync stream so the frontend has one event handler.
_EVT_START = "figma_sync.start"
_EVT_OK = "figma_sync.ok"
_EVT_FAILED = "figma_sync.failed"


async def sync_batch(
    session_id: str,
    ui_ids: list[str],
    on_event: Callable[[str, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run the page-sync + frame-push for one batch of UI ids.

    Returns a summary dict for caller logging:
        {
          "skipped": True,                      # no active binding, or no plugin connected
          "syncedCount": int,                   # successful pushes
          "failedCount": int,                   # failed pushes (incl orphans + unreachable pages)
          "orphanUis": list[str],
          "unreachablePages": list[dict],       # [{commandId, reason}]
        }
    """
    binding = repository.get_active_binding()
    if not binding:
        return {"skipped": True, "syncedCount": 0, "failedCount": 0}

    if not ui_ids:
        return {"skipped": False, "syncedCount": 0, "failedCount": 0}

    # 020: Stamp every figmaSync* status write with the binding file key so the
    # FR-020 retry classifier can detect "이전 바인딩" failures after a replace.
    binding_file_key = binding.get("figmaFileKey")

    # Plugin-presence guard. If no Figma plugin is currently polling for this
    # file, every push_frame_for_ui below would burn its full 120 s timeout —
    # silently, since push_frame_for_ui never raises — stalling the ingestion
    # UI phase ~20 min per batch. Skip fast instead; the architect can sync
    # later from the Design tab once the plugin is connected.
    from ..ingestion.figma_plugin_ws import is_polling_active  # noqa: PLC0415
    if not binding_file_key or not is_polling_active(binding_file_key):
        SmartLogger.log(
            "INFO",
            f"figma_binding.bulk_sync.skipped_no_plugin session={session_id} "
            f"batch={len(ui_ids)} (Figma 플러그인 미연결 — 푸시 건너뜀)",
            category="figma_binding.bulk_sync.skipped_no_plugin",
            params={
                "sessionId": session_id,
                "batchSize": len(ui_ids),
                "figmaFileKey": binding_file_key,
            },
        )
        return {
            "skipped": True,
            "reason": "plugin-not-connected",
            "syncedCount": 0,
            "failedCount": 0,
        }

    SmartLogger.log(
        "INFO",
        f"figma_binding.bulk_sync.start session={session_id} batch={len(ui_ids)}",
        category="figma_binding.bulk_sync.start",
        params={"sessionId": session_id, "batchSize": len(ui_ids)},
    )

    # Step 1: ensure Figma pages exist for every storyboard touched by this
    # batch. sync_storyboards_for_ids never raises — orphans / plugin errors
    # come back as `orphanUis` / `unreachable` arrays.
    page_summary = await service.sync_storyboards_for_ids(ui_ids)
    ui_to_page_id: dict[str, str] = page_summary.get("uiToPageId", {}) or {}
    orphan_uis: list[str] = page_summary.get("orphanUis", []) or []
    unreachable_pages: list[dict[str, Any]] = page_summary.get("unreachable", []) or []

    # Pre-mark orphans as failed so the architect sees them in the FR-020
    # failed list rather than as "never attempted".
    for uid in orphan_uis:
        err = "이 UI는 어떤 스토리보드에도 속하지 않습니다."
        repository.mark_ui_sync_failed(uid, error_ko=err)
        repository.update_ui_sync_binding_file_key(uid, binding_file_key)
        if on_event:
            on_event(_EVT_FAILED, {"uiId": uid, "errorKo": err})
        SmartLogger.log(
            "WARN",
            f"figma_binding.bulk_sync.orphan ui_id={uid}",
            category="figma_binding.bulk_sync.failed",
            params={"sessionId": session_id, "uiId": uid, "errorKo": err},
        )

    # If any storyboards' pages couldn't be created, every UI under those
    # storyboards inherits the failure (no page → no place to push the frame).
    # `ui_to_page_id` already excludes those; mark them failed here.
    failed_due_to_page: list[str] = []
    for uid in ui_ids:
        if uid in orphan_uis:
            continue
        if uid in ui_to_page_id:
            continue
        # Find the page error this UI would have inherited (best-effort).
        # `_ensure_page_for_command` (in service.py) keys the message under
        # 'error'; tolerate 'reason' too in case a future caller normalizes.
        err = "Figma 페이지를 준비하지 못했습니다."
        if unreachable_pages:
            first = unreachable_pages[0]
            err = first.get("error") or first.get("reason") or err
        repository.mark_ui_sync_failed(uid, error_ko=err)
        repository.update_ui_sync_binding_file_key(uid, binding_file_key)
        if on_event:
            on_event(_EVT_FAILED, {"uiId": uid, "errorKo": err})
        failed_due_to_page.append(uid)
        SmartLogger.log(
            "WARN",
            f"figma_binding.bulk_sync.page_failed ui_id={uid}",
            category="figma_binding.bulk_sync.failed",
            params={"sessionId": session_id, "uiId": uid, "errorKo": err},
        )

    # Step 2: push each UI's frame. push_frame_for_ui already emits
    # figma_sync.start/ok/failed via on_event AND returns ok / errorKo for
    # us to record on the Neo4j node.
    synced = 0
    failed = len(orphan_uis) + len(failed_due_to_page)
    for uid in ui_ids:
        if uid in orphan_uis or uid not in ui_to_page_id:
            continue
        result = await service.push_frame_for_ui(
            uid,
            figma_page_id=ui_to_page_id[uid],
            on_event=on_event,
        )
        if result.get("ok"):
            repository.mark_ui_sync_ok(
                uid,
                page_id=result.get("figmaPageId") or ui_to_page_id[uid],
                node_id=result["figmaNodeId"],
            )
            repository.update_ui_sync_binding_file_key(uid, binding_file_key)
            synced += 1
            SmartLogger.log(
                "INFO",
                f"figma_binding.bulk_sync.ok ui_id={uid}",
                category="figma_binding.bulk_sync.ok",
                params={
                    "sessionId": session_id,
                    "uiId": uid,
                    "figmaPageId": result.get("figmaPageId"),
                    "figmaNodeId": result.get("figmaNodeId"),
                },
            )
        else:
            err = result.get("errorKo") or "Figma 동기화에 실패했습니다."
            repository.mark_ui_sync_failed(uid, error_ko=err)
            repository.update_ui_sync_binding_file_key(uid, binding_file_key)
            failed += 1
            SmartLogger.log(
                "WARN",
                f"figma_binding.bulk_sync.failed ui_id={uid}: {err}",
                category="figma_binding.bulk_sync.failed",
                params={"sessionId": session_id, "uiId": uid, "errorKo": err},
            )

    SmartLogger.log(
        "INFO",
        f"figma_binding.bulk_sync.done session={session_id} synced={synced} failed={failed}",
        category="figma_binding.bulk_sync.done",
        params={"sessionId": session_id, "syncedCount": synced, "failedCount": failed},
    )
    return {
        "skipped": False,
        "syncedCount": synced,
        "failedCount": failed,
        "orphanUis": orphan_uis,
        "unreachablePages": unreachable_pages,
    }
