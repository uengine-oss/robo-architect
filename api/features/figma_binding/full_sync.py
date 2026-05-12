"""Retroactive full-sync orchestrator (spec 020).

Ties together storyboard page sync (existing 016 service.sync_storyboards_for_ids
which ensures pages AND returns a uiId → pageId map), on-demand figma-mode
sceneGraph generation (via the ingestion bridge
`api/features/ingestion/workflow/phases/ui_wireframes.generate_jsx_for_existing_ui`),
and per-UI frame push (existing 016 service.push_frame_for_ui).

The orchestrator is an async function that yields per-item progress events via
the `on_event` callback. Lock acquisition, run lifecycle, and queue fan-out
live in service.py.

See specs/020-figma-sync-recovery/plan.md § Phase 3 (US1) and research.md D2/D4.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

from . import repository


# Same fan-out as 016 bulk ingestion — never bypass.
BATCH_SIZE = 10


def _list_project_uis() -> list[dict[str, Any]]:
    """Every :UI node in the project, ordered for deterministic processing."""
    with get_session() as session:
        records = session.run(
            """
            MATCH (u:UI)
            RETURN u.id AS id,
                   coalesce(u.displayName, u.name, '') AS displayName,
                   u.sceneGraph AS sceneGraph,
                   u.figmaSyncStatus AS figmaSyncStatus
            ORDER BY coalesce(u.displayName, u.name), u.id
            """
        ).data()
    out: list[dict[str, Any]] = []
    for r in records:
        sg = r.get("sceneGraph")
        has_scene_graph = False
        if isinstance(sg, str) and sg.strip():
            try:
                parsed = json.loads(sg)
                has_scene_graph = bool(parsed and parsed.get("nodes"))
            except Exception:
                has_scene_graph = False
        elif isinstance(sg, dict):
            has_scene_graph = bool(sg.get("nodes"))
        out.append(
            {
                "id": r["id"],
                "displayName": r["displayName"],
                "hasSceneGraph": has_scene_graph,
            }
        )
    return out


def _persist_scene_graph(ui_id: str, scene_graph: dict[str, Any]) -> None:
    """Write a fresh sceneGraph onto a :UI node. Used by full_sync after the
    bridge generates one for a UI that didn't previously have one.
    """
    with get_session() as session:
        session.run(
            """
            MATCH (u:UI {id: $uid})
            SET u.sceneGraph = $sg
            """,
            uid=ui_id,
            sg=json.dumps(scene_graph, ensure_ascii=False),
        )


async def run_full_sync(
    *,
    run_id: str,
    actor: str,
    on_event: Callable[[str, dict[str, Any]], Awaitable[None]],
    sync_storyboards_for_ids_fn: Callable[..., Awaitable[dict[str, Any]]],
    push_frame_fn: Callable[..., Awaitable[dict[str, Any]]],
    generate_jsx_fn: Callable[..., Awaitable[dict | None]],
    is_cancel_requested: Callable[[], bool],
    binding_file_key: str,
) -> dict[str, Any]:
    """Execute a retroactive full-sync. Returns the final summary dict.

    The caller (service.full_sync) holds the run lock and finalizes the
    :SyncRun row in a `finally` block — this function focuses on the work
    itself plus emitting events. It MUST NOT raise on per-item failures.
    """

    summary = {
        "storyboardsTotal": 0,
        "pagesCreated": 0,
        "pagesAlreadyOk": 0,
        "uisTotal": 0,
        "framesPushed": 0,
        "generated": 0,
        "overwrites": 0,
        "failures": 0,
    }
    cancelled = False
    aborted_reason: str | None = None

    uis = _list_project_uis()
    summary["uisTotal"] = len(uis)
    ui_ids = [u["id"] for u in uis]

    # ── 1. Page-creation phase via existing helper ────────────────────────
    page_summary: dict[str, Any] = {}
    try:
        page_summary = await sync_storyboards_for_ids_fn(ui_ids=ui_ids)
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            f"figma_binding.full_sync sync_storyboards_for_ids failed: {e}",
            category="figma_binding.full_sync.page_failed",
            params={"runId": run_id},
        )

    pages_created = page_summary.get("pagesCreated") or []
    pages_reused = page_summary.get("pagesReused") or []
    pages_renamed = page_summary.get("pagesRenamed") or []
    pages_unreachable = page_summary.get("unreachable") or []
    orphan_uis: set[str] = set(page_summary.get("orphanUis") or [])
    ui_to_page_id: dict[str, str] = page_summary.get("uiToPageId") or {}

    summary["storyboardsTotal"] = (
        len(pages_created) + len(pages_reused) + len(pages_renamed) + len(pages_unreachable)
    )
    summary["pagesCreated"] = len(pages_created)
    summary["pagesAlreadyOk"] = len(pages_reused) + len(pages_renamed)

    for it in pages_created:
        await on_event(
            "page_ok",
            {
                "runId": run_id,
                "storyboardId": it.get("commandId"),
                "displayName": it.get("figmaPageName"),
                "figmaPageId": it.get("figmaPageId"),
            },
        )
    for it in pages_reused + pages_renamed:
        await on_event(
            "page_ok",
            {
                "runId": run_id,
                "storyboardId": it.get("commandId"),
                "displayName": it.get("figmaPageName"),
                "figmaPageId": it.get("figmaPageId"),
                "alreadyOk": True,
            },
        )
    for it in pages_unreachable:
        await on_event(
            "page_failed",
            {
                "runId": run_id,
                "storyboardId": it.get("commandId"),
                "displayName": it.get("commandId"),
                "lastErrorKr": it.get("error") or "Figma 페이지 생성 실패",
            },
        )
        summary["failures"] += 1

    if is_cancel_requested():
        cancelled = True

    # ── 2. UI-iteration phase ─────────────────────────────────────────────
    if not cancelled and not aborted_reason:
        await on_event(
            "progress",
            {
                "runId": run_id,
                "storyboardsDone": summary["storyboardsTotal"]
                - len(pages_unreachable),
                "storyboardsTotal": summary["storyboardsTotal"],
                "uisDone": 0,
                "uisTotal": summary["uisTotal"],
                "currentTarget": None,
            },
        )

        uis_done = 0
        for batch_start in range(0, len(uis), BATCH_SIZE):
            if is_cancel_requested():
                cancelled = True
                break

            cur_binding = repository.get_active_binding()
            if (
                not cur_binding
                or cur_binding.get("status") == "unreachable"
                or cur_binding.get("figmaFileKey") != binding_file_key
            ):
                aborted_reason = "binding_unreachable"
                break

            batch = uis[batch_start : batch_start + BATCH_SIZE]
            await asyncio.gather(
                *(
                    _process_one_ui(
                        run_id=run_id,
                        actor=actor,
                        ui=ui,
                        page_id=ui_to_page_id.get(ui["id"]),
                        is_orphan=(ui["id"] in orphan_uis),
                        on_event=on_event,
                        push_frame_fn=push_frame_fn,
                        generate_jsx_fn=generate_jsx_fn,
                        binding_file_key=binding_file_key,
                        summary=summary,
                    )
                    for ui in batch
                ),
                return_exceptions=True,
            )
            uis_done = batch_start + len(batch)

            await on_event(
                "progress",
                {
                    "runId": run_id,
                    "storyboardsDone": summary["storyboardsTotal"]
                    - len(pages_unreachable),
                    "storyboardsTotal": summary["storyboardsTotal"],
                    "uisDone": uis_done,
                    "uisTotal": summary["uisTotal"],
                    "currentTarget": None,
                },
            )

    # ── 3. Decide terminal status ─────────────────────────────────────────
    if aborted_reason:
        status = "aborted-binding-unreachable"
    elif cancelled:
        status = "cancelled"
    elif summary["failures"] > 0:
        status = "partially-succeeded"
    else:
        status = "succeeded"

    summary["status"] = status
    summary["abortedReason"] = aborted_reason
    return summary


async def _process_one_ui(
    *,
    run_id: str,
    actor: str,
    ui: dict[str, Any],
    page_id: str | None,
    is_orphan: bool,
    on_event: Callable[[str, dict[str, Any]], Awaitable[None]],
    push_frame_fn: Callable[..., Awaitable[dict[str, Any]]],
    generate_jsx_fn: Callable[..., Awaitable[dict | None]],
    binding_file_key: str,
    summary: dict[str, Any],
) -> None:
    """Generate-if-needed-then-push for one UI. Per-item failures are caught."""
    ui_id = ui["id"]
    display_name = ui["displayName"] or ui_id

    if is_orphan or not page_id:
        err = "어떤 스토리보드(entry command)에도 도달할 수 없는 UI 입니다."
        await on_event(
            "ui_failed",
            {"runId": run_id, "uiId": ui_id, "displayName": display_name, "lastErrorKr": err},
        )
        try:
            repository.mark_ui_sync_failed(ui_id, error_ko=err)
            repository.update_ui_sync_binding_file_key(ui_id, binding_file_key)
        except Exception:
            pass
        summary["failures"] += 1
        return

    try:
        if not ui["hasSceneGraph"]:
            sg = await generate_jsx_fn(ui_id=ui_id, actor=actor)
            if not sg:
                err = "sceneGraph 생성 실패 — 와이어프레임 서비스가 응답하지 않음"
                await on_event(
                    "ui_failed",
                    {"runId": run_id, "uiId": ui_id, "displayName": display_name, "lastErrorKr": err},
                )
                repository.mark_ui_sync_failed(ui_id, error_ko=err)
                repository.update_ui_sync_binding_file_key(ui_id, binding_file_key)
                summary["failures"] += 1
                return
            _persist_scene_graph(ui_id, sg)
            summary["generated"] += 1
            await on_event(
                "ui_generated",
                {
                    "runId": run_id,
                    "uiId": ui_id,
                    "displayName": display_name,
                    "sceneGraphNodes": len(sg.get("nodes") or {}),
                    "overwroteExisting": False,
                },
            )
        else:
            # Existing sceneGraph — overwrite policy per spec 020 Q2.
            summary["overwrites"] += 1
            await on_event(
                "ui_generated",
                {
                    "runId": run_id,
                    "uiId": ui_id,
                    "displayName": display_name,
                    "sceneGraphNodes": None,
                    "overwroteExisting": True,
                },
            )

        result = await push_frame_fn(ui_id, figma_page_id=page_id)
        if result and result.get("ok"):
            summary["framesPushed"] += 1
            try:
                repository.mark_ui_sync_ok(
                    ui_id,
                    page_id=result.get("figmaPageId") or page_id,
                    node_id=result.get("figmaNodeId") or "",
                )
                repository.update_ui_sync_binding_file_key(ui_id, binding_file_key)
            except Exception:
                pass
            await on_event(
                "ui_pushed",
                {
                    "runId": run_id,
                    "uiId": ui_id,
                    "displayName": display_name,
                    "figmaPageId": result.get("figmaPageId"),
                    "figmaNodeId": result.get("figmaNodeId"),
                },
            )
        else:
            err = (result or {}).get("errorKo") or "Figma 가 응답하지 않음"
            try:
                repository.mark_ui_sync_failed(ui_id, error_ko=err)
                repository.update_ui_sync_binding_file_key(ui_id, binding_file_key)
            except Exception:
                pass
            await on_event(
                "ui_failed",
                {"runId": run_id, "uiId": ui_id, "displayName": display_name, "lastErrorKr": err},
            )
            summary["failures"] += 1
    except Exception as e:
        SmartLogger.log(
            "ERROR",
            f"figma_binding.full_sync ui crashed: {ui_id} {e}",
            category="figma_binding.full_sync.ui_failed",
            params={"runId": run_id, "uiId": ui_id, "error": str(e)},
        )
        await on_event(
            "ui_failed",
            {
                "runId": run_id,
                "uiId": ui_id,
                "displayName": display_name,
                "lastErrorKr": f"내부 오류: {e}",
            },
        )
        try:
            repository.mark_ui_sync_failed(ui_id, error_ko=f"내부 오류: {e}")
            repository.update_ui_sync_binding_file_key(ui_id, binding_file_key)
        except Exception:
            pass
        summary["failures"] += 1
