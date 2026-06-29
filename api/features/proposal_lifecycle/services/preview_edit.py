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
from api.platform.observability.smart_logger import SmartLogger
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
            "MATCH (p:Proposal {id: $id}) RETURN p.tacticalDiff AS td, p.planDraft AS draft",
            id=proposal_id,
        ).single()
    if not rec:
        return []
    raw = rec.get("td")
    if not raw and rec.get("draft"):
        try:
            draft = json.loads(rec["draft"]) or {}
            tactical = draft.get("tacticalDiff")
            if isinstance(tactical, list):
                return tactical
        except Exception:
            pass
    if not raw:
        return []
    try:
        return json.loads(raw) or []
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
    # C-1(데이터 손실 방지): ops 를 비우기 전에 obj_append(원본 enum/VO 자식)를 item-level
    #   배열로 흡수해 보존한다. 종전엔 semanticDiff.ops 를 통째로 비워, 원본 인텐트가 ops 에
    #   싣던 자식(OrderStatus/OrderLine/ShippingAddress 등)이 Aggregate 의 사소한 필드 하나만
    #   수정해도 영속 tacticalDiff 에서 영구 삭제됐다(데이터 손실). 흡수 후 비우면 "중복 렌더
    #   방지" 목적은 유지하면서 원본 자식을 지킨다.
    orig_ops = list(((item.get("semanticDiff") or {}).get("ops")) or [])
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
    # deep 정규화: 모든 자식을 item-level 로. semanticDiff.ops 는 (흡수 후) 비워 중복 렌더 방지.
    for fld in ("properties", "invariants", "enumerations", "valueObjects"):
        if fld in edited:
            item[fld] = _strip_meta(edited.get(fld) or [])
    # C-1: 원본 ops 자식을 item-level 배열에 합친다(중복 name 제외 → 이중 렌더 방지).
    for fld in ("enumerations", "valueObjects"):
        merged = list(item.get(fld) or [])
        names = {_norm_name(x.get("name")) for x in merged if isinstance(x, dict)}
        for op in orig_ops:
            if op.get("op") != "obj_append" or op.get("field") != fld:
                continue
            obj = op.get("obj_data") if isinstance(op.get("obj_data"), dict) else (
                {"name": op.get("obj_name")} if op.get("obj_name") else None)
            if not obj or _norm_name(obj.get("name")) in names:
                continue
            merged.append(_strip_meta([dict(obj)])[0])
            names.add(_norm_name(obj.get("name")))
        if merged:
            item[fld] = merged
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

    # A-1: 같은 confirm 배치에서 막 만든 VO/Enum 노드를 그 필드/항목 draft 가 찾을 수 있도록,
    #   temp child id → (kind, 부모 Aggregate 항목 index, 이름) 매핑을 적재한다.
    new_child_locator: dict[str, tuple] = {}
    # E-1: 실제 반영 못 한 draft 를 무음으로 흘리지 않고 사유와 함께 모은다.
    unresolved: list[dict] = []

    def agg_parent_idx(d: dict, after: dict, target_id: str, kind: str) -> Optional[int]:
        """자식 draft 의 소유 Aggregate 항목 index 해소: parentId → 캔버스 id 역추적(원인 D) 순."""
        pid = _child_parent_id(d, after)
        ai = resolve_idx(pid) if pid else None
        if ai is None:
            apid = _parent_agg_from_canvas_id(tactical, target_id, kind)
            ai = resolve_idx(apid) if apid else None
        return ai

    # A-1: 2패스 — 부모 노드 생성(VO/Enum/Aggregate/top-level)을 먼저 처리해 그 자식(필드/항목)
    #   draft 가 같은 배치에서 부모를 해소할 수 있게 한다. 원래 상대순서는 보존(stable).
    sel = [d for d in (drafts or []) if not approved or d.get("changeId") in approved]

    def _rank(d: dict) -> int:
        act = d.get("action")
        tt = (d.get("targetType") or "").lower()
        if act == "create" and (tt in ("valueobject", "enumeration", "enum", "aggregate") or tt in _TOPLEVEL_LABEL):
            return 0
        return 1

    ordered = [d for _, d in sorted(enumerate(sel), key=lambda t: (_rank(t[1]), t[0]))]

    for d in ordered:
        target_id = str(d.get("targetId") or "")
        after = d.get("after") or d.get("updates") or {}
        ttype = (d.get("targetType") or "").lower()
        action = d.get("action")
        parent_ref = str(d.get("aggregateId") or d.get("parentId") or after.get("parentId") or "")
        if not target_id and not parent_ref and action != "create":
            unresolved.append(_unresolved(d, "targetId/parent 모두 없음"))
            continue
        # rename → nodeTitle / name
        if action == "rename" and after.get("name"):
            after = {**after, "name": after["name"]}

        # 043-fix2 — VO 필드 편집: parent 가 ValueObject 인 Property. 부모 Aggregate 항목의
        # 해당 VO obj_data.fields 를 직접 수정한다(별도 top-level 항목 생성 금지).
        parent_type = str(after.get("parentType") or d.get("parentType") or "").lower()
        if ttype == "property" and parent_type == "valueobject":
            vo_id = str(after.get("parentId") or d.get("parentId") or "")
            agg_id, vo_idx = _parse_child_canvas_id(vo_id, "vo")
            ai = resolve_idx(agg_id) if agg_id else None
            vo_obj = _resolve_child_obj(tactical[ai], "valueObjects", vo_idx, None) if ai is not None else None
            # A-1: 같은 배치에서 막 만든 VO(temp id)면 locator 로 부모 agg + 이름 해소.
            if vo_obj is None and vo_id in new_child_locator:
                kind, nai, cname = new_child_locator[vo_id]
                if kind == "vo":
                    ai = nai
                    vo_obj = _resolve_child_obj(tactical[ai], "valueObjects", None, cname)
            # D-1: 슬러그 vo id → 부모 agg 역추적 + tail(이름)로 VO 해소.
            if vo_obj is None:
                apid = _parent_agg_from_canvas_id(tactical, vo_id, "vo")
                ai = resolve_idx(apid) if apid else ai
                if ai is not None:
                    vo_obj = _resolve_child_obj(tactical[ai], "valueObjects", None, _slug_tail(vo_id, apid))
            if vo_obj is not None and _apply_vo_field_edit(vo_obj, d, after):
                touched_bc = touched_bc or tactical[ai].get("boundedContextId")
                applied += 1
            else:
                unresolved.append(_unresolved(d, "VO 필드의 부모 ValueObject 미해소"))
            continue

        # 043-fix2 — Enum 항목 편집: targetType=Enumeration + itemsToAdd/Remove/Rename.
        if ttype in ("enumeration", "enum") and any(
            k in after for k in ("itemsToAdd", "itemsToRemove", "itemsRename")
        ):
            agg_id, enum_idx = _parse_child_canvas_id(target_id, "enum")
            ai = resolve_idx(agg_id) if agg_id else None
            enum_obj = _resolve_child_obj(tactical[ai], "enumerations", enum_idx, d.get("targetName")) if ai is not None else None
            # D-1: 슬러그 enum id(예: enum-AGG-order-OrderStatus) → 부모 agg 역추적 + 이름 해소.
            if enum_obj is None:
                ai = agg_parent_idx(d, after, target_id, "enum")
                if ai is not None:
                    name_hint = d.get("targetName") or _slug_tail(target_id, tactical[ai].get("nodeId"))
                    enum_obj = _resolve_child_obj(tactical[ai], "enumerations", None, name_hint)
            if enum_obj is not None and _apply_enum_items_edit(enum_obj, after):
                touched_bc = touched_bc or tactical[ai].get("boundedContextId")
                applied += 1
            else:
                unresolved.append(_unresolved(d, "대상 Enum 미해소"))
            continue

        # 043-fix5(RC-2) — top-level 노드(Command/Event/ReadModel/Aggregate/Policy) 삭제.
        #   제안 전용(CREATE) 항목이면 tacticalDiff 에서 완전 제거, 라이브 항목이면
        #   changeType=DELETE tombstone(build_design_preview 가 drop). 종전엔 삭제 분기가 없어
        #   노드 레벨 merge 로 흡수돼 no-op + 과대보고였다. 자식 컬렉션 타입은 아래 전용 분기 사용.
        if action == "delete" and ttype in _NODE_LEVEL_LABEL and ttype not in _CHILD_COLLECTION:
            i = resolve_idx(target_id)
            if i is not None and tactical[i] is not None:
                it = tactical[i]
                touched_bc = touched_bc or it.get("boundedContextId") or bc_id
                if (it.get("changeType") or "") == "CREATE":
                    tactical[i] = None  # 제안 전용 신규 → 완전 제거(말미 None 정리)
                else:
                    it["changeType"] = "DELETE"  # 라이브 → tombstone
            else:
                tactical.append({
                    "nodeId": target_id, "nodeLabel": _NODE_LEVEL_LABEL[ttype],
                    "nodeTitle": d.get("targetName") or target_id, "changeType": "DELETE",
                    "impactLevel": "MEDIUM", "reason": "Chat 삭제 요청 반영", "boundedContextId": bc_id,
                })
                touched_bc = touched_bc or bc_id
            applied += 1
            continue

        # connect — 반응 정책 레일(Event ─TRIGGERS→ Policy ─INVOKES→ Command)을 Policy 항목의
        #   참조키로 반영한다. LLM 이 Policy 생성과 별개로 connect draft 를 함께 내는 경우가 있어
        #   (create 가 이미 invokeCommandId 를 실으면 중복이지만) 여기서 멱등 반영해 "미반영"
        #   오인을 막는다. INVOKES: source=Policy→invokeCommandId=target. TRIGGERS: source=Event,
        #   target=Policy→triggerEventId=source.
        if action == "connect":
            ctype = str(d.get("connectionType") or "").upper()
            src = str(d.get("sourceId") or "")
            if ctype == "INVOKES":
                pi = resolve_idx(src)
                if pi is not None and tactical[pi] and tactical[pi].get("nodeLabel") == "Policy":
                    tactical[pi]["invokeCommandId"] = target_id
                    touched_bc = touched_bc or tactical[pi].get("boundedContextId")
                    applied += 1
                    continue
            elif ctype == "TRIGGERS":
                pi = resolve_idx(target_id)
                if pi is not None and tactical[pi] and tactical[pi].get("nodeLabel") == "Policy":
                    tactical[pi]["triggerEventId"] = src
                    touched_bc = touched_bc or tactical[pi].get("boundedContextId")
                    applied += 1
                    continue
            unresolved.append(_unresolved(d, f"connect 미해소(type={ctype or '?'})"))
            continue

        # 노드 레벨 편집(Aggregate/Command/Event/ReadModel update·rename) — 자식 컬렉션 타입 제외.
        # 043-fix5(RC-1): action 가드 추가 — create/delete/connect 가 이 MODIFY 분기에 가로채여
        #   top-level 생성이 changeType=MODIFY 로 오저장되던 결함을 막는다. update/rename 만 처리.
        i = resolve_idx(target_id)
        if i is not None and ttype not in _CHILD_COLLECTION and action in ("update", "rename"):
            tactical[i] = _normalize_item_from_edit(tactical[i], _draft_after_to_edit(tactical[i], after), bc_id)
            if (tactical[i].get("nodeLabel") or ttype) == "Policy":
                _apply_policy_extras(tactical[i], after)
            touched_bc = touched_bc or tactical[i].get("boundedContextId")
            applied += 1
            continue
        if target_id and ttype in _NODE_LEVEL_LABEL and i is None and action in ("update", "rename"):
            item = _normalize_item_from_edit(
                {"nodeId": target_id, "nodeLabel": _NODE_LEVEL_LABEL[ttype],
                 "nodeTitle": after.get("name") or target_id,
                 "changeType": "MODIFY", "impactLevel": "MEDIUM", "reason": "Chat 수정 요청 반영"},
                _draft_after_to_edit({}, after), bc_id,
            )
            if _NODE_LEVEL_LABEL[ttype] == "Policy":
                _apply_policy_extras(item, after)
            tactical.append(item)
            by_id[target_id] = len(tactical) - 1
            touched_bc = touched_bc or item.get("boundedContextId")
            applied += 1
            continue

        # 자식요소 신규 생성(VO/Enum 노드, Aggregate property) — 부모 Aggregate 항목에 병합.
        if action == "create" and ttype in _CHILD_COLLECTION:
            coll = _CHILD_COLLECTION[ttype]
            kind = "vo" if ttype == "valueobject" else ("enum" if ttype in ("enum", "enumeration") else "prop")
            ai = resolve_idx(parent_ref) if parent_ref else None
            if ai is None and parent_ref:
                tactical.append({
                    "nodeId": parent_ref,
                    "nodeLabel": after.get("parentType") or d.get("parentType") or "Aggregate",
                    "nodeTitle": d.get("parentName") or parent_ref,
                    "changeType": "MODIFY", "impactLevel": "MEDIUM",
                    "reason": "Chat 자식요소 추가", "boundedContextId": bc_id,
                })
                ai = by_id[parent_ref] = len(tactical) - 1
            if ai is None:  # D-1: 캔버스 id 로 부모 agg 역추적.
                apid = _parent_agg_from_canvas_id(tactical, target_id, kind)
                ai = resolve_idx(apid) if apid else None
            if ai is not None:
                item = dict(tactical[ai])
                arr = list(item.get(coll) or [])
                child = {k: v for k, v in after.items() if k not in ("parentType", "parentId")}
                cname = d.get("targetName") or after.get("name") or target_id
                child.setdefault("name", cname)
                child.setdefault("nodeId", target_id)
                arr.append(_strip_meta([child])[0])
                item[coll] = arr
                tactical[ai] = item
                touched_bc = touched_bc or item.get("boundedContextId")
                applied += 1
                # A-1: VO/Enum 노드를 만들었으면 이후 필드/항목 draft 가 찾도록 locator 적재.
                if ttype in ("valueobject", "enumeration", "enum") and target_id:
                    new_child_locator[target_id] = (kind, ai, cname)
            else:
                unresolved.append(_unresolved(d, "신규 자식의 부모 Aggregate 미해소"))
            continue

        # 자식요소 삭제/수정/이름변경(Property/VO/Enum) — 원본(ops) 자식 포함(B-1).
        if action in ("delete", "update", "rename") and ttype in _CHILD_COLLECTION:
            coll = _CHILD_COLLECTION[ttype]
            kind = "vo" if ttype == "valueobject" else ("enum" if ttype in ("enum", "enumeration") else "prop")
            ai = agg_parent_idx(d, after, target_id, kind)
            if ai is not None:
                item = dict(tactical[ai])
                # B-1: 원본 인텐트가 ops(obj_append)에 실은 자식을 item-level 배열로 이관해
                #   삭제/이름변경/수정 매칭 대상이 되게 한다(종전엔 배열만 뒤져 ops 자식 미매칭).
                _absorb_ops_children(item, coll)
                arr = list(item.get(coll) or [])
                j = _match_child_index(arr, d, after, parent_id=item.get("nodeId"))
                if j is not None:
                    if action == "delete":
                        arr.pop(j)
                    elif action == "rename":
                        child = dict(arr[j])
                        child["name"] = d.get("targetName") or after.get("name") or child.get("name")
                        arr[j] = child
                    else:  # update — 변경 필드 병합(라우팅 메타 제외)
                        child = dict(arr[j])
                        for k, v in after.items():
                            if k not in ("parentType", "parentId", "oldName"):
                                child[k] = v
                        arr[j] = _strip_meta([child])[0]
                    item[coll] = arr
                    tactical[ai] = item
                    touched_bc = touched_bc or item.get("boundedContextId")
                    applied += 1
                else:
                    tactical[ai] = item  # ops 흡수 결과(원본 자식 보존)는 기록.
                    unresolved.append(_unresolved(d, "대상 자식요소 미해소"))
            else:
                unresolved.append(_unresolved(d, "자식요소의 부모 Aggregate 미해소"))
            continue

        # top-level 신규 요소(Command/Event/ReadModel/Aggregate/Policy) — 새 tactical 항목.
        # 043-fix5(RC-1): build_design_preview 가 렌더하려면 changeType=CREATE + 한글 제목 +
        #   렌더 필수 참조키(Command:aggregateId, Event:commandId, ReadModel/Aggregate/Policy:
        #   boundedContextId)가 필요하다. draft 에서 취하고, 없으면 bcId+기존 tacticalDiff 로
        #   서버측 보강한다(LLM 이 참조키를 자주 누락하므로). fields 에는 참조키/메타를 제외한
        #   설계 필드만 싣는다.
        if action == "create" and ttype in _TOPLEVEL_LABEL and resolve_idx(target_id) is None:
            label = _TOPLEVEL_LABEL[ttype]
            item = {
                "nodeId": target_id, "nodeLabel": label,
                "nodeTitle": d.get("targetName") or after.get("name") or target_id,
                "changeType": "CREATE", "impactLevel": "MEDIUM",
                "reason": "Chat 수정 요청 반영",
            }
            item.update(_derive_create_refs(tactical, label, d, after, bc_id))
            # invokeCommandId/triggerEventId 는 _derive_create_refs 가 top-level 로 올렸으므로
            # fields 에서 제외한다(중복·오해소 방지). condition 등 도메인 필드는 fields 로 보존.
            fld = {k: v for k, v in (after or {}).items()
                   if k not in _META_KEYS
                   and k not in ("aggregateId", "commandId", "parentId", "parentType", "name",
                                 "invokeCommandId", "triggerEventId")}
            if fld:
                item["fields"] = fld
            tactical.append(item)
            by_id[target_id] = len(tactical) - 1
            touched_bc = touched_bc or item.get("boundedContextId") or bc_id
            applied += 1
            continue

        unresolved.append(_unresolved(d, f"지원하지 않는 편집 유형(action={action}, type={ttype})"))

    # 043-fix5: DELETE 로 제거 표시된(None) 항목을 실제로 떨어낸다.
    tactical = [it for it in tactical if it is not None]
    _write_tactical(proposal_id, tactical)

    # E-2: 미해소(미반영) draft 를 경고 로그로 남긴다 — 무음 과대 카운트 방지.
    if unresolved:
        SmartLogger.log(
            "WARNING",
            "preview chat drafts: 일부 변경을 반영하지 못함(미해소).",
            category="proposal_lifecycle.preview.edit.chat.unresolved",
            params={"proposalId": proposal_id, "appliedCount": applied,
                    "unresolvedCount": len(unresolved), "unresolved": unresolved},
        )

    tree = build_data_preview(proposal_id, touched_bc) if touched_bc else {"_preview": {"saved": True}}
    # E-1: 반영/미반영 건수를 메타로 실어 프런트가 정직한 메시지를 띄우게 한다.
    if isinstance(tree, dict):
        tree.setdefault("_preview", {})
        if isinstance(tree["_preview"], dict):
            tree["_preview"]["appliedCount"] = applied
            tree["_preview"]["unresolvedCount"] = len(unresolved)
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
    # 043-fix5: Aggregate 도 top-level CREATE 라우팅 대상(종전 누락 → CREATE 가 MODIFY 로 오저장).
    "aggregate": "Aggregate",
}
# 노드 레벨 라벨(라이브 노드 첫 수정 시 MODIFY 신규 생성용). Aggregate 포함.
_NODE_LEVEL_LABEL = {**_TOPLEVEL_LABEL, "aggregate": "Aggregate"}


def _derive_create_refs(tactical: list[dict], label: str, d: dict, after: dict,
                        bc_id: Optional[str]) -> dict:
    """top-level CREATE 노드가 build_design_preview 에 렌더되도록 필수 참조키를 보강한다.

    Command→aggregateId, Event→commandId, 그 외(ReadModel/Aggregate/Policy)→boundedContextId.
    draft(after/d)에 있으면 그대로, 없으면 bc_id + 기존 tacticalDiff 로 서버측 추론한다
    (LLM 이 참조키를 자주 누락하므로). 추론 실패 시 해당 키는 비운다(렌더 누락은 unresolved 가
    아니라 best-effort — 적어도 changeType=CREATE 로는 저장됨)."""
    refs: dict[str, Any] = {}
    # 이 BC 에 속한 Aggregate id 집합(자식 Command/Event 의 BC 소속 판정용).
    agg_in_bc = {str(it.get("nodeId")) for it in tactical
                 if it and it.get("nodeLabel") == "Aggregate"
                 and str(it.get("boundedContextId") or "") == str(bc_id or "")}
    if label == "Command":
        agg = d.get("aggregateId") or after.get("aggregateId") or after.get("parentId")
        if not agg:
            agg = next(iter(agg_in_bc), None)  # BC 의 (대표) Aggregate
        if agg:
            refs["aggregateId"] = str(agg)
    elif label == "Event":
        cmd = d.get("commandId") or after.get("commandId")
        if not cmd:
            agg = d.get("aggregateId") or after.get("aggregateId") or after.get("parentId")
            # 같은 BC 의 Command 만 후보로(다른 BC 의 첫 Command 로 잘못 연결되는 것 방지).
            cands = [str(it.get("nodeId")) for it in tactical
                     if it and it.get("nodeLabel") == "Command"
                     and str(it.get("aggregateId") or "") in agg_in_bc
                     and (not agg or str(it.get("aggregateId") or "") == str(agg))]
            # 같은 배치에서 막 만든 형제 Command(가장 최근 추가)를 우선 — 멀티-생성
            # ("Command + 그 결과 Event")에서 Event 를 의도한 새 Command 에 연결한다.
            cmd = cands[-1] if cands else None
        if cmd:
            refs["commandId"] = str(cmd)
    else:  # ReadModel / Aggregate / Policy → BC 직속
        refs["boundedContextId"] = bc_id or str(d.get("aggregateId") or "") or None
        if label == "Policy":
            # 반응 정책 레일 참조키(Event ─TRIGGERS→ Policy ─INVOKES→ Command). draft(updates/
            # after 또는 d)에서 취해 **top-level** 로 올린다 — build_design_preview 가 이 키들로
            # INVOKES/TRIGGERS 엣지를 긋고 Policy 를 호출 Command 왼쪽에 배치한다. fields 에만
            # 있으면(아래 fld) 엣지/배치가 누락된다.
            inv = d.get("invokeCommandId") or after.get("invokeCommandId")
            trg = d.get("triggerEventId") or after.get("triggerEventId")
            if inv:
                refs["invokeCommandId"] = str(inv)
            if trg:
                refs["triggerEventId"] = str(trg)
    return refs


def _apply_policy_extras(item: dict, after: dict) -> bool:
    """Policy 전용 필드를 항목에 반영(Chat update 경로). `condition` 은 fields(도메인 속성)로,
    `invokeCommandId`/`triggerEventId` 는 top-level 참조키로 둔다 — build_design_preview 가
    후자로 INVOKES/TRIGGERS 엣지와 좌측 배치를 결정하므로 fields 가 아니라 top-level 이어야 한다.
    (_draft_after_to_edit 는 이 키들을 통과시키지 않아 별도 처리한다.)"""
    changed = False
    if after.get("condition") is not None:
        f = dict(item.get("fields") or {})
        f["condition"] = after["condition"]
        item["fields"] = f
        changed = True
    for k in ("invokeCommandId", "triggerEventId"):
        if after.get(k):
            item[k] = str(after[k])
            changed = True
    return changed


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


def _match_child_index(arr: list, d: dict, after: dict, parent_id: Optional[str] = None) -> Optional[int]:
    """부모 컬렉션에서 대상 자식의 인덱스를 찾는다.

    미리보기 오버레이 자식은 Neo4j id 가 없을 수 있어(prop-noid-*) targetId 매칭이 불가하므로
    nodeId/id → name 순으로 찾는다(인텐트 포맷 속성은 name 만 보유).

    rename 은 targetName 이 '새 이름'이라 저장된 '옛 이름' 자식과 일치하지 않는다. 프런트가
    updates.oldName 에 '옛 이름'을 실어 보내므로(delete/update 와 달리 rename 전용), 매칭 시
    oldName 을 최우선으로 사용한다.

    D-1: LLM 이 비표준 슬러그 id(예: vo-AGG-order-ShippingAddress, enum-AGG-order-OrderStatus)를
    만들면 nodeId 매칭이 실패한다. parent_id(소유 Aggregate id)가 주어지면 슬러그 꼬리(tail)를
    떼어 이름 후보에 추가해 매칭한다(_norm_name 은 하이픈/대소문자를 무시하므로 'shipping-address'
    ↔ 'ShippingAddress' 가 일치)."""
    target_id = str(d.get("targetId") or "")
    name_cands: list[str] = []
    for cand in (after.get("oldName"), d.get("targetName"), after.get("name")):
        if cand:
            name_cands.append(_norm_name(cand))
    tail = _slug_tail(target_id, parent_id)
    if tail:
        name_cands.append(_norm_name(tail))
    if target_id:
        for j, c in enumerate(arr):
            if isinstance(c, dict) and str(c.get("nodeId") or c.get("id") or "") == target_id:
                return j
    if name_cands:
        for j, c in enumerate(arr):
            if isinstance(c, dict) and _norm_name(c.get("name")) in name_cands:
                return j
    return None


def _slug_tail(node_id: Any, parent_id: Optional[str]) -> Optional[str]:
    """`<kind>-<aggId>-<tail>` 슬러그 자식 id 에서 tail(원본 이름 힌트)을 떼어낸다(원인 D).
    parent_id(소유 Aggregate id)가 있어야 aggId 에 하이픈이 있어도 정확히 분리된다."""
    s = str(node_id or "")
    if parent_id:
        for kind in ("vo", "enum", "prop"):
            pfx = f"{kind}-{parent_id}-"
            if s.startswith(pfx):
                return s[len(pfx):]
    return None


def _parent_agg_from_canvas_id(tactical: list[dict], node_id: Any, kind: str) -> Optional[str]:
    """자식 캔버스 id(`<kind>-<aggId>-...`, 인덱스/슬러그 모두)에서 소유 Aggregate id 를
    역추적한다(원인 D). tacticalDiff 의 Aggregate nodeId 들과 prefix 매칭해 해소."""
    s = str(node_id or "")
    for it in tactical:
        if (it.get("nodeLabel") or "") != "Aggregate":
            continue
        aid = str(it.get("nodeId") or "")
        if aid and s.startswith(f"{kind}-{aid}-"):
            return aid
    return None


def _absorb_ops_children(item: dict, coll: str) -> None:
    """B-1: 해당 컬렉션의 obj_append ops(원본 인텐트 자식)를 item-level 배열로 이관하고 그 ops
    를 제거한다. 이로써 원본 자식이 이후 item-level 매칭/삭제/수정/렌더 대상이 된다(이중 저장
    해소). 중복 name 은 추가하지 않는다(이중 렌더 방지)."""
    sd = item.get("semanticDiff") or {}
    ops = list(sd.get("ops") or [])
    if not ops:
        return
    arr = list(item.get(coll) or [])
    names = {_norm_name(x.get("name")) for x in arr if isinstance(x, dict)}
    kept: list[dict] = []
    moved = False
    for op in ops:
        if op.get("op") == "obj_append" and op.get("field") == coll:
            obj = op.get("obj_data") if isinstance(op.get("obj_data"), dict) else (
                {"name": op.get("obj_name")} if op.get("obj_name") else None)
            if obj:
                if _norm_name(obj.get("name")) not in names:
                    arr.append(_strip_meta([dict(obj)])[0])
                    names.add(_norm_name(obj.get("name")))
                moved = True
                continue
        kept.append(op)
    if moved:
        item[coll] = arr
        item["semanticDiff"] = {**sd, "ops": kept}


def _unresolved(d: dict, reason: str) -> dict:
    """E-1: 미반영 draft 의 진단 레코드(프런트 메시지·로그용)."""
    return {"changeId": d.get("changeId"), "action": d.get("action"),
            "targetType": d.get("targetType"), "targetName": d.get("targetName"),
            "targetId": d.get("targetId"), "reason": reason}


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
