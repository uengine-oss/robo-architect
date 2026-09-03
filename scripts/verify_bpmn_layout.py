"""BPMN 레이아웃 폭 회귀 — 되돌아가는 흐름이 도형을 무한정 오른쪽으로 밀지 않는지.

업무 흐름은 늘 되돌아간다. 반려하면 다시 신청하고, 마감을 해제하면 다시 집계한다.
열 배치를 '시작점에서의 최장 경로'로 잡으면 그 순환이 통과할 때마다 열이 하나씩
밀려서, 노드 40개짜리 그림이 **32,350px** 로 나왔다. 도형은 다 있고 배치만 망가지니
오류로는 안 보인다.

    robo-architect/.venv/bin/python scripts/verify_bpmn_layout.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.features.ingestion.hybrid.contracts import (  # noqa: E402
    BpmActor, BpmFlowDTO, BpmGatewayDTO, BpmSkeleton, BpmTaskDTO,
)
from api.features.ingestion.hybrid.document_to_bpm.bpmn_builder import build_bpmn_xml  # noqa: E402

GAP_X = 200          # bpmn_builder 의 열 간격
failed = 0


def check(ok: bool, label: str, detail: str = "") -> None:
    global failed
    print(f"{'✓' if ok else '✗'} {label}{'  ' + detail if detail else ''}")
    if not ok:
        failed += 1


def width_of(xml: str) -> int:
    bounds = re.findall(r'<dc:Bounds x="(-?\d+)" y="-?\d+" width="(\d+)"', xml)
    return max((int(x) + int(w) for x, w in bounds), default=0)


def skeleton(n_tasks: int, loops: list[tuple[int, int]]) -> BpmSkeleton:
    """작업 n개의 선형 흐름 + `loops` 로 준 (from, to) 되돌아가는 간선."""
    actors = [BpmActor(id="a1", name="시스템"), BpmActor(id="a2", name="담당자")]
    tasks = [
        BpmTaskDTO(id=f"t{i}", name=f"단계 {i}", sequence_index=i,
                   actor_ids=["a1" if i % 5 else "a2"])
        for i in range(n_tasks)
    ]
    gws = [BpmGatewayDTO(id="gw1", name="분기", gateway_type="exclusive")]
    flows = [BpmFlowDTO(id=f"f{i}", source_id=f"t{i}", target_id=f"t{i+1}")
             for i in range(n_tasks - 1)]
    flows.append(BpmFlowDTO(id="fg", source_id=f"t{n_tasks-1}", target_id="gw1"))
    for k, (a, b) in enumerate(loops):
        flows.append(BpmFlowDTO(id=f"bk{k}", source_id=f"t{a}", target_id=f"t{b}", name="재처리"))
    return BpmSkeleton(actors=actors, tasks=tasks, gateways=gws, flows=flows)


N = 14
linear = width_of(build_bpmn_xml(skeleton(N, [])))
# 노드 수 + 시작/끝 + 여유. 이보다 넓으면 열이 밀린 것이다.
budget = (N + 6) * GAP_X
check(0 < linear <= budget, "순환 없는 흐름이 노드 수만큼만 넓다",
      f"{linear}px (한도 {budget}px)")

looped = width_of(build_bpmn_xml(skeleton(N, [(12, 3), (9, 5), (13, 0)])))
check(looped <= budget, "되돌아가는 흐름 3개가 폭을 밀지 않는다",
      f"{looped}px (한도 {budget}px)")
check(looped <= linear * 1.5, "순환이 있어도 선형 대비 1.5배를 넘지 않는다",
      f"선형 {linear}px → 순환 {looped}px")

# 순환 간선 자체는 그림에 남아야 한다 — 지우는 게 아니라 열만 안 미는 것이다.
xml = build_bpmn_xml(skeleton(N, [(12, 3)]))
flows = len(re.findall(r"<sequenceFlow", xml))
back = "재처리" in xml
check(flows >= N and back, "되돌아가는 간선이 그림에서 사라지지 않았다",
      f"sequenceFlow {flows}개 · 되돌아가는 간선 {'있음' if back else '없음'}")

print()
print("전부 통과" if not failed else f"실패 {failed}건")
sys.exit(1 if failed else 0)
