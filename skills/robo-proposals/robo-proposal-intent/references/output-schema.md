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
  ] },

  // 요소별 레거시 근거 — 모든 항목 필수(없으면 빈 배열):
  "legacyRefs": [
    { "nodeId": "code:<project>/<file>:<function>",
      "role": "derived-from", "evidence": "상태 전이 검증·갱신 트랜잭션이 이 Aggregate 경계로 이동" }
  ]
}
```

## 요소별 레거시 근거(legacyRefs) 불변식 — strategic·tactical 공통

- **모든 요소(strategic 카테고리 항목 + tacticalDiff 항목)는 `legacyRefs` 배열을 가진다.**
  레거시에 대응 근거가 없는 신규 요소는 빈 배열 `[]`로 정직하게 표기한다 — 생략하지 않는다.
- `nodeId`는 **이 실행에서 `cluster_retrieve` 검색 결과 또는 `node_detail` 성공 응답으로 실제
  확인한 ID만** 사용한다. 기억·추측으로 ID를 만들지 않는다. 서버가 관찰집합 밖 ID를 제거하고
  경고를 남긴다.
- 항목 형상: `{"nodeId": "<확인된 id>", "role"?: "derived-from|refines|reads|writes",
  "evidence"?: "<이 노드가 근거인 이유 한 줄>", "field"?: "<특정 필드 근거일 때만>"}`.
- 같은 요소에 같은 `nodeId`를 중복하지 않는다. 요소당 근거는 판단에 실제 사용한 것만(보통 1~4개).

### 내용 단위 인용 — 규칙·사례·테이블까지 꼬리표를 정밀하게

응답에 **내장되어 온**(별도 id 가 없는) 업무 규칙·사례·테이블이 근거라면, 함수 `nodeId` 에
본 내용을 그대로 첨부하라. 서버가 그래프에서 실제 노드로 해석해 꼬리표를 그 단위로 찍는다.

- 규칙: `{"nodeId": "<그 규칙을 본 함수 id>", "rule": "<응답에서 본 규칙 문장 그대로>"}`
- 사례: `{"nodeId": "<함수 id>", "example": {"given": "...", "when": "...", "then": "..."}}`
  (응답에서 본 사례의 given/when/then 을 그대로 — 일부 키만 있어도 된다)
- 테이블: `{"nodeId": "<그 테이블 참조를 본 함수 id>", "table": "<테이블명>", "role": "reads|writes"}`
  (검색 결과에 TABLE 노드 id 가 직접 있으면 그 id 를 바로 쓰고 이 필드는 불필요)

문장·내용을 바꿔 쓰지 말고 **본 그대로** 옮겨라 — 서버 대조에 실패하면 그 인용은 기각되고
경고가 남는다. 요소가 특정 규칙에서 유래했으면 함수 id 만 쓰지 말고 규칙 인용을 우선하라.

## 어떤 라벨이 무엇을 갖는가 (필수 채움)
| nodeLabel | 부모 ref | 필수 fields | properties | 기타 |
|---|---|---|---|---|
| Aggregate | boundedContextId | rootEntity, description | 엔티티 속성 전부 | semanticDiff로 VO/Enum/Exception, **invariants** |
| Command | aggregateId | actor, category, inputSchema | 명령 파라미터 | **userStoryRefs**, **gwt** 필수, **ui** |
| Event | commandId | version, payload | 이벤트 페이로드 | past-tense 이름 |
| ReadModel | boundedContextId | actor, isMultipleResult, description | 조회 필드 | userStoryRefs, **ui** |
| Policy | boundedContextId | description, condition | — | triggerEventId, invokeCommandId |

## 절대 규칙
0. 모든 항목은 `legacyRefs` 배열을 가진다(위 불변식) — 근거 없으면 `[]`.
1. 모든 CREATE는 `tempId`/`nodeId` + 부모 ref를 채운다 — 안 그러면 그래프에서 고아가 된다.
2. **Command는 반드시** `inputSchema`+`properties`(파라미터), `userStoryRefs`(어느 US를 구현하는지), `gwt`(최소 1개 시나리오)를 채운다.
3. Event는 발행 Command(`commandId`)와 `payload` 속성을 갖는다. 각 Command는 최소 1개 Event를 emit.
4. 모든 Aggregate/Command/Event/ReadModel은 `properties`로 도메인 속성을 갖는다(이름만 있는 빈 노드 금지).
5. 기존 노드는 입력 "도메인 구성 요소 목록"의 실제 id를 ref로 사용하고 `op/changeType:"MODIFY"`.
