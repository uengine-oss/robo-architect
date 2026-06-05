from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from starlette.requests import Request

from api.features.requirement_changes.requirement_changes_contracts import (
    ChangeStatus,
    DesignApplyResult,
    DesignChangeItem,
    ImpactLevel,
    SemanticDiff,
)
from api.features.requirement_changes.routes.changes_approval import (
    _append_status_history,
    _get_change_row,
)
from api.features.requirement_changes.services.design_applier import (
    _clear_diff_in_effect,
    _fetch_effects_with_diff,
    apply_design_changes,
    reverse_semantic_diff,
)
from api.platform.neo4j import get_session
from api.platform.observability.request_logging import http_context
from api.platform.observability.smart_logger import SmartLogger

router = APIRouter()


# ── apply-design ──────────────────────────────────────────────────────────

@router.post("/{change_id}/apply-design")
async def apply_design(change_id: str, request: Request):
    """
    PLAN_APPROVED → DESIGN_APPLIED.
    AI가 EFFECT 대상 노드를 업데이트하고, 각 EFFECT 관계에 SemanticDiff를 저장한다.
    SSE 스트림: {"phase": "applying"|"item_start"|"item_done"|"done"|"error", ...}
    """
    row = _get_change_row(change_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Change {change_id} not found")
    if row["status"] != ChangeStatus.PLAN_APPROVED.value:
        raise HTTPException(
            status_code=400,
            detail=f"설계 반영은 PLAN_APPROVED 상태에서만 가능합니다 (현재: {row['status']})",
        )

    prompt = row.get("originalPrompt", "")

    async def event_stream():
        applied_count = 0
        try:
            async for event in apply_design_changes(change_id, prompt):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("phase") == "item_done":
                    applied_count += 1

            # 상태 전환 (designChanges는 더 이상 RequirementChange에 저장하지 않음 — EFFECT에 저장)
            _append_status_history(change_id, "PLAN_APPROVED", "DESIGN_APPLIED", "system", None)
            SmartLogger.log(
                "INFO", f"Design applied: {change_id}, {applied_count} items",
                category="requirement_changes.design.done",
                params={"changeId": change_id, "count": applied_count},
            )
            yield f"data: {json.dumps({'phase': 'done', 'appliedCount': applied_count}, ensure_ascii=False)}\n\n"

        except Exception as e:
            SmartLogger.log(
                "ERROR", f"Design apply error: {change_id}: {e}",
                category="requirement_changes.design.error",
                params={"changeId": change_id, "error": str(e)},
            )
            yield f"data: {json.dumps({'phase': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    SmartLogger.log(
        "INFO", f"apply-design started: {change_id}",
        category="requirement_changes.design.start",
        params={**http_context(request), "changeId": change_id},
    )
    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── get design-changes ────────────────────────────────────────────────────

@router.get("/{change_id}/design-changes", response_model=DesignApplyResult)
async def get_design_changes(change_id: str):
    """
    EFFECT 관계에 저장된 SemanticDiff를 읽어 DesignChangeItem 목록으로 반환.
    apply 전이라면 items=[] 반환.
    """
    with get_session() as session:
        result = session.run(
            "MATCH (n:RequirementChange {id: $id}) RETURN n.status AS status",
            id=change_id,
        )
        rec = result.single()
    if not rec:
        raise HTTPException(status_code=404, detail=f"Change {change_id} not found")

    rows = _fetch_effects_with_diff(change_id)
    items = [_row_to_design_change_item(r) for r in rows]
    return DesignApplyResult(
        changeId=change_id,
        appliedCount=len(items),
        skippedCount=0,
        items=items,
    )


def _row_to_design_change_item(row: dict) -> DesignChangeItem:
    """EFFECT 조회 행 → DesignChangeItem 변환 (MODIFY + CREATE 모두 처리)."""
    diff_raw = row.get("diff")
    semantic: dict | None = None

    if diff_raw:
        try:
            semantic = json.loads(diff_raw) if isinstance(diff_raw, str) else diff_raw
        except Exception:
            semantic = None

    # CREATE 유형 처리
    if semantic and semantic.get("changeType") == "CREATE":
        template_raw = row.get("templateData")
        template: dict | None = None
        if template_raw:
            try:
                template = json.loads(template_raw) if isinstance(template_raw, str) else template_raw
            except Exception:
                template = None
        return DesignChangeItem(
            nodeId=row.get("nodeId", ""),
            nodeLabel=row.get("nodeLabel", ""),
            nodeTitle=row.get("nodeTitle", "") or semantic.get("nodeTitle", ""),
            impactLevel=ImpactLevel(row.get("impactLevel") or "MEDIUM"),
            appliedAt=row.get("appliedAt"),
            changeType="CREATE",
            createdNodeId=semantic.get("createdNodeId") or row.get("appliedNodeId"),
            templateData=template,
            semanticDiff=semantic,
        )

    # MODIFY 유형 처리 (기존 로직)
    field = "description"
    before = ""
    after  = ""
    field_changes       = None
    value_object_changes = None
    enum_changes        = None
    invariant_changes   = None

    if semantic:
        # replace op에서 before/after/field 추출
        for op in semantic.get("ops", []):
            if op.get("op") == "replace":
                field  = op.get("field", field)
                before = op.get("from_val", "")
                after  = op.get("to_val", "")
                break
        # 구조화 변경은 별도 저장된 AI 분석 결과 없이 ops에서 재구성
        field_changes        = _ops_to_field_changes(semantic.get("ops", []))
        value_object_changes = _ops_to_vo_changes(semantic.get("ops", []))
        enum_changes         = _ops_to_enum_changes(semantic.get("ops", []))
        invariant_changes    = _ops_to_invariant_changes(semantic.get("ops", []))

    return DesignChangeItem(
        nodeId=row.get("nodeId", ""),
        nodeLabel=row.get("nodeLabel", ""),
        nodeTitle=row.get("nodeTitle", ""),
        impactLevel=ImpactLevel(row.get("impactLevel") or "MEDIUM"),
        appliedAt=row.get("appliedAt"),
        changeType="MODIFY",
        field=field,
        before=before,
        after=after,
        fieldChanges=field_changes,
        valueObjectChanges=value_object_changes,
        enumChanges=enum_changes,
        invariantChanges=invariant_changes,
        semanticDiff=semantic,
    )


def _ops_to_field_changes(ops: list[dict]) -> list[dict] | None:
    """replace ops → fieldChanges 형식으로 변환 (프론트 테이블용)."""
    result = []
    for op in ops:
        if op.get("op") == "replace" and op.get("field") not in (
            "valueObjects", "enumerations", "invariants", "acceptanceCriteria"
        ):
            result.append({
                "type": "MODIFIED",
                "name": op.get("field"),
                "dataType": None,
                "before": op.get("from_val"),
                "after":  op.get("to_val"),
                "description": None,
            })
    return result or None


def _ops_to_vo_changes(ops: list[dict]) -> list[dict] | None:
    result = []
    for op in ops:
        if op.get("field") == "valueObjects":
            if op["op"] == "obj_append":
                data = op.get("obj_data") or {}
                result.append({
                    "type": "ADDED",
                    "name": op.get("obj_name"),
                    "displayName": data.get("displayName"),
                    "fields": data.get("fields"),
                    "description": None,
                })
            elif op["op"] == "obj_remove":
                result.append({
                    "type": "REMOVED",
                    "name": op.get("obj_name"),
                    "displayName": None,
                    "fields": None,
                    "description": None,
                })
    return result or None


def _ops_to_enum_changes(ops: list[dict]) -> list[dict] | None:
    result = []
    for op in ops:
        if op.get("field") == "enumerations":
            if op["op"] == "obj_append":
                data = op.get("obj_data") or {}
                result.append({
                    "enumName": op.get("obj_name"),
                    "type": "ADDED",
                    "addedItems": data.get("items", []),
                    "removedItems": [],
                })
            elif op["op"] in ("enum_add_items", "enum_remove_items"):
                result.append({
                    "enumName": op.get("enum_name"),
                    "type": "MODIFIED",
                    "addedItems":   op.get("items") if op["op"] == "enum_add_items" else [],
                    "removedItems": op.get("items") if op["op"] == "enum_remove_items" else [],
                })
    return result or None


def _ops_to_invariant_changes(ops: list[dict]) -> list[str] | None:
    for op in ops:
        if op.get("field") == "invariants" and op["op"] == "list_append":
            return op.get("items") or []
    return None


# ── undo-design ───────────────────────────────────────────────────────────

@router.post("/{change_id}/undo-design")
async def undo_design(change_id: str, request: Request):
    """
    DESIGN_APPLIED → PLAN_APPROVED.
    EFFECT 관계에 저장된 SemanticDiff를 역방향 적용하여 노드를 복원한다.
    텍스트 충돌이 있으면 AI가 CHG 기여분만 제거한다.
    """
    row = _get_change_row(change_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Change {change_id} not found")
    if row["status"] != ChangeStatus.DESIGN_APPLIED.value:
        raise HTTPException(
            status_code=400,
            detail=f"되돌리기는 DESIGN_APPLIED 상태에서만 가능합니다 (현재: {row['status']})",
        )

    effect_rows = _fetch_effects_with_diff(change_id)
    if not effect_rows:
        raise HTTPException(
            status_code=400,
            detail="적용된 설계 변경 내역이 없습니다 (EFFECT.diff 없음)",
        )

    reverted = 0
    all_errors: list[dict] = []

    for r in effect_rows:
        node_id    = r.get("nodeId", "")
        node_label = r.get("nodeLabel", "")
        diff_raw   = r.get("diff")
        if not diff_raw:
            continue
        try:
            diff_dict = json.loads(diff_raw) if isinstance(diff_raw, str) else diff_raw
            diff = SemanticDiff(**diff_dict)
        except Exception as e:
            all_errors.append({"nodeId": node_id, "error": f"diff 파싱 실패: {e}"})
            continue

        result = await reverse_semantic_diff(node_id, node_label, diff)
        if result["reverted"]:
            reverted += 1
            # CREATE 유형은 reverse_semantic_diff 내부에서 이미 EFFECT 초기화됨
            if diff.changeType != "CREATE":
                _clear_diff_in_effect(change_id, node_id)
        else:
            all_errors.extend(
                {"nodeId": node_id, "error": err} for err in result["errors"]
            )

    # 상태 복원
    with get_session() as session:
        session.run(
            "MATCH (n:RequirementChange {id: $id}) SET n.status = 'PLAN_APPROVED'",
            id=change_id,
        )
    _append_status_history(change_id, "DESIGN_APPLIED", "PLAN_APPROVED", "system", "설계 변경 되돌리기")

    SmartLogger.log(
        "INFO", f"Design undone: {change_id}, reverted={reverted}",
        category="requirement_changes.design.undo",
        params={**http_context(request), "changeId": change_id, "reverted": reverted},
    )
    return {
        "changeId": change_id,
        "status":   "PLAN_APPROVED",
        "reverted": reverted,
        "errors":   all_errors,
    }
