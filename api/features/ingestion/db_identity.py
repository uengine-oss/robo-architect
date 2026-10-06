# -*- coding: utf-8 -*-
"""DB 가 돌려준 **진짜 id** 를 모델에 심는다 — 못 심으면 **말한다**.

## 왜 한 자리에 모으나

승격은 요소를 만들 때 LLM 이 지어낸 임시 id 를 들고 가다가, DB 가 돌려준 UUID 로
덮어쓴다. 그 덮어쓰기가 여러 곳에서 이렇게 적혀 있었다 —

```python
try:
    cmd.id = created_cmd.get("id")
    cmd.key = created_cmd.get("key")
except Exception:
    pass
```

**실패하면 아무 일도 안 일어난다.** 그런데 실패한 뒤에도 코드는 계속 가고, 다음
단계는 그 객체의 id 로 관계를 잇는다 — 즉 **DB 에 없는 id 로 링크를 걸고, 링크는
조용히 안 붙는다.** 이 저장소가 여러 번 만난 모양이다(출처가 비는 요소, 안 붙는
관계). 사유가 사라지는 자리를 하나로 모으고, 거기서 한 번 말하게 한다.

## 왜 막지는 않나

여기서 예외를 올리면 **승격 전체가 선다.** 한 요소의 id 를 못 심은 것이 그만한
일은 아니다 — 나머지는 멀쩡히 만들어진다. 대신 **WARN 과 함께 어느 요소인지**를
남겨, 나중에 "이 링크가 왜 비었나" 를 물을 때 답이 로그에 있게 한다.
"""

from __future__ import annotations

from typing import Any, Mapping

from api.platform.observability.smart_logger import SmartLogger

__all__ = ["adopt_db_identity"]


def adopt_db_identity(
    target: Any,
    created: Mapping[str, Any] | None,
    *,
    kind: str,
    name: str = "",
    fields: tuple[str, ...] = ("id", "key"),
) -> bool:
    """`created` 의 값을 `target` 에 심는다. 심었으면 True.

    `target` 이 dict 면 키로, 객체면 속성으로 쓴다 — 두 모양이 섞여 들어온다.
    `created` 에 없는 필드는 건너뛴다(없는 것을 `None` 으로 덮으면 **있던 id 가
    사라진다**).
    """
    if created is None:
        SmartLogger.log(
            "WARN", f"{kind} 의 DB 응답이 비어 id 를 심지 못했다",
            category="ingestion.identity.missing",
            params={"kind": kind, "name": name},
        )
        return False

    wrote: list[str] = []
    try:
        for field in fields:
            if field not in created:
                continue
            value = created.get(field)
            if value is None:
                continue
            if isinstance(target, dict):
                target[field] = value
            else:
                setattr(target, field, value)
            wrote.append(field)
    except Exception as exc:  # noqa: BLE001 — 한 요소 때문에 승격을 세우지 않는다
        SmartLogger.log(
            "WARN",
            f"{kind} 에 DB id 를 심지 못했다 (이 요소의 링크가 안 붙을 수 있다): {exc}",
            category="ingestion.identity.failed",
            params={"kind": kind, "name": name, "error": str(exc),
                    "wrote": wrote, "target_type": type(target).__name__},
        )
        return False

    if not wrote:
        SmartLogger.log(
            "WARN", f"{kind} 의 DB 응답에 심을 값이 없었다",
            category="ingestion.identity.empty",
            params={"kind": kind, "name": name, "keys": sorted(created.keys())},
        )
        return False
    return True
