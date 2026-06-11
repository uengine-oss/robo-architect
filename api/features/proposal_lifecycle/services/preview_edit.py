"""040 — 미리보기 편집 → 제안 diff 반영.

모델러가 미리보기 설계 화면(Inspector 직접 편집 / Chat 자연어 수정)에서 변경한 내용을
**라이브 그래프가 아니라 Proposal.tacticalDiff(JSON)** 에 반영한다. 라이브 디자인 그래프는
절대 건드리지 않는다(Constitution I) — 단, 쓰는 대상은 `:Proposal` 노드의 자기 자신 속성
(tacticalDiff)이므로 read-only 투영 모듈과 분리해 둔다.

핵심: 미리보기에 보이는 Aggregate 의 정규화된 deep 표현(properties/enumerations/
valueObjects/invariants/fields)을 tacticalDiff 항목에 그대로 저장 → 다음 투영 시 그대로 렌더.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from api.platform.neo4j import get_session
from api.features.proposal_lifecycle.services.preview_projection import (
    build_data_preview, _load_proposal,
)

# 저장 시 제거할 미리보기 전용 메타(출처/배지). 라이브 필드만 남긴다.
_META_KEYS = ("source", "badge")


def _strip_meta(items: list) -> list:
    out = []
    for it in items or []:
        if isinstance(it, dict):
            out.append({k: v for k, v in it.items() if k not in _META_KEYS})
        else:
            out.append(it)
    return out


def _read_tactical(proposal_id: str) -> list[dict]:
    with get_session() as session:
        rec = session.run(
            "MATCH (p:Proposal {id: $id}) RETURN p.tacticalDiff AS td", id=proposal_id
        ).single()
    if not rec or not rec.get("td"):
        return []
    try:
        return json.loads(rec["td"]) or []
    except Exception:
        return []


def _write_tactical(proposal_id: str, tactical: list[dict]) -> None:
    """Proposal 노드의 tacticalDiff 속성만 갱신(제안 자기 데이터). 라이브 디자인 그래프 무관."""
    td_json = json.dumps(tactical, ensure_ascii=False)
    with get_session() as session:
        session.run(
            "MATCH (p:Proposal {id: $id}) SET p.tacticalDiff = $td",
            id=proposal_id, td=td_json,
        )


def _normalize_item_from_edit(item: dict, edited: dict, bc_id: Optional[str]) -> dict:
    """편집된 Aggregate(deep 뷰)를 tacticalDiff 항목으로 정규화해 덮어쓴다."""
    item = dict(item)
    if edited.get("name"):
        item["nodeTitle"] = edited["name"]
    fields = dict(item.get("fields") or {})
    if "rootEntity" in edited and edited["rootEntity"] is not None:
        fields["rootEntity"] = edited["rootEntity"]
    if edited.get("displayName"):
        fields["displayName"] = edited["displayName"]
    if fields:
        item["fields"] = fields
    if bc_id and not item.get("boundedContextId"):
        item["boundedContextId"] = bc_id
    # deep 정규화: 모든 자식을 item-level 로. semanticDiff.ops 는 비워 중복 렌더 방지.
    for fld in ("properties", "invariants", "enumerations", "valueObjects"):
        if fld in edited:
            item[fld] = _strip_meta(edited.get(fld) or [])
    item["semanticDiff"] = {"v": 1, "ops": [], "changeType": item.get("changeType", "MODIFY")}
    return item


def reconcile_aggregate_edit(proposal_id: str, node_id: str, bc_id: Optional[str], edited: dict) -> dict:
    """편집된 Aggregate 를 tacticalDiff 에 반영하고, 갱신된 미리보기 트리를 반환한다.

    - 해당 nodeId 의 tacticalDiff 항목이 있으면 정규화 덮어쓰기.
    - 없으면(라이브 Aggregate 를 처음 수정) MODIFY 항목 신규 생성.
    """
    proposal = _load_proposal(proposal_id)
    if proposal is None:
        raise ValueError(f"Proposal {proposal_id} not found")

    tactical = _read_tactical(proposal_id)
    idx = next((i for i, it in enumerate(tactical) if str(it.get("nodeId") or "") == str(node_id)), None)

    if idx is not None:
        tactical[idx] = _normalize_item_from_edit(tactical[idx], edited, bc_id)
    else:
        # 라이브 Aggregate 를 처음 편집 → MODIFY 항목 생성.
        new_item = _normalize_item_from_edit(
            {"nodeId": node_id, "nodeLabel": "Aggregate", "nodeTitle": edited.get("name") or node_id,
             "changeType": "MODIFY", "impactLevel": "MEDIUM",
             "reason": "미리보기에서 직접 수정"},
            edited, bc_id,
        )
        tactical.append(new_item)

    _write_tactical(proposal_id, tactical)
    # bc_id 가 없으면 항목에서 해소.
    resolved_bc = bc_id or (tactical[idx].get("boundedContextId") if idx is not None else None)
    return build_data_preview(proposal_id, resolved_bc) if resolved_bc else {"_preview": {"saved": True}}


def apply_chat_drafts(proposal_id: str, drafts: list[dict], approved_ids: list[str], bc_id: Optional[str]) -> dict:
    """Chat 초안(DraftChange[]) 중 승인된 것을 tacticalDiff 에 반영(제안 diff 대상, 라이브 무관).

    각 draft 의 `after`(결과 상태) 또는 `updates` 를 대상 Aggregate 항목에 병합한다. 보수적으로
    Aggregate 타깃 + after.properties/name/rootEntity 위주로 처리한다.
    """
    proposal = _load_proposal(proposal_id)
    if proposal is None:
        raise ValueError(f"Proposal {proposal_id} not found")

    approved = set(approved_ids or [])
    tactical = _read_tactical(proposal_id)
    by_id = {str(it.get("nodeId") or ""): i for i, it in enumerate(tactical)}
    touched_bc = bc_id

    for d in drafts or []:
        if approved and d.get("changeId") not in approved:
            continue
        target_id = str(d.get("targetId") or "")
        after = d.get("after") or d.get("updates") or {}
        if not target_id:
            continue
        # rename → nodeTitle / name
        if d.get("action") == "rename" and after.get("name"):
            after = {**after, "name": after["name"]}
        i = by_id.get(target_id)
        if i is not None:
            tactical[i] = _normalize_item_from_edit(tactical[i], _draft_after_to_edit(tactical[i], after), bc_id)
            touched_bc = touched_bc or tactical[i].get("boundedContextId")
        # 대상이 diff 에 없으면(라이브 Aggregate) MODIFY 신규
        elif (d.get("targetType") or "").lower() == "aggregate":
            item = _normalize_item_from_edit(
                {"nodeId": target_id, "nodeLabel": "Aggregate", "nodeTitle": after.get("name") or target_id,
                 "changeType": "MODIFY", "impactLevel": "MEDIUM", "reason": "Chat 수정 요청 반영"},
                _draft_after_to_edit({}, after), bc_id,
            )
            tactical.append(item)
            by_id[target_id] = len(tactical) - 1

    _write_tactical(proposal_id, tactical)
    return build_data_preview(proposal_id, touched_bc) if touched_bc else {"_preview": {"saved": True}}


def _draft_after_to_edit(existing_item: dict, after: dict) -> dict:
    """draft.after(부분 상태)를 reconcile 가 기대하는 edited 형태로 변환.

    after 가 properties/enumerations/valueObjects/invariants/name/rootEntity 를 부분적으로
    담는다고 가정하고, 없는 필드는 기존 항목 값을 유지한다(부분 병합)."""
    edit: dict[str, Any] = {}
    for k in ("name", "displayName", "rootEntity"):
        if after.get(k) is not None:
            edit[k] = after[k]
    for fld in ("properties", "enumerations", "valueObjects", "invariants"):
        if fld in after and after[fld] is not None:
            edit[fld] = after[fld]
        elif existing_item.get(fld) is not None:
            edit[fld] = existing_item.get(fld)
    return edit
