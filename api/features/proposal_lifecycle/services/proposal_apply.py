"""
Proposal Diff 반영 엔진 (038 Change Management의 design_applier 포팅).

dual_merge가 Accept 시 호출한다.
- apply_strategic_diff: Epic/Feature/UserStory/Process(+제네릭 카테고리) 생성·수정
- apply_tactical_diff:  Aggregate/Command/Event/BoundedContext/VO 생성·수정 (SemanticDiff op 적용)
- revoke_accepted_proposal: Accept된 Proposal을 그래프(+선택적으로 코드)에서 되돌린다(수거)

핵심 설계:
- 노드 id는 항상 안정적 고유값(us-uuid, agg-slug-uuid6 …). 제목 기반 MERGE 충돌 금지.
- 각 변경마다 (:Proposal)-[:EFFECT {reason, impactLevel, changeType, diff}]->(node) 생성.
  diff에는 되돌리기에 필요한 역방향 정보(from_val/existed/removed/added)를 함께 저장.
- 스킬이 내보내는 op 어휘(set/scalar_set/replace/obj_append/obj_remove/
  list_append/list_remove/enum_add_items/enum_remove_items)를 모두 정규화해 처리.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger


# ── 유틸 ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_label(label: str | None, default: str = "Node") -> str:
    """Cypher 라벨 인젝션 방지: 영문/숫자만 허용."""
    if not label:
        return default
    cleaned = re.sub(r"[^A-Za-z0-9]", "", str(label))
    return cleaned or default


def _slug(text: str, fallback: str = "node") -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return (s[:32] or fallback)


def _short_uuid() -> str:
    return uuid.uuid4().hex[:6]


_ID_PREFIX = {
    "Aggregate": "agg",
    "Command": "cmd",
    "Event": "evt",
    "BoundedContext": "bc",
    "Policy": "pol",
    "ReadModel": "rm",
    "Feature": "feature",
    "Epic": "epic",
    "UserStory": "us",
}

# obj 배열(JSON 문자열로 저장)로 다루는 필드
_OBJ_ARRAY_FIELDS = {"valueObjects", "enumerations", "properties", "exceptions"}
# Neo4j 네이티브 리스트로 저장하는 필드
_NATIVE_LIST_FIELDS = {"invariants"}


def _gen_node_id(label: str, title: str, proposal_id: str) -> str:
    prefix = _ID_PREFIX.get(label, _safe_label(label).lower()[:4] or "node")
    return f"{prefix}-{_slug(title, proposal_id.lower())}-{_short_uuid()}"


def _to_scalar(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def _as_obj_list(v) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def _norm_op(op: str | None) -> str:
    m = {
        "set": "set", "scalar_set": "set", "replace": "set",
        "obj_append": "obj_append", "obj_remove": "obj_remove",
        "list_append": "list_append", "list_remove": "list_remove",
        "enum_add_items": "enum_add_items", "enum_remove_items": "enum_remove_items",
    }
    return m.get(op or "", op or "")


# ── Neo4j 단순 접근자 ───────────────────────────────────────────────────────

def _get_field(session, label: str, node_id: str, field: str):
    lbl = _safe_label(label)
    fld = _safe_label(field, "x")
    row = session.run(
        f"MATCH (n:{lbl} {{id: $id}}) RETURN n.{fld} AS v", id=node_id
    ).single()
    return row["v"] if row else None


def _set_array(session, label: str, node_id: str, field: str, arr: list) -> None:
    lbl = _safe_label(label)
    fld = _safe_label(field, "x")
    if field in _NATIVE_LIST_FIELDS:
        value = [str(x) for x in arr]
    else:
        value = json.dumps(arr, ensure_ascii=False)
    session.run(
        f"MATCH (n:{lbl} {{id: $id}}) SET n.{fld} = $v", id=node_id, v=value
    )


def _set_scalar(session, label: str, node_id: str, field: str, value) -> None:
    lbl = _safe_label(label)
    fld = _safe_label(field, "x")
    session.run(
        f"MATCH (n:{lbl} {{id: $id}}) SET n.{fld} = $v",
        id=node_id, v=value if not isinstance(value, (list, dict)) else json.dumps(value, ensure_ascii=False),
    )


# ── SemanticDiff op 적용 (역방향 정보 캡처) ────────────────────────────────

def _apply_ops(session, label: str, node_id: str, ops: list) -> list[dict]:
    """ops를 노드에 적용하고, 되돌리기에 필요한 정보를 담은 op 기록을 반환한다."""
    applied: list[dict] = []
    for op in (ops or []):
        if not isinstance(op, dict):
            continue
        field = op.get("field")
        ot = _norm_op(op.get("op"))
        if not field:
            continue
        rec: dict = {"field": field, "op": ot}

        try:
            if ot == "set":
                val = op.get("value")
                if val is None:
                    val = op.get("to_val")
                old = _get_field(session, label, node_id, field)
                _set_scalar(session, label, node_id, field, val)
                rec.update({"value": val, "from_val": _to_scalar(old)})

            elif ot == "obj_append":
                obj_data = op.get("obj_data")
                if obj_data is None and isinstance(op.get("items"), dict):
                    obj_data = op.get("items")
                obj_name = op.get("obj_name") or (obj_data or {}).get("name")
                cur = _as_obj_list(_get_field(session, label, node_id, field))
                existed = any(isinstance(x, dict) and x.get("name") == obj_name for x in cur)
                if obj_data is not None and not existed:
                    cur.append(obj_data)
                    _set_array(session, label, node_id, field, cur)
                rec.update({"obj_name": obj_name, "obj_data": obj_data, "existed": existed})

            elif ot == "obj_remove":
                obj_name = op.get("obj_name")
                cur = _as_obj_list(_get_field(session, label, node_id, field))
                removed = [x for x in cur if isinstance(x, dict) and x.get("name") == obj_name]
                if removed:
                    cur = [x for x in cur if not (isinstance(x, dict) and x.get("name") == obj_name)]
                    _set_array(session, label, node_id, field, cur)
                rec.update({"obj_name": obj_name, "removed": removed})

            elif ot == "list_append":
                items = op.get("items")
                if items is None and op.get("value") is not None:
                    items = [op.get("value")]
                items = items or []
                cur = _get_field(session, label, node_id, field)
                curlist = cur if isinstance(cur, list) else _as_obj_list(cur)
                added = [i for i in items if i not in curlist]
                if added:
                    _set_array(session, label, node_id, field, curlist + added)
                rec.update({"added": added})

            elif ot == "list_remove":
                items = op.get("items") or []
                cur = _get_field(session, label, node_id, field)
                curlist = cur if isinstance(cur, list) else _as_obj_list(cur)
                removed = [i for i in items if i in curlist]
                if removed:
                    _set_array(session, label, node_id, field, [i for i in curlist if i not in removed])
                rec.update({"removed_items": removed})

            elif ot in ("enum_add_items", "enum_remove_items"):
                enum_name = op.get("enum_name")
                items = op.get("items") or []
                enums = _as_obj_list(_get_field(session, label, node_id, "enumerations"))
                enum = next((e for e in enums if isinstance(e, dict) and e.get("name") == enum_name), None)
                changed = []
                if enum is not None:
                    cur_items = list(enum.get("items") or [])
                    if ot == "enum_add_items":
                        changed = [i for i in items if i not in cur_items]
                        cur_items += changed
                    else:
                        changed = [i for i in items if i in cur_items]
                        cur_items = [i for i in cur_items if i not in changed]
                    enum["items"] = cur_items
                    _set_array(session, label, node_id, "enumerations", enums)
                rec.update({"enum_name": enum_name, "changed_items": changed})

            applied.append(rec)
        except Exception as e:  # 한 op 실패가 전체를 막지 않도록
            SmartLogger.log("WARN", f"apply op failed {label}.{field}: {e}",
                            category="proposal_lifecycle.apply.op_warn",
                            params={"nodeId": node_id, "field": field})
    return applied


def _reverse_ops(session, label: str, node_id: str, ops: list) -> None:
    """_apply_ops가 기록한 op들을 역순으로 되돌린다."""
    for op in reversed(ops or []):
        if not isinstance(op, dict):
            continue
        field = op.get("field")
        ot = op.get("op")
        try:
            if ot == "set":
                _set_scalar(session, label, node_id, field, op.get("from_val"))
            elif ot == "obj_append":
                if not op.get("existed"):
                    cur = _as_obj_list(_get_field(session, label, node_id, field))
                    cur = [x for x in cur if not (isinstance(x, dict) and x.get("name") == op.get("obj_name"))]
                    _set_array(session, label, node_id, field, cur)
            elif ot == "obj_remove":
                cur = _as_obj_list(_get_field(session, label, node_id, field))
                for obj in (op.get("removed") or []):
                    if not any(isinstance(x, dict) and x.get("name") == obj.get("name") for x in cur):
                        cur.append(obj)
                _set_array(session, label, node_id, field, cur)
            elif ot == "list_append":
                added = set(op.get("added") or [])
                cur = _get_field(session, label, node_id, field)
                curlist = cur if isinstance(cur, list) else _as_obj_list(cur)
                _set_array(session, label, node_id, field, [i for i in curlist if i not in added])
            elif ot == "list_remove":
                cur = _get_field(session, label, node_id, field)
                curlist = cur if isinstance(cur, list) else _as_obj_list(cur)
                for i in (op.get("removed_items") or []):
                    if i not in curlist:
                        curlist.append(i)
                _set_array(session, label, node_id, field, curlist)
            elif ot in ("enum_add_items", "enum_remove_items"):
                enums = _as_obj_list(_get_field(session, label, node_id, "enumerations"))
                enum = next((e for e in enums if isinstance(e, dict) and e.get("name") == op.get("enum_name")), None)
                if enum is not None:
                    cur_items = list(enum.get("items") or [])
                    changed = op.get("changed_items") or []
                    if ot == "enum_add_items":
                        cur_items = [i for i in cur_items if i not in changed]
                    else:
                        cur_items += [i for i in changed if i not in cur_items]
                    enum["items"] = cur_items
                    _set_array(session, label, node_id, "enumerations", enums)
        except Exception as e:
            SmartLogger.log("WARN", f"reverse op failed {label}.{field}: {e}",
                            category="proposal_lifecycle.revoke.op_warn",
                            params={"nodeId": node_id, "field": field})


# ── EFFECT 관계 기록 ────────────────────────────────────────────────────────

def _record_effect(session, proposal_id: str, label: str, node_id: str,
                   *, reason: str, impact: str, change_type: str,
                   ops: list, node_title: str, created_node_id: str | None = None) -> None:
    lbl = _safe_label(label)
    diff = {
        "v": 1,
        "nodeLabel": label,
        "nodeTitle": node_title,
        "changeType": change_type,
        "createdNodeId": created_node_id,
        "appliedAt": _now_iso(),
        "ops": ops,
    }
    session.run(
        f"""
        MATCH (p:Proposal {{id: $pid}})
        MATCH (n:{lbl} {{id: $nid}})
        MERGE (p)-[e:EFFECT]->(n)
        SET e.reason = $reason, e.impactLevel = $impact,
            e.changeType = $ct, e.diff = $diff, e.appliedAt = datetime()
        """,
        pid=proposal_id, nid=node_id, reason=reason or "",
        impact=impact or "MEDIUM", ct=change_type,
        diff=json.dumps(diff, ensure_ascii=False),
    )


# ── UserStory 필드 추출 ─────────────────────────────────────────────────────

def _extract_rab(entry: dict) -> tuple[str, str, str]:
    """role/action/benefit 추출. 우선순위: 명시 필드 → fields → entityTitle 파싱."""
    def _val(v):
        if isinstance(v, dict):
            return v.get("after") or v.get("value") or ""
        return v or ""

    fields = entry.get("fields") or {}
    role = entry.get("role") or _val(fields.get("role")) or ""
    action = entry.get("action") or _val(fields.get("action")) or ""
    benefit = entry.get("benefit") or _val(fields.get("benefit")) or ""

    title = entry.get("entityTitle") or entry.get("storyTitle") or ""
    if (not role or not action) and title:
        # "역할: 행동" 형태 파싱
        if ":" in title:
            head, _, tail = title.partition(":")
            role = role or head.strip()
            action = action or tail.strip()
        else:
            action = action or title.strip()
    return role.strip(), action.strip(), benefit.strip()


# ── 계층 참조 해소 (tempId/symbolic-id → 실제 노드 id) ──────────────────────
#
# 한 diff 배치 안의 신규 노드들은 모두 entityId=null 이고, 자식이 부모를
# tempId(예: epicId="EP-001")로 가리킨다. 생성 순서대로 ref_map[tempId] = {label,id,bc}
# 를 쌓아 두고, 자식 생성 시 부모의 실제 id를 해소해 관계를 건다.
# ref_map은 strategic→tactical에 걸쳐 공유된다(Aggregate가 Epic(=BC)를 참조 가능).

def _entry_temp_ids(entry: dict) -> list[str]:
    """이 엔트리를 자식이 가리킬 때 쓰는 식별자 후보(여러 별칭 허용)."""
    ids = [entry.get("tempId"), entry.get("clientId"), entry.get("entityId"),
           entry.get("nodeId"), entry.get("storyId"), entry.get("featureId_self")]
    return [str(i) for i in ids if i]


def _register_ref(ref_map: dict, entry: dict, label: str, node_id: str, bc: str | None = None) -> None:
    rec = {"label": label, "id": node_id, "bc": bc}
    for t in _entry_temp_ids(entry):
        ref_map[t] = rec
    # 제목으로도 찾을 수 있게(스킬이 ref를 제목으로 줄 때 대비)
    title = entry.get("entityTitle") or entry.get("nodeTitle")
    if title:
        ref_map.setdefault(f"@title:{title}", rec)


def _resolve_ref(session, ref_map: dict, ref: str | None, expected_label: str) -> str | None:
    """tempId → 실제 id. ref_map 우선, 없으면 그래프(id/key/name)에서 해소."""
    if not ref:
        return None
    rec = ref_map.get(ref)
    if rec:
        return rec["id"]
    rid = _resolve_id_or_key(session, expected_label, ref)
    if rid:
        return rid
    return _resolve_existing_by_name(session, expected_label, ref)


def _bc_for_ref(session, ref_map: dict, ref: str | None) -> str | None:
    """참조가 가리키는 노드의 소속 BC(있으면)."""
    if not ref:
        return None
    rec = ref_map.get(ref)
    if rec and rec.get("bc"):
        return rec["bc"]
    return None


def _bc_of_feature(session, feature_id: str) -> str | None:
    if not feature_id:
        return None
    row = session.run(
        "MATCH (bc:BoundedContext)-[:HAS_FEATURE]->(f:Feature {id: $fid}) RETURN bc.id AS id LIMIT 1",
        fid=feature_id,
    ).single()
    return row["id"] if row else None


# ── Strategic 적용 ──────────────────────────────────────────────────────────

# 생성 순서(부모 먼저). 나머지 제네릭 카테고리는 뒤에 붙는다.
_STRATEGIC_ORDER = ["epics", "boundedContexts", "features", "userStories", "processes"]


# entityType(또는 카테고리 키) → Neo4j 라벨
def _label_for(entry: dict, category_key: str) -> str:
    et = entry.get("entityType") or ""
    if et:
        # camelCase → PascalCase
        lbl = et[0].upper() + et[1:]
    else:
        singular = {
            "userStories": "UserStory", "features": "Feature",
            "epics": "Epic", "processes": "Process",
            "boundedContexts": "BoundedContext",
        }
        if category_key in singular:
            lbl = singular[category_key]
        else:
            # 제네릭 복수형 → 단수 PascalCase (policies→Policy, businessRules→BusinessRule)
            base = category_key
            if base.endswith("ies"):
                base = base[:-3] + "y"
            elif base.endswith("s"):
                base = base[:-1]
            lbl = base[:1].upper() + base[1:]
    # 이 모델엔 별도 Epic 라벨이 없다 — BoundedContext가 Requirements 트리의 'Epic' 그룹이자
    # Aggregate 컨테이너다(tree_service: BoundedContext(Epic)→Feature→UserStory).
    if lbl == "Epic":
        lbl = "BoundedContext"
    return lbl


def apply_strategic_diff(session, proposal_id: str, strategic_diff: dict, ref_map: dict | None = None) -> int:
    """StrategicDiff의 모든 카테고리(고착 + 제네릭)를 부모→자식 순서로 적용. 반환: 적용 건수."""
    if not isinstance(strategic_diff, dict):
        return 0
    ref_map = ref_map if ref_map is not None else {}
    ordered = [k for k in _STRATEGIC_ORDER if isinstance(strategic_diff.get(k), list)]
    ordered += [k for k in strategic_diff
                if k not in _STRATEGIC_ORDER and k != "version" and isinstance(strategic_diff.get(k), list)]
    count = 0
    for key in ordered:
        for entry in strategic_diff[key]:
            if not isinstance(entry, dict):
                continue
            try:
                if _apply_strategic_entry(session, proposal_id, key, entry, ref_map):
                    count += 1
            except Exception as e:
                SmartLogger.log("WARN", f"strategic entry failed ({key}): {e}",
                                category="proposal_lifecycle.apply.strategic_warn",
                                params={"proposalId": proposal_id})
    return count


def _apply_strategic_entry(session, proposal_id: str, category_key: str, entry: dict, ref_map: dict) -> bool:
    op = (entry.get("op") or "MODIFY").upper()
    label = _safe_label(_label_for(entry, category_key))
    entity_id = entry.get("entityId") or entry.get("storyId")
    title = entry.get("entityTitle") or entry.get("storyTitle") or entry.get("featureTitle") or ""
    impact = entry.get("impactLevel", "MEDIUM")
    reason = entry.get("reason", "")

    if op == "CREATE":
        bc = None
        if label == "UserStory":
            node_id, bc = _create_user_story(session, proposal_id, entry, ref_map)
        elif label == "BoundedContext":
            node_id = _create_generic_strategic(session, proposal_id, label, entry, ref_map)
            bc = node_id  # BC는 자기 자신이 컨테이너
        else:
            node_id = _create_generic_strategic(session, proposal_id, label, entry, ref_map)
            if label == "Feature":
                bc = _resolve_ref(session, ref_map, entry.get("epicId") or entry.get("boundedContextId"), "BoundedContext")
        _register_ref(ref_map, entry, label, node_id, bc=bc)
        _record_effect(session, proposal_id, label, node_id, reason=reason,
                       impact=impact, change_type="CREATE", ops=[],
                       node_title=title, created_node_id=node_id)
        return True

    if op == "MODIFY" and entity_id:
        fields = entry.get("fields") or {}
        ops = []
        for f, v in fields.items():
            after = v.get("after") if isinstance(v, dict) else v
            ops.append({"field": f, "op": "set", "value": after})
        # acceptanceCriteria 직접 제공 시 교체
        if entry.get("acceptanceCriteria") is not None:
            ops.append({"field": "acceptanceCriteria", "op": "set",
                        "value": entry.get("acceptanceCriteria")})
        applied = _apply_ops(session, label, entity_id, ops)
        _record_effect(session, proposal_id, label, entity_id, reason=reason,
                       impact=impact, change_type="MODIFY", ops=applied, node_title=title)
        return True
    return False


def _create_user_story(session, proposal_id: str, entry: dict, ref_map: dict) -> tuple[str, str | None]:
    us_id = f"us-{uuid.uuid4()}"
    role, action, benefit = _extract_rab(entry)
    title = entry.get("entityTitle") or (f"{role}: {action}" if role else action)
    ac = entry.get("acceptanceCriteria") or []
    if isinstance(ac, str):
        ac = [ac]
    feature_id = _resolve_ref(session, ref_map, entry.get("featureId"), "Feature")
    bc_id = _resolve_ref(session, ref_map, entry.get("boundedContextId") or entry.get("epicId"), "BoundedContext")
    # BC가 명시 안 됐으면 Feature의 소속 BC에서 유도(US가 트리에 IMPLEMENTS로 매달리도록)
    if not bc_id and feature_id:
        bc_id = _bc_for_ref(session, ref_map, entry.get("featureId")) or _bc_of_feature(session, feature_id)

    session.run(
        """
        CREATE (us:UserStory {
            id: $id, role: $role, action: $action, benefit: $benefit,
            name: $name, displayName: $name,
            acceptanceCriteria: $ac, status: 'draft', priority: 'medium',
            proposalSource: $pid, createdAt: datetime(), updatedAt: datetime()
        })
        """,
        id=us_id, role=role, action=action, benefit=benefit,
        name=title, ac=[str(x) for x in ac], pid=proposal_id,
    )
    if feature_id:
        session.run(
            "MATCH (us:UserStory {id: $us}), (f:Feature {id: $fid}) "
            "MERGE (f)-[r:HAS_USER_STORY]->(us) "
            "ON CREATE SET r.createdAt = datetime(), r.source = 'proposal'",
            us=us_id, fid=feature_id,
        )
    if bc_id:
        session.run(
            "MATCH (us:UserStory {id: $us}), (bc:BoundedContext {id: $bid}) "
            "MERGE (us)-[:IMPLEMENTS]->(bc)",
            us=us_id, bid=bc_id,
        )
    return us_id, bc_id


def _create_generic_strategic(session, proposal_id: str, label: str, entry: dict, ref_map: dict) -> str:
    title = entry.get("entityTitle") or ""
    node_id = _gen_node_id(label, title, proposal_id)
    fields = entry.get("fields") or {}
    desc = ""
    d = fields.get("description")
    if isinstance(d, dict):
        desc = d.get("after") or ""
    elif isinstance(d, str):
        desc = d
    lbl = _safe_label(label)
    session.run(
        f"""
        CREATE (n:{lbl} {{
            id: $id, name: $name, title: $name, displayName: $name, description: $desc,
            key: $key, proposalSource: $pid, createdAt: datetime(), updatedAt: datetime()
        }})
        """,
        id=node_id, name=title, desc=desc,
        key=_slug(title, node_id), pid=proposal_id,
    )
    # Feature는 상위 BC(epicId/boundedContextId)에 연결
    if label == "Feature":
        bc_id = _resolve_ref(session, ref_map, entry.get("epicId") or entry.get("boundedContextId"), "BoundedContext")
        if bc_id:
            session.run(
                "MATCH (f:Feature {id: $fid}), (bc:BoundedContext {id: $bid}) "
                "MERGE (bc)-[r:HAS_FEATURE]->(f) ON CREATE SET r.createdAt = datetime()",
                fid=node_id, bid=bc_id,
            )
    return node_id


# ── Tactical 적용 ───────────────────────────────────────────────────────────

# 생성 순서(부모 먼저): BC → Aggregate/ReadModel → Command → Event → Policy → 기타
# (Policy는 Event TRIGGERS·Command INVOKES를 참조하므로 가장 뒤)
_TACTICAL_ORDER = {"BoundedContext": 0, "Aggregate": 1, "ReadModel": 1,
                   "Command": 2, "Event": 3, "Policy": 4}


def apply_tactical_diff(session, proposal_id: str, tactical_diff: list, ref_map: dict | None = None) -> int:
    if not isinstance(tactical_diff, list):
        return 0
    ref_map = ref_map if ref_map is not None else {}
    items = [it for it in tactical_diff if isinstance(it, dict)]
    items.sort(key=lambda it: _TACTICAL_ORDER.get(_safe_label(it.get("nodeLabel", "Aggregate")), 9))
    count = 0
    # Invariant ─VERIFIED_BY→ Command 는 Command 생성 후에만 가능하므로 (invariant_id, [cmdRef]) 를 모았다가 마지막에 연결.
    deferred: list[tuple[str, list]] = []
    for item in items:
        try:
            if _apply_tactical_item(session, proposal_id, item, ref_map, deferred):
                count += 1
        except Exception as e:
            SmartLogger.log("WARN", f"tactical item failed: {e}",
                            category="proposal_lifecycle.apply.tactical_warn",
                            params={"proposalId": proposal_id})
    # 후처리: Invariant VERIFIED_BY Command
    for inv_id, cmd_refs in deferred:
        for cr in (cmd_refs or []):
            cmd_id = _resolve_ref(session, ref_map, cr, "Command")
            if cmd_id:
                session.run(
                    "MATCH (inv:Invariant {id: $iid}), (cmd:Command {id: $cid}) "
                    "MERGE (inv)-[r:VERIFIED_BY]->(cmd) ON CREATE SET r.createdAt = datetime()",
                    iid=inv_id, cid=cmd_id,
                )
    # 후처리: FK Property ─REFERENCES→ PK Property (모든 Property 생성 후)
    _resolve_fk_references(session, proposal_id)
    return count


def _resolve_fk_references(session, proposal_id: str) -> int:
    """fkTargetHint('TargetType:TargetKey:TargetProp')를 실제 Property로 해소해 REFERENCES 연결."""
    rows = session.run(
        "MATCH (fk:Property {proposalSource: $pid}) "
        "WHERE fk.isForeignKey = true AND fk.fkTargetHint IS NOT NULL "
        "RETURN fk.id AS id, fk.fkTargetHint AS hint",
        pid=proposal_id,
    ).data()
    n = 0
    for r in rows:
        parts = [p.strip() for p in str(r.get("hint") or "").split(":")]
        if len(parts) < 3 or not parts[2]:
            continue
        tkey, tprop = parts[1], parts[2]
        tgt = session.run(
            "MATCH (parent)-[:HAS_PROPERTY]->(tp:Property {name: $tprop}) "
            "WHERE parent.name = $tkey OR parent.key = $tkey OR toLower(parent.name) = toLower($tkey) "
            "RETURN tp.id AS id LIMIT 1",
            tprop=tprop, tkey=tkey,
        ).single()
        if not tgt:  # fallback: 같은 이름의 PK Property
            tgt = session.run(
                "MATCH (tp:Property {name: $tprop, isKey: true}) RETURN tp.id AS id LIMIT 1",
                tprop=tprop,
            ).single()
        if tgt:
            session.run(
                "MATCH (fk:Property {id: $f}), (tp:Property {id: $t}) "
                "MERGE (fk)-[:REFERENCES]->(tp)",
                f=r["id"], t=tgt["id"],
            )
            n += 1
    return n


def _resolve_existing_by_name(session, label: str, name: str) -> str | None:
    if not name:
        return None
    lbl = _safe_label(label)
    row = session.run(
        f"MATCH (n:{lbl}) WHERE n.name = $name OR n.title = $name RETURN n.id AS id LIMIT 1",
        name=name,
    ).single()
    return row["id"] if row else None


def _fields_to_ops(fields) -> list[dict]:
    """item.fields(스칼라 속성: actor/category/inputSchema/version/payload 등)를 set op으로 변환."""
    ops: list[dict] = []
    if isinstance(fields, dict):
        for k, v in fields.items():
            after = v.get("after") if isinstance(v, dict) else v
            ops.append({"field": k, "op": "set", "value": after})
    return ops


def _create_properties(session, parent_label: str, parent_id: str, props, proposal_id: str) -> int:
    """설계 노드(Aggregate/Command/Event/ReadModel)에 Property 자식 + HAS_PROPERTY 생성."""
    if not isinstance(props, list):
        return 0
    n = 0
    for p in props:
        if not isinstance(p, dict) or not p.get("name"):
            continue
        prop_id = f"prop-{_slug(p.get('name'))}-{_short_uuid()}"
        session.run(
            """
            MATCH (parent {id: $parent})
            CREATE (pr:Property {
                id: $id, name: $name, type: $type, description: $desc, displayName: $dn,
                isKey: $isKey, isForeignKey: $isFk, isRequired: $isReq, fkTargetHint: $fkHint,
                parentType: $ptype, parentId: $parent,
                proposalSource: $pid, createdAt: datetime(), updatedAt: datetime()
            })
            MERGE (parent)-[:HAS_PROPERTY]->(pr)
            """,
            parent=parent_id, id=prop_id, name=str(p.get("name")),
            type=str(p.get("type") or "String"), desc=str(p.get("description") or ""),
            dn=p.get("displayName"), isKey=bool(p.get("isKey")),
            isFk=bool(p.get("isForeignKey")), isReq=bool(p.get("isRequired", False)),
            fkHint=p.get("fkTargetHint"), ptype=parent_label, pid=proposal_id,
        )
        n += 1
    return n


_GWT_KINDS = (("given", "Given", "HAS_GIVEN"), ("when", "When", "HAS_WHEN"), ("then", "Then", "HAS_THEN"))


def _create_gwt(session, command_id: str, gwt_list, proposal_id: str) -> int:
    """Command에 BDD 시나리오(Given/When/Then) 노드 + HAS_GIVEN/WHEN/THEN 생성."""
    if not isinstance(gwt_list, list):
        return 0
    n = 0
    for sc in gwt_list:
        if not isinstance(sc, dict):
            continue
        for key, lbl, rel in _GWT_KINDS:
            part = sc.get(key)
            if not isinstance(part, dict):
                continue
            gid = f"{key}-{_short_uuid()}"
            fv = part.get("fieldValues") or {}
            session.run(
                f"""
                MATCH (cmd:Command {{id: $cmd}})
                CREATE (g:{lbl} {{
                    id: $id, name: $name, description: $desc,
                    parentType: 'Command', parentId: $cmd,
                    fieldValues: $fv, scenario: $scenario,
                    proposalSource: $pid, createdAt: datetime()
                }})
                MERGE (cmd)-[:{rel}]->(g)
                """,
                cmd=command_id, id=gid, name=str(part.get("name") or ""),
                desc=str(part.get("description") or ""),
                fv=json.dumps(fv, ensure_ascii=False),
                scenario=str(sc.get("scenario") or sc.get("scenarioDescription") or ""),
                pid=proposal_id,
            )
        n += 1
    return n


def _create_invariants(session, agg_id: str, invariants, proposal_id: str, deferred: list | None) -> int:
    """Aggregate 불변식 → Invariant 노드 + HAS_INVARIANT. VERIFIED_BY는 deferred로 미룬다."""
    if not isinstance(invariants, list):
        return 0
    n = 0
    for seq, inv in enumerate(invariants):
        if not isinstance(inv, dict):
            # 문자열 선언만 온 경우도 허용
            inv = {"declaration": str(inv)} if inv else None
        if not inv or not inv.get("declaration"):
            continue
        inv_id = f"inv-{_slug(inv.get('declaration'))}-{_short_uuid()}"
        session.run(
            """
            MATCH (agg:Aggregate {id: $agg})
            CREATE (inv:Invariant {
                id: $id, declaration: $decl, name: $name, description: $desc,
                aggregateId: $agg, seq: $seq, source: 'ingested',
                proposalSource: $pid, createdAt: datetime(), updatedAt: datetime()
            })
            MERGE (agg)-[:HAS_INVARIANT]->(inv)
            """,
            agg=agg_id, id=inv_id, decl=str(inv.get("declaration")),
            name=inv.get("name") or "", desc=inv.get("description") or "",
            seq=seq, pid=proposal_id,
        )
        cmd_refs = inv.get("verifyingCommandRefs") or inv.get("verifyingCommandNames") or []
        if deferred is not None and cmd_refs:
            deferred.append((inv_id, cmd_refs))
        n += 1
    return n


def _create_ui(session, design_label: str, design_id: str, item: dict, ref_map: dict, proposal_id: str) -> None:
    """Command/ReadModel에 UI 화면 → BC ─HAS_UI→ UI ─ATTACHED_TO→ (Command|ReadModel)."""
    ui = item.get("ui")
    if not isinstance(ui, dict) or not (ui.get("name") or ui.get("title")):
        return
    ui_id = f"ui-{_slug(ui.get('name') or ui.get('title'))}-{_short_uuid()}"
    us_refs = item.get("userStoryRefs") or item.get("userStoryIds") or []
    us_id = None
    for r in us_refs:
        us_id = _resolve_ref(session, ref_map, r, "UserStory")
        if us_id:
            break
    session.run(
        """
        MATCH (d {id: $did})
        CREATE (ui:UI {
            id: $id, name: $name, description: $desc, template: $tpl,
            attachedToId: $did, attachedToType: $dtype, attachedToName: $dname,
            userStoryId: $usid, designSource: 'html',
            proposalSource: $pid, createdAt: datetime(), updatedAt: datetime()
        })
        MERGE (ui)-[:ATTACHED_TO]->(d)
        """,
        did=design_id, id=ui_id, name=str(ui.get("name") or ui.get("title")),
        desc=str(ui.get("description") or ""), tpl=ui.get("template"),
        dtype=design_label, dname=_get_field(session, design_label, design_id, "name") or "",
        usid=us_id, pid=proposal_id,
    )
    # 소속 BC에 HAS_UI 연결
    bc_id = None
    if design_label == "ReadModel":
        bc_id = _resolve_ref(session, ref_map, item.get("boundedContextId") or item.get("bcId"), "BoundedContext")
    else:  # Command → aggregate 의 BC
        bc_id = _bc_for_ref(session, ref_map, item.get("aggregateId"))
    if bc_id:
        session.run(
            "MATCH (bc:BoundedContext {id: $bid}), (ui:UI {id: $uid}) "
            "MERGE (bc)-[r:HAS_UI]->(ui) ON CREATE SET r.createdAt = datetime()",
            bid=bc_id, uid=ui_id,
        )


def _apply_tactical_item(session, proposal_id: str, item: dict, ref_map: dict, deferred: list | None = None) -> bool:
    label = _safe_label(item.get("nodeLabel", "Aggregate"))
    change_type = (item.get("changeType") or "MODIFY").upper()
    title = item.get("nodeTitle") or ""
    impact = item.get("impactLevel", "MEDIUM")
    reason = item.get("reason", "")
    sd = item.get("semanticDiff") or {}
    ops = list((sd.get("ops") if isinstance(sd, dict) else None) or [])
    # 스칼라 속성(actor/category/inputSchema/version/payload 등)도 set op으로 합류
    ops += _fields_to_ops(item.get("fields"))
    node_id = item.get("nodeId")

    if change_type == "CREATE":
        # 기존 노드 재사용 시도 → 없으면 신규 생성. nodeId가 tempId일 수 있으므로 실제 id를 새로 만든다.
        real_id = _resolve_existing_by_name(session, label, title) or _gen_node_id(label, title, proposal_id)
        lbl = _safe_label(label)
        session.run(
            f"""
            MERGE (n:{lbl} {{id: $id}})
            ON CREATE SET n.createdAt = datetime(), n.proposalSource = $pid,
                          n.key = $key
            SET n.updatedAt = datetime()
            """,
            id=real_id, pid=proposal_id, key=_slug(title, real_id),
        )
        applied = _apply_ops(session, label, real_id, ops)
        # name 보정
        if not _get_field(session, label, real_id, "name") and title:
            _set_scalar(session, label, real_id, "name", title)
        # tempId(nodeId) → 실제 id 등록(다른 tactical item이 이 노드를 가리킬 수 있게)
        bc = real_id if label == "BoundedContext" else _resolve_ref(
            session, ref_map, item.get("boundedContextId") or item.get("bcId"), "BoundedContext")
        _register_ref(ref_map, item, label, real_id, bc=bc)
        _link_tactical(session, label, real_id, item, ref_map)
        # Property(HAS_PROPERTY) + Command GWT(HAS_GIVEN/WHEN/THEN) + Invariant + UI
        _create_properties(session, label, real_id, item.get("properties"), proposal_id)
        if label == "Aggregate":
            _create_invariants(session, real_id, item.get("invariants"), proposal_id, deferred)
        if label == "Command":
            _create_gwt(session, real_id, item.get("gwt"), proposal_id)
        if label in ("Command", "ReadModel"):
            _create_ui(session, label, real_id, item, ref_map, proposal_id)
        _record_effect(session, proposal_id, label, real_id, reason=reason,
                       impact=impact, change_type="CREATE", ops=applied,
                       node_title=title, created_node_id=real_id)
        return True

    # MODIFY
    if not node_id:
        node_id = _resolve_existing_by_name(session, label, title)
    else:
        node_id = _resolve_ref(session, ref_map, node_id, label) or node_id
    if not node_id:
        return False
    applied = _apply_ops(session, label, node_id, ops)
    _create_properties(session, label, node_id, item.get("properties"), proposal_id)
    _link_tactical(session, label, node_id, item, ref_map)
    if label == "Aggregate":
        _create_invariants(session, node_id, item.get("invariants"), proposal_id, deferred)
    if label == "Command":
        _create_gwt(session, node_id, item.get("gwt"), proposal_id)
    if label in ("Command", "ReadModel"):
        _create_ui(session, label, node_id, item, ref_map, proposal_id)
    _record_effect(session, proposal_id, label, node_id, reason=reason,
                   impact=impact, change_type="MODIFY", ops=applied, node_title=title)
    return True


def _resolve_id_or_key(session, label: str, ref: str) -> str | None:
    lbl = _safe_label(label)
    row = session.run(
        f"MATCH (n:{lbl}) WHERE n.id = $ref OR n.key = $ref RETURN n.id AS id LIMIT 1",
        ref=ref,
    ).single()
    return row["id"] if row else None


def _link_user_stories(session, ref_map: dict, design_label: str, design_id: str, refs) -> None:
    """UserStory ─IMPLEMENTS→ 설계요소(Command/ReadModel) 추적성 연결."""
    for usr in (refs or []):
        us_id = _resolve_ref(session, ref_map, usr, "UserStory")
        if us_id:
            session.run(
                f"MATCH (us:UserStory {{id: $us}}), (d:{_safe_label(design_label)} {{id: $did}}) "
                "MERGE (us)-[r:IMPLEMENTS]->(d) ON CREATE SET r.createdAt = datetime(), r.source = 'proposal'",
                us=us_id, did=design_id,
            )


def _link_tactical(session, label: str, node_id: str, item: dict, ref_map: dict) -> None:
    """Tactical 노드를 상위 구조에 연결한다(ref_map으로 tempId 해소)."""
    bc_ref = item.get("boundedContextId") or item.get("bcId")
    agg_ref = item.get("aggregateId")
    cmd_ref = item.get("commandId")
    us_refs = item.get("userStoryRefs") or item.get("userStoryIds")

    if label == "Aggregate" and bc_ref:
        bc_id = _resolve_ref(session, ref_map, bc_ref, "BoundedContext")
        if bc_id:
            session.run(
                "MATCH (bc:BoundedContext {id: $bid}), (agg:Aggregate {id: $aid}) "
                "MERGE (bc)-[r:HAS_AGGREGATE]->(agg) ON CREATE SET r.createdAt = datetime()",
                bid=bc_id, aid=node_id,
            )
    elif label == "Command":
        if agg_ref:
            agg_id = _resolve_ref(session, ref_map, agg_ref, "Aggregate")
            if agg_id:
                session.run(
                    "MATCH (agg:Aggregate {id: $aid}), (cmd:Command {id: $cid}) "
                    "MERGE (agg)-[r:HAS_COMMAND]->(cmd) ON CREATE SET r.createdAt = datetime()",
                    aid=agg_id, cid=node_id,
                )
        # UserStory ─IMPLEMENTS→ Command (추적성)
        _link_user_stories(session, ref_map, "Command", node_id, us_refs)
    elif label == "Event" and cmd_ref:
        cmd_id = _resolve_ref(session, ref_map, cmd_ref, "Command")
        if cmd_id:
            session.run(
                "MATCH (cmd:Command {id: $cid}), (evt:Event {id: $eid}) "
                "MERGE (cmd)-[r:EMITS]->(evt) ON CREATE SET r.createdAt = datetime()",
                cid=cmd_id, eid=node_id,
            )
    elif label == "ReadModel":
        if bc_ref:
            bc_id = _resolve_ref(session, ref_map, bc_ref, "BoundedContext")
            if bc_id:
                session.run(
                    "MATCH (bc:BoundedContext {id: $bid}), (rm:ReadModel {id: $rid}) "
                    "MERGE (bc)-[r:HAS_READMODEL]->(rm) ON CREATE SET r.createdAt = datetime()",
                    bid=bc_id, rid=node_id,
                )
        _link_user_stories(session, ref_map, "ReadModel", node_id, us_refs)
    elif label == "Policy":
        if bc_ref:
            bc_id = _resolve_ref(session, ref_map, bc_ref, "BoundedContext")
            if bc_id:
                session.run(
                    "MATCH (bc:BoundedContext {id: $bid}), (pol:Policy {id: $pid}) "
                    "MERGE (bc)-[r:HAS_POLICY]->(pol) ON CREATE SET r.createdAt = datetime()",
                    bid=bc_id, pid=node_id,
                )
        # Event ─TRIGGERS→ Policy ─INVOKES→ Command (BC간 반응 정책)
        trig = _resolve_ref(session, ref_map, item.get("triggerEventId"), "Event")
        if trig:
            session.run(
                "MATCH (evt:Event {id: $eid}), (pol:Policy {id: $pid}) "
                "MERGE (evt)-[r:TRIGGERS]->(pol) ON CREATE SET r.priority = 1, r.isEnabled = true, r.createdAt = datetime()",
                eid=trig, pid=node_id,
            )
        invoke = _resolve_ref(session, ref_map, item.get("invokeCommandId"), "Command")
        if invoke:
            session.run(
                "MATCH (pol:Policy {id: $pid}), (cmd:Command {id: $cid}) "
                "MERGE (pol)-[r:INVOKES]->(cmd) ON CREATE SET r.isAsync = true, r.createdAt = datetime()",
                pid=node_id, cid=invoke,
            )


# ── Journey 적용 (화면 흐름) ─────────────────────────────────────────────────

def apply_journeys(session, proposal_id: str, journeys, ref_map: dict | None = None) -> int:
    """
    사용자 여정: BoundedContext ─HAS_JOURNEY→ Journey ─HAS_STEP→ JourneyStep,
    JourneyStep ─NEXT→ JourneyStep, JourneyStep ─SHOWS→ UI.
    UI는 step이 가리키는 Command/ReadModel(commandRef/readModelRef)에 ATTACHED_TO된 화면으로 해소한다.
    tacticalDiff(UI 생성) 이후에 호출해야 한다.
    """
    if not isinstance(journeys, list):
        return 0
    ref_map = ref_map if ref_map is not None else {}
    count = 0
    for j in journeys:
        if not isinstance(j, dict) or not (j.get("name") or j.get("title")):
            continue
        try:
            jname = j.get("name") or j.get("title")
            jid = _gen_node_id("Journey", jname, proposal_id)
            session.run(
                """
                CREATE (jn:Journey {id: $id, name: $name, description: $desc,
                    proposalSource: $pid, createdAt: datetime(), updatedAt: datetime()})
                """,
                id=jid, name=jname, desc=str(j.get("description") or ""), pid=proposal_id,
            )
            steps = [st for st in (j.get("steps") or []) if isinstance(st, dict)]
            # 1단계: step 노드 생성 + HAS_STEP + SHOWS(UI). 이름/tempId 둘 다로 색인.
            step_ids: dict = {}
            bc_candidates: list = []
            for seq, st in enumerate(steps):
                sname = st.get("name") or st.get("title") or f"step-{seq}"
                sid = _gen_node_id("JourneyStep", sname, proposal_id)
                # 설계요소 참조: commandRef/readModelRef/ref/uiRef (라벨 모를 수 있음 → ref_map으로 직접 해소)
                design_ref = st.get("commandRef") or st.get("readModelRef") or st.get("ref") or st.get("uiRef")
                rec = ref_map.get(design_ref) if design_ref else None
                kind = st.get("kind") or ("screen" if design_ref else "gateway")
                session.run(
                    """
                    MATCH (jn:Journey {id: $jid})
                    CREATE (s:JourneyStep {id: $id, name: $name, kind: $kind, seq: $seq,
                        proposalSource: $pid, createdAt: datetime()})
                    MERGE (jn)-[:HAS_STEP]->(s)
                    """,
                    jid=jid, id=sid, name=sname, kind=kind, seq=seq, pid=proposal_id,
                )
                for temp in _entry_temp_ids(st):
                    step_ids[temp] = sid
                step_ids.setdefault(sname, sid)
                if rec:
                    if rec.get("bc"):
                        bc_candidates.append(rec["bc"])
                    # SHOWS: 그 설계요소(Command/ReadModel)에 ATTACHED_TO된 UI
                    session.run(
                        "MATCH (s:JourneyStep {id: $sid}), (ui:UI)-[:ATTACHED_TO]->(d {id: $did}) "
                        "MERGE (s)-[:SHOWS]->(ui)",
                        sid=sid, did=rec["id"],
                    )
            # HAS_JOURNEY: 명시 boundedContextId, 없으면 step들이 가리킨 설계요소의 BC로 유도
            bc_id = _resolve_ref(session, ref_map, j.get("boundedContextId") or j.get("epicId"), "BoundedContext") \
                or (bc_candidates[0] if bc_candidates else None)
            if bc_id:
                session.run(
                    "MATCH (bc:BoundedContext {id: $bid}), (jn:Journey {id: $jid}) "
                    "MERGE (bc)-[r:HAS_JOURNEY]->(jn) ON CREATE SET r.createdAt = datetime()",
                    bid=bc_id, jid=jid,
                )
            # 2단계: NEXT 엣지 (next는 tempId 또는 step 이름, 문자열 또는 리스트 모두 허용)
            for st in steps:
                src = next((step_ids[t] for t in _entry_temp_ids(st) if t in step_ids), None) \
                    or step_ids.get(st.get("name") or st.get("title"))
                if not src:
                    continue
                nxts = st.get("next")
                if isinstance(nxts, str):
                    nxts = [nxts]
                for nxt in (nxts or []):
                    dst = step_ids.get(nxt)
                    if dst:
                        session.run(
                            "MATCH (a:JourneyStep {id: $a}), (b:JourneyStep {id: $b}) "
                            "MERGE (a)-[r:NEXT]->(b) ON CREATE SET r.condition = $cond, r.source = 'proposal', r.createdAt = datetime()",
                            a=src, b=dst, cond=st.get("condition") or "",
                        )
            count += 1
        except Exception as e:
            SmartLogger.log("WARN", f"journey failed: {e}",
                            category="proposal_lifecycle.apply.journey_warn",
                            params={"proposalId": proposal_id})
    return count


# ── 수거 (Revoke) ───────────────────────────────────────────────────────────

def revoke_accepted_proposal(session, proposal_id: str) -> dict:
    """
    Accept된 Proposal의 그래프 변경을 되돌린다.
    - CREATE EFFECT: 생성된 노드 DETACH DELETE
    - MODIFY EFFECT: ops 역방향 복원 후 EFFECT 관계 제거
    반환: {"reverted": n, "errors": [...]}
    """
    rows = session.run(
        """
        MATCH (p:Proposal {id: $pid})-[e:EFFECT]->(n)
        RETURN n.id AS nodeId, labels(n) AS labels, e.diff AS diff, e.changeType AS ct
        """,
        pid=proposal_id,
    ).data()

    reverted = 0
    errors: list[str] = []
    for row in rows:
        node_id = row.get("nodeId")
        labels = row.get("labels") or []
        label = labels[0] if labels else "Node"
        ct = row.get("ct") or "MODIFY"
        try:
            diff = json.loads(row["diff"]) if row.get("diff") else {}
        except Exception:
            diff = {}
        change_type = diff.get("changeType", ct)
        try:
            if change_type == "CREATE":
                created = diff.get("createdNodeId") or node_id
                # 자식 Property/GWT(Given/When/Then)도 함께 제거(고아 방지)
                session.run(
                    f"""
                    MATCH (n:{_safe_label(label)} {{id: $id}})
                    OPTIONAL MATCH (n)-[:HAS_PROPERTY|HAS_GIVEN|HAS_WHEN|HAS_THEN|HAS_INVARIANT]->(child)
                    DETACH DELETE child, n
                    """,
                    id=created,
                )
            else:
                _reverse_ops(session, label, node_id, diff.get("ops") or [])
            reverted += 1
        except Exception as e:
            errors.append(f"{label}:{node_id} — {e}")

    # 남은 자식 노드(이 Proposal이 만든 Property/GWT/UI/Invariant) 정리 —
    # MODIFY로 기존 노드에 덧붙인 자식까지 포함해 일괄 제거(고아 방지).
    session.run(
        """
        MATCH (c {proposalSource: $pid})
        WHERE c:Property OR c:Given OR c:When OR c:Then OR c:UI OR c:Invariant
           OR c:Journey OR c:JourneyStep
        DETACH DELETE c
        """,
        pid=proposal_id,
    )

    # 모든 EFFECT 관계 제거 (CREATE 노드는 DETACH DELETE로 이미 제거됨)
    session.run("MATCH (p:Proposal {id: $pid})-[e:EFFECT]->() DELETE e", pid=proposal_id)

    return {"reverted": reverted, "errors": errors}
