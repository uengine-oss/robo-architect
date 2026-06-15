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
    applied = 0  # I13: 실제 반영 건수(0이면 프런트가 "반영 없음"으로 표시)

    for d in drafts or []:
        if approved and d.get("changeId") not in approved:
            continue
        target_id = str(d.get("targetId") or "")
        after = d.get("after") or d.get("updates") or {}
        ttype = (d.get("targetType") or "").lower()
        if not target_id:
            continue
        # rename → nodeTitle / name
        if d.get("action") == "rename" and after.get("name"):
            after = {**after, "name": after["name"]}
        i = by_id.get(target_id)
        if i is not None:
            tactical[i] = _normalize_item_from_edit(tactical[i], _draft_after_to_edit(tactical[i], after), bc_id)
            touched_bc = touched_bc or tactical[i].get("boundedContextId")
            applied += 1
        # 대상이 diff 에 없으면(라이브 Aggregate) MODIFY 신규
        elif ttype == "aggregate":
            item = _normalize_item_from_edit(
                {"nodeId": target_id, "nodeLabel": "Aggregate", "nodeTitle": after.get("name") or target_id,
                 "changeType": "MODIFY", "impactLevel": "MEDIUM", "reason": "Chat 수정 요청 반영"},
                _draft_after_to_edit({}, after), bc_id,
            )
            tactical.append(item)
            by_id[target_id] = len(tactical) - 1
            applied += 1
        # I13: 자식요소 신규 추가(Property/VO/Enum) — 부모(보통 Aggregate) 항목에 병합.
        # 부모 식별자는 표현마다 다르다: 라이브 create 는 `aggregateId`, Property create 는
        # `updates.parentId`(=after.parentId). (모델모디파이어는 ValueObject targetType 이
        # 없어 "VO 추가"가 Property 로 변환되므로 parentId 경로가 실사용 케이스다.)
        elif d.get("action") == "create" and ttype in _CHILD_COLLECTION:
            coll = _CHILD_COLLECTION[ttype]
            parent_id = str(d.get("aggregateId") or d.get("parentId") or after.get("parentId") or "")
            ai = by_id.get(parent_id)
            if ai is None and parent_id:
                tactical.append({
                    "nodeId": parent_id,
                    "nodeLabel": after.get("parentType") or d.get("parentType") or "Aggregate",
                    "nodeTitle": d.get("parentName") or parent_id,
                    "changeType": "MODIFY", "impactLevel": "MEDIUM",
                    "reason": "Chat 자식요소 추가", "boundedContextId": bc_id,
                })
                ai = by_id[parent_id] = len(tactical) - 1
            if ai is not None:
                item = dict(tactical[ai])
                arr = list(item.get(coll) or [])
                # 자식 entry — 라우팅 메타(parentType/parentId)는 제외.
                child = {k: v for k, v in after.items() if k not in ("parentType", "parentId")}
                child.setdefault("name", d.get("targetName") or after.get("name") or target_id)
                child.setdefault("nodeId", target_id)
                arr.append(_strip_meta([child])[0])
                item[coll] = arr
                tactical[ai] = item
                touched_bc = touched_bc or item.get("boundedContextId")
                applied += 1
        # 미리보기 자식요소 삭제/수정/이름변경(Property/VO/Enum) — 부모 항목 컬렉션을 직접 변경.
        # 부모는 parentId(=updates.parentId)/aggregateId 로 식별한다. 미리보기 오버레이 자식은
        # Neo4j id 가 없어(prop-noid-*) targetId 매칭이 불가하므로 nodeId/id→name 순으로 찾는다.
        # 부모가 제안에 없으면(라이브 전용 Aggregate) 매칭 0 → applied 미증가(layer-2 백로그).
        elif d.get("action") in ("delete", "update", "rename") and ttype in _CHILD_COLLECTION:
            coll = _CHILD_COLLECTION[ttype]
            parent_id = _child_parent_id(d, after)
            ai = by_id.get(parent_id)
            if ai is not None:
                item = dict(tactical[ai])
                arr = list(item.get(coll) or [])
                j = _match_child_index(arr, d, after)
                if j is not None:
                    if d.get("action") == "delete":
                        arr.pop(j)
                    elif d.get("action") == "rename":
                        child = dict(arr[j])
                        child["name"] = d.get("targetName") or after.get("name") or child.get("name")
                        arr[j] = child
                    else:  # update — 변경 필드 병합(라우팅 메타 제외)
                        child = dict(arr[j])
                        for k, v in after.items():
                            if k not in ("parentType", "parentId"):
                                child[k] = v
                        arr[j] = _strip_meta([child])[0]
                    item[coll] = arr
                    tactical[ai] = item
                    touched_bc = touched_bc or item.get("boundedContextId")
                    applied += 1
        # I13: top-level 신규 요소(Command/Event/ReadModel/Policy) — 새 tactical 항목.
        elif d.get("action") == "create" and ttype in _TOPLEVEL_LABEL and target_id not in by_id:
            item = {
                "nodeId": target_id, "nodeLabel": _TOPLEVEL_LABEL[ttype],
                "nodeTitle": d.get("targetName") or after.get("name") or target_id,
                "changeType": "CREATE", "impactLevel": "MEDIUM",
                "reason": "Chat 수정 요청 반영",
                "boundedContextId": bc_id or str(d.get("aggregateId") or "") or None,
            }
            if after:
                item["fields"] = {k: v for k, v in after.items() if k not in _META_KEYS}
            tactical.append(item)
            by_id[target_id] = len(tactical) - 1
            applied += 1

    _write_tactical(proposal_id, tactical)
    tree = build_data_preview(proposal_id, touched_bc) if touched_bc else {"_preview": {"saved": True}}
    # 반영 건수를 메타로 실어 보내 프런트가 정직한 메시지를 띄우게 한다(I13).
    if isinstance(tree, dict):
        tree.setdefault("_preview", {})
        if isinstance(tree["_preview"], dict):
            tree["_preview"]["appliedCount"] = applied
    return tree


# I13: chat draft targetType → Aggregate 자식 컬렉션 / top-level 라벨 매핑.
_CHILD_COLLECTION = {
    "valueobject": "valueObjects",
    "enumeration": "enumerations",
    "enum": "enumerations",
    "property": "properties",
}
_TOPLEVEL_LABEL = {
    "command": "Command",
    "event": "Event",
    "readmodel": "ReadModel",
    "policy": "Policy",
}


def _child_parent_id(d: dict, after: dict) -> str:
    """자식 draft 가 가리키는 부모(보통 Aggregate) id 를 해소한다."""
    return str(d.get("aggregateId") or d.get("parentId") or after.get("parentId") or "")


def _match_child_index(arr: list, d: dict, after: dict) -> Optional[int]:
    """부모 컬렉션에서 대상 자식의 인덱스를 찾는다.

    미리보기 오버레이 자식은 Neo4j id 가 없을 수 있어(prop-noid-*) targetId 매칭이 불가하므로
    nodeId/id → name 순으로 찾는다(인텐트 포맷 속성은 name 만 보유)."""
    target_id = str(d.get("targetId") or "")
    name = d.get("targetName") or after.get("name")
    if target_id:
        for j, c in enumerate(arr):
            if isinstance(c, dict) and str(c.get("nodeId") or c.get("id") or "") == target_id:
                return j
    if name:
        for j, c in enumerate(arr):
            if isinstance(c, dict) and c.get("name") == name:
                return j
    return None


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
