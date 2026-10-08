# -*- coding: utf-8 -*-
"""`full-tree` 가 **같은 부모 id 를 두 번 묻지 않는지** (2026-10-08).

## 왜 이 검사가 있나

산출물 문서의 Event 표에서 `approvalLineId(String)` 이 **네 번** 찍혔다. 재 보니
그래프에는 필드가 한 개씩만 있었고, 불어난 자리는 이 라우터였다 —

```
evt_ids 를 aggregate.events 와 command.events **양쪽에서** 모은다
  → 한 Event id 가 2번 들어간다 (Aggregate 둘에 걸린 Event 는 4번)
  → `UNWIND $parent_ids as pid` 가 같은 (pid, prop) 짝을 그만큼 낸다
  → `collect(prop {...})` 가 **필드를 그 배수로** 묶는다
```

실측(기준 프로젝트 `prj_16972790c0`) — Event 필드가 **242행인데 서로 다른 id 는 91개**.

**오류는 안 났다.** 같은 값이 더 많이 나올 뿐이라서, 문서를 열어 보기 전까지 몰랐다.
그래서 "중복이 생기지 않는다" 를 여기에 못 박는다. `implementationFiles` 질의도
같은 `UNWIND` 모양이라 같은 결함이었다 — 그쪽은 값이 비어 있어 안 보였다.
"""

from __future__ import annotations

import re
from pathlib import Path

ROUTER = Path(__file__).resolve().parent / "router.py"


def _source() -> str:
    return ROUTER.read_text(encoding="utf-8")


def test_parent_ids_are_unique() -> None:
    """`parent_ids` 를 만들 때 중복을 떨어낸다."""
    source = _source()
    assert "parent_ids = list(dict.fromkeys([" in source, (
        "parent_ids 가 중복을 떨어내지 않는다 — UNWIND 가 필드를 배수로 묶는다"
    )


def test_event_ids_still_collected_from_both_places() -> None:
    """양쪽에서 모으는 것 **자체는 맞다** — 합친 뒤에 떨어내야 한다.

    Event 는 aggregate 아래에도, command 아래에도 달린다. 한쪽만 보면 필드가
    **빠지는** 쪽이 생긴다. 그래서 모으기는 그대로 두고 중복만 떨어낸다.
    """
    source = _source()
    block = source[source.index("evt_ids: list[str] = []"):source.index("rm_ids = list(")]
    assert block.count('a.get("events"') == 1, "aggregate 쪽에서 모으는 것이 사라졌다"
    assert block.count('c.get("events"') == 1, "command 쪽에서 모으는 것이 사라졌다"


def test_dedupe_keeps_order() -> None:
    """`dict.fromkeys` 는 **처음 나온 순서**를 지킨다 — 정렬이 뒤집히면 안 된다."""
    ids = ["agg1", "cmd1", "evt1", "evt1", "evt2", "agg1"]
    assert list(dict.fromkeys(ids)) == ["agg1", "cmd1", "evt1", "evt2"]


def test_unwind_queries_are_the_ones_we_fixed() -> None:
    """고친 `parent_ids` 를 쓰는 질의가 **둘**이다 — 하나만 고치면 다른 쪽이 남는다."""
    source = _source()
    unwinds = re.findall(r"UNWIND \$parent_ids as (\w+)", source)
    assert sorted(unwinds) == ["eid", "pid"], (
        "parent_ids 를 UNWIND 하는 질의가 둘이어야 한다(속성·구현파일). 지금: %r" % unwinds
    )
