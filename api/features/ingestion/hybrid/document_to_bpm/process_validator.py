"""추출한 프로세스의 구조 검사 · 고치기 — pdf2bpmn(process-gpt-bpmn-extractor)의 정적 검사를 옮겨 왔다.

pdf2bpmn 은 "정적 검사 → 결함 목록을 LLM 에 주고 다시 만들기 → 다시 검사" 로 모델을 다듬는다
(validation/process_validator.py 527-625 · 1064-1124). 여기서는

  1) `find_defects`   — 이름 수준(LLM 이 낸 그대로)에서 결함을 찾는다. 결함이 있으면 추출기가 LLM 에
                        **한 번** 고치게 한다(entity_extractor.extract_bpm_from_document).
  2) `repair`         — 그래도 남은 것을 **코드로** 고친다. 그래프 불변식은 LLM 이 지키리라 믿지 않는다.

이름 수준에서 보는 까닭: 고치기를 LLM 에 맡길 때 LLM 이 쓴 말(작업 이름) 그대로 결함을 말해야 알아듣는다.

흐름의 뜻(빌더와 같다): 작업 목록 순서가 주 흐름이다. 바로 앞 작업이 분기의 after_task 이면 그 사이는
분기를 거친다(직선으로 잇지 않는다). 분기의 갈래는 to_task(작업) 또는 to_end(결말 이름) 하나로 간다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class _Branch(Protocol):
    condition: str
    to_task: str
    to_end: str


@dataclass
class Defect:
    kind: str          # unreachable_task | duplicate_branch_target | too_few_branches | unknown_target | unknown_anchor
    where: str         # 사람이 읽는 자리(작업/분기 이름)
    detail: str

    def text(self) -> str:
        return f"- [{self.kind}] {self.where}: {self.detail}"


@dataclass
class Report:
    defects: list[Defect] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.defects

    def text(self) -> str:
        return "\n".join(d.text() for d in self.defects)


def _norm(s: str | None) -> str:
    return (s or "").strip()


def find_defects(proc: Any) -> Report:
    """LLM 이 낸 한 프로세스(`_ExtractedProcess`)의 결함 — 이름 수준."""
    rep = Report()
    names = [_norm(t.name) for t in proc.tasks]
    name_set = set(names)
    after_of = {}
    for g in proc.gateways or []:
        a = _norm(g.after_task)
        if a not in name_set:
            rep.defects.append(Defect("unknown_anchor", _norm(g.name), f"after_task '{a}' 가 작업 목록에 없다"))
            continue
        after_of.setdefault(a, []).append(g)
        targets = []
        for b in g.branches or []:
            to_task, to_end = _norm(getattr(b, "to_task", "")), _norm(getattr(b, "to_end", ""))
            if to_task:
                if to_task not in name_set:
                    rep.defects.append(Defect("unknown_target", _norm(g.name), f"갈래 '{_norm(b.condition)}' 의 to_task '{to_task}' 가 작업 목록에 없다"))
                    continue
                targets.append(("task", to_task))
            elif to_end:
                targets.append(("end", to_end))
        distinct = set(targets)
        if len(distinct) < len(targets):
            rep.defects.append(Defect("duplicate_branch_target", _norm(g.name),
                                      "서로 다른 조건의 갈래가 같은 곳으로 간다 — 진짜 분기가 아니면 분기를 없애고, 분기면 각 조건에서 실제로 다음에 하는 일로 보낸다"))
        if len(distinct) < 2:
            rep.defects.append(Defect("too_few_branches", _norm(g.name), "갈래가 서로 다른 곳 2개 미만이다"))

    # 시작에서 닿지 않는 작업(pdf2bpmn unreachable_node) — 빌더와 같은 흐름 규칙으로 따진다:
    #   앞 작업 → 다음 작업(앞 작업이 분기로 빠지지 않으면) · after_task → 분기 → 갈래 대상
    adj: dict[str, set[str]] = {}
    for i in range(1, len(names)):
        if names[i - 1] not in after_of:
            adj.setdefault(names[i - 1], set()).add(names[i])
    for a, gs in after_of.items():
        for g in gs:
            for b in g.branches or []:
                t = _norm(getattr(b, "to_task", ""))
                if t in name_set:
                    adj.setdefault(a, set()).add(t)
    seen, stack = set(), names[:1]
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack.extend(adj.get(n, ()))
    for i, n in enumerate(names):
        if i and n not in seen:
            prev = names[i - 1]
            how = f"바로 앞 '{prev}' 는 분기로 빠진다" if prev in after_of else "앞에서 이어지는 흐름이 없다"
            rep.defects.append(Defect("unreachable_task", n,
                                      f"시작에서 닿지 않는다 — {how}. 어느 분기의 어떤 조건에서 이 작업으로 오는지 갈래로 밝힌다"))
    return rep


def repair_flows(task_ids: list[str], flows: list, gateways: list, *, new_flow) -> tuple[list, list]:
    """ID 수준에서 남은 결함을 코드로 고친다. (flows, gateways) 를 돌려준다.

    - 같은 (출발, 도착) 흐름은 하나만
    - 분기의 나가는 대상이 서로 다른 곳 2개 미만이면 분기를 없애고 들어오던 쪽을 그 대상에 바로 잇는다
    - 들어오는 흐름이 없는 작업(첫 작업 제외)은 바로 앞 작업에서 잇는다 — 빌더의 직선이 분기 때문에 끊긴 경우
    `new_flow(src, dst, name="")` 은 흐름 DTO 를 만드는 함수.
    """
    # 1) 중복 흐름
    seen, uniq = set(), []
    for f in flows:
        k = (f.source_id, f.target_id)
        if k in seen:
            continue
        seen.add(k)
        uniq.append(f)
    flows = uniq

    # 2) 갈래가 모자란 분기는 없앤다
    keep = []
    for g in gateways:
        outs = [f for f in flows if f.source_id == g.id]
        ins = [f for f in flows if f.target_id == g.id]
        if len({f.target_id for f in outs}) >= 2 and ins:
            keep.append(g)
            continue
        flows = [f for f in flows if f.source_id != g.id and f.target_id != g.id]
        if outs:
            for i in ins:
                flows.append(new_flow(i.source_id, outs[0].target_id, outs[0].name or ""))
    gateways = keep

    # 3) 들어오는 흐름이 없는 작업 — 빌더의 직선 규칙(앞 작업이 분기로 빠질 때만 끊는다)을 그대로 따져 본다
    explicit_out = {f.source_id for f in flows}
    explicit_in = {f.target_id for f in flows}
    for i in range(1, len(task_ids)):
        a, b = task_ids[i - 1], task_ids[i]
        backbone = a not in explicit_out
        if b not in explicit_in and not backbone:
            flows.append(new_flow(a, b, ""))
            explicit_in.add(b)
    return flows, gateways
