from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from api.features.requirement_changes.requirement_changes_contracts import (
    DiffOp,
    DiffOpType,
    SemanticDiff,
)
from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

_SKILL_FILE = Path(__file__).parents[4] / "skills" / "robo-changes" / "robo-change-specify" / "SKILL.md"

# 설계 반영 대상 노드 유형 → 주 텍스트 필드
_FIELD_MAP = {
    "UserStory":      "acceptanceCriteria",
    "Feature":        "description",
    "BoundedContext": "description",
    "Aggregate":      "description",
    "Command":        "description",
    "Event":          "description",
}

# 구조화 diff(VO/Enum/Invariant)를 별도 분석할 노드 유형
_DESIGN_LABELS = {"Aggregate", "Command", "Event", "Policy", "ReadModel"}


# ── 유틸 ───────────────────────────────────────────────────────────────────

def _to_str(val) -> str:
    if val is None:
        return ""
    if isinstance(val, list):
        return "\n".join(str(v) for v in val)
    return str(val)


def _parse_json(val):
    if val is None:
        return None
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return val
    return val


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Neo4j helpers ──────────────────────────────────────────────────────────

def _fetch_effects(change_id: str) -> list[dict]:
    query = """
    MATCH (chg:RequirementChange {id: $id})-[e:EFFECT]->(n)
    RETURN n.id AS nodeId,
           CASE WHEN 'CreationIntent' IN labels(n)
                THEN n.nodeLabel
                ELSE labels(n)[0]
           END AS nodeLabel,
           COALESCE(n.title, n.name, n.action, '') AS nodeTitle,
           COALESCE(n.acceptanceCriteria, n.description, n.body, '') AS currentContent,
           e.reason AS reason,
           e.impactLevel AS impactLevel,
           COALESCE(e.changeType, 'MODIFY') AS changeType,
           e.templateData AS templateData,
           e.appliedNodeId AS appliedNodeId
    """
    with get_session() as session:
        rows = session.run(query, id=change_id).data()
    for row in rows:
        row["currentContent"] = _to_str(row.get("currentContent", ""))
    return rows


# ── CREATE 유형 헬퍼 (신규 노드 생성) ─────────────────────────────────────

def _resolve_bc_by_name(name: str) -> str | None:
    """BC 이름 fuzzy 조회 → id 반환."""
    if not name:
        return None
    with get_session() as session:
        row = session.run(
            "MATCH (bc:BoundedContext) "
            "WHERE bc.name CONTAINS $name OR bc.key CONTAINS $name "
            "RETURN bc.id LIMIT 1",
            name=name,
        ).single()
    return row["bc.id"] if row else None


def _resolve_feature_by_name(name: str, bc_id: str | None) -> str | None:
    """Feature 이름 fuzzy 조회. bc_id 있으면 해당 BC 내에서만 조회."""
    if not name:
        return None
    if bc_id:
        with get_session() as session:
            row = session.run(
                "MATCH (bc:BoundedContext {id: $bc_id})-[:HAS_FEATURE|CONTAINS]->(f:Feature) "
                "WHERE f.name CONTAINS $name "
                "RETURN f.id LIMIT 1",
                bc_id=bc_id, name=name,
            ).single()
        if row:
            return row["f.id"]
    with get_session() as session:
        row = session.run(
            "MATCH (f:Feature) WHERE f.name CONTAINS $name RETURN f.id LIMIT 1",
            name=name,
        ).single()
    return row["f.id"] if row else None


def _create_user_story_node(template: dict) -> str:
    """templateData로 UserStory 노드를 Neo4j에 생성하고 id를 반환한다."""
    us_id = f"us-{uuid.uuid4()}"
    bc_id = _resolve_bc_by_name(template.get("parentBCName", ""))
    feature_id = _resolve_feature_by_name(template.get("parentFeatureName", ""), bc_id)
    acceptance = template.get("acceptanceCriteria", [])
    if isinstance(acceptance, str):
        acceptance = [acceptance]

    with get_session() as session:
        session.run(
            "CREATE (us:UserStory {"
            "  id: $id, role: $role, action: $action, benefit: $benefit,"
            "  acceptanceCriteria: $criteria,"
            "  boundedContextId: $bc_id, featureId: $feature_id,"
            "  createdAt: datetime()"
            "})",
            id=us_id,
            role=template.get("role", ""),
            action=template.get("action", ""),
            benefit=template.get("benefit", ""),
            criteria=acceptance,
            bc_id=bc_id or "",
            feature_id=feature_id or "",
        )
        if bc_id:
            session.run(
                "MATCH (us:UserStory {id: $us_id}), (bc:BoundedContext {id: $bc_id}) "
                "MERGE (bc)-[:CONTAINS_STORY]->(us)",
                us_id=us_id, bc_id=bc_id,
            )
        if feature_id:
            session.run(
                "MATCH (us:UserStory {id: $us_id}), (f:Feature {id: $fid}) "
                "MERGE (f)-[:CONTAINS]->(us)",
                us_id=us_id, fid=feature_id,
            )
    return us_id


def _create_feature_node(template: dict) -> str:
    """templateData로 Feature 노드를 Neo4j에 생성하고 id를 반환한다."""
    f_id = f"feature-{uuid.uuid4()}"
    bc_id = _resolve_bc_by_name(template.get("parentBCName", ""))

    with get_session() as session:
        session.run(
            "CREATE (f:Feature {"
            "  id: $id, name: $name, description: $desc,"
            "  boundedContextId: $bc_id, createdAt: datetime()"
            "})",
            id=f_id,
            name=template.get("name", ""),
            desc=template.get("description", ""),
            bc_id=bc_id or "",
        )
        if bc_id:
            session.run(
                "MATCH (f:Feature {id: $fid}), (bc:BoundedContext {id: $bc_id}) "
                "MERGE (bc)-[:HAS_FEATURE]->(f)",
                fid=f_id, bc_id=bc_id,
            )
    return f_id


def _create_bounded_context_node(template: dict) -> str:
    """templateData로 BoundedContext 노드를 Neo4j에 생성하고 id를 반환한다."""
    bc_key = re.sub(r"[^a-zA-Z0-9]", "", template.get("name", "bc")) or f"bc{uuid.uuid4().hex[:6]}"
    bc_id = f"bc-{bc_key.lower()}-{uuid.uuid4().hex[:6]}"

    with get_session() as session:
        session.run(
            "CREATE (bc:BoundedContext {"
            "  id: $id, key: $key, name: $name, description: $desc,"
            "  createdAt: datetime()"
            "})",
            id=bc_id,
            key=bc_key,
            name=template.get("name", ""),
            desc=template.get("description", ""),
        )
    return bc_id


async def _apply_create_effect(change_id: str, effect: dict) -> dict:
    """CREATE 유형 EFFECT를 처리 — 실제 노드 생성 후 EFFECT.appliedNodeId 업데이트."""
    raw_template = effect.get("templateData")
    if isinstance(raw_template, str):
        try:
            template = json.loads(raw_template)
        except Exception:
            template = {}
    else:
        template = raw_template or {}

    node_label = effect.get("nodeLabel", "")
    placeholder_id = effect["nodeId"]   # CreationIntent.id

    creator_map = {
        "UserStory": _create_user_story_node,
        "Feature": _create_feature_node,
        "BoundedContext": _create_bounded_context_node,
    }
    creator = creator_map.get(node_label)
    if not creator:
        return {"error": f"Unknown nodeLabel for CREATE: {node_label}"}

    try:
        real_id = creator(template)
    except Exception as e:
        return {"error": f"Node creation failed: {e}"}

    # EFFECT.appliedNodeId 업데이트
    with get_session() as session:
        session.run(
            "MATCH (chg:RequirementChange {id: $cid})-[e:EFFECT]->(ci:CreationIntent {id: $pid}) "
            "SET e.appliedNodeId = $real_id, e.appliedAt = $now",
            cid=change_id, pid=placeholder_id, real_id=real_id, now=_now_iso(),
        )

    # SemanticDiff 저장 (CREATE용: ops 빈 리스트, createdNodeId로 undo)
    node_title = (
        template.get("action") or template.get("name") or node_label
    )
    diff = SemanticDiff(
        nodeLabel=node_label,
        nodeTitle=node_title,
        appliedAt=_now_iso(),
        ops=[],
        changeType="CREATE",
        createdNodeId=real_id,
    )
    _store_diff_in_effect(change_id, placeholder_id, diff)

    return {
        "nodeId": placeholder_id,
        "createdNodeId": real_id,
        "nodeLabel": node_label,
        "nodeTitle": node_title,
        "changeType": "CREATE",
    }


def _fetch_change_prompt(change_id: str) -> str:
    with get_session() as session:
        rec = session.run(
            "MATCH (n:RequirementChange {id: $id}) RETURN n.originalPrompt AS p",
            id=change_id,
        ).single()
    return (rec["p"] or "") if rec else ""


def _fetch_design_node_detail(node_id: str, node_label: str) -> dict:
    """Aggregate/Command/Event 구조 상세 조회."""
    query = f"""
    MATCH (n:{node_label} {{id: $id}})
    RETURN n.valueObjects    AS valueObjects,
           n.enumerations    AS enumerations,
           n.invariants      AS invariants,
           n.fieldDescriptors AS fieldDescriptors
    """
    with get_session() as session:
        row = session.run(query, id=node_id).single()
    if not row:
        return {}
    return {
        "valueObjects":    _parse_json(row["valueObjects"]),
        "enumerations":    _parse_json(row["enumerations"]),
        "invariants":      _parse_json(row["invariants"]),
        "fieldDescriptors":_parse_json(row["fieldDescriptors"]),
    }


def _update_node_field(node_id: str, node_label: str, field: str, new_value) -> None:
    query = f"MATCH (n:{node_label}) WHERE n.id = $id SET n.{field} = $value"
    with get_session() as session:
        session.run(query, id=node_id, value=new_value)


def _store_diff_in_effect(change_id: str, node_id: str, diff: SemanticDiff) -> None:
    """EFFECT 관계에 semantic diff를 저장한다."""
    with get_session() as session:
        session.run(
            "MATCH (chg:RequirementChange {id: $cid})-[e:EFFECT]->(n) "
            "WHERE n.id = $nid "
            "SET e.diff = $diff, e.appliedAt = $at",
            cid=change_id,
            nid=node_id,
            diff=json.dumps(diff.model_dump(), ensure_ascii=False),
            at=diff.appliedAt,
        )


def _clear_diff_in_effect(change_id: str, node_id: str) -> None:
    """EFFECT 관계의 diff를 초기화한다 (undo 완료 후)."""
    with get_session() as session:
        session.run(
            "MATCH (chg:RequirementChange {id: $cid})-[e:EFFECT]->(n) "
            "WHERE n.id = $nid "
            "REMOVE e.diff, e.appliedAt",
            cid=change_id,
            nid=node_id,
        )


def _fetch_effects_with_diff(change_id: str) -> list[dict]:
    """apply 완료 후 EFFECT.diff가 있는 항목 조회 (MODIFY + CREATE 모두)."""
    query = """
    MATCH (chg:RequirementChange {id: $id})-[e:EFFECT]->(n)
    WHERE e.diff IS NOT NULL
    RETURN n.id AS nodeId,
           CASE WHEN 'CreationIntent' IN labels(n)
                THEN n.nodeLabel
                ELSE labels(n)[0]
           END AS nodeLabel,
           COALESCE(n.title, n.name, n.action, '') AS nodeTitle,
           e.diff AS diff,
           e.impactLevel AS impactLevel,
           e.appliedAt AS appliedAt,
           e.templateData AS templateData,
           e.appliedNodeId AS appliedNodeId
    """
    with get_session() as session:
        return session.run(query, id=change_id).data()


# ── AI 호출 ────────────────────────────────────────────────────────────────

def _claude_env() -> dict:
    """헤드리스 claude 서브프로세스용 환경.

    백엔드가 .env 의 (만료/무효일 수 있는) ANTHROPIC_API_KEY 를 os.environ 에 로드하면
    헤드리스 claude 가 그 키로 인증을 시도해 'Invalid API key' 로 즉시 실패한다.
    키를 제거하면 claude.ai 로그인(구독)으로 폴백한다.
    """
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(k, None)
    return env


# claude CLI 가 인증/실행 실패 시 stdout 으로 흘리는 에러 문구. 정상 출력으로 오인해
# 그래프에 적용되는 일을 막는 방어 가드.
_CLAUDE_ERROR_MARKERS = (
    "Invalid API key",
    "Fix external API key",
    "authentication_error",
    "Credit balance is too low",
)


async def _call_claude(system: str, human: str, timeout: int = 90) -> str | None:
    claude_bin = shutil.which("claude") or "claude"
    cmd = [claude_bin, "-p", human, "--system-prompt", system,
           "--output-format", "text", "--dangerously-skip-permissions"]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env=_claude_env(),
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        result = stdout.decode("utf-8", errors="replace").strip()
        if not result:
            return None
        # 인증/실행 실패 문구가 그대로 적용되는 데이터 오염 방지.
        if proc.returncode != 0 or any(m in result for m in _CLAUDE_ERROR_MARKERS):
            SmartLogger.log("WARN", f"Claude call returned error output (rc={proc.returncode}): {result[:120]}",
                            category="requirement_changes.design.ai_error", params={})
            return None
        return result
    except Exception as e:
        SmartLogger.log("WARN", f"Claude call failed: {e}",
                        category="requirement_changes.design.ai_error", params={})
        return None


async def _generate_text_update(change_prompt: str, node: dict, field: str) -> str | None:
    """텍스트 필드 업데이트 생성."""
    system = (
        "당신은 소프트웨어 요구사항 전문가입니다. "
        "요구사항 변경이 특정 도메인 요소에 미치는 영향을 반영하여 해당 요소의 내용을 업데이트하세요.\n\n"
        "출력 규칙:\n"
        "- 업데이트된 텍스트만 출력 (마크다운 코드블록, 설명 없이)\n"
        "- 기존 내용을 보존하면서 변경사항만 반영\n"
        "- 변경이 필요 없으면 정확히 'NO_CHANGE' 출력"
    )
    human = (
        f"요구사항 변경: {change_prompt}\n\n"
        f"노드 유형: {node['nodeLabel']}\n"
        f"노드 이름: {node['nodeTitle']}\n"
        f"변경 이유: {node.get('reason', '')} (영향도: {node.get('impactLevel', 'MEDIUM')})\n\n"
        f"현재 {field}:\n{node['currentContent'] or '(없음)'}\n\n"
        f"위 변경사항을 반영한 새로운 {field}를 작성하세요."
    )
    result = await _call_claude(system, human, timeout=60)
    if not result or result == "NO_CHANGE":
        return None
    return result


async def _generate_struct_diff_json(
    change_prompt: str, node: dict, detail: dict
) -> dict | None:
    """Aggregate/Command/Event의 구조적 변경 계획을 JSON으로 생성."""
    system = """당신은 도메인 모델 전문가입니다. 요구사항 변경이 도메인 객체 구조에 미치는 영향을 JSON으로 분석합니다.

출력 규칙 (CRITICAL):
- 반드시 순수 JSON만 출력. 마크다운 코드블록, 설명 없음.
- 형식:
{
  "fieldChanges": [
    {"type": "ADDED|REMOVED|MODIFIED|RENAMED", "name": "fieldName", "dataType": "String", "before": null, "after": "String", "description": "이유"}
  ],
  "valueObjectChanges": [
    {"type": "ADDED|REMOVED", "name": "VOName", "displayName": "한글명", "fields": [{"name": "f", "type": "String"}], "description": "이유"}
  ],
  "enumChanges": [
    {"enumName": "EnumName", "type": "ADDED|MODIFIED", "addedItems": ["NEW_VALUE"], "removedItems": []}
  ],
  "invariantChanges": ["추가될 불변식 문장"]
}
- 변경 없는 항목은 빈 배열"""
    current_vos   = json.dumps(detail.get("valueObjects")  or [], ensure_ascii=False)
    current_enums = json.dumps(detail.get("enumerations")  or [], ensure_ascii=False)
    current_invs  = json.dumps(detail.get("invariants")    or [], ensure_ascii=False)
    human = (
        f"요구사항 변경: {change_prompt}\n\n"
        f"노드: {node['nodeLabel']} — {node['nodeTitle']}\n"
        f"변경 이유: {node.get('reason', '')} (영향도: {node.get('impactLevel', 'MEDIUM')})\n\n"
        f"현재 Value Objects:\n{current_vos}\n\n"
        f"현재 Enumerations:\n{current_enums}\n\n"
        f"현재 Invariants:\n{current_invs}\n\n"
        "위 변경사항을 반영하기 위한 구조적 변경을 JSON으로 분석하세요."
    )
    raw = await _call_claude(system, human, timeout=90)
    if not raw:
        return None
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    return None


async def _ai_undo_text(
    field: str, node_label: str, node_title: str,
    from_val: str, to_val: str, current_val: str,
) -> str:
    """
    replace op 역방향 복원.
    current == to_val이면 단순 복원.
    current != to_val이면 (이후에 다른 변경이 있음) AI가 CHG 기여분만 제거.
    """
    if not current_val or current_val == to_val:
        return from_val

    system = (
        "당신은 소프트웨어 요구사항 전문가입니다. "
        "특정 변경사항(CHG)이 적용된 텍스트에서 그 CHG의 기여분만 제거하고, "
        "이후에 추가된 다른 변경사항은 최대한 보존해야 합니다.\n\n"
        "출력 규칙:\n- 복원된 텍스트만 출력 (설명, 코드블록 없이)"
    )
    human = (
        f"노드: {node_label} — {node_title}\n"
        f"필드: {field}\n\n"
        f"CHG 적용 전 값 (복원 목표):\n{from_val}\n\n"
        f"CHG가 적용한 값:\n{to_val}\n\n"
        f"현재 값 (이후 변경이 있을 수 있음):\n{current_val}\n\n"
        "CHG의 기여분만 제거하고 이후 변경은 보존하여 복원된 값을 출력하세요."
    )
    result = await _call_claude(system, human, timeout=60)
    return result or from_val


# ── Semantic diff 빌더 ─────────────────────────────────────────────────────

def _build_ops_from_struct(
    before_detail: dict,
    struct_diff: dict,
    before_text: str,
    after_text: str,
    field: str,
) -> list[DiffOp]:
    """struct_diff JSON → DiffOp 목록 변환."""
    ops: list[DiffOp] = []

    # 1. 텍스트 replace op
    if after_text and after_text != before_text:
        ops.append(DiffOp(
            field=field,
            op=DiffOpType.REPLACE,
            from_val=before_text,
            to_val=after_text,
        ))

    # 2. Value Object 변경
    for vc in struct_diff.get("valueObjectChanges") or []:
        if vc.get("type") == "ADDED":
            ops.append(DiffOp(
                field="valueObjects",
                op=DiffOpType.OBJ_APPEND,
                obj_name=vc.get("name"),
                obj_data={
                    "name": vc.get("name"),
                    "displayName": vc.get("displayName"),
                    "alias": None,
                    "referencedAggregateName": None,
                    "referencedAggregateField": None,
                    "fields": vc.get("fields") or [],
                },
            ))
        elif vc.get("type") == "REMOVED":
            old_vo = next(
                (v for v in (before_detail.get("valueObjects") or [])
                 if v.get("name") == vc.get("name")), None
            )
            ops.append(DiffOp(
                field="valueObjects",
                op=DiffOpType.OBJ_REMOVE,
                obj_name=vc.get("name"),
                obj_data=old_vo,  # undo 시 복원용
            ))

    # 3. Enumeration 변경
    for ec in struct_diff.get("enumChanges") or []:
        enum_name = ec.get("enumName")
        if ec.get("type") == "ADDED":
            ops.append(DiffOp(
                field="enumerations",
                op=DiffOpType.OBJ_APPEND,
                obj_name=enum_name,
                obj_data={
                    "name": enum_name,
                    "displayName": enum_name,
                    "alias": None,
                    "items": ec.get("addedItems") or [],
                },
            ))
        else:
            if ec.get("addedItems"):
                ops.append(DiffOp(
                    field="enumerations",
                    op=DiffOpType.ENUM_ADD_ITEMS,
                    enum_name=enum_name,
                    items=ec["addedItems"],
                ))
            if ec.get("removedItems"):
                ops.append(DiffOp(
                    field="enumerations",
                    op=DiffOpType.ENUM_REMOVE_ITEMS,
                    enum_name=enum_name,
                    items=ec["removedItems"],
                ))

    # 4. Invariant 추가
    new_invs = struct_diff.get("invariantChanges") or []
    if new_invs:
        ops.append(DiffOp(
            field="invariants",
            op=DiffOpType.LIST_APPEND,
            items=new_invs,
        ))

    return ops


def _build_ops_text_only(
    before_text: str, after_text: str, field: str, node_label: str
) -> list[DiffOp]:
    """텍스트 전용 노드(UserStory, Feature, BC)의 DiffOp 생성."""
    ops: list[DiffOp] = []
    if field == "acceptanceCriteria" and node_label == "UserStory":
        # acceptanceCriteria: Neo4j list — 줄 단위 비교
        def _to_list(v: str) -> list[str]:
            if not v:
                return []
            try:
                parsed = json.loads(v) if v.startswith("[") else None
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
            except Exception:
                pass
            return [line.strip() for line in v.splitlines() if line.strip()]

        old_list = _to_list(before_text)
        new_list = _to_list(after_text)
        added   = [x for x in new_list if x not in old_list]
        removed = [x for x in old_list if x not in new_list]
        if added:
            ops.append(DiffOp(field=field, op=DiffOpType.LIST_APPEND, items=added))
        if removed:
            ops.append(DiffOp(field=field, op=DiffOpType.LIST_REMOVE, items=removed))
        if not added and not removed and after_text != before_text:
            # 내용은 바뀌었지만 항목 단위로 파악 불가 → replace
            ops.append(DiffOp(field=field, op=DiffOpType.REPLACE,
                              from_val=before_text, to_val=after_text))
    else:
        if after_text and after_text != before_text:
            ops.append(DiffOp(field=field, op=DiffOpType.REPLACE,
                              from_val=before_text, to_val=after_text))
    return ops


# ── 구조적 변경 적용 (Neo4j) ──────────────────────────────────────────────

def _apply_struct_ops(node_id: str, node_label: str, ops: list[DiffOp], detail: dict) -> None:
    """DiffOp 목록을 Neo4j 구조 필드에 실제 반영한다."""
    new_vos   = list(detail.get("valueObjects")  or [])
    new_enums = list(detail.get("enumerations")  or [])
    new_invs  = list(detail.get("invariants")    or [])
    dirty = False

    for op in ops:
        if op.field == "valueObjects":
            if op.op == DiffOpType.OBJ_APPEND and op.obj_data:
                if not any(v.get("name") == op.obj_name for v in new_vos):
                    new_vos.append(op.obj_data)
                    dirty = True
            elif op.op == DiffOpType.OBJ_REMOVE:
                before_len = len(new_vos)
                new_vos = [v for v in new_vos if v.get("name") != op.obj_name]
                if len(new_vos) < before_len:
                    dirty = True

        elif op.field == "enumerations":
            if op.op == DiffOpType.OBJ_APPEND and op.obj_data:
                if not any(e.get("name") == op.obj_name for e in new_enums):
                    new_enums.append(op.obj_data)
                    dirty = True
            else:
                enum = next((e for e in new_enums if e.get("name") == op.enum_name), None)
                if enum:
                    items = list(enum.get("items") or [])
                    if op.op == DiffOpType.ENUM_ADD_ITEMS:
                        for item in (op.items or []):
                            if item not in items:
                                items.append(item)
                                dirty = True
                    elif op.op == DiffOpType.ENUM_REMOVE_ITEMS:
                        before_len = len(items)
                        items = [x for x in items if x not in (op.items or [])]
                        if len(items) < before_len:
                            dirty = True
                    enum["items"] = items

        elif op.field == "invariants":
            if op.op == DiffOpType.LIST_APPEND:
                for inv in (op.items or []):
                    if inv not in new_invs:
                        new_invs.append(inv)
                        dirty = True

    if dirty:
        with get_session() as session:
            session.run(
                f"MATCH (n:{node_label}) WHERE n.id = $id "
                "SET n.valueObjects = $vo, n.enumerations = $enums, n.invariants = $inv",
                id=node_id,
                vo=json.dumps(new_vos,   ensure_ascii=False),
                enums=json.dumps(new_enums, ensure_ascii=False),
                inv=new_invs,
            )


# ── undo 역방향 적용 ───────────────────────────────────────────────────────

async def reverse_semantic_diff(
    node_id: str, node_label: str, diff: SemanticDiff
) -> dict:
    """
    SemanticDiff를 역방향으로 적용하여 노드를 복원한다.
    CREATE 유형은 생성된 노드를 삭제한다.
    반환: {"reverted": True/False, "errors": [...]}
    """
    # ── CREATE 유형: 생성된 노드 삭제 ────────────────────────────────
    if diff.changeType == "CREATE":
        errors: list[str] = []
        if diff.createdNodeId:
            label_map = {
                "UserStory": "UserStory",
                "Feature": "Feature",
                "BoundedContext": "BoundedContext",
            }
            label = label_map.get(diff.nodeLabel, diff.nodeLabel)
            try:
                with get_session() as session:
                    session.run(
                        f"MATCH (n:{label} {{id: $id}}) DETACH DELETE n",
                        id=diff.createdNodeId,
                    )
            except Exception as e:
                errors.append(f"삭제 실패({diff.createdNodeId}): {e}")
        # EFFECT.appliedNodeId / diff / appliedAt 초기화 (CreationIntent는 보존)
        try:
            with get_session() as session:
                session.run(
                    "MATCH ()-[e:EFFECT]->(ci:CreationIntent {id: $pid}) "
                    "REMOVE e.appliedNodeId, e.diff, e.appliedAt",
                    pid=node_id,
                )
        except Exception as e:
            errors.append(f"EFFECT 초기화 실패: {e}")
        return {"reverted": not errors, "errors": errors}

    # ── MODIFY 유형: ops 역방향 복원 ─────────────────────────────────
    errors: list[str] = []

    # 현재 노드 상태 조회
    field_map_rev = _FIELD_MAP.get(node_label)
    struct_detail = {}
    if node_label in _DESIGN_LABELS:
        struct_detail = _fetch_design_node_detail(node_id, node_label)

    for op in reversed(diff.ops):  # ops를 역순으로 처리
        try:
            if op.op == DiffOpType.REPLACE:
                # 현재 값 조회
                with get_session() as session:
                    row = session.run(
                        f"MATCH (n:{node_label}) WHERE n.id = $id "
                        f"RETURN n.{op.field} AS v",
                        id=node_id,
                    ).single()
                current = _to_str(row["v"] if row else "")
                restored = await _ai_undo_text(
                    op.field, node_label, diff.nodeTitle,
                    from_val=op.from_val or "",
                    to_val=op.to_val or "",
                    current_val=current,
                )
                _update_node_field(node_id, node_label, op.field, restored)

            elif op.op == DiffOpType.LIST_APPEND:
                # 추가된 항목 제거
                with get_session() as session:
                    row = session.run(
                        f"MATCH (n:{node_label}) WHERE n.id = $id "
                        f"RETURN n.{op.field} AS v",
                        id=node_id,
                    ).single()
                current_list = _parse_json(_to_str(row["v"] if row else "")) or []
                if isinstance(current_list, str):
                    current_list = [x.strip() for x in current_list.splitlines() if x.strip()]
                removed_items = set(op.items or [])
                new_list = [x for x in current_list if x not in removed_items]
                _update_node_field(node_id, node_label, op.field, new_list)

            elif op.op == DiffOpType.LIST_REMOVE:
                # 제거된 항목 복원
                with get_session() as session:
                    row = session.run(
                        f"MATCH (n:{node_label}) WHERE n.id = $id "
                        f"RETURN n.{op.field} AS v",
                        id=node_id,
                    ).single()
                current_list = _parse_json(_to_str(row["v"] if row else "")) or []
                if isinstance(current_list, str):
                    current_list = [x.strip() for x in current_list.splitlines() if x.strip()]
                for item in (op.items or []):
                    if item not in current_list:
                        current_list.append(item)
                _update_node_field(node_id, node_label, op.field, current_list)

            elif op.op == DiffOpType.OBJ_APPEND:
                # 추가된 객체 제거
                struct_detail = _fetch_design_node_detail(node_id, node_label)
                arr = list(_parse_json(struct_detail.get(op.field)) or [])
                arr = [x for x in arr if x.get("name") != op.obj_name]
                _update_node_field(node_id, node_label, op.field,
                                   json.dumps(arr, ensure_ascii=False))

            elif op.op == DiffOpType.OBJ_REMOVE:
                # 제거된 객체 복원
                struct_detail = _fetch_design_node_detail(node_id, node_label)
                arr = list(_parse_json(struct_detail.get(op.field)) or [])
                if op.obj_data and not any(x.get("name") == op.obj_name for x in arr):
                    arr.append(op.obj_data)
                _update_node_field(node_id, node_label, op.field,
                                   json.dumps(arr, ensure_ascii=False))

            elif op.op == DiffOpType.ENUM_ADD_ITEMS:
                struct_detail = _fetch_design_node_detail(node_id, node_label)
                enums = list(_parse_json(struct_detail.get("enumerations")) or [])
                enum = next((e for e in enums if e.get("name") == op.enum_name), None)
                if enum:
                    items = list(enum.get("items") or [])
                    items = [x for x in items if x not in (op.items or [])]
                    enum["items"] = items
                _update_node_field(node_id, node_label, "enumerations",
                                   json.dumps(enums, ensure_ascii=False))

            elif op.op == DiffOpType.ENUM_REMOVE_ITEMS:
                struct_detail = _fetch_design_node_detail(node_id, node_label)
                enums = list(_parse_json(struct_detail.get("enumerations")) or [])
                enum = next((e for e in enums if e.get("name") == op.enum_name), None)
                if enum:
                    items = list(enum.get("items") or [])
                    for item in (op.items or []):
                        if item not in items:
                            items.append(item)
                    enum["items"] = items
                _update_node_field(node_id, node_label, "enumerations",
                                   json.dumps(enums, ensure_ascii=False))

        except Exception as e:
            errors.append(f"{op.op}:{op.field} — {e}")

    return {"reverted": not errors, "errors": errors}


# ── 메인 apply 제너레이터 ──────────────────────────────────────────────────

async def apply_design_changes(
    change_id: str,
    original_prompt: str,
) -> AsyncGenerator[dict, None]:
    """
    EFFECT 대상 노드들의 설계를 AI로 업데이트하고,
    각 EFFECT 관계에 SemanticDiff를 저장한다.
    """
    effects = _fetch_effects(change_id)
    prompt  = original_prompt or _fetch_change_prompt(change_id)

    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    effects.sort(key=lambda e: order.get(e.get("impactLevel", "LOW"), 3))

    total   = len(effects)
    applied = 0

    yield {"phase": "applying", "total": total,
           "message": f"총 {total}개 노드 설계 반영 시작..."}

    for i, node in enumerate(effects):
        node_id    = node["nodeId"]
        node_label = node.get("nodeLabel", "")
        change_type = node.get("changeType", "MODIFY")

        # ── CREATE 유형: 신규 노드 생성 경로 ─────────────────────────
        if change_type == "CREATE":
            yield {
                "phase":      "item_start",
                "index":      i,
                "nodeId":     node_id,
                "nodeLabel":  node_label,
                "nodeTitle":  node.get("nodeTitle", ""),
                "changeType": "CREATE",
                "impactLevel": node.get("impactLevel", "MEDIUM"),
                "message":    f"[{i+1}/{total}] {node_label} 신규 생성 중...",
            }
            try:
                result = await _apply_create_effect(change_id, node)
                if "error" in result:
                    yield {"phase": "item_error", "index": i,
                           "nodeId": node_id, "message": result["error"]}
                else:
                    applied += 1
                    yield {
                        "phase": "item_done",
                        "index": i,
                        "item": {
                            **result,
                            "impactLevel": node.get("impactLevel", "MEDIUM"),
                            "appliedAt": _now_iso(),
                        },
                        "message": f"✦ 신규 {node_label} 생성 완료 ({result.get('createdNodeId', '')})",
                    }
            except Exception as e:
                yield {"phase": "item_error", "index": i,
                       "nodeId": node_id, "message": f"신규 노드 생성 실패: {e}"}
            continue

        # ── MODIFY 유형: 기존 노드 업데이트 경로 ─────────────────────
        field = _FIELD_MAP.get(node_label)
        if not field:
            yield {"phase": "item_skipped", "index": i,
                   "nodeId": node_id, "nodeLabel": node_label,
                   "reason": "설계 반영 대상 노드 유형이 아님"}
            continue

        before_text = node.get("currentContent", "")
        yield {
            "phase":       "item_start",
            "index":       i,
            "nodeId":      node_id,
            "nodeLabel":   node_label,
            "nodeTitle":   node.get("nodeTitle", ""),
            "field":       field,
            "before":      before_text,
            "impactLevel": node.get("impactLevel", "MEDIUM"),
            "message":     f"[{i+1}/{total}] {node_label}: {node.get('nodeTitle', node_id)} 반영 중...",
        }

        after_text = await _generate_text_update(prompt, node, field)
        if not after_text:
            yield {"phase": "item_skipped", "index": i,
                   "nodeId": node_id, "nodeLabel": node_label, "reason": "변경 불필요"}
            continue

        try:
            # ── 텍스트 필드 업데이트 ──────────────────────────
            _update_node_field(node_id, node_label, field, after_text)
            applied += 1

            # ── 구조적 분석 및 적용 (Design 레이어) ──────────
            struct_diff_json: dict | None = None
            ops: list[DiffOp] = []

            if node_label in _DESIGN_LABELS:
                yield {"phase": "item_struct_start", "index": i,
                       "nodeId": node_id,
                       "message": "  → 필드/ValueObject 변경 분석 및 반영 중..."}
                detail = _fetch_design_node_detail(node_id, node_label)
                struct_diff_json = await _generate_struct_diff_json(prompt, node, detail)
                if struct_diff_json:
                    ops = _build_ops_from_struct(
                        detail, struct_diff_json, before_text, after_text, field
                    )
                    _apply_struct_ops(node_id, node_label, ops, detail)
                else:
                    ops = _build_ops_text_only(before_text, after_text, field, node_label)
            else:
                ops = _build_ops_text_only(before_text, after_text, field, node_label)

            # ── SemanticDiff 저장 (EFFECT 관계) ──────────────
            semantic_diff = SemanticDiff(
                nodeLabel=node_label,
                nodeTitle=node.get("nodeTitle", ""),
                appliedAt=_now_iso(),
                ops=ops,
            )
            _store_diff_in_effect(change_id, node_id, semantic_diff)

            yield {
                "phase": "item_done",
                "index": i,
                "item": {
                    "nodeId":      node_id,
                    "nodeLabel":   node_label,
                    "nodeTitle":   node.get("nodeTitle", ""),
                    "field":       field,
                    "before":      before_text,
                    "after":       after_text,
                    "impactLevel": node.get("impactLevel", "MEDIUM"),
                    "appliedAt":   semantic_diff.appliedAt,
                    # 구조화 diff (프론트 렌더링용)
                    "fieldChanges":
                        struct_diff_json.get("fieldChanges") if struct_diff_json else None,
                    "valueObjectChanges":
                        struct_diff_json.get("valueObjectChanges") if struct_diff_json else None,
                    "enumChanges":
                        struct_diff_json.get("enumChanges") if struct_diff_json else None,
                    "invariantChanges":
                        struct_diff_json.get("invariantChanges") if struct_diff_json else None,
                    "semanticDiff": semantic_diff.model_dump(),
                },
                "message": f"✓ {node.get('nodeTitle', node_id)} 업데이트 완료",
            }

        except Exception as e:
            yield {"phase": "item_error", "index": i,
                   "nodeId": node_id, "message": f"업데이트 실패: {e}"}

    yield {"phase": "applying_done", "applied": applied, "total": total}
