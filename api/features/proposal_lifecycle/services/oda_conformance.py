"""043 — ODA 적합성 게이트(차단형).

"준수 후 확장(comply-then-extend)" 거버넌스를 강제한다(FR-006/007/008). 하드 규칙 위반이
있으면 게이트 FAIL → plan/submit 진행 차단, 아키텍트가 명시 면제(waive)해야만 통과.

순수 평가 함수(`evaluate_gate`/`all_classified`/`can_proceed`)는 LLM/DB 비의존이라 단위
테스트의 핵심이다. 영속/강제 함수(`apply_waiver`/`ensure_can_proceed`)만 Neo4j 를 만진다.

스킬=에이전트, 백엔드=게이트(Principle X). 면제는 사람 확정 게이트(Principle IV).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger

VALID_CLASSIFICATIONS = {"REUSE", "EXTEND", "NEW"}


# --- 순수 평가 로직 ---------------------------------------------------------

def evaluate_gate(report: Optional[dict]) -> dict:
    """적합성 리포트를 평가해 게이트 결과를 돌려준다.

    하드 위반(violations 비어있지 않음)이면 FAIL, 아니면 PASS. 이미 면제(waiver) 처리된
    FAIL 은 WAIVED 로 본다. report 가 없으면 PENDING(아직 미산출).
    """
    if not report:
        return {"result": "PENDING", "blocking": False, "violations": []}

    violations = report.get("violations") or []
    waiver = report.get("waiver")

    if violations:
        if waiver and waiver.get("reason"):
            return {"result": "WAIVED", "blocking": False, "violations": violations}
        return {"result": "FAIL", "blocking": True, "violations": violations}
    return {"result": "PASS", "blocking": False, "violations": []}


def all_classified(report: Optional[dict]) -> bool:
    """모든 적합성 항목이 REUSE/EXTEND/NEW 중 하나로 분류되었는지(FR-004/SC-003)."""
    if not report:
        return False
    items = report.get("items") or []
    if not items:
        return False
    return all((it.get("classification") in VALID_CLASSIFICATIONS) for it in items)


def can_proceed(report: Optional[dict]) -> bool:
    """plan/submit 진행 가능 여부 — PASS 또는 WAIVED 만 허용(FR-007)."""
    return evaluate_gate(report)["result"] in ("PASS", "WAIVED")


# --- 영속 / 강제 ------------------------------------------------------------

def _load(proposal_id: str) -> Optional[dict]:
    with get_session() as session:
        rec = session.run(
            "MATCH (p:Proposal {id:$id}) RETURN "
            "p.decompositionMode AS mode, p.odaConformance AS conf",
            id=proposal_id,
        ).single()
    if not rec:
        return None
    try:
        conf = json.loads(rec.get("conf")) if rec.get("conf") else None
    except Exception:
        conf = None
    return {"mode": rec.get("mode") or "SIMPLIFIED", "conformance": conf}


def apply_waiver(proposal_id: str, reason: str) -> Optional[dict]:
    """FAIL 게이트를 명시 면제하고 사유를 기록(FR-008). 위반이 없으면 422.

    반환: 오류 dict 또는 None(성공).
    """
    state = _load(proposal_id)
    if state is None:
        return {"reason": "not_found"}
    report = state.get("conformance")
    gate = evaluate_gate(report)
    if gate["result"] != "FAIL":
        # 면제할 위반이 없음 — 차단 상태가 아니면 면제 불필요.
        return {"reason": "nothing_to_waive", "gateResult": gate["result"]}

    report = dict(report or {})
    report["waiver"] = {"reason": reason, "at": datetime.now(timezone.utc).isoformat()}
    report["gateResult"] = "WAIVED"
    with get_session() as session:
        session.run(
            "MATCH (p:Proposal {id:$id}) SET p.odaConformance=$conf",
            id=proposal_id, conf=json.dumps(report, ensure_ascii=False),
        )
    SmartLogger.log("INFO", f"oda conformance waived: {proposal_id}",
                    category="proposal_lifecycle.oda.waive",
                    params={"proposalId": proposal_id})
    return None


def ensure_can_proceed(proposal_id: str) -> Optional[dict]:
    """ODA 모드 Proposal 이 plan/submit 으로 진행 가능한지 강제(FR-007).

    ODA 모드가 아니면 통과(None). ODA 모드인데 게이트가 차단 상태면 오류 dict 를 반환한다.
    호출자가 이를 409 로 변환한다.
    """
    state = _load(proposal_id)
    if state is None:
        return None
    if state.get("mode") != "ODA_STANDARD":
        return None
    report = state.get("conformance")
    gate = evaluate_gate(report)
    if gate["result"] == "PENDING":
        return {"reason": "oda_conformance_pending",
                "message": "ODA 적합성 점검이 아직 완료되지 않았습니다."}
    if gate["blocking"]:
        return {"reason": "oda_conformance_failed",
                "message": "ODA 표준 적합성 게이트가 FAIL 입니다. 위반을 해소하거나 면제하세요.",
                "violations": gate["violations"]}
    return None
