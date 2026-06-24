"""042 US4 — 지속 전략 메모리 승격 + 충돌 감지.

지속 결정(차별성/Core·Supporting·Generic/결합 posture/유비쿼터스 언어)은 한 번
Constitution 의 strategicMemory 로 승격되어 후속 Proposal 이 재사용한다(FR-016~018).
로컬 결정이 메모리와 어긋나면 충돌로 surface 하고, amend-or-justify 없이는 진행 불가(FR-019).
변경별 전술 상세(이벤트/Aggregate/invariant)는 절대 승격하지 않는다(FR-020).
"""

from __future__ import annotations

import json
from typing import Optional

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger
from api.features.constitution.services import constitution_store as cstore


# --- 충돌 감지 --------------------------------------------------------------

def detect_conflicts(proposal_id: str, stage: str, artifact: dict) -> list[dict]:
    """스테이지 결정 vs 기존 메모리 비교 → MemoryConflict dict 목록(UNRESOLVED)."""
    memory = cstore.get_project_strategic_memory() or {}
    conflicts: list[dict] = []

    if stage == "STRATEGIZE":
        ctxs = memory.get("contexts") or {}
        for c in artifact.get("classifications", []) or []:
            name = c.get("subDomain")
            new_kind = c.get("kind")
            recorded = (ctxs.get(name) or {}).get("classification")
            if recorded and new_kind and recorded != new_kind:
                conflicts.append({
                    "bcId": name, "field": "classification",
                    "memoryValue": recorded, "proposalValue": new_kind,
                    "resolution": "UNRESOLVED", "justification": None,
                })

    elif stage == "CONNECT":
        default = (memory.get("couplingPosture") or {}).get("default")
        if default == "PUBSUB":
            for it in artifact.get("interactions", []) or []:
                if it.get("sync") and it.get("kind") != "EVENT":
                    pair = f"{it.get('from')}→{it.get('to')}:{it.get('message')}"
                    conflicts.append({
                        "bcId": None, "field": "couplingPosture",
                        "memoryValue": "PUBSUB", "proposalValue": f"SYNC ({pair})",
                        "resolution": "UNRESOLVED", "justification": None,
                    })

    return conflicts


# --- 확정 적용(충돌 게이트 + 승격) ------------------------------------------

def apply_stage_confirmation(proposal_id: str, stage: str, artifact: dict,
                             resolutions: list[dict]) -> Optional[dict]:
    """확정 시 호출. 미해결 충돌이 있으면 error dict 반환(409), 아니면 메모리 승격.

    resolutions: [{bcId, field, resolution: AMEND_MEMORY|JUSTIFY_LOCAL, justification?}]
    """
    conflicts = detect_conflicts(proposal_id, stage, artifact)
    res_map = {(r.get("bcId"), r.get("field")): r for r in (resolutions or [])}

    unresolved = []
    justify_skip: set = set()   # (bcId, field) — 로컬 예외로 메모리 보존
    for c in conflicts:
        key = (c.get("bcId"), c.get("field"))
        r = res_map.get(key)
        if not r or r.get("resolution") not in ("AMEND_MEMORY", "JUSTIFY_LOCAL"):
            unresolved.append(c)
        elif r.get("resolution") == "JUSTIFY_LOCAL":
            justify_skip.add(key)
            c["resolution"] = "JUSTIFY_LOCAL"
            c["justification"] = r.get("justification")
        else:
            c["resolution"] = "AMEND_MEMORY"

    if unresolved:
        return {"reason": "unresolved_conflicts", "conflicts": unresolved,
                "message": "메모리와 충돌하는 결정은 amend-or-justify 가 필요합니다."}

    # 감사 로그: 해소된 충돌을 Proposal 에 기록.
    if conflicts:
        _record_conflicts(proposal_id, conflicts)

    # 지속 섹션 승격(JUSTIFY_LOCAL 필드는 메모리 보존 → skip).
    promote(stage, artifact, justify_skip)
    return None


def promote(stage: str, artifact: dict, skip: Optional[set] = None) -> None:
    """스테이지의 지속 결정만 strategicMemory 로 승격(FR-016/FR-020).

    전술 상세(이벤트/Aggregate/invariant)는 Tactical 단계라도 승격하지 않는다.
    """
    skip = skip or set()
    if stage not in ("STRATEGIZE", "CONNECT", "DEFINE"):
        return  # Discover/Decompose/Tactical 의 산출물은 지속 메모리에 올리지 않음.

    memory = cstore.get_project_strategic_memory() or {"version": 1, "contexts": {}}
    memory.setdefault("contexts", {})

    if stage == "STRATEGIZE":
        for c in artifact.get("classifications", []) or []:
            name = c.get("subDomain")
            if not name or (name, "classification") in skip:
                continue
            ctx = memory["contexts"].setdefault(name, {})
            ctx["classification"] = c.get("kind")
            ctx["rationale"] = c.get("rationale")
            if c.get("buildVsBuy"):
                ctx["buildVsBuy"] = c.get("buildVsBuy")
        # 선택: strategize 산출물이 차별성을 담으면 루트 differentiation 시드.
        if artifact.get("differentiation"):
            memory["differentiation"] = artifact["differentiation"]

    elif stage == "CONNECT":
        if (None, "couplingPosture") not in skip:
            interactions = artifact.get("interactions", []) or []
            sync_n = sum(1 for it in interactions if it.get("sync"))
            default = "SYNC" if interactions and sync_n > len(interactions) / 2 else "PUBSUB"
            memory["couplingPosture"] = {
                "default": default,
                "rationale": "Connect 단계 분석에서 도출",
                "pairs": [{"from": it.get("from"), "to": it.get("to"),
                           "kind": it.get("kind"), "sync": bool(it.get("sync"))}
                          for it in interactions],
            }

    elif stage == "DEFINE":
        for c in artifact.get("contexts", []) or []:
            name = c.get("name")
            if not name:
                continue
            ctx = memory["contexts"].setdefault(name, {})
            ctx["purpose"] = c.get("purpose")
            ctx["domainRoles"] = c.get("domainRoles", [])
            ctx["ubiquitousLanguage"] = c.get("ubiquitousLanguage", [])
            ctx["businessDecisions"] = c.get("businessDecisions", [])
            if c.get("classification"):
                ctx.setdefault("classification", c.get("classification"))

    cstore.upsert_project_strategic_memory(memory)
    SmartLogger.log("INFO", f"strategic memory promoted from {stage}",
                    category="proposal_lifecycle.staged.memory_promote",
                    params={"stage": stage})


def _record_conflicts(proposal_id: str, conflicts: list[dict]) -> None:
    with get_session() as session:
        rec = session.run("MATCH (p:Proposal {id:$id}) RETURN p.memoryConflicts AS mc",
                          id=proposal_id).single()
    existing = []
    if rec and rec.get("mc"):
        try:
            existing = json.loads(rec["mc"])
        except Exception:
            existing = []
    existing.extend(conflicts)
    with get_session() as session:
        session.run("MATCH (p:Proposal {id:$id}) SET p.memoryConflicts=$mc",
                    id=proposal_id, mc=json.dumps(existing, ensure_ascii=False))
