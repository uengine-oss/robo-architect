# -*- coding: utf-8 -*-
"""그래프가 거절한 것을 **사람이 읽을 수 있는 말**로 옮긴다.

## 왜 있어야 하나 (2026-10-02 실측)

중앙 DB 에서 `AUTH_ROLE_SECRET` 이 서버와 다른 PC 를 쓰면, 읽기 등급 사용자가
프로젝트를 여는 순간 이렇게 끝났다 —

```
서버 로그   neo4j.exceptions.AuthError · Neo.ClientError.Security.Unauthorized
화면       500 internal server error → "서버 오류"
```

**사람에게는 아무 말도 안 간 것이다.** 같은 원인을 `ensure_role` 쪽은 503 과 함께
"이 PC 의 `AUTH_ROLE_SECRET` 이 다르다" 로 말해 준다(`projects/roles.py`, `164d8db`).
한쪽은 말하고 한쪽은 침묵하는데, **사람이 먼저 만나는 쪽이 침묵하는 쪽**이다 —
잘못 설치된 PC 를 쓰는 사람은 무엇이 틀렸는지 알 길이 없다.

## 왜 여기서 가르나

읽기 등급은 **그 사람의 role 로 Bolt 에 붙는다**(`connection_binding.py`). 그래서
자격 실패는 바인딩할 때가 아니라 **나중에, 세션을 열 때** 난다 — 라우터 안이다.
라우터마다 이 둘을 해석하면 한 곳이 빠지고, **빠진 곳은 다시 500 으로 조용해진다.**
그래서 한 자리에 둔다.

```
AuthError    자격이 틀렸다      → 503. 서버가 아니라 **이 PC 의 설정**이 문제다
Forbidden    권한이 없다        → 403. 등급이 막은 것이고, 고장이 아니다
```

둘 다 **500 이 아니다.** 500 은 "우리 잘못이고 원인을 모른다" 는 뜻이고, 여기 둘은
원인을 정확히 안다.
"""

from __future__ import annotations

from typing import Any

__all__ = ["AUTH_DETAIL", "FORBIDDEN_DETAIL", "explain"]

# 고칠 수 있는 말이어야 한다. **증상이 아니라 할 일**을 적는다.
AUTH_DETAIL = (
    "이 PC 의 계정 비밀 값(AUTH_ROLE_SECRET)이 중앙 DB 서버의 값과 다릅니다. "
    "그래서 이 PC 에서만 프로젝트가 열리지 않습니다 — 다른 PC 에서는 멀쩡합니다. "
    "설치 담당자에게 이 메시지를 그대로 전해 주세요."
)

FORBIDDEN_DETAIL = (
    "이 프로젝트에서 그 작업을 할 권한이 없습니다. "
    "읽기 권한으로는 편집할 수 없습니다 — 담당자에게 쓰기 권한을 요청해 주세요."
)


def explain(exc: BaseException) -> tuple[int, str, str] | None:
    """`(상태코드, 코드, 사람에게 할 말)`. 우리가 아는 거절이 아니면 `None`.

    `None` 이면 **손대지 않는다** — 모르는 실패를 아는 척 옮기면, 진짜 고장이
    "권한 문제" 로 분류돼 조용히 묻힌다.
    """
    name = type(exc).__name__
    code = str(getattr(exc, "code", "") or "")

    # 드라이버 클래스 이름과 서버 코드를 **둘 다** 본다. 드라이버를 올리면 클래스가
    # 바뀔 수 있고, 게이트웨이를 거치면 코드만 오는 경우가 있다.
    if name in ("AuthError", "TokenExpired") or code.endswith("Security.Unauthorized"):
        return 503, "GRAPH_ROLE_AUTH_FAILED", AUTH_DETAIL
    if name == "Forbidden" or code.endswith("Security.Forbidden"):
        return 403, "GRAPH_PERMISSION_DENIED", FORBIDDEN_DETAIL
    return None


def payload(exc: BaseException) -> dict[str, Any] | None:
    """`explain` 을 응답 본문 모양으로. 라우터는 `detail` 을 읽는다."""
    told = explain(exc)
    if not told:
        return None
    _status, code, detail = told
    return {"detail": detail, "code": code}
