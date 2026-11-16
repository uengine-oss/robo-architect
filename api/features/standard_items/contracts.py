"""표준 항목(데이터 사전) 조회 — 공급원과 무관한 모양.

공급원은 망마다 다르다.

- 포스코망: POSCO 표준항목 MCP (`searchDataDictionary`) — `mcp_provider.py`
- 그룹사망: (나중) LLM 이 KS 철강 표준을 검색해 적용하는 공급원 — 같은 자리에 꽂는다

설계 흐름(속성 생성 단계)은 이 파일의 `StandardItemProvider` 만 안다. 공급원이 무엇이든
돌려주는 것은 `StandardLookup` 하나 — 표준항목 칸 + **출처** + **조회 시각** + (실패면) 오류.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class StandardItem:
    """표준항목 한 건. 첫 칸(`standard_korean_name`) 말고는 비어 있을 수 있다."""

    standard_korean_name: str
    standard_english_id: str | None = None
    value_type: str | None = None            # stdItemValueType  값유형구분
    data_length: int | None = None           # dataLength        데이터자리수
    decimal_length: int | None = None        # decimalLength     소수점자리수
    code_item: str | None = None             # codeItem          코드항목여부 (값 모양 미확인 — 문자열 그대로)
    uom: str | None = None                   # mesUnitOfMeasure  MES_UOM
    macro_micro_type: str | None = None      # macroMicroItemType
    supervisory_dept: str | None = None      # supervisoryDept   주관부서명
    status: str | None = None                # standardItemStatus 표준항목상태구분
    definition: str | None = None            # standardItemDefinitionContent
    management_method: str | None = None     # standardItemManagementMethodExplanation
    raw: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True)
class StandardLookup:
    """한 번의 조회 결과. `error` 가 있으면 **표준 미확인** 이다(항목이 없다는 뜻이 아니다)."""

    keyword: str
    items: tuple[StandardItem, ...]
    source: str                              # 예: "posco-mcp:http://ace.posco.com:8029/mcp"
    checked_at: str                          # ISO-8601 UTC
    error: str | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@runtime_checkable
class StandardItemProvider(Protocol):
    """표준 항목 조회 공급원.

    `search` 는 **예외를 밖으로 내지 않는다** — 연결 실패·시간 초과는 `StandardLookup.error`
    로 돌려준다. 설계 흐름은 이 결과로 멈추지 않는다.
    """

    @property
    def source(self) -> str: ...

    async def search(self, keyword: str) -> StandardLookup: ...
