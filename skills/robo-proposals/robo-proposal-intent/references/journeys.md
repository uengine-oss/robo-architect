# Reference: Journey (사용자 여정 / 화면 흐름)

사용자가 목표를 달성하며 거치는 화면·단계의 흐름. **최상위 `journeys` 배열**로 출력한다(strategicDiff/tacticalDiff와 형제).
applier가 `BoundedContext ─HAS_JOURNEY→ Journey ─HAS_STEP→ JourneyStep`, `JourneyStep ─NEXT→ JourneyStep`,
`JourneyStep ─SHOWS→ UI`(해당 step이 가리키는 Command/ReadModel에 붙은 화면)를 만든다.

## 구조 (최상위)
```json
"journeys": [
  {
    "tempId": "JNY-order",
    "boundedContextId": "EP-order",
    "name": "음식 주문 여정",
    "description": "메뉴 조회부터 주문 확정까지",
    "steps": [
      { "tempId": "ST-browse", "name": "메뉴 조회", "kind": "screen",
        "readModelRef": "RM-menu-list", "next": ["ST-order"] },
      { "tempId": "ST-order", "name": "주문 생성", "kind": "screen",
        "commandRef": "CMD-place-order", "next": ["ST-confirm"] },
      { "tempId": "ST-confirm", "name": "주문 확정", "kind": "screen",
        "commandRef": "CMD-confirm-order", "next": [] }
    ]
  }
]
```

## 규칙
- 각 Journey는 하나의 BC(`boundedContextId`)에 속한다(보통 core BC의 주요 흐름).
- step `kind`: `screen`(화면) / `gateway`(분기). screen step은 `commandRef` 또는 `readModelRef`로 어떤 설계요소의 화면인지 가리킨다 → 그 요소에 붙은 UI에 SHOWS로 연결된다.
- `next`: 다음 step의 tempId 목록(분기면 여러 개). 마지막 step은 `[]`.
- 분기 step에는 `condition`(자연어 조건)을 줄 수 있다.
- 한 요구사항에 사용자 흐름이 뚜렷하면 1~2개 Journey를 만든다. 단순 CRUD만이면 생략 가능.

> UI는 Command/ReadModel의 `ui`로 생성되므로(references/invariants-ui.md), Journey의 screen step이 가리키는 설계요소에 `ui`가 있어야 SHOWS가 연결된다.
