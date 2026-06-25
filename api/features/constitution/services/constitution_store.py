"""
041 — Constitution 그래프 저장소 (Neo4j).

- 프로젝트 루트 헌장: 싱글톤 (:Constitution {scope:'PROJECT', id:'CON-ROOT'})
- BC 오버라이드: (:BoundedContext {id})-[:HAS_CONSTITUTION]->(:Constitution {scope:'BOUNDED_CONTEXT'})
- BC 유효(effective) 헌장 = 프로젝트 루트 + 해당 BC 오버라이드 병합(BC 우선).

레포 파일/프로포절 사본 아님 — 그래프가 원천(Principle I).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

ROOT_ID = "CON-ROOT"
_FIELD_KEYS = ["designPrinciples", "techStack", "architectureStyle", "repoStrategy", "repoMode"]


def constitution_hash(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_memory(raw) -> Optional[dict]:
    """042 — strategicMemory 속성을 dict 로 파싱(없으면 None)."""
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return None


def _combined_hash(raw: Optional[str], memory: Optional[dict]) -> Optional[str]:
    """042 — staleness 판정용 해시. 헌장 본문 + 전략 메모리를 함께 해싱해
    전략 메모리만 바뀌어도(FR-021) 해시가 달라지게 한다."""
    if not raw and not memory:
        return None
    mem_str = json.dumps(memory, ensure_ascii=False, sort_keys=True) if memory else ""
    return hashlib.sha256(((raw or "") + "\x00" + mem_str).encode("utf-8")).hexdigest()


def parse_fields_from_raw(raw: Optional[str]) -> dict:
    """헌장 Markdown 본문에서 핵심 결정값을 best-effort 추출(필드 입력 폐지 → 선언만).

    구조화 입력이 없으므로 plan 단계가 참고할 수 있도록 노드 속성을 느슨히 채운다.
    """
    out = {k: None for k in _FIELD_KEYS}
    if not raw:
        return out
    low = raw.lower()
    if "microservice" in low or "마이크로서비스" in raw:
        out["architectureStyle"] = "MICROSERVICES"
    elif "monolith" in low or "모놀리" in raw:
        out["architectureStyle"] = "MONOLITH"
    if "repo_per_service" in low or "repo per service" in low or "서비스별 레포" in raw:
        out["repoStrategy"] = "REPO_PER_SERVICE"
    elif "mono_repo" in low or "mono-repo" in low or "monorepo" in low or "모노레포" in raw:
        out["repoStrategy"] = "MONOREPO"
    if "split_git" in low or "split git" in low:
        out["repoMode"] = "SPLIT_GIT"
    elif "reuse" in low or "재사용" in raw:
        out["repoMode"] = "REUSE_EXISTING"
    return out


def _node_to_dict(node) -> Optional[dict]:
    if not node:
        return None
    d = dict(node)
    fields = {k: d.get(k) for k in _FIELD_KEYS}
    memory = _parse_memory(d.get("strategicMemory"))
    return {
        "id": d.get("id"),
        "scope": d.get("scope"),
        "raw": d.get("raw"),
        "fields": fields,
        # 042 — staleness 와 일관되도록 raw + strategicMemory 결합 해시를 노출.
        "constitutionHash": _combined_hash(d.get("raw"), memory),
        "strategicMemory": memory,
        "updatedAt": d.get("updatedAt"),
        **fields,
    }


def get_project_constitution() -> Optional[dict]:
    with get_session() as session:
        rec = session.run(
            "MATCH (c:Constitution {scope:'PROJECT', id:$id}) RETURN c", id=ROOT_ID
        ).single()
    return _node_to_dict(rec["c"]) if rec else None


def project_constitution_raw() -> Optional[str]:
    c = get_project_constitution()
    return c.get("raw") if c else None


def project_constitution_hash() -> Optional[str]:
    """042 — 프로젝트 헌장 본문 + 전략 메모리 결합 해시(staleness 원천)."""
    c = get_project_constitution()
    if not c:
        return None
    return _combined_hash(c.get("raw"), c.get("strategicMemory"))


def get_project_strategic_memory() -> Optional[dict]:
    c = get_project_constitution()
    return c.get("strategicMemory") if c else None


def _mark_proposals_stale(new_hash: Optional[str]) -> None:
    """프로젝트 헌장이 바뀌면 모든 Proposal 의 constitutionHash 를 최신으로 올려,
    확정 plan 의 스냅샷 해시와 불일치하게 만들어 staleness 를 유발한다(FR-018)."""
    if not new_hash:
        return
    with get_session() as session:
        session.run("MATCH (p:Proposal) SET p.constitutionHash = $h", h=new_hash)


def upsert_project_constitution(raw: str, fields: Optional[dict] = None,
                                strategic_memory: Optional[dict] = None) -> str:
    # 필드 입력은 폐지됨 — fields 가 비면 Markdown 본문에서 best-effort 유도.
    fields = fields or parse_fields_from_raw(raw)
    now = datetime.now(timezone.utc).isoformat()
    params = {"id": ROOT_ID, "raw": raw, "updatedAt": now}
    for k in _FIELD_KEYS:
        params[k] = fields.get(k)
    set_fields = ", ".join([f"c.{k} = ${k}" for k in _FIELD_KEYS])
    # strategic_memory 가 주어지면 갱신, 아니면 기존 값을 보존(다른 경로가 관리).
    mem_clause = ""
    if strategic_memory is not None:
        params["strategicMemory"] = json.dumps(strategic_memory, ensure_ascii=False)
        mem_clause = ", c.strategicMemory = $strategicMemory"
    with get_session() as session:
        session.run(
            f"""
            MERGE (c:Constitution {{id:$id}})
            SET c.scope='PROJECT', c.raw=$raw, c.updatedAt=$updatedAt, {set_fields}{mem_clause}
            """,
            **params,
        )
    h = project_constitution_hash() or ""
    _mark_proposals_stale(h)
    SmartLogger.log("INFO", "project constitution upserted",
                    category="constitution.project.upsert", params={"hash": h[:8]})
    return h


def upsert_project_strategic_memory(memory: dict) -> str:
    """042 — 프로젝트 루트 전략 메모리만 갱신(헌장 본문은 보존). 해시 변동 → staleness."""
    now = datetime.now(timezone.utc).isoformat()
    with get_session() as session:
        session.run(
            """
            MERGE (c:Constitution {id:$id})
            SET c.scope='PROJECT', c.updatedAt=$updatedAt,
                c.strategicMemory = $mem
            """,
            id=ROOT_ID, updatedAt=now,
            mem=json.dumps(memory, ensure_ascii=False),
        )
    h = project_constitution_hash() or ""
    _mark_proposals_stale(h)
    SmartLogger.log("INFO", "project strategic memory upserted",
                    category="constitution.project.memory", params={"hash": h[:8]})
    return h


def upsert_bc_strategic_memory(bc_id: str, memory: dict) -> str:
    """042 — BC 오버라이드 노드의 전략 메모리만 갱신. BC 없으면 no-op 반환."""
    now = datetime.now(timezone.utc).isoformat()
    with get_session() as session:
        session.run(
            """
            MATCH (bc:BoundedContext {id:$bcId})
            MERGE (bc)-[:HAS_CONSTITUTION]->(c:Constitution {id:$cid})
            SET c.scope='BOUNDED_CONTEXT', c.updatedAt=$updatedAt,
                c.strategicMemory = $mem
            """,
            bcId=bc_id, cid=f"CON-{bc_id}", updatedAt=now,
            mem=json.dumps(memory, ensure_ascii=False),
        )
    # BC 메모리 변동도 프로젝트 plan staleness 를 유발(루트 해시는 그대로지만,
    # 보수적으로 전체를 stale 처리해 plan↔전략 불일치를 막는다, FR-021).
    _mark_proposals_stale(project_constitution_hash() or "BC-MEMORY-CHANGED")
    SmartLogger.log("INFO", "bc strategic memory upserted",
                    category="constitution.bc.memory", params={"bcId": bc_id})
    return f"CON-{bc_id}"


def get_bc_override(bc_id: str) -> Optional[dict]:
    with get_session() as session:
        rec = session.run(
            "MATCH (:BoundedContext {id:$bcId})-[:HAS_CONSTITUTION]->(c:Constitution) RETURN c",
            bcId=bc_id,
        ).single()
    return _node_to_dict(rec["c"]) if rec else None


# BC 오버라이드에 들어갈 수 없는 프로젝트-레벨 결정(레포/마이크로서비스).
_PROJECT_ONLY_KEYS = {"architectureStyle", "repoStrategy", "repoMode"}


def upsert_bc_override(bc_id: str, raw: Optional[str] = None, fields: Optional[dict] = None) -> str:
    # BC 헌장은 레포/마이크로서비스 결정을 가질 수 없다(프로젝트 루트 전용). 들어와도 제거.
    fields = {k: v for k, v in (fields or {}).items() if k not in _PROJECT_ONLY_KEYS}
    now = datetime.now(timezone.utc).isoformat()
    h = constitution_hash(raw) or ""
    params = {"bcId": bc_id, "cid": f"CON-{bc_id}", "raw": raw, "updatedAt": now}
    for k in _FIELD_KEYS:
        params[k] = fields.get(k)
    set_fields = ", ".join([f"c.{k} = ${k}" for k in _FIELD_KEYS])
    with get_session() as session:
        session.run(
            f"""
            MATCH (bc:BoundedContext {{id:$bcId}})
            MERGE (bc)-[:HAS_CONSTITUTION]->(c:Constitution {{id:$cid}})
            SET c.scope='BOUNDED_CONTEXT', c.raw=$raw, c.updatedAt=$updatedAt, {set_fields}
            """,
            **params,
        )
    SmartLogger.log("INFO", "bc constitution upserted",
                    category="constitution.bc.upsert", params={"bcId": bc_id})
    return h


def delete_bc_override(bc_id: str) -> None:
    with get_session() as session:
        session.run(
            "MATCH (:BoundedContext {id:$bcId})-[:HAS_CONSTITUTION]->(c:Constitution) DETACH DELETE c",
            bcId=bc_id,
        )


def effective_for_bc(bc_id: str) -> dict:
    """프로젝트 루트 + BC 오버라이드 병합(BC 우선, 값이 있는 필드만 덮어씀)."""
    root = get_project_constitution() or {"fields": {k: None for k in _FIELD_KEYS}, "raw": None}
    override = get_bc_override(bc_id)
    merged = dict(root.get("fields") or {})
    if override:
        for k in _FIELD_KEYS:
            v = (override.get("fields") or {}).get(k)
            if v is not None and v != "":
                merged[k] = v
    raw = (override.get("raw") if override and override.get("raw") else root.get("raw"))

    # 042 — 전략 메모리 병합: differentiation/couplingPosture 는 루트 전용,
    # contexts 는 섹션(BC키)별로 BC 오버라이드가 루트를 덮어쓴다.
    root_mem = root.get("strategicMemory") or {}
    over_mem = (override.get("strategicMemory") if override else None) or {}
    merged_contexts = dict(root_mem.get("contexts") or {})
    for k, v in (over_mem.get("contexts") or {}).items():
        merged_contexts[k] = v
    merged_memory = {
        "version": root_mem.get("version", 1),
        "differentiation": root_mem.get("differentiation"),
        "couplingPosture": root_mem.get("couplingPosture"),
        "contexts": merged_contexts,
    }

    return {
        "fields": merged,
        "raw": raw,
        "constitutionHash": _combined_hash(raw, merged_memory),
        "strategicMemory": merged_memory,
        "hasOverride": override is not None,
        **merged,
    }
