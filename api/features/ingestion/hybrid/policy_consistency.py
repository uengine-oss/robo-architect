# -*- coding: utf-8 -*-
"""Policy 가 **자기 설명과 다른 Command 를 부르는가** (2026-10-06).

## 왜 재나

기준 그래프를 세어 보니 Policy 6개 중 하나가 이랬다 —

```
설명   "When 연차 부여됨 in ApprovalWorkflow then **GrantAnnualLeave** in LeaveEntitlement…"
엣지   INVOKES → **DeductAnnualLeaveBalance**
```

업무로 맞는지 틀린지를 따지기 전에, **자기 설명과 엣지가 다르다.** 이것은 사람의
판단이 필요 없는 불일치라 기계가 잡을 수 있다 — 나머지(인과가 거꾸로인가)는
의미의 문제라 여기서 다루지 않는다.

## 왜 막지 않고 **세기만** 하나

이 저장소는 문턱을 먼저 만들었다가 틀린 적이 있다(9/29). 여기서는 **보고만** 한다 —
`pipeline_ready` 를 뒤집지 않는다. 몇 건인지, 어느 Policy 인지가 보이면 사람이
판단할 수 있고, 판단이 쌓이면 그때 규칙을 만든다.

승격이 **같은 이름의 Command 를 두 벌** 만드는 것도 같은 성격이라 함께 센다
(PROMO-1 · done6 §134). 고치는 것은 별도 결정이다.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

__all__ = ["declared_command", "check_policy_targets", "duplicate_commands"]

# "… then GrantAnnualLeave in LeaveEntitlement …" 에서 `GrantAnnualLeave`.
# 한글 설명에도 Command 이름은 영문 식별자로 적힌다.
# 대소문자를 가리지 않는다 — 설명은 LLM 이 쓴 문장이라 `then`·`Then`·`THEN` 이 섞인다.
_THEN = re.compile(r"\bthen\s+(?P<name>[A-Za-z][A-Za-z0-9_]*)", re.IGNORECASE)


def declared_command(description: str | None) -> str | None:
    """설명이 **스스로 적어 둔** Command 이름. 안 적혀 있으면 `None`.

    `None` 은 "틀렸다" 가 아니라 **"비교할 근거가 없다"** 다. 산문으로 적힌 설명이
    대부분이라, 없는 것을 불일치로 세면 거의 전부가 불일치가 된다.
    """
    if not description:
        return None
    m = _THEN.search(description)
    return m.group("name") if m else None


def check_policy_targets(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """`{policy, description, command}` 들에서 **설명과 엣지가 다른 것**을 고른다.

    돌려주는 것 —
      checked    비교할 수 있었던 수(설명에 `then <Command>` 가 있는 것)
      mismatched 그중 엣지가 다른 것
      samples    사람이 바로 볼 수 있게 몇 개(최대 5)
    """
    checked = 0
    samples: list[dict[str, str]] = []
    for row in rows or []:
        declared = declared_command(row.get("description"))
        if not declared:
            continue
        checked += 1
        actual = (row.get("command") or "").strip()
        if actual and actual.lower() != declared.lower():
            if len(samples) < 5:
                samples.append({
                    "policy": row.get("policy") or "",
                    "declared": declared,
                    "actual": actual,
                })
    return {"checked": checked, "mismatched": len(samples), "samples": samples}


def duplicate_commands(names: Iterable[str]) -> dict[str, Any]:
    """같은 이름의 Command 가 두 벌 이상인가 (PROMO-1).

    이름만 본다 — 어느 쪽이 중복인지는 **출처와 소유 Aggregate** 가 가린다
    (done6 §134). 여기서는 "있다/없다/몇 개" 까지다.
    """
    seen: dict[str, int] = {}
    for n in names or []:
        key = (n or "").strip()
        if key:
            seen[key] = seen.get(key, 0) + 1
    dups = {k: v for k, v in seen.items() if v > 1}
    return {
        "total": sum(seen.values()),
        "unique": len(seen),
        "duplicated": sorted(dups),
        "extra": sum(v - 1 for v in dups.values()),
    }
