"""맵 투영을 통과한 값을 파이썬 모양으로 되돌린다.

Ontological 은 **맵 투영 안에 넣은 배열을 JSON 문자열로 돌려준다.**

```
RETURN bc.userStoryIds AS u                 →  ['US-FR-001', 'US-FR-002']   list
RETURN {userStoryIds: bc.userStoryIds} AS m →  '["US-FR-001", "US-FR-002"]' str
```

**오류가 안 난다.** 그리고 문자열도 순회가 되므로 `for i in bc["userStoryIds"]`
가 글자를 하나씩 돈다 — 다섯 글자짜리 id 목록이 371개의 한 글자가 된다.

그 결과가 인제스천에서 이렇게 나왔다:

```
bc_us_ids 가 글자 목록 → 어떤 US 와도 안 맞음 → stories_context 빈 문자열
                       → LLM 이 입력 없이 불림 → Command 0개
```

애그리거트 22개 중 21개가 서브 요소 0개로 끝났고, 화면에는 "완료"로 보였다.
`enumerations`·`valueObjects` 두 개만 호출부에서 손으로 풀고 있었는데,
`userStoryIds`·`invariants` 는 빠져 있었다. 그래서 한 곳에 모은다.

관련: `enterprise-todo.md` §21
"""

from __future__ import annotations

import json
from typing import Any


def as_list(value: Any) -> list[Any]:
    """맵 투영을 통과한 배열 속성을 list 로 되돌린다.

    이미 list 면 그대로, JSON 문자열이면 풀고, None·빈 값·못 푸는 것은 `[]`.
    **문자열을 그냥 돌려주지 않는다** — 그러면 호출부가 글자를 순회한다.
    """
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        try:
            parsed = json.loads(s)
        except (json.JSONDecodeError, TypeError):
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def coerce_lists(row: dict[str, Any], *fields: str) -> dict[str, Any]:
    """`row` 의 주어진 필드들을 제자리에서 list 로 맞춘다."""
    for f in fields:
        row[f] = as_list(row.get(f))
    return row
