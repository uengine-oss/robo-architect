"""040 Proposal Impact Artifact Preview — 오버레이 투영 엔진.

미리보기 요청 시 (라이브 그래프 슬라이스 READ) + (Proposal 직렬화 diff 오버레이) 를
메모리에서 합성한다. **읽기 전용** — 어떤 경로도 Neo4j 에 쓰지 않는다(Constitution I, US2).

응답은 대응 라이브 read 엔드포인트의 형태를 미러하며 노드별 `source`/`badge` 만 추가하므로,
프런트 뷰어 스토어는 fetch base URL 분기 외 파싱 변경이 없다.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from api.platform.neo4j import get_session
from api.platform.neo4j_helpers import build_context_full_tree, resolve_bc_id_for_node
from api.features.proposal_lifecycle.proposal_contracts import ProposalResponse
from api.features.proposal_lifecycle.services.overlay_apply import apply_data_overlay


# nodeLabel → viewer 매핑 (data-model §4). 미매핑 라벨은 renderable=false.
LABEL_TO_VIEWER: dict[str, str] = {
    "Aggregate": "data",
    "ValueObject": "data",
    "Enum": "data",
    "Enumeration": "data",
    # Command/Event/ReadModel 은 Event Modeling 산출물이므로 processes(이벤트모델링) 뷰어로
    # 일관화한다(I18). 단 processes 뷰어는 오버레이가 없어 신규 요소는 플로우 맥락만 보이고,
    # 기존/수정 요소는 정상 포커스된다. 신규 가시성은 후속(이벤트모델링 오버레이) 과제.
    "Command": "processes",
    "Event": "processes",
    "ReadModel": "processes",
    "UI": "design",
    "Screen": "design",
    "UiFlow": "design",
    "Process": "process",
    "BpmnFlow": "process",
    "Journey": "processes",
    "EventModel": "processes",
}

VIEWER_TO_TAB = {"data": "Data", "design": "Design", "process": "Process", "processes": "Processes"}

# 프런트 오케스트레이션이 배선된 뷰어. data 는 오버레이 미리보기, design/process/processes 는
# 라이브 읽기 전용 포커스(인텐트가 이 타입을 신규 생성하는 일이 드뭄 — research D5).
WIRED_VIEWERS = {"data", "design", "process", "processes"}


class PreviewError(Exception):
    """미리보기 합성 불가(대상 노드 없음 등). renderable=false 로 변환된다."""


def _load_proposal(proposal_id: str) -> Optional[ProposalResponse]:
    """Proposal 단건을 읽기 전용으로 로드(diff 포함). 없으면 None."""
    with get_session() as session:
        rec = session.run(
            "MATCH (p:Proposal {id: $id}) RETURN p {.*} AS p", id=proposal_id
        ).single()
    if not rec:
        return None
    return ProposalResponse.from_neo4j(rec["p"], [])


def _context_note(status: str) -> Optional[str]:
    if status == "ACCEPTED":
        return "이미 반영됨 (ACCEPTED)"
    if status == "DESTROYED":
        return "폐기됨 (DESTROYED)"
    return None


def resolve_open_target(proposal_id: str, node_id: Optional[str], node_label: Optional[str]) -> dict:
    """임팩트/diff 항목 하나가 어떤 뷰어로 열리는지 + 열기 가능 여부를 판정한다.

    Returns: { renderable, viewer, targetNodeId, bcId, reason }
    """
    proposal = _load_proposal(proposal_id)
    if proposal is None:
        return {"renderable": False, "viewer": None, "targetNodeId": node_id,
                "bcId": None, "reason": f"Proposal {proposal_id} not found"}

    label = (node_label or "").strip()
    viewer = LABEL_TO_VIEWER.get(label)
    if not viewer:
        return {"renderable": False, "viewer": None, "targetNodeId": node_id,
                "bcId": None, "reason": f"'{label}' 타입은 미리보기 뷰어 매핑이 없습니다."}

    if viewer not in WIRED_VIEWERS:
        return {"renderable": False, "viewer": viewer, "targetNodeId": node_id,
                "bcId": None, "reason": f"{VIEWER_TO_TAB.get(viewer, viewer)} 뷰어 미리보기는 준비 중입니다(US3)."}

    # 신규(임시) 노드는 라이브 id 가 없을 수 있다 — temp id 그대로 사용.
    target_id = node_id
    bc_id = None
    if viewer == "data":
        # 1) tacticalDiff 항목이 명시한 대상 BC(깊은 인텐트 포맷 boundedContextId) 우선.
        item = _find_tactical_item(proposal, node_id)
        if item:
            bc_id = item.get("boundedContextId")
        # 2) 라이브 노드면 그래프에서 소속 BC 해소.
        if not bc_id and node_id and not str(node_id).startswith("PREVIEW:"):
            bc_id = resolve_bc_id_for_node(str(node_id))
        # 3) 임팩트맵의 BoundedContext 항목으로 추정.
        if not bc_id:
            bc_id = _guess_bc_from_proposal(proposal)
        if not bc_id:
            return {"renderable": False, "viewer": viewer, "targetNodeId": target_id,
                    "bcId": None, "reason": "대상의 BoundedContext 를 해소할 수 없습니다."}
        # Data 뷰어는 Aggregate 를 포커스한다 — Command/Event/VO 등 비-Aggregate 노드를
        # 그대로 포커스하면 "Aggregate not found" 가 난다. 소속 Aggregate 로 포커스를 돌린다.
        if label != "Aggregate":
            focus = _resolve_focus_aggregate(proposal, node_id)
            if focus:
                target_id = focus

    # 신규(CREATE) 요소는 오버레이가 있는 data 뷰어에선 보이지만, 오버레이가 없는
    # processes/design/process 뷰어에는 라이브 그래프에 없어 표시되지 않는다(I18-C 백로그).
    # 그 경우 사용자가 "왜 안 보이지?" 하지 않도록 안내 문구를 함께 내려준다.
    notice = None
    if viewer != "data":
        item = _find_tactical_item(proposal, node_id)
        if item and (item.get("changeType") or "").upper() == "CREATE":
            notice = "이 항목은 제안에만 있는 신규 요소라 이 뷰어 캔버스에는 아직 표시되지 않습니다. 내용은 제안 Diff에서 확인하세요."

    return {"renderable": True, "viewer": viewer, "targetNodeId": target_id,
            "bcId": bc_id, "reason": None, "notice": notice}


def _resolve_focus_aggregate(proposal: ProposalResponse, node_id: Optional[str]) -> Optional[str]:
    """비-Aggregate 노드(Command/Event/VO 등)를 소속 Aggregate id 로 해소한다.

    - Command: 항목의 `aggregateId`.
    - Event: 항목의 `commandId` → 그 Command 의 `aggregateId`.
    - 폴백: 제안의 첫 Aggregate tactical 항목.
    """
    item = _find_tactical_item(proposal, node_id)
    if item:
        agg = item.get("aggregateId")
        if agg:
            return str(agg)
        cmd_id = item.get("commandId")
        if cmd_id:
            cmd = _find_tactical_item(proposal, cmd_id)
            if cmd and cmd.get("aggregateId"):
                return str(cmd.get("aggregateId"))
    for it in proposal.tacticalDiff or []:
        if isinstance(it, dict) and it.get("nodeLabel") == "Aggregate" and it.get("nodeId"):
            return str(it.get("nodeId"))
    return None


def _find_tactical_item(proposal: ProposalResponse, node_id: Optional[str]) -> Optional[dict]:
    """tacticalDiff 에서 nodeId 가 일치하는 항목을 찾는다(깊은 포맷 boundedContextId 조회용)."""
    if not node_id:
        return None
    for item in proposal.tacticalDiff or []:
        if str(item.get("nodeId") or "") == str(node_id):
            return item
    return None


def _guess_bc_from_proposal(proposal: ProposalResponse) -> Optional[str]:
    """제안 전체에서 대표 BoundedContext 를 추정한다.

    신규 Command/Event 항목은 자체 boundedContextId 가 없어 BC 해소에 실패하는데(I5),
    같은 제안의 다른 tactical 항목(보통 부모 Aggregate)이 가진 boundedContextId 로 보완한다.
    우선순위: ①impactMap 의 BoundedContext 항목 → ②tacticalDiff 항목의 boundedContextId.
    """
    for entry in proposal.impactMap or []:
        if entry.nodeLabel == "BoundedContext" and entry.nodeId:
            return entry.nodeId
    for item in proposal.tacticalDiff or []:
        bc = item.get("boundedContextId") if isinstance(item, dict) else None
        if bc:
            return bc
    return None


def build_data_preview(proposal_id: str, bc_id: str) -> dict:
    """Data(Aggregate) 미리보기: 라이브 BC full-tree + tacticalDiff 오버레이.

    라이브 `GET /api/contexts/{bc}/full-tree` 와 동일 구조 + 노드별 source/badge.
    """
    proposal = _load_proposal(proposal_id)
    if proposal is None:
        raise PreviewError(f"Proposal {proposal_id} not found")

    live_tree = build_context_full_tree(bc_id)
    if live_tree is None:
        # 라이브 BC 가 아직 없을 수 있다(완전 신규 제안) — 빈 셸 위에 오버레이.
        live_tree = {"id": bc_id, "name": bc_id, "displayName": bc_id, "type": "BoundedContext",
                     "aggregates": [], "userStories": [], "policies": [], "readmodels": [], "uis": []}

    projected, meta = apply_data_overlay(live_tree, proposal_id, proposal.tacticalDiff)

    projected["_preview"] = {
        "proposalId": proposal_id,
        "viewer": "data",
        "contextNote": _context_note(proposal.status.value if proposal.status else ""),
        "meta": meta,
    }
    return projected


def preview_summary(proposal_id: str) -> dict:
    """관측용 요약(노드 수·source 분포) — 로깅에 사용."""
    return {"proposalId": proposal_id}
