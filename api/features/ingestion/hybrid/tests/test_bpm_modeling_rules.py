"""네이티브 문서→BPM — pdf2bpmn 에서 옮긴 구조 규칙(2026-11-17)."""

from types import SimpleNamespace as NS

from api.features.ingestion.hybrid.contracts import (
    BpmActor, BpmEndEventDTO, BpmFlowDTO, BpmGatewayDTO, BpmSkeleton, BpmTaskDTO,
)
from api.features.ingestion.hybrid.document_to_bpm.bpmn_builder import build_bpmn_xml
from api.features.ingestion.hybrid.document_to_bpm.entity_extractor import MODELING_SKILL
from api.features.ingestion.hybrid.document_to_bpm.process_validator import find_defects, repair_flows


def _proc(tasks, gateways):
    return NS(tasks=[NS(name=t) for t in tasks], gateways=[
        NS(name=g[0], after_task=g[1], branches=[NS(condition=c, to_task=tt, to_end=te) for c, tt, te in g[2]])
        for g in gateways])


def test_skill_is_loaded_into_prompt():
    assert "모델링 규칙" in MODELING_SKILL or "분기" in MODELING_SKILL


def test_unreachable_task_is_a_defect():
    # 마감 상태 판단: 이미 마감됨 → 맨 끝(건너뜀) — "마감 해제" 는 어디서도 닿지 않는다
    p = _proc(["마감 대상 확인", "월 근태 집계", "마감 해제", "전 사원 마감 배치"],
              [("마감 상태 판단", "마감 대상 확인", [("미마감", "월 근태 집계", ""), ("이미 마감됨", "전 사원 마감 배치", "")]),
               ("집계 판단", "월 근태 집계", [("있음", "전 사원 마감 배치", ""), ("없음", "", "집계 없음 종료")])])
    kinds = {d.kind for d in find_defects(p).defects}
    assert "unreachable_task" in kinds


def test_duplicate_targets_and_too_few_branches():
    p = _proc(["A", "B"], [("기한 판단", "A", [("기한 있음", "B", ""), ("기한 없음", "B", "")])])
    kinds = {d.kind for d in find_defects(p).defects}
    assert {"duplicate_branch_target", "too_few_branches"} <= kinds


def test_to_end_counts_as_a_distinct_branch():
    p = _proc(["A", "B"], [("중복 판단", "A", [("중복 없음", "B", ""), ("중복 있음", "", "중복 신청 반려")])])
    assert find_defects(p).ok


def _flow(s, t, n=""):
    return BpmFlowDTO(id=f"f_{s}_{t}", source_id=s, target_id=t, name=n)


def test_repair_demotes_gateway_with_one_target_and_dedupes():
    flows = [_flow("a", "g"), _flow("g", "b", "x"), _flow("g", "b", "y"), _flow("g", "b", "y")]
    gws = [BpmGatewayDTO(id="g", name="판단")]
    flows, gws = repair_flows(["a", "b"], flows, gws, new_flow=_flow)
    assert gws == []
    assert {(f.source_id, f.target_id) for f in flows} == {("a", "b")}


def _skel():
    actors = [BpmActor(id="ac", name="담당자")]
    tasks = [BpmTaskDTO(id=t, name=t, sequence_index=i, actor_ids=["ac"], task_type="human")
             for i, t in enumerate(["접수", "확인", "결재", "완료처리"])]
    gws = [BpmGatewayDTO(id="g1", name="확인 결과 판단", actor_ids=["ac"]),
           BpmGatewayDTO(id="g2", name="결재 결과 판단", actor_ids=["ac"])]
    ends = [BpmEndEventDTO(id="e1", name="반려 종료", actor_ids=["ac"])]
    flows = [_flow("확인", "g1"), _flow("g1", "결재", "적합"), _flow("g1", "e1", "부적합"),
             _flow("결재", "g2"), _flow("g2", "완료처리", "승인"), _flow("g2", "결재", "다음 결재자")]
    return BpmSkeleton(actors=actors, tasks=tasks, gateways=gws, flows=flows, end_events=ends)


def test_builder_ends_per_outcome_and_user_tasks():
    xml = build_bpmn_xml(_skel())
    assert xml.count("<endEvent") == 2                 # 반려 종료 + 완료처리 뒤의 끝
    assert 'name="반려 종료"' in xml
    assert "<userTask" in xml and "<task " not in xml


def test_builder_keeps_backbone_when_next_task_only_has_a_loop_in():
    # "결재" 로 들어오는 명시 흐름은 되돌림(g2 → 결재)과 g1 갈래뿐 — 그래도 시작에서 닿아야 한다
    xml = build_bpmn_xml(_skel())
    assert 'sourceRef="StartEvent_1" targetRef="Task_' in xml
