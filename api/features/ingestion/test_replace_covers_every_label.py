# -*- coding: utf-8 -*-
"""재적재는 **교체**다 — 만드는 라벨이 전부 지우는 목록에 있는가.

## 왜 이 검사가 있나

적재는 지우기로 시작한다(표준 경로 `clear_event_storming_nodes`, 하이브리드
`clear_all_hybrid_workspace` + 같은 ES 지우기). 그 "교체" 가 성립하려면 조건이
하나다 — **적재가 만드는 모든 라벨이 지우는 목록에 있어야 한다.**

하나라도 빠지면 앞 판의 노드가 새 판과 **섞여 남는다.** 그리고 그 모양은 조용하다:

```
2026-10-07 측정 — `Journey` · `JourneyStep` (spec 025) 이 두 목록 어디에도 없었다
그런데 여정의 걸음은 `(:JourneyStep)-[:SHOWS]->(:UI)` 로 화면을 가리키고,
**그 `UI` 는 지워진다.** 즉 재적재할수록 **어디도 가리키지 않는 여정**이 쌓인다.
```

목록을 손으로 맞추면 다음에 또 빠진다. 그래서 **코드에서 긁어 견준다** — 새
라벨을 만드는 순간 이 검사가 먼저 무다.

## 세는 법

적재 경로(`api/features/ingestion/`)의 Cypher 에서 `MERGE (x:Label`·`CREATE (x:Label`
을 긁는다. 대문자 라벨(`:RULE`·`:FUNCTION` 등)은 **애널라이저 소유**라 센 뒤
빼낸다 — 우리가 만드는 것이 아니고, 지워서도 안 된다.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

ING = Path(__file__).resolve().parent

CREATE = re.compile(r"(?:MERGE|CREATE)\s*\(\s*\w*\s*:\s*([A-Za-z_][A-Za-z0-9_]*)")

# 전부 대문자지만 **우리 것**인 라벨. 약자라서 그렇게 생겼을 뿐이다 —
# `UI`·`GWT` 를 애널라이저 소유로 보면 지우는 목록에서 빠지고, 재적재가
# 화면과 GWT 를 남긴다.
ES_ACRONYMS = {"UI", "GWT"}


def _analyzer_owned(label: str) -> bool:
    """애널라이저가 만드는 라벨인가 — UPPER_SNAKE 가 그쪽 관례다(`:RULE`·`:FUNCTION`)."""
    return label.isupper() and label not in ES_ACRONYMS

# 적재가 만들지만 **지우면 안 되는** 것. 이유를 같이 적는다.
KEEP = {
    # 프로젝트·사용자 표는 Postgres 이고, 그래프의 이 라벨들은 적재 산출물이 아니다.
    "Constitution",  # 041 — 프로젝트 헌장. 적재와 수명이 다르다
    "Proposal",      # 039 — 변경 제안. 적재가 지울 것이 아니다
}


def _labels_created() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in sorted(ING.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        if path.name.startswith("test_") or "tests" in path.parts:
            continue
        text = io.open(path, encoding="utf-8", errors="replace").read()
        for label in CREATE.findall(text):
            if _analyzer_owned(label):
                continue  # 애널라이저 소유 — 우리가 지울 것이 아니다
            found.setdefault(label, set()).add(str(path.relative_to(ING)))
    return found


def _wiped() -> set[str]:
    from api.features.ingestion.hybrid.ontology.schema import ALL_HYBRID_LABELS
    from api.features.ingestion.ingestion_workflow_runner import _ES_LABELS

    return set(ALL_HYBRID_LABELS) | set(_ES_LABELS)


def test_만드는_라벨이_전부_지우는_목록에_있다():
    created = _labels_created()
    wiped = _wiped()
    missing = {
        label: sorted(where)
        for label, where in created.items()
        if label not in wiped and label not in KEEP
    }
    assert not missing, (
        "재적재가 안 지우는 라벨이 있다 — 앞 판이 새 판과 섞여 남는다:\n"
        + "\n".join(f"  {label}: {', '.join(where)}" for label, where in missing.items())
    )


def test_여정도_지운다():
    """`Journey`·`JourneyStep` 이 빠져 있었다(2026-10-07). 그 자리를 못으로 박는다."""
    wiped = _wiped()
    assert "Journey" in wiped and "JourneyStep" in wiped


def test_검사가_실제로_라벨을_긁는다():
    """긁기가 0개를 돌려주면 위 검사는 **언제나 통과한다** — 그 함정을 먼저 막는다."""
    created = _labels_created()
    assert len(created) >= 10, f"라벨을 너무 적게 긁었다({len(created)}개) — 정규식을 확인한다"
    assert "Command" in created and "Journey" in created


def test_애널라이저_소유는_지우지_않는다():
    """UPPER_SNAKE 라벨의 생산자는 애널라이저다 — 적재가 지우면 **남의 데이터를 지운다.**

    `UI`·`GWT` 는 전부 대문자지만 **우리 것**이다(약자일 뿐이다). 그 둘을 저쪽으로
    분류하면 지우는 목록에서 빠지고, 재적재가 화면과 GWT 를 남긴다 — 이 검사가
    양쪽을 같이 본다.
    """
    wiped = _wiped()
    intruders = sorted(label for label in wiped if _analyzer_owned(label))
    assert not intruders, f"지우는 목록에 애널라이저 소유 라벨이 들어갔다: {intruders}"
    assert ES_ACRONYMS <= wiped, f"약자 라벨이 지우는 목록에서 빠졌다: {sorted(ES_ACRONYMS - wiped)}"
