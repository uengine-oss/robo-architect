"""040 Proposal Impact Artifact Preview — 오버레이 엔진.

라이브 그래프 슬라이스(딥카피) 위에 Proposal 의 직렬화된 strategicDiff/tacticalDiff 를
얹어, 각 노드에 출처(source)와 배지를 태깅한다. **순수 함수 / 메모리 전용** — Neo4j 에
절대 쓰지 않는다(Constitution I, US2).

source 판정 (data-model §2):
  - live           : 변경 없는 라이브 노드
  - live+modified  : 라이브 + MODIFY 오버레이
  - temporary      : CREATE 신규 노드 (라이브 미존재)
  - conflict       : MODIFY 대상이 라이브에 없음 (엣지)
"""

from __future__ import annotations

import copy
from typing import Any

SOURCE_LIVE = "live"
SOURCE_MODIFIED = "live+modified"
SOURCE_TEMPORARY = "temporary"
SOURCE_CONFLICT = "conflict"

BADGE = {
    SOURCE_LIVE: None,
    SOURCE_MODIFIED: "수정",
    SOURCE_TEMPORARY: "신규",
    SOURCE_CONFLICT: "충돌",
}


def temp_id(proposal_id: str, index: int) -> str:
    """CREATE(id=null) 항목용 결정론적 임시 ID. 반복 미리보기에서 안정적."""
    return f"PREVIEW:{proposal_id}:{index}"


def _tag(node: dict, source: str) -> dict:
    node["source"] = source
    badge = BADGE.get(source)
    if badge:
        node["badge"] = badge
    return node


def _tactical_index(tactical_diff: list[dict] | None) -> dict[str, dict]:
    """tacticalDiff 항목을 nodeId 기준으로 인덱싱(라이브 매칭용). nodeId 없는 CREATE 는 제외."""
    idx: dict[str, dict] = {}
    for item in tactical_diff or []:
        nid = item.get("nodeId")
        if nid:
            idx[str(nid)] = item
    return idx


def _populate_from_deep_item(node: dict, item: dict) -> list[str]:
    """깊은 인텐트 포맷(`fields`/`properties`/`invariants`)을 노드 dict 에 반영.

    robo-proposal-intent 가 semanticDiff.ops 외에 항목 최상위에 직접 싣는 구조를 처리한다
    (data-model 의 SemanticDiff 예시와 실제 스킬 출력 둘 다 지원). 모두 임시(신규) 태그.
    """
    changed: list[str] = []
    fields = item.get("fields") or {}
    for k, v in fields.items():
        node[k] = v
        changed.append(k)
    props = item.get("properties") or []
    if props:
        bucket = node.setdefault("properties", [])
        for p in props:
            entry = dict(p)
            entry["source"] = SOURCE_TEMPORARY
            entry["badge"] = "신규"
            bucket.append(entry)
        changed.append("properties")
    invs = item.get("invariants") or []
    if invs:
        bucket = node.setdefault("invariants", [])
        for iv in invs:
            entry = dict(iv) if isinstance(iv, dict) else {"declaration": str(iv)}
            entry["source"] = SOURCE_TEMPORARY
            entry["badge"] = "신규"
            bucket.append(entry)
        changed.append("invariants")
    # 편집(reconcile)으로 item-level 로 정규화된 enum/VO. 원본 인텐트 항목은 이 키가
    # 없고 semanticDiff.ops(obj_append)로만 들어오므로 중복 렌더되지 않는다.
    for fld in ("enumerations", "valueObjects"):
        objs = item.get(fld) or []
        if objs:
            bucket = node.setdefault(fld, [])
            for o in objs:
                entry = dict(o) if isinstance(o, dict) else {"name": str(o)}
                entry["source"] = SOURCE_TEMPORARY
                entry["badge"] = "신규"
                bucket.append(entry)
            changed.append(fld)
    return changed


def _apply_semantic_ops(agg: dict, semantic: dict) -> list[str]:
    """SemanticDiff ops 를 Aggregate dict(딥카피)에 적용. 변경 필드 키 목록 반환.

    지원 ops (data-model §3 Data):
      - obj_append (field=valueObjects|enumerations|exceptions): 신규 객체 추가(배지 신규)
      - list_append (field=invariants|...): 목록 항목 추가(배지 수정)
    """
    changed: list[str] = []
    for op in (semantic or {}).get("ops", []) or []:
        field = op.get("field")
        kind = op.get("op")
        if not field:
            continue
        if kind == "obj_append":
            obj = dict(op.get("obj_data") or {})
            if not obj and op.get("obj_name"):
                obj = {"name": op["obj_name"]}
            obj["source"] = SOURCE_TEMPORARY
            obj["badge"] = "신규"
            bucket = agg.setdefault(field, [])
            if isinstance(bucket, list):
                bucket.append(obj)
                changed.append(field)
        elif kind == "list_append":
            bucket = agg.setdefault(field, [])
            if isinstance(bucket, list):
                for item in op.get("items", []) or []:
                    # invariants 는 dict(027) 또는 문자열일 수 있다. 문자열이면 표시용 래핑.
                    if isinstance(item, dict):
                        entry = dict(item)
                        entry["source"] = SOURCE_TEMPORARY
                        entry["badge"] = "신규"
                        bucket.append(entry)
                    else:
                        bucket.append({"declaration": str(item), "source": SOURCE_TEMPORARY, "badge": "신규"})
                changed.append(field)
    return changed


def apply_data_overlay(live_tree: dict, proposal_id: str, tactical_diff: list[dict] | None) -> tuple[dict, list[dict]]:
    """라이브 BC full-tree(딥카피) 위에 tacticalDiff 를 오버레이한다.

    Returns (projected_tree, node_meta_list). projected_tree 는 full-tree 와 동일 형태
    + 노드별 `source`/`badge`. node_meta_list 는 PreviewNodeMeta dict 목록.
    """
    tree = copy.deepcopy(live_tree)
    meta: list[dict] = []
    tactical = tactical_diff or []
    by_id = _tactical_index(tactical)

    aggregates = tree.setdefault("aggregates", [])

    # 1) 라이브 Aggregate 에 MODIFY 오버레이
    live_ids = set()
    for agg in aggregates:
        aid = str(agg.get("id") or "")
        live_ids.add(aid)
        item = by_id.get(aid)
        if item and (item.get("changeType") or "MODIFY") == "MODIFY" and item.get("nodeLabel") == "Aggregate":
            changed = _apply_semantic_ops(agg, item.get("semanticDiff") or {})
            changed += _populate_from_deep_item(agg, item)
            _tag(agg, SOURCE_MODIFIED if changed else SOURCE_LIVE)
            meta.append({"nodeId": aid, "source": agg["source"], "changedFields": changed, "badge": agg.get("badge")})
        else:
            _tag(agg, SOURCE_LIVE)
            meta.append({"nodeId": aid, "source": SOURCE_LIVE, "changedFields": [], "badge": None})

    # 2) MODIFY 대상이 라이브에 없으면 conflict 표기(엣지 케이스)
    for item in tactical:
        if item.get("nodeLabel") != "Aggregate":
            continue
        nid = item.get("nodeId")
        ctype = item.get("changeType") or "MODIFY"
        if ctype == "MODIFY" and nid and str(nid) not in live_ids:
            ghost = {"id": str(nid), "name": item.get("nodeTitle") or str(nid),
                     "valueObjects": [], "enumerations": [], "invariants": [], "properties": [],
                     "commands": [], "events": [], "type": "Aggregate"}
            _tag(ghost, SOURCE_CONFLICT)
            aggregates.append(ghost)
            meta.append({"nodeId": str(nid), "source": SOURCE_CONFLICT, "changedFields": [], "badge": "충돌"})

    # 3) 신규(CREATE) Aggregate/Command/Event 를 트리에 삽입(temp id)
    for i, item in enumerate(tactical):
        if (item.get("changeType") or "") != "CREATE":
            continue
        label = item.get("nodeLabel")
        nid = item.get("nodeId") or temp_id(proposal_id, i)
        title = item.get("nodeTitle") or nid
        if label == "Aggregate":
            new_agg = {"id": nid, "name": title, "displayName": title,
                       "valueObjects": [], "enumerations": [], "invariants": [], "properties": [],
                       "commands": [], "events": [], "type": "Aggregate"}
            _apply_semantic_ops(new_agg, item.get("semanticDiff") or {})
            _populate_from_deep_item(new_agg, item)
            _tag(new_agg, SOURCE_TEMPORARY)
            aggregates.append(new_agg)
            meta.append({"nodeId": nid, "source": SOURCE_TEMPORARY, "changedFields": [], "badge": "신규"})
        elif label in ("Command", "Event"):
            # 신규 Command/Event 는 대상 Aggregate(있으면)에 붙이거나, 없으면 첫 Aggregate.
            target_agg = aggregates[0] if aggregates else None
            child = {"id": nid, "name": title, "displayName": title, "type": label, "events": [], "properties": []}
            _populate_from_deep_item(child, item)
            _tag(child, SOURCE_TEMPORARY)
            if target_agg is not None:
                bucket = "commands" if label == "Command" else "events"
                target_agg.setdefault(bucket, []).append(child)
            meta.append({"nodeId": nid, "source": SOURCE_TEMPORARY, "changedFields": [], "badge": "신규"})

    return tree, meta
