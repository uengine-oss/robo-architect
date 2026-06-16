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
from api.features.proposal_lifecycle.services.overlay_apply import (
    apply_data_overlay,
    _apply_semantic_ops,
    _populate_from_deep_item,
    _tag,
    temp_id,
    SOURCE_LIVE,
    SOURCE_MODIFIED,
    SOURCE_TEMPORARY,
)


# nodeLabel → viewer 매핑 (data-model §4). 미매핑 라벨은 renderable=false.
# 043-fix: Command/Event/ReadModel 은 Data(Aggregate 패널) 대신 **Design(캔버스)** 으로 연다.
#   사용자는 이 요소들이 BC 그래프 안에서 어디에 위치하는지(J1) 와 인스펙터로 미리보기
#   정보를 확인/수정(J2) 하길 원하는데, Data 패널은 이를 제공하지 못한다.
LABEL_TO_VIEWER: dict[str, str] = {
    "Aggregate": "data",
    "ValueObject": "data",
    "Enum": "data",
    "Enumeration": "data",
    # Command/Event/ReadModel 은 소속 BC 그래프를 Design 캔버스에 투영해 연다(아래
    # DESIGN_CANVAS_LABELS). Command/Event 는 소유 Aggregate 안에, ReadModel 은 Aggregate
    # 소유 관계가 없어 BC 직속으로 배치한다.
    "Command": "design",
    "Event": "design",
    "ReadModel": "design",
    "UI": "design",
    "Screen": "design",
    "UiFlow": "design",
    "Process": "process",
    "BpmnFlow": "process",
    "Journey": "processes",
    "EventModel": "processes",
}

VIEWER_TO_TAB = {"data": "Data", "design": "Design", "process": "Process", "processes": "Processes"}

# 043-fix: Design 캔버스에 BC 그래프(Aggregate→Command→Event→ReadModel→UI)로 투영해
# 포커스 + 인스펙터를 여는 라벨. Command/Event 는 소유 Aggregate 까지 해소해 그 안에 배치하고,
# ReadModel 은 Aggregate 소유 관계가 없어 소속 BC 만 해소해 BC 직속으로 불러온다.
# 다른 design 라벨(UI/Screen/UiFlow)은 기존처럼 라이브 뷰어를 읽기 전용 맥락으로만 연다
# (캔버스 오버레이 로드 없음 — 회귀 방지).
DESIGN_CANVAS_LABELS = {"Command", "Event", "ReadModel"}

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


def resolve_open_target(proposal_id: str, node_id: Optional[str], node_label: Optional[str],
                        node_title: Optional[str] = None) -> dict:
    """임팩트/diff 항목 하나가 어떤 뷰어로 열리는지 + 열기 가능 여부를 판정한다.

    Returns: { renderable, viewer, targetNodeId, bcId, reason }
    """
    proposal = _load_proposal(proposal_id)
    if proposal is None:
        return {"renderable": False, "viewer": None, "targetNodeId": node_id,
                "bcId": None, "aggregateId": None, "reason": f"Proposal {proposal_id} not found"}

    label = (node_label or "").strip()
    viewer = LABEL_TO_VIEWER.get(label)
    if not viewer:
        return {"renderable": False, "viewer": None, "targetNodeId": node_id,
                "bcId": None, "aggregateId": None, "reason": f"'{label}' 타입은 미리보기 뷰어 매핑이 없습니다."}

    # 040/043-fix — impactMap(충돌 가능성 분석) 항목은 nodeId 가 null 일 수 있다: LLM
    # (robo-proposal-context)이 신규 CREATE 노드를 라이브 그래프 id 로 묶지 못하면 SKILL 규칙상
    # nodeId=null 로 둔다. 그러면 Tactical Diff '열기'와 달리 포커스 대상 id 가 없어 빈 캔버스/
    # 'No aggregates selected' 가 된다. 같은 제안 tacticalDiff 에서 (label, title) 로 동일 논리
    # 노드를 찾아 합성 nodeId 를 복원하면, 이후 전부 Tactical Diff '열기'와 동일 경로로 해소된다.
    if not node_id:
        recovered = _match_tactical_by_label_title(proposal, label, node_title)
        if recovered:
            node_id = recovered

    if viewer not in WIRED_VIEWERS:
        return {"renderable": False, "viewer": viewer, "targetNodeId": node_id,
                "bcId": None, "aggregateId": None, "reason": f"{VIEWER_TO_TAB.get(viewer, viewer)} 뷰어 미리보기는 준비 중입니다(US3)."}

    # 신규(임시) 노드는 라이브 id 가 없을 수 있다 — temp id 그대로 사용.
    target_id = node_id
    bc_id = None
    aggregate_id = None

    # Data 뷰어, 또는 Design 캔버스 라벨(Command/Event/ReadModel)은 소속 BC(Command/Event 는
    # 추가로 소유 Aggregate)를 해소해야 해당 BC 그래프를 그려 대상 노드를 포커스할 수 있다.
    needs_bc = viewer == "data" or (viewer == "design" and label in DESIGN_CANVAS_LABELS)
    if needs_bc:
        # 1) tacticalDiff 항목이 명시한 대상 BC(깊은 인텐트 포맷 boundedContextId) 우선.
        item = _find_tactical_item(proposal, node_id)
        if item:
            bc_id = item.get("boundedContextId")
        # 1b) 자식(Command/Event/VO) 항목은 boundedContextId 를 직접 들지 않고 부모를
        #     aggregateId/commandId 로 가리킨다(robo-proposal-intent 실제 출력). 부모
        #     체인(Event→Command→Aggregate)을 따라 BC 를 해소한다 — 각 홉에서 라이브면
        #     그래프에서, 아니면 같은 tacticalDiff 의 부모 항목 boundedContextId 에서.
        if not bc_id and item:
            bc_id = _resolve_bc_via_parent(proposal, item)
        # 2) 라이브 노드면 그래프에서 소속 BC 해소.
        if not bc_id and node_id and not str(node_id).startswith("PREVIEW:"):
            bc_id = resolve_bc_id_for_node(str(node_id))
        # 3) 임팩트맵의 BoundedContext 항목으로 추정.
        if not bc_id:
            bc_id = _guess_bc_from_proposal(proposal)
        if not bc_id:
            return {"renderable": False, "viewer": viewer, "targetNodeId": target_id,
                    "bcId": None, "aggregateId": None,
                    "reason": "대상의 BoundedContext 를 해소할 수 없습니다."}
        # Data 뷰어는 Aggregate 단위로 포커스하고, Design 캔버스는 소유 Aggregate 컨테이너
        #   안에 Command/Event 를 배치한다 — 둘 다 소유 Aggregate 가 필요하므로 환원한다.
        #   ReadModel 은 Aggregate 소유가 없어 None 이 되고, BC 그래프에서 자기 노드로 포커스한다.
        aggregate_id = _resolve_owning_aggregate(proposal, node_id, label)

    # 신규(CREATE) 요소는 오버레이가 그려지는 data 뷰어와 Design 캔버스 라벨(Command/Event/
    # ReadModel)에선 정상 표시된다. 그러나 오버레이가 없는 processes/process 뷰어, 또는
    # design+UI/Screen 등에는 라이브 그래프에 없어 표시되지 않는다(I18-C 백로그). 그 경우만
    # 사용자가 "왜 안 보이지?" 하지 않도록 안내 문구를 함께 내려준다.
    notice = None
    overlay_rendered = viewer == "data" or (viewer == "design" and label in DESIGN_CANVAS_LABELS)
    if not overlay_rendered:
        item = _find_tactical_item(proposal, node_id)
        if item and (item.get("changeType") or "").upper() == "CREATE":
            notice = "이 항목은 제안에만 있는 신규 요소라 이 뷰어 캔버스에는 아직 표시되지 않습니다. 내용은 제안 Diff에서 확인하세요."

    return {"renderable": True, "viewer": viewer, "targetNodeId": target_id,
            "bcId": bc_id, "aggregateId": aggregate_id, "reason": None, "notice": notice}


def _find_tactical_item(proposal: ProposalResponse, node_id: Optional[str]) -> Optional[dict]:
    """tacticalDiff 에서 nodeId 가 일치하는 항목을 찾는다(깊은 포맷 boundedContextId 조회용)."""
    if not node_id:
        return None
    for item in proposal.tacticalDiff or []:
        if str(item.get("nodeId") or "") == str(node_id):
            return item
    return None


def _match_tactical_by_label_title(proposal: ProposalResponse, node_label: str,
                                   node_title: Optional[str]) -> Optional[str]:
    """nodeId 가 없는 impactMap 항목을 (nodeLabel, nodeTitle)로 tacticalDiff 의 동일 논리
    노드에 매칭해 그 합성 nodeId 를 복원한다. 한 제안 안에서 (label, title)은 사실상 유일하다.
    매칭 실패 시 None."""
    if not node_title:
        return None
    label = (node_label or "").strip()
    title = str(node_title).strip()
    for item in proposal.tacticalDiff or []:
        if (str(item.get("nodeLabel") or "").strip() == label
                and str(item.get("nodeTitle") or "").strip() == title):
            nid = item.get("nodeId")
            if nid:
                return str(nid)
    return None


# 자식 항목이 부모를 가리키는 참조 키. 우선순위 순(Aggregate 가 BC 를 직접 보유).
_PARENT_REF_KEYS = ("aggregateId", "commandId")


def _resolve_bc_via_parent(proposal: ProposalResponse, item: dict,
                           _seen: Optional[set] = None) -> Optional[str]:
    """자식 항목의 부모 참조(aggregateId/commandId)를 따라 BC 를 해소한다.

    robo-proposal-intent 출력은 boundedContextId 를 Aggregate 레벨에만 싣고, 자식은
    부모를 참조로만 가리킨다:
      Event --commandId--> Command --aggregateId--> Aggregate(boundedContextId)
    각 홉에서 (1) 부모가 라이브면 그래프에서 BC 를, (2) 아니면 같은 tacticalDiff 의
    부모 항목 boundedContextId 를, 없으면 그 부모의 부모로 재귀해 체인을 끝까지 따라간다.
    `_seen` 으로 순환 참조를 방어한다.
    """
    _seen = _seen if _seen is not None else set()
    for ref_key in _PARENT_REF_KEYS:
        ref = item.get(ref_key)
        if not ref:
            continue
        ref = str(ref)
        if ref in _seen:
            continue
        _seen.add(ref)
        # 1) 라이브 부모 경유(비-그린필드: 기존 노드에 신규 자식 추가 등).
        if not ref.startswith("PREVIEW:"):
            bc = resolve_bc_id_for_node(ref)
            if bc:
                return bc
        # 2) 같은 제안의 부모 항목 — boundedContextId 가 있으면 사용, 없으면 상위로 재귀.
        parent = _find_tactical_item(proposal, ref)
        if parent:
            bc = parent.get("boundedContextId")
            if bc:
                return bc
            bc = _resolve_bc_via_parent(proposal, parent, _seen)
            if bc:
                return bc
    return None


# Command 는 aggregateId 를, Event 는 commandId(→Command→aggregateId)를 든다.
# 부모 체인을 따라 소유 Aggregate 에 도달하기 위한 참조 키(우선순위 순).
_AGG_PARENT_REF_KEYS = ("aggregateId", "commandId")


def _resolve_owning_aggregate(proposal: ProposalResponse, node_id: Optional[str],
                              node_label: str, _seen: Optional[set] = None) -> Optional[str]:
    """data 뷰어 focus 대상이 될 **소유 Aggregate id** 를 해소한다.

    Data 뷰어(AggregatePanel)는 Aggregate 단위로만 포커스/렌더하므로, Command/Event/VO/Enum
    대상은 소유 Aggregate 로 환원해야 한다. robo-proposal-intent 출력 참조 형태는
        Aggregate(자기 자신) / Command --aggregateId--> Aggregate
        Event --commandId--> Command(--aggregateId--> Aggregate)
    라, _resolve_bc_via_parent 와 동형으로 부모 체인을 따라 Aggregate 를 찾는다.
    `_seen` 으로 순환 참조를 방어한다. 해소 불가 시 None.
    """
    if not node_id:
        return None
    label = (node_label or "").strip()
    if label == "Aggregate":
        return str(node_id)

    _seen = _seen if _seen is not None else set()
    item = _find_tactical_item(proposal, node_id)

    # 1) 항목이 직접 aggregateId 를 들면(=Command, 또는 라이브 Aggregate 에 붙는 신규 자식)
    #    그게 소유 Aggregate.
    if item and item.get("aggregateId"):
        return str(item["aggregateId"])

    # 2) 부모 참조 체인(Event--commandId-->Command--aggregateId-->Agg)을 추적.
    if item:
        for ref_key in _AGG_PARENT_REF_KEYS:
            ref = item.get(ref_key)
            if not ref:
                continue
            ref = str(ref)
            if ref in _seen:
                continue
            _seen.add(ref)
            parent = _find_tactical_item(proposal, ref)
            if parent:
                if (parent.get("nodeLabel") or "").strip() == "Aggregate":
                    return str(parent.get("nodeId") or ref)
                got = _resolve_owning_aggregate(proposal, ref,
                                                parent.get("nodeLabel") or "", _seen)
                if got:
                    return got
            # 라이브 부모(비-그린필드): 그래프에서 소유 Aggregate 직접 조회.
            if not ref.startswith("PREVIEW:"):
                got = _owning_aggregate_in_graph(ref)
                if got:
                    return got

    # 3) 라이브 그래프: 노드의 소유 Aggregate 직접 조회(비-그린필드 fallback).
    if not str(node_id).startswith("PREVIEW:"):
        got = _owning_aggregate_in_graph(str(node_id))
        if got:
            return got
    return None


def _owning_aggregate_in_graph(node_id: str) -> Optional[str]:
    """라이브 Neo4j 에서 node_id 의 소유 Aggregate id 를 조회(읽기 전용).

    스키마: (:Aggregate)-[:HAS_COMMAND]->(:Command)-[:EMITS]->(:Event).
    node 자체가 Aggregate 면 자기 자신을, Command/Event 면 소유 Aggregate 를 돌려준다.
    해소 불가 시 None.
    """
    with get_session() as session:
        rec = session.run(
            """
            MATCH (a:Aggregate)
            WHERE a.id = $id
               OR (a)-[:HAS_COMMAND]->({id: $id})
               OR (a)-[:HAS_COMMAND]->(:Command)-[:EMITS]->({id: $id})
            RETURN a.id AS aggId
            LIMIT 1
            """,
            id=str(node_id),
        ).single()
    return rec["aggId"] if rec and rec["aggId"] else None


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


def build_design_preview(proposal_id: str, bc_id: str) -> dict:
    """Design(캔버스) 미리보기: 라이브 BC 슬라이스 + tacticalDiff 오버레이를 **캔버스 그래프**
    형태(`{nodes, relationships, bcContext}`)로 합성한다.

    `/api/graph/expand-with-bc/{id}` 와 동일 형태라 프런트 canvasStore.addNodesWithLayout 가
    파싱 변경 없이 그대로 소비한다(라이브 그래프가 비어 있어도 — CREATE 전용 제안 — 오버레이로
    Aggregate→Command→Event→ReadModel→UI 와 관계를 그린다). **읽기 전용**(Constitution I).

    데이터 오버레이(apply_data_overlay)는 신규 Command/Event 를 무조건 aggregates[0] 에 붙이는
    단순화가 있어 멀티-Aggregate 제안에서 부모가 틀어진다. 여기서는 항목의 aggregateId/commandId
    참조를 따라 **정확한 부모**에 배치한다.

    '연계 요소' 범위 = **BC 그래프 전체**(소유 Aggregate + 같은 BC 의 다른 Aggregate/Command/
    Event/ReadModel/UI). 라이브 `expand-with-bc` 와 동일하게 BC 컨테이너 단위로 그리므로,
    "해당 Aggregate 와 연계된 요소가 있으면 함께 불러온다"를 누락 없이 만족한다(상위집합).
    """
    proposal = _load_proposal(proposal_id)
    if proposal is None:
        raise PreviewError(f"Proposal {proposal_id} not found")

    tactical: list[dict] = list(proposal.tacticalDiff or [])
    live_tree = build_context_full_tree(bc_id)

    nodes: list[dict] = []
    relationships: list[dict] = []
    meta: list[dict] = []
    seen: set[str] = set()

    def push(node: dict) -> bool:
        nid = str(node.get("id") or "")
        if not nid or nid in seen:
            return False
        nodes.append(node)
        seen.add(nid)
        src = node.get("source")
        if src and src != SOURCE_LIVE:
            meta.append({"nodeId": nid, "source": src, "badge": node.get("badge")})
        return True

    def rel(src: str, tgt: str, rtype: str) -> None:
        relationships.append({"source": str(src), "target": str(tgt), "type": rtype})

    def overlay_live(node: dict, nid: str) -> str:
        """라이브 자식 노드(Command/Event/ReadModel)에 같은 BC 의 MODIFY 항목을 얹는다.
        미리보기 인스펙터로 라이브 노드를 수정하면 MODIFY 항목이 생기는데, 이때 변경 필드/
        속성이 캔버스에도 반영되도록 한다(없으면 그대로 live)."""
        it = by_id.get(nid)
        if it and (it.get("changeType") or "MODIFY") == "MODIFY":
            _apply_semantic_ops(node, it.get("semanticDiff") or {})
            _populate_from_deep_item(node, it)
            return SOURCE_MODIFIED
        return SOURCE_LIVE

    # BC 컨테이너 노드.
    bc_name = bc_id
    if isinstance(live_tree, dict):
        bc_name = live_tree.get("displayName") or live_tree.get("name") or bc_id
    push(_tag({"id": bc_id, "name": bc_name, "displayName": bc_name, "type": "BoundedContext"}, SOURCE_LIVE))

    by_id = {str(it.get("nodeId")): it for it in tactical if it.get("nodeId")}

    # --- 1) 라이브 Aggregate 와 자식(Command/Event/ReadModel/UI) ---
    if isinstance(live_tree, dict):
        for agg in live_tree.get("aggregates", []) or []:
            aid = str(agg.get("id") or "")
            if not aid:
                continue
            agg_node = {k: v for k, v in agg.items() if k not in ("commands", "events")}
            agg_node.update({"id": aid, "type": "Aggregate", "bcId": bc_id})
            item = by_id.get(aid)
            source = SOURCE_LIVE
            if item and (item.get("changeType") or "MODIFY") == "MODIFY":
                _apply_semantic_ops(agg_node, item.get("semanticDiff") or {})
                _populate_from_deep_item(agg_node, item)
                source = SOURCE_MODIFIED
            _tag(agg_node, source)
            if push(agg_node):
                rel(bc_id, aid, "HAS_AGGREGATE")
            for cmd in agg.get("commands", []) or []:
                cid = str(cmd.get("id") or "")
                if not cid:
                    continue
                cmd_node = {**cmd, "id": cid, "type": "Command", "bcId": bc_id, "parentId": aid}
                _tag(cmd_node, overlay_live(cmd_node, cid))
                if push(cmd_node):
                    rel(aid, cid, "HAS_COMMAND")
                for evt in cmd.get("events", []) or []:
                    eid = str(evt.get("id") or "")
                    if not eid:
                        continue
                    evt_node = {**evt, "id": eid, "type": "Event", "bcId": bc_id}
                    _tag(evt_node, overlay_live(evt_node, eid))
                    if push(evt_node):
                        rel(cid, eid, "EMITS")
        for rm in live_tree.get("readmodels", []) or []:
            rid = str(rm.get("id") or "")
            if not rid:
                continue
            rm_node = {**rm, "id": rid, "type": "ReadModel", "bcId": bc_id}
            _tag(rm_node, overlay_live(rm_node, rid))
            if push(rm_node):
                rel(bc_id, rid, "HAS_READMODEL")
        for ui in live_tree.get("uis", []) or []:
            uid = str(ui.get("id") or "")
            if not uid:
                continue
            ui_node = {**ui, "id": uid, "type": "UI", "bcId": bc_id}
            _tag(ui_node, SOURCE_LIVE)
            if push(ui_node):
                rel(bc_id, uid, "HAS_UI")

    # --- 2) 신규(CREATE) Aggregate — 이 BC 소속 ---
    for i, it in enumerate(tactical):
        if (it.get("changeType") or "") != "CREATE" or it.get("nodeLabel") != "Aggregate":
            continue
        if str(it.get("boundedContextId") or "") != str(bc_id):
            continue
        aid = str(it.get("nodeId") or temp_id(proposal_id, i))
        title = it.get("nodeTitle") or aid
        node = {"id": aid, "name": title, "displayName": title, "type": "Aggregate", "bcId": bc_id,
                "valueObjects": [], "enumerations": [], "invariants": [], "properties": []}
        _apply_semantic_ops(node, it.get("semanticDiff") or {})
        _populate_from_deep_item(node, it)
        _tag(node, SOURCE_TEMPORARY)
        if push(node):
            rel(bc_id, aid, "HAS_AGGREGATE")

    # --- 3) 신규(CREATE) Command — 소유 Aggregate(aggregateId)가 캔버스에 있을 때 ---
    for i, it in enumerate(tactical):
        if (it.get("changeType") or "") != "CREATE" or it.get("nodeLabel") != "Command":
            continue
        aid = str(it.get("aggregateId") or "")
        if not aid or aid not in seen:
            continue
        cid = str(it.get("nodeId") or temp_id(proposal_id, i))
        title = it.get("nodeTitle") or cid
        node = {"id": cid, "name": title, "displayName": title, "type": "Command",
                "bcId": bc_id, "parentId": aid, "properties": [], "events": []}
        _populate_from_deep_item(node, it)
        _tag(node, SOURCE_TEMPORARY)
        if push(node):
            rel(aid, cid, "HAS_COMMAND")

    # --- 4) 신규(CREATE) Event — 소유 Command(commandId)가 캔버스에 있을 때 ---
    for i, it in enumerate(tactical):
        if (it.get("changeType") or "") != "CREATE" or it.get("nodeLabel") != "Event":
            continue
        cid = str(it.get("commandId") or "")
        if not cid or cid not in seen:
            continue
        eid = str(it.get("nodeId") or temp_id(proposal_id, i))
        title = it.get("nodeTitle") or eid
        node = {"id": eid, "name": title, "displayName": title, "type": "Event",
                "bcId": bc_id, "properties": []}
        _populate_from_deep_item(node, it)
        _tag(node, SOURCE_TEMPORARY)
        if push(node):
            rel(cid, eid, "EMITS")

    # --- 5) 신규(CREATE) ReadModel — 이 BC 소속 ---
    for i, it in enumerate(tactical):
        if (it.get("changeType") or "") != "CREATE" or it.get("nodeLabel") != "ReadModel":
            continue
        if str(it.get("boundedContextId") or "") != str(bc_id):
            continue
        rid = str(it.get("nodeId") or temp_id(proposal_id, i))
        title = it.get("nodeTitle") or rid
        node = {"id": rid, "name": title, "displayName": title, "type": "ReadModel",
                "bcId": bc_id, "properties": []}
        _populate_from_deep_item(node, it)
        _tag(node, SOURCE_TEMPORARY)
        if push(node):
            rel(bc_id, rid, "HAS_READMODEL")

    # --- 6) 신규(CREATE) UI — 이 BC 소속 ---
    for i, it in enumerate(tactical):
        if (it.get("changeType") or "") != "CREATE" or it.get("nodeLabel") != "UI":
            continue
        if str(it.get("boundedContextId") or "") != str(bc_id):
            continue
        uid = str(it.get("nodeId") or temp_id(proposal_id, i))
        title = it.get("nodeTitle") or uid
        node = {"id": uid, "name": title, "displayName": title, "type": "UI",
                "bcId": bc_id, "properties": []}
        _populate_from_deep_item(node, it)
        _tag(node, SOURCE_TEMPORARY)
        if push(node):
            rel(bc_id, uid, "HAS_UI")

    bc_ctx = {"id": bc_id, "name": bc_name, "displayName": bc_name}
    return {
        "nodes": nodes,
        "relationships": relationships,
        "bcContext": bc_ctx,
        "_preview": {
            "proposalId": proposal_id,
            "viewer": "design",
            "contextNote": _context_note(proposal.status.value if proposal.status else ""),
            "meta": meta,
        },
    }


def preview_summary(proposal_id: str) -> dict:
    """관측용 요약(노드 수·source 분포) — 로깅에 사용."""
    return {"proposalId": proposal_id}
