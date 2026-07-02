"""FastAPI router for /api/figma-binding/* endpoints.

Thin wrappers around service.py. Every endpoint emits a SmartLogger event;
the request_id middleware in api/main.py provides correlation IDs.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from api.platform.observability.smart_logger import SmartLogger

from . import service
from .plugin_messages import router as plugin_messages_router
from .schemas import (
    BindingHistoryResponse,
    ConnectRequest,
    FailuresListResponse,
    FigmaBindingResponse,
    FigmaComponentsListResponse,
    FullSyncStartResponse,
    ScanComponentsRequest,
    ScanComponentsResponse,
    StoryboardListItem,
    SyncRunsListResponse,
    SyncStoryboardsResponse,
)


router = APIRouter(prefix="/api/figma-binding", tags=["figma-binding"])


def _actor_from_request(req: Request) -> str:
    """Best-effort actor resolution.

    The project does not currently have an auth model; clients may opt-in to
    pass `X-User-Email` / `X-Actor` headers. Otherwise we fall back to the
    request's source IP, then to "unknown".
    """
    h = req.headers
    return (
        h.get("x-user-email")
        or h.get("x-actor")
        or h.get("x-forwarded-for")
        or (req.client.host if req.client else None)
        or "unknown"
    )


# ─── Lifecycle ───────────────────────────────────────────────────────────


@router.get("", response_model=FigmaBindingResponse)
async def get_binding() -> dict[str, Any]:
    b = service.get_active_binding_response()
    if not b:
        raise HTTPException(status_code=404, detail="바인딩된 Figma 다큐먼트가 없습니다.")
    return b


@router.post("/connect", response_model=FigmaBindingResponse)
async def post_connect(req: ConnectRequest, request: Request) -> dict[str, Any]:
    actor = _actor_from_request(request)
    return service.connect_binding(
        figma_file_key=req.figmaFileKey,
        figma_file_name=req.figmaFileName,
        actor=actor,
    )


@router.delete("", status_code=204, response_class=Response, response_model=None)
async def delete_binding(request: Request) -> None:
    actor = _actor_from_request(request)
    service.disconnect_binding(actor=actor)


@router.post("/replace", response_model=FigmaBindingResponse)
async def post_replace(req: ConnectRequest, request: Request) -> dict[str, Any]:
    actor = _actor_from_request(request)
    return service.replace_binding(
        figma_file_key=req.figmaFileKey,
        figma_file_name=req.figmaFileName,
        actor=actor,
    )


@router.get("/history", response_model=BindingHistoryResponse)
async def get_history(limit: int = 50) -> dict[str, Any]:
    items = service.get_history(limit=limit)
    return {"items": items}


# ─── 024: Component library (scan / list / clear) ────────────────────────


@router.post("/components/scan", response_model=ScanComponentsResponse)
async def post_scan_components(req: ScanComponentsRequest, request: Request) -> dict[str, Any]:
    """Scan the bound Figma file's component library.

    Synchronous. Returns counts (scanned/added/updated/removed) plus the
    final component count for the singleton binding. Per FR-010, returns
    404 if no binding, 409 if a scan is already in flight.
    """
    from . import component_library  # noqa: PLC0415

    actor = _actor_from_request(request)
    SmartLogger.log(
        "INFO",
        f"figma_binding.components.scan.requested actor={actor} pushed={len(req.components)}",
        category="figma_binding.components.scan.requested",
        params={"actor": actor, "pushed": len(req.components)},
    )
    return await component_library.scan_components(
        components=[c.model_dump() for c in req.components],
        actor=actor,
    )


@router.get("/components", response_model=FigmaComponentsListResponse)
async def get_components() -> dict[str, Any]:
    from . import component_library  # noqa: PLC0415

    rows = component_library.list_components()
    return {"components": rows, "componentCount": len(rows)}


@router.get("/components/scan/stream")
async def get_components_scan_stream(request: Request) -> StreamingResponse:
    """Server-Sent Events stream of the active (or most recent) scan's progress.

    Emits an initial `snapshot` with the current state, then one `progress`
    event per state bump (phase change, VLM completion, upsert). Terminal
    events `done` or `error` close the stream. Heartbeats every ~15s keep
    proxies from buffering. Multiple subscribers are supported — each gets
    woken on the shared progress Event.
    """
    from . import component_library  # noqa: PLC0415

    async def _gen():
        snap = component_library.get_progress_snapshot()
        last_version = snap.get("version", 0)
        yield f"event: snapshot\ndata: {json.dumps(snap, ensure_ascii=False)}\n\n"
        # If the scan already finished before subscribing, snapshot carries
        # done/error — close immediately so the client doesn't hang.
        if snap.get("phase") in ("done", "error"):
            return
        while True:
            if await request.is_disconnected():
                return
            updated = await component_library.wait_for_progress(last_version, timeout=15.0)
            snap = component_library.get_progress_snapshot()
            if snap.get("version", 0) <= last_version:
                # Heartbeat keeps the connection open through long VLM stalls.
                yield ": keepalive\n\n"
                continue
            last_version = snap["version"]
            phase = snap.get("phase", "")
            event_name = phase if phase in ("done", "error") else "progress"
            yield f"event: {event_name}\ndata: {json.dumps(snap, ensure_ascii=False)}\n\n"
            if phase in ("done", "error"):
                return

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/components", status_code=204, response_class=Response, response_model=None)
async def delete_components(request: Request) -> None:
    from . import component_library  # noqa: PLC0415

    actor = _actor_from_request(request)
    removed = component_library.clear_components()
    SmartLogger.log(
        "INFO",
        f"figma_binding.components.cleared actor={actor} removed={removed}",
        category="figma_binding.components.cleared",
        params={"actor": actor, "removed": removed},
    )


# ─── 024-DEV: end-to-end component-render smoke test ────────────────────
# Demonstrates the full pipeline: bound catalog → LLM pick → INSTANCE
# sceneGraph → Figma plugin push (new page + frame).
# Useful for manual smoke testing; the production path is the ingestion
# upload flow with `ui_generation_mode = "figma-with-components"`.


from pydantic import BaseModel as _BaseModel  # noqa: E402


class _ComponentRenderTestRequest(_BaseModel):
    screen_brief: str
    frame_name: str = "Spec 024 Test Frame"
    page_name: str | None = None  # default: f"Spec 024 Test {timestamp}"


@router.post("/components/_dev/test-render")
async def post_test_component_render(req: _ComponentRenderTestRequest, request: Request) -> dict[str, Any]:
    """End-to-end smoke for spec 024 figma-with-components mode.

    Flow: run the open-pencil JSX agent with the bound component catalog
    injected as extra_context → post-process the returned sceneGraph
    (retype `$INSTANCE:Name` FRAME leaves to INSTANCE leaves with
    componentId) → push the sceneGraph to Figma via the plugin
    (new page + frame). Mirrors the production figma-with-components
    ingestion path (`_generate_figma_components_scene_graph`).
    """
    import asyncio as _asyncio  # noqa: PLC0415
    import time as _time  # noqa: PLC0415

    from . import component_library, plugin_messages, repository  # noqa: PLC0415
    from ..ingestion.figma_plugin_ws import is_polling_active  # noqa: PLC0415
    from api.features.ai_design.wireframe_agent import run_render_agent  # noqa: PLC0415

    binding = repository.get_active_binding()
    if not binding:
        raise HTTPException(status_code=404, detail="활성 바인딩 없음")
    file_key = binding["figmaFileKey"]

    if not is_polling_active(file_key):
        raise HTTPException(
            status_code=503,
            detail={"error": "plugin_not_connected", "messageKr": "Figma 플러그인이 연결되어 있지 않습니다."},
        )

    catalog = component_library.get_catalog_for_prompt()
    if not catalog:
        raise HTTPException(
            status_code=400,
            detail={"error": "empty_catalog", "messageKr": "스캔된 컴포넌트가 없습니다. 먼저 /components/scan을 호출하세요."},
        )

    actor = _actor_from_request(request)
    SmartLogger.log(
        "INFO",
        f"figma_binding.components.dev_render.start brief_len={len(req.screen_brief)} actor={actor}",
        category="figma_binding.components.dev_render.start",
        params={"actor": actor, "brief_preview": req.screen_brief[:120]},
    )

    # 1) Invoke the open-pencil JSX agent with the bound catalog injected as
    #    extra_context. The agent renders JSX → SceneGraph via Yoga so layout
    #    properly respects auto-layout, padding, alignment.
    extra_ctx = component_library.build_jsx_agent_extra_context(catalog)
    agent_events: list[dict[str, Any]] = []
    def _capture_event(name: str, data: dict[str, Any]) -> None:
        # Trim long payloads so the dev response stays readable.
        compact = {k: (v if not isinstance(v, str) else (v[:200] + "…" if len(v) > 200 else v)) for k, v in (data or {}).items()}
        agent_events.append({"name": name, **compact})

    started = _time.monotonic()
    scene_graph, summary = await run_render_agent(
        name=req.frame_name,
        description=req.screen_brief,
        bc_name="",
        bc_description="",
        extra_context=extra_ctx,
        on_event=_capture_event,
    )
    llm_ms = int((_time.monotonic() - started) * 1000)

    if not scene_graph:
        return {
            "ok": False,
            "step": "run_render_agent_failed",
            "llmDurationMs": llm_ms,
            "summary": summary,
            "catalogChars": len(catalog),
            "extraContextChars": len(extra_ctx),
            "agentEvents": agent_events[-30:],
        }

    # 2) Post-process: retype `$INSTANCE:Name|k=v` FRAME leaves to INSTANCE
    #    nodes (the Figma plugin instantiates them by name from its local cache).
    name_index = component_library.build_name_to_node_index()
    scene_graph, retype_counts = component_library.retype_instance_markers(
        scene_graph, name_index
    )
    instance_count = retype_counts["retyped"]
    instance_names = retype_counts["instance_names"]
    unresolved = retype_counts["unresolved"]

    # Count "native" (non-INSTANCE non-Document/CANVAS) leaves for visibility.
    native_count = 0
    if isinstance(scene_graph.get("nodes"), dict):
        for n in scene_graph["nodes"].values():
            t = (n.get("type") or "").upper()
            if t in ("TEXT", "RECTANGLE", "ELLIPSE", "LINE", "VECTOR"):
                native_count += 1

    page_name = req.page_name or f"Spec 024 Test {int(_time.time())}"

    # Step A: create page.
    create_page_msg = plugin_messages.build_create_page(page_name)
    try:
        page_ack = await plugin_messages.send_and_wait(file_key, create_page_msg, 90.0)
    except plugin_messages.PluginNotConnectedError:
        raise HTTPException(status_code=503, detail="Figma 플러그인 연결이 끊겼습니다.")
    except _asyncio.TimeoutError:
        return {"ok": False, "step": "create_page_timeout"}
    if not page_ack.get("ok") or not page_ack.get("figmaPageId"):
        return {"ok": False, "step": "create_page_failed", "ack": page_ack}
    page_id = page_ack["figmaPageId"]

    # Step B: build frame on the new page using the sceneGraph.
    frame_msg = plugin_messages.build_create_frame_in_page(
        figma_page_id=page_id, frame_name=req.frame_name, scene_graph=scene_graph
    )
    try:
        frame_ack = await plugin_messages.send_and_wait(file_key, frame_msg, 120.0)
    except _asyncio.TimeoutError:
        return {"ok": False, "step": "create_frame_timeout", "figmaPageId": page_id}

    SmartLogger.log(
        "INFO",
        f"figma_binding.components.dev_render.done instances={instance_count} natives={native_count} unresolved={unresolved}",
        category="figma_binding.components.dev_render.done",
        params={
            "instances": instance_count,
            "natives": native_count,
            "unresolved": unresolved,
            "pageId": page_id,
            "frameAck": frame_ack,
        },
    )

    # Build a deep link so the user can jump straight to the new frame
    # in Figma. URL encoding rule: replace ":" with "-" in node id.
    figma_node_id_for_url = (frame_ack.get("figmaNodeId") or "").replace(":", "-")
    file_name_url_safe = (binding.get("figmaFileName") or "Wireframe").replace(" ", "-")
    figma_url = (
        f"https://www.figma.com/design/{file_key}/{file_name_url_safe}?node-id={figma_node_id_for_url}"
        if figma_node_id_for_url
        else None
    )

    return {
        "ok": frame_ack.get("ok", False),
        "llmDurationMs": llm_ms,
        "summary": summary,
        "instanceCount": instance_count,
        "nativeCount": native_count,
        "instanceNames": instance_names,
        "unresolved": unresolved,
        "sceneGraph": scene_graph,
        "figmaPageId": page_id,
        "figmaPageName": page_ack.get("figmaPageName"),
        "figmaNodeId": frame_ack.get("figmaNodeId"),
        "figmaFrameName": frame_ack.get("figmaFrameName"),
        "figmaUrl": figma_url,
        "nodesCreated": frame_ack.get("nodesCreated"),
        "nodesFailed": frame_ack.get("nodesFailed"),
        "renderErrors": frame_ack.get("renderErrors") or [],
        "pluginBuildId": frame_ack.get("buildId"),
        "frameAck": frame_ack,
    }


def _hex_to_rgb(hex_color: str) -> dict[str, float]:
    """Convert "#rrggbb" to Figma SOLID color dict {r,g,b} 0–1."""
    s = (hex_color or "#9ca3af").lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        s = "9ca3af"
    try:
        r = int(s[0:2], 16) / 255.0
        g = int(s[2:4], 16) / 255.0
        b = int(s[4:6], 16) / 255.0
    except ValueError:
        r, g, b = 0.6, 0.6, 0.6
    return {"r": r, "g": g, "b": b}


# ─── Storyboards (read-only listing) ────────────────────────────────────


@router.get("/storyboards", response_model=list[StoryboardListItem])
async def get_storyboards() -> list[dict[str, Any]]:
    return service.list_storyboards()


# ─── Sync storyboards (US2: T031, T032) ──────────────────────────────────


def _normalize_sync_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """Adapt service.sync_storyboards' output to the SyncStoryboardsResponse
    schema shape. Service emits richer per-item payloads (figmaPageId etc.);
    schema strips down to (commandId, reason / from / to)."""
    return {
        "created": [
            {"commandId": c["commandId"], "figmaPageId": c["figmaPageId"], "figmaPageName": c["figmaPageName"]}
            for c in summary.get("created", [])
        ],
        "reused": [
            {"commandId": c["commandId"], "figmaPageId": c["figmaPageId"], "figmaPageName": c["figmaPageName"]}
            for c in summary.get("reused", [])
        ],
        "renamed": [
            {"commandId": c["commandId"], "from": c.get("oldName") or "", "to": c.get("figmaPageName") or ""}
            for c in summary.get("renamed", [])
        ],
        "archived": [
            {"commandId": cid, "reason": "entry_command_removed"} for cid in summary.get("archived", [])
        ],
        "unreachable": [
            {"commandId": u["commandId"], "reason": u.get("error") or "unknown"}
            for u in summary.get("unreachable", [])
        ],
    }


@router.post("/sync-storyboards", response_model=SyncStoryboardsResponse)
async def post_sync_storyboards(request: Request) -> dict[str, Any]:
    actor = _actor_from_request(request)
    summary = await service.sync_storyboards(actor=actor)
    return _normalize_sync_summary(summary)


@router.get("/sync-storyboards/stream")
async def get_sync_storyboards_stream(request: Request) -> StreamingResponse:
    """SSE variant. Emits one event per page operation as it completes,
    finishing with a `done` event carrying the full summary."""
    actor = _actor_from_request(request)

    async def _gen():
        try:
            async for name, payload in service.sync_storyboards_stream(actor=actor):
                if name == "done":
                    payload = _normalize_sync_summary(payload)
                yield f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        except Exception as e:  # noqa: BLE001
            yield f"event: error\ndata: {json.dumps({'detail': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")


# ─── Retry sync (FR-020 / T087) ───────────────────────────────────────────


from pydantic import BaseModel  # noqa: E402

from . import bulk_sync  # noqa: E402


class RetrySyncRequest(BaseModel):
    uiIds: list[str] | None = None  # null/missing → retry every :UI {figmaSyncStatus:'failed'}


@router.post("/retry-sync")
async def post_retry_sync(req: RetrySyncRequest, request: Request) -> dict[str, Any]:
    """Re-run the Figma push for selected UIs (or every failed-sync UI when
    uiIds is null/missing). Synchronous v1: waits for all pushes to complete
    and returns the summary.

    020 extensions:
      - In-flight retry deduplication via `retry_dedupe.RetryDedupeStore` —
        concurrent retries on the same uiId share one plugin dispatch.
      - Read-time classifier — non-retryable ids are skipped with a Korean
        reason. Skipped events appear in `events` as `retry_skipped`.
    """
    actor = _actor_from_request(request)

    from . import (
        failure_classifier,  # noqa: PLC0415
        repository as _repo,  # noqa: PLC0415
        retry_dedupe,  # noqa: PLC0415
    )

    # Resolve UI ids: explicit list, or every failed-sync UI.
    if req.uiIds is None:
        failed = _repo.list_failures_with_binding_key()
        ui_ids = [r["uiId"] for r in failed]
    else:
        ui_ids = req.uiIds

    if not ui_ids:
        return {"sessionId": None, "queuedCount": 0, "syncedCount": 0, "failedCount": 0, "message": "재시도할 UI가 없습니다."}

    SmartLogger.log(
        "INFO",
        f"figma_binding.retry.requested actor={actor} count={len(ui_ids)}",
        category="figma_binding.retry.requested",
        params={"actor": actor, "uiIds": ui_ids[:50], "count": len(ui_ids)},
    )

    # ── Classifier-based skip ────────────────────────────────────────────
    binding = _repo.get_active_binding()
    failures_raw = {f["uiId"]: f for f in _repo.list_failures_with_binding_key()}
    neo_view = _repo.fetch_classifier_view(ui_ids)
    dedupe = retry_dedupe.get_store()
    in_flight = dedupe.inflight_set()

    eligible_ids: list[str] = []
    skipped: list[dict[str, Any]] = []
    for uid in ui_ids:
        f = failures_raw.get(uid) or {"uiId": uid, "figmaSyncBindingFileKey": None}
        cls = failure_classifier.classify(
            failure=f, current_binding=binding, neo4j_view=neo_view, in_flight=in_flight
        )
        if cls["retryability"] == "non-retryable":
            skipped.append(
                {
                    "uiId": uid,
                    "reason": "non-retryable",
                    "reasonKr": cls.get("nonRetryableReason"),
                }
            )
            SmartLogger.log(
                "INFO",
                f"figma_binding.retry.classified_skip uid={uid} reason={cls.get('nonRetryableReason')}",
                category="figma_binding.retry.classified_skip",
                params={"uiId": uid, "reason": cls.get("nonRetryableReason")},
            )
        else:
            eligible_ids.append(uid)

    import uuid as _uuid
    session_id = _uuid.uuid4().hex[:12]

    events: list[dict[str, Any]] = []
    def _capture(name: str, payload: dict[str, Any]) -> None:
        events.append({"name": name, **payload})

    # Surface skipped events in the same shape the SSE stream uses.
    for s in skipped:
        _capture("retry_skipped", s)

    if not eligible_ids:
        return {
            "sessionId": session_id,
            "queuedCount": len(ui_ids),
            "syncedCount": 0,
            "failedCount": 0,
            "skippedCount": len(skipped),
            "events": events,
            "summary": {"syncedCount": 0, "failedCount": 0, "skippedCount": len(skipped)},
        }

    # ── Dedupe: claim each uid; joiners await the existing future ──────
    own_claims: list[str] = []
    join_futures: list[tuple[str, Any]] = []
    for uid in eligible_ids:
        first, fut = dedupe.claim_or_join(uid)
        if first:
            own_claims.append(uid)
        else:
            join_futures.append((uid, fut))

    summary = {"syncedCount": 0, "failedCount": 0}
    try:
        if own_claims:
            summary = await bulk_sync.sync_batch(
                session_id=session_id,
                ui_ids=own_claims,
                on_event=_capture,
            )
            # Resolve the futures for our own claims with their final result.
            # Outcomes per uid are inferable from the events list — use
            # `figma_sync.ok` events as the success signal; everything else
            # the caller treats as failure.
            ok_uids = {e["uiId"] for e in events if e.get("name") == "figma_sync.ok" and e.get("uiId")}
            for uid in own_claims:
                dedupe.complete(uid, {"ok": uid in ok_uids})
    except Exception as e:  # noqa: BLE001
        for uid in own_claims:
            dedupe.fail(uid, e)
        raise

    # Wait for joined futures and surface their outcomes (the dispatcher
    # already broadcasts events for them, but we mirror them here for the
    # synchronous return shape).
    for uid, fut in join_futures:
        try:
            res = await fut
            if res.get("ok"):
                summary["syncedCount"] = (summary.get("syncedCount") or 0) + 1
                _capture("figma_sync.ok", {"uiId": uid, "deduped": True})
            else:
                summary["failedCount"] = (summary.get("failedCount") or 0) + 1
                _capture("figma_sync.failed", {"uiId": uid, "deduped": True})
        except Exception:  # noqa: BLE001
            summary["failedCount"] = (summary.get("failedCount") or 0) + 1
            _capture("figma_sync.failed", {"uiId": uid, "deduped": True})

    summary["skippedCount"] = len(skipped)

    SmartLogger.log(
        "INFO",
        f"figma_binding.retry.done session={session_id} synced={summary.get('syncedCount')} failed={summary.get('failedCount')} skipped={len(skipped)}",
        category="figma_binding.retry.done",
        params={"sessionId": session_id, **summary},
    )

    return {
        "sessionId": session_id,
        "queuedCount": len(ui_ids),
        "syncedCount": summary.get("syncedCount", 0),
        "failedCount": summary.get("failedCount", 0),
        "skippedCount": len(skipped),
        "events": events,
        "summary": summary,
    }


# ─── Bidirectional sync (RA ↔ Figma per UI) ───────────────────────────────


@router.post("/update-frame/{ui_id}")
async def post_update_frame(ui_id: str, request: Request) -> dict[str, Any]:
    """RA → Figma: push the UI's current sceneGraph as an in-place update
    of its linked Figma frame. Frame must already exist (UI.figmaNodeId set).
    """
    actor = _actor_from_request(request)
    SmartLogger.log(
        "INFO",
        f"figma_binding.update_frame.start ui={ui_id} actor={actor}",
        category="figma_binding.update_frame",
    )
    result = await service.update_frame_for_ui(ui_id)
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result.get("errorKo") or "Figma 프레임 업데이트 실패")
    return result


@router.post("/pull-frame/{ui_id}")
async def post_pull_frame(ui_id: str, request: Request) -> dict[str, Any]:
    """Figma → RA: pull the linked Figma frame's current state via the
    plugin, convert to sceneGraph, persist on the UI node. No Figma API
    token needed (plugin reads in-process).
    """
    actor = _actor_from_request(request)
    SmartLogger.log(
        "INFO",
        f"figma_binding.pull_frame.start ui={ui_id} actor={actor}",
        category="figma_binding.pull_frame",
    )
    result = await service.pull_frame_via_plugin(ui_id)
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result.get("errorKo") or "Figma 프레임 pull 실패")
    return result


# ─── 020: Retroactive full-sync ───────────────────────────────────────────


@router.post("/full-sync", status_code=202, response_model=FullSyncStartResponse)
async def post_full_sync(request: Request) -> dict[str, Any]:
    """Start a project-wide retroactive full-sync. Returns 202 with a runId
    on success, 409 with the in-flight runId on lock contention, 404 if no
    binding, 502 if binding is unreachable.
    """
    actor = _actor_from_request(request)
    result = await service.full_sync(actor=actor)
    if result.get("_locked"):
        result.pop("_locked", None)
        raise HTTPException(status_code=409, detail=result)
    return result


@router.get("/full-sync/{run_id}/stream")
async def get_full_sync_stream(run_id: str, request: Request) -> StreamingResponse:
    """SSE progress stream for a full-sync run. Late subscribers get the
    cached run_started + most-recent progress immediately."""

    async def _gen():
        try:
            async for name, payload in service.full_sync_stream(run_id):
                yield f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        except Exception as e:  # noqa: BLE001
            yield f"event: error\ndata: {json.dumps({'detail': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/full-sync/{run_id}/cancel", status_code=202)
async def post_full_sync_cancel(run_id: str, request: Request) -> dict[str, Any]:
    """Cancel a running full-sync. In-flight items finish naturally; no new
    dispatches are made. Returns 404 if the run is unknown or already
    terminated."""
    return await service.cancel_full_sync(run_id)


@router.get("/sync-runs", response_model=SyncRunsListResponse)
async def get_sync_runs(
    request: Request,
    limit: int = 20,
    includePreviousBinding: bool = True,
) -> dict[str, Any]:
    """List past :SyncRun summaries for the History tab. Each row carries a
    `previousBinding` flag derived from the active binding's file key."""
    return service.list_sync_runs(
        limit=limit, include_previous_binding=includePreviousBinding
    )


@router.get("/failures", response_model=FailuresListResponse)
async def get_failures(request: Request) -> dict[str, Any]:
    """Canonical project-scoped failure list, classified by retryability.
    Source for the History tab + ingestion floating panel + Inspector badge."""
    return service.list_failures()


# Mount the plugin ack endpoints (CREATE_PAGE_ACK / CREATE_FRAME_IN_PAGE_ACK).
# These live under /api/figma-plugin/* because the plugin already speaks that prefix.
# Importing here keeps the wiring local to feature 016.
__all__ = ["router", "plugin_messages_router"]
