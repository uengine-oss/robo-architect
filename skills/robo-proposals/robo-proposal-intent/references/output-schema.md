# Reference: 출력 스키마 (강화된 strategicDiff + tacticalDiff)

이 파일이 **출력 계약(contract)**이다. `proposal_apply.py`가 이 구조를 그대로 그래프로 반영한다.
모든 신규 항목은 `tempId`/`nodeId`(배치 내 고유)와 부모 참조를 채워 계층이 연결되게 한다.

## 최상위
```json
{ "action": "done", "strategicDiff": { ... }, "tacticalDiff": [ ... ], "journeys": [ ... ] }
```
명확화가 필요하면 `{ "action": "clarify", "questions": [...] }` (relationship/property 작업 전 단계).
`journeys`는 사용자 화면 흐름(선택) — references/journeys.md 참고.

## strategicDiff (요구사항 계층: BoundedContext(=Epic) → Feature → UserStory)
```json
{
  "version": 1,
  "epics": [
    { "op": "CREATE", "entityType": "epic", "entityId": null, "tempId": "EP-order",
      "entityTitle": "주문", "fields": { "description": {"after": "..."}, "classification": {"after": "core"} } }
  ],
  "features": [
    { "op": "CREATE", "entityType": "feature", "entityId": null, "tempId": "FT-order-place",
      "entityTitle": "음식 주문", "epicId": "EP-order" }
  ],
  "userStories": [
    { "op": "CREATE", "entityType": "userStory", "entityId": null, "tempId": "US-order-place",
      "entityTitle": "주문자: 음식을 선택해 주문한다",
      "featureId": "FT-order-place", "boundedContextId": "EP-order",
      "role": "주문자", "action": "메뉴에서 음식을 선택하고 수량을 지정해 주문한다",
      "benefit": "원하는 음식을 받기 위해",
      "acceptanceCriteria": ["Given 메뉴 등록됨, When 선택·수량 입력, Then 주문 생성"] }
  ],
  "processes": [
    { "op": "CREATE", "entityType": "process", "entityId": null, "tempId": "PROC-order",
      "entityTitle": "음식 주문 처리", "fields": { "steps": {"after": "선택→생성→검증→확정"} } }
  ]
}
```
- **Epic = BoundedContext** (별도 Epic 노드 없음). `epics`가 곧 요구사항 트리 최상위이자 Aggregate 컨테이너.
- 참조: feature→`epicId`, userStory→`featureId`(+`boundedContextId`). 기존 노드 수정 시 `op:"MODIFY"` + `entityId`(실제 id) + `fields`.

## tacticalDiff (설계 계층: Aggregate → Command → Event, +ReadModel/Policy)
배열. 각 항목:
```json
{
  "nodeId": "<tempId>",            // 배치 내 고유. 다른 항목이 이걸로 참조
  "nodeLabel": "Aggregate | Command | Event | ReadModel | Policy",
  "nodeTitle": "표시명",
  "changeType": "CREATE | MODIFY",
  "impactLevel": "HIGH | MEDIUM | LOW",
  "reason": "왜 이 변경이 필요한가",

  // 부모 참조(tempId 또는 기존 실제 id):
  "boundedContextId": "EP-order",  // Aggregate / ReadModel / Policy → 소속 BC
  "aggregateId": "AGG-order",      // Command → 소속 Aggregate
  "commandId": "CMD-place-order",  // Event → 발행 Command

  // 스칼라 속성(노드에 set):
  "fields": { "actor": "주문자", "category": "Create",
              "description": "...", "version": "1.0.0",
              "inputSchema": { "menuId": "UUID", "qty": "int" } },

  // 속성 목록 → HAS_PROPERTY 자식 노드:
  "properties": [
    { "name": "orderId", "type": "UUID", "isKey": true, "isRequired": true, "description": "주문 식별자" },
    { "name": "menuId", "type": "UUID", "isForeignKey": true, "fkTargetHint": "Aggregate:menu:menuId" },
    { "name": "totalPrice", "type": "Long", "isRequired": true }
  ],

  // Command 전용 — 추적성 & BDD:
  "userStoryRefs": ["US-order-place"],   // UserStory ─IMPLEMENTS→ Command
  "gwt": [
    { "scenario": "정상 주문",
      "given": { "name": "Aggregate: 주문", "description": "메뉴 등록 상태", "fieldValues": { "status": "NONE" } },
      "when":  { "name": "Command: 음식주문", "fieldValues": { "menuId": "m-1", "qty": "2" } },
      "then":  { "name": "Event: 음식주문됨", "fieldValues": { "totalPrice": "20000" } } }
  ],

  // Policy 전용 — 반응 정책(Event→Policy→Command):
  "triggerEventId": "EVT-order-placed",
  "invokeCommandId": "CMD-reserve-stock",

  // Aggregate 전용 — 불변식(→ HAS_INVARIANT, VERIFIED_BY):
  "invariants": [
    { "declaration": "주문 총액은 0보다 커야 한다", "verifyingCommandRefs": ["CMD-place-order"] }
  ],

  // Command/ReadModel 전용 — 화면(→ BC HAS_UI, ATTACHED_TO):
  "ui": { "name": "주문 화면", "description": "메뉴 선택·수량 입력 폼" },

  // Aggregate VO/Enum/Exception 변경 시:
  "semanticDiff": { "v": 1, "ops": [
    { "field": "valueObjects", "op": "obj_append", "obj_name": "Money",
      "obj_data": { "name": "Money", "fields": [{"name":"amount","type":"Long"},{"name":"currency","type":"String"}] } },
    { "field": "enumerations", "op": "obj_append", "obj_name": "OrderStatus",
      "obj_data": { "name": "OrderStatus", "items": ["PENDING","CONFIRMED","CANCELLED"] } }
  ] }
}
```

## 어떤 라벨이 무엇을 갖는가 (필수 채움)
| nodeLabel | 부모 ref | 필수 fields | properties | 기타 |
|---|---|---|---|---|
| Aggregate | boundedContextId | rootEntity, description | 엔티티 속성 전부 | semanticDiff로 VO/Enum/Exception, **invariants** |
| Command | aggregateId | actor, category, inputSchema | 명령 파라미터 | **userStoryRefs**, **gwt** 필수, **ui** |
| Event | commandId | version, payload | 이벤트 페이로드 | past-tense 이름 |
| ReadModel | boundedContextId | actor, isMultipleResult, description | 조회 필드 | userStoryRefs, **ui** |
| Policy | boundedContextId | description, condition | — | triggerEventId, invokeCommandId |

## 절대 규칙
1. 모든 CREATE는 `tempId`/`nodeId` + 부모 ref를 채운다 — 안 그러면 그래프에서 고아가 된다.
2. **Command는 반드시** `inputSchema`+`properties`(파라미터), `userStoryRefs`(어느 US를 구현하는지), `gwt`(최소 1개 시나리오)를 채운다.
3. Event는 발행 Command(`commandId`)와 `payload` 속성을 갖는다. 각 Command는 최소 1개 Event를 emit.
4. 모든 Aggregate/Command/Event/ReadModel은 `properties`로 도메인 속성을 갖는다(이름만 있는 빈 노드 금지).
5. 기존 노드는 입력 "도메인 구성 요소 목록"의 실제 id를 ref로 사용하고 `op/changeType:"MODIFY"`.
