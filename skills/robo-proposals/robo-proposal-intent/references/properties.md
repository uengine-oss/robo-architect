# Reference: Property (HAS_PROPERTY)

Aggregate/Command/Event/ReadModel은 모두 `properties: [...]`로 도메인 속성을 갖는다.
applier가 각 항목을 Property 노드로 만들고 부모와 `HAS_PROPERTY`로 연결한다. **이름만 있는 빈 설계 노드 금지.**

## Property 필드
```json
{
  "name": "orderId",          // camelCase
  "type": "UUID",             // Java 타입: UUID, String, Long, int, Boolean, BigDecimal, LocalDateTime, List<String> ...
  "description": "주문 식별자",
  "displayName": "주문 ID",    // 선택(UI 라벨, 언어 설정 반영)
  "isKey": true,              // PK 여부
  "isForeignKey": false,      // 타 노드 참조 여부
  "isRequired": true,
  "fkTargetHint": "Aggregate:menu:menuId"   // FK일 때 "<TargetType>:<TargetKey>:<TargetProp>"
}
```

## 규칙
- 각 Aggregate 루트는 정확히 1개 `isKey:true` 속성(식별자)을 갖는다.
- 다른 Aggregate를 참조하는 속성은 `isForeignKey:true` + `fkTargetHint`.
- Command properties = 파라미터(inputSchema와 일치). Event properties = payload 필드.
- 타입은 구현 가능한 구체 타입으로(막연한 "object" 지양; 복합값은 ValueObject로 Aggregate에 정의).
