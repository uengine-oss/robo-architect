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
import re
from typing import Any, Optional

from api.platform.neo4j import get_session
from api.features.proposal_lifecycle.services.preview_projection import (
    build_data_preview, build_design_preview, _load_proposal,
)

# 저장 시 제거할 미리보기 전용 메타(출처/배지). 라이브 필드만 남긴다.
_META_KEYS = ("source", "badge")


def _norm_name(s: Any) -> str:
    """속성/필드/Enum 항목 이름 매칭용 정규화(대소문자 무시 + 양끝 공백 제거).

    Chat 수정 draft 는 LLM 이 사용자 프롬프트 표기를 그대로 따라 targetName 을 내보내는데,
    실제 속성명과 케이스/공백이 어긋나면(예: 사용자가 'productID' 라 적었지만 실제 속성은
    'productId') 정확 일치가 실패해 부모 컬렉션에서 대상 자식을 못 찾고 "0개 반영"이 됐다
    (재현: PRO-001 Event '장바구니에담김' productId FK). 이름 기반 매칭은 모두 이 정규화를
    거친다(targetId 매칭은 그대로 — id 는 케이스가 의미를 가짐)."""
    return str(s or "").strip().lower()


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


# 노드 레벨(Command/Event/ReadModel/Aggregate) 스칼라 설계 필드. name 은 nodeTitle 로 따로
# 처리하므로 제외한다. Chat/Inspector 공통으로 tacticalDiff item.fields 에 실어
# build_design_preview(_populate_from_deep_item)가 캔버스에 그대로 환원하게 한다. 아래
# _DESIGN_FIELD_KEYS(Inspector 경로)와 동일 집합 — Chat 경로도 같은 필드를 보존해야 한다.
_NODE_SCALAR_FIELDS = (
    "displayName", "description", "category", "actor", "version",
    "rootEntity", "provisioningType", "isMultipleResult", "gwtSets",
)


def _normalize_item_from_edit(item: dict, edited: dict, bc_id: Optional[str]) -> dict:
    """편집된 Aggregate(deep 뷰)를 tacticalDiff 항목으로 정규화해 덮어쓴다."""
    item = dict(item)
    fields = dict(item.get("fields") or {})
    if edited.get("name"):
        item["nodeTitle"] = edited["name"]
        # MODIFY(라이브) Aggregate 는 nodeTitle 만으로는 캔버스/트리에 이름이 안 바뀐다
        # (_populate_from_deep_item 는 fields 만 본다). fields.name 에도 실어 반영되게 한다.
        fields["name"] = edited["name"]
    # 043-fix4: name 외 모든 노드 레벨 설계 필드(version/category/actor/rootEntity/...)를
    # fields 로 보존한다. 종전엔 rootEntity/displayName/description 만 처리해 Chat 경로의
    # Event version, Command category/actor, ReadModel actor/isMultipleResult/provisioningType
    # 변경이 "1건 반영" 카운트만 되고 실제론 떨어져 캔버스/Neo4j 에 반영되지 않았다(재현:
    # PRO-001 Event '장바구니에담김' version 1.1.0). isMultipleResult=False 같은 falsy 값도
    # 보존해야 하므로 `is not None` 으로 판정한다.
    for k in _NODE_SCALAR_FIELDS:
        if k in edited and edited[k] is not None:
            fields[k] = edited[k]
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

    prefix = f"PREVIEW:{proposal_id}:"

    def resolve_idx(node_id: Any) -> Optional[int]:
        """캔버스 노드 id → tacticalDiff 인덱스. CREATE 신규 노드는 nodeId 가 null 일 수
        있어 캔버스 id 가 temp id(PREVIEW:<pid>:<idx>)로 나오므로, 그 경우 인덱스로 환원하고
        그 외에는 실 nodeId(by_id)로 찾는다. (build_data/design_preview 가 동일 규칙으로
        id 를 부여하므로 draft 의 parent/target id 도 두 형태 중 하나다.)"""
        s = str(node_id or "")
        if not s:
            return None
        if s.startswith(prefix):
            try:
                idx = int(s[len(prefix):])
            except ValueError:
                return None
            return idx if 0 <= idx < len(tactical) else None
        return by_id.get(s)

    for d in drafts or []:
        if approved and d.get("changeId") not in approved:
            continue
        target_id = str(d.get("targetId") or "")
        after = d.get("after") or d.get("updates") or {}
        ttype = (d.get("targetType") or "").lower()
        # 043-fix3: Property/VO-field/Enum 의 update/delete/rename/create draft 는 targetId=null
        # 로 오고(LLM 라우팅이 targetName + updates.parentId 기반), 부모(Aggregate/Command/Event/
        # ReadModel) 컬렉션으로 반영된다. 기존 `if not target_id: continue` 가드가 이 draft 들을
        # 통째로 떨궈 "0개 반영"(예: Event quantity Property 타입 변경)을 유발했다 — target 도
        # parent 도 없을 때만 건너뛴다.
        parent_ref = str(d.get("aggregateId") or d.get("parentId") or after.get("parentId") or "")
        if not target_id and not parent_ref:
            continue
        # rename → nodeTitle / name
        if d.get("action") == "rename" and after.get("name"):
            after = {**after, "name": after["name"]}

        # 043-fix2 — VO 필드 편집: parent 가 ValueObject 인 Property. 부모 Aggregate 항목의
        # 해당 VO obj_data.fields 를 직접 수정한다(별도 top-level 항목 생성 금지 — 그래야
        # 캔버스의 기존 VO 에 즉시 반영된다).
        parent_type = str(after.get("parentType") or d.get("parentType") or "").lower()
        if ttype == "property" and parent_type == "valueobject":
            vo_id = str(after.get("parentId") or d.get("parentId") or "")
            agg_id, vo_idx = _parse_child_canvas_id(vo_id, "vo")
            ai = resolve_idx(agg_id) if agg_id else None
            if ai is not None:
                item = tactical[ai]
                vo_obj = _resolve_child_obj(item, "valueObjects", vo_idx, None)
                if vo_obj is not None and _apply_vo_field_edit(vo_obj, d, after):
                    touched_bc = touched_bc or item.get("boundedContextId")
                    applied += 1
                # 부모 VO 를 찾았으면(또는 못 찾아도) 여기서 처리 종료 — 폴백 분기로 흘려보내
                # 엉뚱한 top-level ValueObject 항목을 만들지 않는다.
                continue

        # 043-fix2 — Enum 항목 편집: targetType=Enumeration + itemsToAdd/Remove/Rename.
        if ttype in ("enumeration", "enum") and any(
            k in after for k in ("itemsToAdd", "itemsToRemove", "itemsRename")
        ):
            agg_id, enum_idx = _parse_child_canvas_id(target_id, "enum")
            ai = resolve_idx(agg_id) if agg_id else None
            if ai is not None:
                item = tactical[ai]
                enum_obj = _resolve_child_obj(item, "enumerations", enum_idx, d.get("targetName"))
                if enum_obj is not None and _apply_enum_items_edit(enum_obj, after):
                    touched_bc = touched_bc or item.get("boundedContextId")
                    applied += 1
                continue

        # 043-fix: 자식요소(Property/VO/Enum) draft 는 targetId 가 우연히 top-level 항목
        # (부모 Command/Aggregate)의 nodeId 와 같아도 node-level 편집으로 처리하면 안 된다.
        # LLM 이 Property 변경을 targetId=<부모 Command id> 로 내보내는 경우가 있는데(예:
        # quantity 변경을 targetId=CMD-add-to-cart 로), 그러면 아래 node-level 분기가
        # _draft_after_to_edit 로 흘러 type 같은 속성 변경을 떨궈버려 "1건 반영"인데 실제론
        # 무변경이 된다. ttype 이 자식 컬렉션이면 아래 부모-컬렉션 라우팅으로 보낸다.
        i = resolve_idx(target_id)
        if i is not None and ttype not in _CHILD_COLLECTION:
            tactical[i] = _normalize_item_from_edit(tactical[i], _draft_after_to_edit(tactical[i], after), bc_id)
            touched_bc = touched_bc or tactical[i].get("boundedContextId")
            applied += 1
        # 대상이 diff 에 없으면(라이브 노드 첫 수정) MODIFY 신규 — Aggregate 뿐 아니라
        # 노드 레벨 라벨(Command/Event/ReadModel/Policy) 전부. 종전엔 aggregate 만 처리해
        # 라이브 Command/Event/ReadModel 을 Chat 으로 수정하면 매칭 0 → 무반영이었다(Inspector
        # 경로 reconcile_design_edit._ensure_modify_item 과 동형으로 맞춘다).
        elif target_id and ttype in _NODE_LEVEL_LABEL:
            item = _normalize_item_from_edit(
                {"nodeId": target_id, "nodeLabel": _NODE_LEVEL_LABEL[ttype],
                 "nodeTitle": after.get("name") or target_id,
                 "changeType": "MODIFY", "impactLevel": "MEDIUM", "reason": "Chat 수정 요청 반영"},
                _draft_after_to_edit({}, after), bc_id,
            )
            tactical.append(item)
            by_id[target_id] = len(tactical) - 1
            touched_bc = touched_bc or item.get("boundedContextId")
            applied += 1
        # I13: 자식요소 신규 추가(Property/VO/Enum) — 부모(보통 Aggregate) 항목에 병합.
        # 부모 식별자는 표현마다 다르다: 라이브 create 는 `aggregateId`, Property create 는
        # `updates.parentId`(=after.parentId). (모델모디파이어는 ValueObject targetType 이
        # 없어 "VO 추가"가 Property 로 변환되므로 parentId 경로가 실사용 케이스다.)
        elif d.get("action") == "create" and ttype in _CHILD_COLLECTION:
            coll = _CHILD_COLLECTION[ttype]
            parent_id = str(d.get("aggregateId") or d.get("parentId") or after.get("parentId") or "")
            ai = resolve_idx(parent_id)
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
            ai = resolve_idx(parent_id)
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
        elif d.get("action") == "create" and ttype in _TOPLEVEL_LABEL and resolve_idx(target_id) is None:
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
# 노드 레벨 라벨(라이브 노드 첫 수정 시 MODIFY 신규 생성용). Aggregate 포함 — _TOPLEVEL_LABEL
# (CREATE 라우팅 전용)과 달리 Aggregate 도 노드 레벨 update 대상이다.
_NODE_LEVEL_LABEL = {**_TOPLEVEL_LABEL, "aggregate": "Aggregate"}


def _child_parent_id(d: dict, after: dict) -> str:
    """자식 draft 가 가리키는 부모(보통 Aggregate) id 를 해소한다."""
    return str(d.get("aggregateId") or d.get("parentId") or after.get("parentId") or "")


# ---------------------------------------------------------------------------
# 043-fix2 — ValueObject 필드 / Enumeration 항목의 Chat 편집을 제안 diff 에 반영.
#
# 캔버스(AggregatePanel)는 Aggregate 의 N번째 VO/Enum 을 `vo-<aggId>-<idx>` /
# `enum-<aggId>-<idx>` 합성 id 로 그린다. VO/Enum 은 별도 tacticalDiff 항목이 아니라 **부모
# Aggregate 항목의 semanticDiff.ops(obj_append) 또는 item-level valueObjects/enumerations
# 배열** 안에 산다. 따라서 VO 필드/Enum 항목 편집은 합성 id 를 (aggId, idx)로 파싱해 부모
# Aggregate 항목을 찾고, 그 안의 해당 VO/Enum obj_data 를 직접 수정해야 한다.
# ---------------------------------------------------------------------------
_VO_ID_RX = re.compile(r"^vo-(?P<agg>.+)-(?P<idx>\d+)$")
_ENUM_ID_RX = re.compile(r"^enum-(?P<agg>.+)-(?P<idx>\d+)$")


def _parse_child_canvas_id(node_id: Any, kind: str) -> tuple[Optional[str], Optional[int]]:
    """`vo-<aggId>-<idx>` / `enum-<aggId>-<idx>` 합성 id 를 (aggregateId, index)로 파싱."""
    rx = _VO_ID_RX if kind == "vo" else _ENUM_ID_RX
    m = rx.match(str(node_id or ""))
    if not m:
        return None, None
    try:
        return m.group("agg"), int(m.group("idx"))
    except (ValueError, IndexError):
        return m.group("agg"), None


def _agg_child_obj_refs(item: dict, collection: str) -> list[dict]:
    """Aggregate 항목 안의 VO/Enum obj_data 참조 목록을 **투영 순서**로 반환한다.

    투영(apply_data_overlay)은 semanticDiff obj_append ops 를 먼저, 그 다음 item-level
    배열을 append 하므로 캔버스 인덱스도 그 순서를 따른다. 같은 순서로 dict 참조를 모아
    호출자가 제자리 수정할 수 있게 한다(반환 dict 은 item 내부 구조의 실제 참조)."""
    refs: list[dict] = []
    ops = ((item.get("semanticDiff") or {}).get("ops")) or []
    for op in ops:
        if op.get("op") == "obj_append" and op.get("field") == collection:
            od = op.get("obj_data")
            if not isinstance(od, dict):
                od = {"name": op.get("obj_name")}
                op["obj_data"] = od
            refs.append(od)
    for o in (item.get(collection) or []):
        if isinstance(o, dict):
            refs.append(o)
    return refs


def _resolve_child_obj(item: dict, collection: str, idx: Optional[int],
                       name: Optional[str]) -> Optional[dict]:
    """부모 Aggregate 항목에서 대상 VO/Enum obj_data 를 찾는다(인덱스 우선, 이름 폴백)."""
    refs = _agg_child_obj_refs(item, collection)
    if not refs:
        return None
    if idx is not None and 0 <= idx < len(refs):
        return refs[idx]
    if name:
        target = _norm_name(name)
        for od in refs:
            if _norm_name(od.get("name")) == target:
                return od
    return None


def _apply_vo_field_edit(vo_obj: dict, d: dict, after: dict) -> bool:
    """VO obj_data 의 `fields` 컬렉션에 필드 create/update/delete/rename 을 적용."""
    fields = list(vo_obj.get("fields") or [])
    action = d.get("action")
    if action == "create":
        fld = {k: v for k, v in after.items() if k not in ("parentType", "parentId", "oldName")}
        fld.setdefault("name", d.get("targetName") or str(d.get("targetId") or ""))
        fields.append(_strip_meta([fld])[0])
        vo_obj["fields"] = fields
        return True
    selector = _norm_name(after.get("oldName") or d.get("targetName") or after.get("name"))
    j = next((k for k, f in enumerate(fields)
              if isinstance(f, dict) and _norm_name(f.get("name")) == selector), None)
    if j is None:
        return False
    if action == "delete":
        fields.pop(j)
    elif action == "rename":
        f = dict(fields[j])
        f["name"] = d.get("targetName") or after.get("name") or f.get("name")
        fields[j] = f
    else:  # update — 변경 필드 병합(라우팅 메타 제외)
        f = dict(fields[j])
        for k, v in after.items():
            if k not in ("parentType", "parentId", "oldName"):
                f[k] = v
        fields[j] = _strip_meta([f])[0]
    vo_obj["fields"] = fields
    return True


def _apply_enum_items_edit(enum_obj: dict, after: dict) -> bool:
    """Enum obj_data 의 `items` 컬렉션에 itemsToAdd/itemsToRemove/itemsRename 을 적용.

    items 는 문자열 리스트다(드물게 {name} dict 가 섞일 수 있어 정규화)."""
    items = [str(x.get("name")) if isinstance(x, dict) else str(x)
             for x in (enum_obj.get("items") or [])]
    changed = False
    for it in (after.get("itemsToAdd") or []):
        s = str(it.get("name") if isinstance(it, dict) else it)
        if s and s not in items:
            items.append(s)
            changed = True
    rem = {str(x.get("name") if isinstance(x, dict) else x) for x in (after.get("itemsToRemove") or [])}
    if rem:
        kept = [x for x in items if x not in rem]
        if len(kept) != len(items):
            items = kept
            changed = True
    ren = after.get("itemsRename")
    if isinstance(ren, dict):
        for old, new in ren.items():
            for k, x in enumerate(items):
                if x == str(old):
                    items[k] = str(new)
                    changed = True
    if changed:
        enum_obj["items"] = items
    return changed


def _match_child_index(arr: list, d: dict, after: dict) -> Optional[int]:
    """부모 컬렉션에서 대상 자식의 인덱스를 찾는다.

    미리보기 오버레이 자식은 Neo4j id 가 없을 수 있어(prop-noid-*) targetId 매칭이 불가하므로
    nodeId/id → name 순으로 찾는다(인텐트 포맷 속성은 name 만 보유).

    rename 은 targetName 이 '새 이름'이라 저장된 '옛 이름' 자식과 일치하지 않는다. 프런트가
    updates.oldName 에 '옛 이름'을 실어 보내므로(delete/update 와 달리 rename 전용), 매칭 시
    oldName 을 최우선으로 사용한다(없으면 기존 targetName/name 순 — delete/update 무변경)."""
    target_id = str(d.get("targetId") or "")
    name = after.get("oldName") or d.get("targetName") or after.get("name")
    if target_id:
        for j, c in enumerate(arr):
            if isinstance(c, dict) and str(c.get("nodeId") or c.get("id") or "") == target_id:
                return j
    if name:
        target_name = _norm_name(name)
        for j, c in enumerate(arr):
            if isinstance(c, dict) and _norm_name(c.get("name")) == target_name:
                return j
    return None


# ---------------------------------------------------------------------------
# 043-fix — Design 캔버스 미리보기 Inspector 편집 → Proposal.tacticalDiff 반영.
#
# Command/Event/ReadModel/Aggregate 를 Design 캔버스 미리보기에서 인스펙터로 수정하면,
# InspectorPanel 이 만든 draft(chat/confirm 포맷)를 라이브가 아니라 제안 diff 에 반영한다.
# 캔버스 노드 id 는 라이브 노드면 실제 Neo4j id, CREATE 신규 노드면 build_design_preview 가
# 부여한 temp id `PREVIEW:<pid>:<idx>`(idx = tacticalDiff 인덱스)다. 두 경우 모두 대상
# tacticalDiff 항목으로 해소한다.
# ---------------------------------------------------------------------------

# 인스펙터 스키마 상의 기본 필드 키(이름은 nodeTitle 로 별도 처리). update draft 의
# updates 에 담겨 오며, build_design_preview 가 _populate_from_deep_item 으로 노드에 반영한다.
_DESIGN_FIELD_KEYS = (
    "displayName", "description", "category", "actor", "version",
    "rootEntity", "provisioningType", "isMultipleResult", "gwtSets",
)


def _resolve_tactical_index(proposal_id: str, tactical: list[dict], node_id: str) -> Optional[int]:
    """캔버스 노드 id → tacticalDiff 항목 인덱스. temp id(PREVIEW:<pid>:<idx>)는 인덱스를
    그대로 들고 있고, 라이브 노드는 nodeId 매칭으로 찾는다. 해소 불가 시 None."""
    s = str(node_id or "")
    if not s:
        return None
    prefix = f"PREVIEW:{proposal_id}:"
    if s.startswith(prefix):
        try:
            idx = int(s[len(prefix):])
        except ValueError:
            idx = None
        if idx is not None and 0 <= idx < len(tactical):
            return idx
    for i, it in enumerate(tactical):
        if str(it.get("nodeId") or "") == s:
            return i
    return None


def _ensure_modify_item(tactical: list[dict], node_id: str, label: str, name: str,
                        bc_id: Optional[str]) -> int:
    """라이브 노드를 처음 수정할 때 tacticalDiff 에 MODIFY 항목을 새로 만들고 인덱스를 반환."""
    tactical.append({
        "nodeId": node_id, "nodeLabel": label, "nodeTitle": name or node_id,
        "changeType": "MODIFY", "impactLevel": "MEDIUM",
        "reason": "미리보기에서 직접 수정", "boundedContextId": bc_id,
    })
    return len(tactical) - 1


def _apply_property_draft(item: dict, d: dict, updates: dict) -> bool:
    """Property create/update/delete/rename draft 를 부모 항목의 properties 컬렉션에 적용."""
    arr = list(item.get("properties") or [])
    action = d.get("action")
    if action == "create":
        child = {k: v for k, v in updates.items() if k not in ("parentType", "parentId")}
        child.setdefault("name", d.get("targetName") or str(d.get("targetId") or ""))
        arr.append(_strip_meta([child])[0])
        item["properties"] = arr
        return True
    j = _match_child_index(arr, d, updates)
    if j is None:
        return False
    if action == "delete":
        arr.pop(j)
    elif action == "rename":
        child = dict(arr[j])
        child["name"] = d.get("targetName") or updates.get("name") or child.get("name")
        arr[j] = child
    else:  # update — 변경 필드 병합(라우팅 메타 제외)
        child = dict(arr[j])
        for k, v in updates.items():
            if k not in ("parentType", "parentId", "oldName"):
                child[k] = v
        arr[j] = _strip_meta([child])[0]
    item["properties"] = arr
    return True


def reconcile_design_edit(proposal_id: str, bc_id: Optional[str], drafts: list[dict],
                          approved_ids: list[str], gwt: Optional[dict] = None) -> dict:
    """Design 캔버스 인스펙터 편집(draft[])을 tacticalDiff 에 반영하고 갱신된 Design 미리보기
    그래프를 반환한다(즉시 재렌더). 라이브 디자인 그래프 무변경(Constitution I)."""
    proposal = _load_proposal(proposal_id)
    if proposal is None:
        raise ValueError(f"Proposal {proposal_id} not found")

    approved = set(approved_ids or [])
    tactical = _read_tactical(proposal_id)
    applied = 0

    for d in drafts or []:
        if approved and d.get("changeId") not in approved:
            continue
        ttype = (d.get("targetType") or "")
        updates = dict(d.get("updates") or {})
        target_id = str(d.get("targetId") or "")

        if ttype == "Property":
            parent_id = str(updates.get("parentId") or "")
            pidx = _resolve_tactical_index(proposal_id, tactical, parent_id)
            if pidx is None:
                # 라이브 부모를 처음 수정 → 부모 MODIFY 항목 생성 후 자식 반영.
                if parent_id:
                    pidx = _ensure_modify_item(
                        tactical, parent_id, updates.get("parentType") or "Aggregate",
                        updates.get("parentType") or parent_id, bc_id)
                else:
                    continue
            item = dict(tactical[pidx])
            if _apply_property_draft(item, d, updates):
                tactical[pidx] = item
                applied += 1
            continue

        # 노드 레벨 rename / update (Command/Event/ReadModel/Aggregate).
        idx = _resolve_tactical_index(proposal_id, tactical, target_id)
        if idx is None:
            # 라이브 노드를 처음 수정 → MODIFY 항목 생성.
            idx = _ensure_modify_item(
                tactical, target_id, ttype or "Aggregate",
                d.get("targetName") or target_id, bc_id)
        item = dict(tactical[idx])
        if d.get("action") == "rename":
            new_name = d.get("targetName")
            if new_name:
                item["nodeTitle"] = new_name
                fields = dict(item.get("fields") or {})
                fields["name"] = new_name
                item["fields"] = fields
                applied += 1
        else:  # update
            fields = dict(item.get("fields") or {})
            for k, v in updates.items():
                if k in _DESIGN_FIELD_KEYS:
                    fields[k] = v
            item["fields"] = fields
            applied += 1
        if bc_id and not item.get("boundedContextId"):
            item["boundedContextId"] = bc_id
        tactical[idx] = item

    # GWT 번들(Command) — 노드 fields.gwtSets 로 저장(build_design_preview 가 그대로 환원).
    if gwt and gwt.get("targetId"):
        gidx = _resolve_tactical_index(proposal_id, tactical, str(gwt.get("targetId")))
        if gidx is not None:
            item = dict(tactical[gidx])
            fields = dict(item.get("fields") or {})
            fields["gwtSets"] = gwt.get("gwtSets") or []
            item["fields"] = fields
            tactical[gidx] = item
            applied += 1

    _write_tactical(proposal_id, tactical)
    graph = build_design_preview(proposal_id, bc_id) if bc_id else {"_preview": {"saved": True}}
    if isinstance(graph, dict):
        graph.setdefault("_preview", {})
        if isinstance(graph["_preview"], dict):
            graph["_preview"]["appliedCount"] = applied
    return graph


def _draft_after_to_edit(existing_item: dict, after: dict) -> dict:
    """draft.after(부분 상태)를 reconcile 가 기대하는 edited 형태로 변환.

    after 가 properties/enumerations/valueObjects/invariants/name + 노드 레벨 스칼라 필드를
    부분적으로 담는다고 가정하고, 없는 필드는 기존 항목 값을 유지한다(부분 병합).

    043-fix4: 종전엔 name/displayName/rootEntity 만 통과시켜 version/category/actor/
    description/provisioningType/isMultipleResult 변경이 통째로 떨어졌다(Chat 경로 무반영).
    name + _NODE_SCALAR_FIELDS 전부를 통과시킨다(falsy 보존 위해 `is not None`)."""
    edit: dict[str, Any] = {}
    if after.get("name") is not None:
        edit["name"] = after["name"]
    for k in _NODE_SCALAR_FIELDS:
        if after.get(k) is not None:
            edit[k] = after[k]
    for fld in ("properties", "enumerations", "valueObjects", "invariants"):
        if fld in after and after[fld] is not None:
            edit[fld] = after[fld]
        elif existing_item.get(fld) is not None:
            edit[fld] = existing_item.get(fld)
    return edit
