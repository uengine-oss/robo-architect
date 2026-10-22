# -*- coding: utf-8 -*-
"""서비스 ID — **사람이 정하는 식별자**.

프로젝트 id(`prj_` + 난수)와 적재 세션 id(uuid 앞 8자)는 우리가 만든 값이고,
프로젝트 id 는 그대로 **Postgres/AGE 의 graph 이름**이다. 기업에는 서비스를
식별하는 자기 체계가 있어서, 그 체계의 값을 어딘가 적어 둘 자리가 필요하다.

## 왜 graph 이름을 그 값으로 쓰지 않나

graph 이름은 `^[a-z][a-z0-9_]{0,62}$` 다 — 하이픈도 대문자도 못 쓴다. 기업 체계가
`ROBO-2026-001` 같은 모양이면 거기에 넣을 수 없고, 넣으려면 값을 **변형**해야
하는데 그러면 두 값이 어긋난다. 그래서 **표시용 ID 와 물리 이름을 가른다** —
`store.py` 머리말이 프로젝트 이름을 가른 것과 같은 이유다.

덤으로 이것이 "나중에 못 바꾼다" 는 결정과도 맞는다. 사용자 지시는 변경 불가인데,
만약 이 값이 graph 이름이었다면 변경 가능으로 바꾸는 날 **그래프를 다시 써야**
한다. 지금 구조에서는 그날이 와도 한 줄짜리 UPDATE 다.

## 모양

```
ROBO-2026-001   HR_LEAVE_01   erp.billing.v2        ← 된다
ROBO 2026       연차관리       a                      ← 안 된다
```

영문·숫자로 시작하고 끝나며, 가운데에 `-` `_` `.` 을 쓸 수 있다. 2~64자.

⚠ **이 규칙은 추측이다.** 사용자가 기업 체계의 모양을 아직 알려 주지 않았다.
한글이나 공백을 허용하지 않는 이유는 이 값이 로그·URL·내보낸 파일 이름에 섞여
나가기 때문이다 — 허용해야 한다면 아래 `_SHAPE` **한 줄만** 고치면 된다.
"""

from __future__ import annotations

import re

__all__ = ["normalize", "validate", "SHAPE_HELP"]

# 모양을 바꿔야 하면 여기만 고친다. 두 곳(프로젝트·적재)이 이 하나를 본다.
_SHAPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}[A-Za-z0-9]$")

SHAPE_HELP = (
    "서비스 ID 는 영문·숫자로 시작하고 끝나며, 가운데에 - _ . 을 쓸 수 있습니다 "
    "(2~64자). 예: ROBO-2026-001"
)


def normalize(raw: str | None) -> str | None:
    """빈 값과 안 준 값을 하나로 만든다.

    화면의 빈 칸은 `""` 로 오고 API 를 직접 부르면 아예 안 온다. 둘을 같게 보지
    않으면 "비웠는데 검사에 걸린다" 가 된다.
    """
    value = (raw or "").strip()
    return value or None


def validate(raw: str | None) -> str | None:
    """모양을 본다. 안 준 값은 그대로 `None` — **서비스 ID 는 필수가 아니다.**

    필수로 하지 않는 이유: 기존 프로젝트에는 이 값이 없고(사용자가 "상관없음"
    이라 했다), 체계를 아직 받지 못한 사람이 프로젝트를 못 만들면 안 된다.
    """
    value = normalize(raw)
    if value is None:
        return None
    if not _SHAPE.match(value):
        raise ValueError(SHAPE_HELP)
    return value
