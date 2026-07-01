# Reference: Define

## Goal
Create a Bounded Context Canvas for each affected context, reusing provided memory and Connect interactions.

## Canvas Fields
Each context should include:

- `name`
- `purpose`
- `classification`: `CORE`, `SUPPORTING`, or `GENERIC`
- `businessModel`: one or more of `revenue`, `engagement`, `compliance`, `cost_reduction`
- `evolution`: `genesis`, `custom_built`, `product`, or `commodity`
- `domainRoles`
- `inbound` and `outbound`: `{collaborator,message,type: Query|Command|Event}`
- `ubiquitousLanguage`: at least five terms when possible
- `businessDecisions`
- `assumptions`
- `verificationMetrics`
- `openQuestions`
- `languageClashes`

## Output

```json
{
  "DefineArtifact": {
    "contexts": [{
      "name": "주문",
      "purpose": "고객 주문 접수와 상태 추적을 책임진다",
      "classification": "CORE",
      "businessModel": ["revenue"],
      "evolution": "custom_built",
      "domainRoles": ["execution"],
      "inbound": [{ "collaborator": "고객", "message": "PlaceOrder", "type": "Command" }],
      "outbound": [{ "collaborator": "상품", "message": "ProductStockReserved", "type": "Event" }],
      "ubiquitousLanguage": [
        { "term": "Order", "definition": "고객이 구매하기로 한 상품 묶음" },
        { "term": "OrderLine", "definition": "주문 내 개별 상품과 수량" },
        { "term": "OrderStatus", "definition": "주문의 진행 상태" },
        { "term": "Cart", "definition": "주문 전 고객이 담아둔 상품 목록" },
        { "term": "Customer", "definition": "주문을 수행하는 사용자" }
      ],
      "businessDecisions": ["재고 부족 시 주문을 거절한다"],
      "assumptions": [],
      "verificationMetrics": ["주문 생성 실패율"],
      "openQuestions": [],
      "languageClashes": []
    }]
  }
}
```

## Rules
1. Inbound/outbound must agree with Connect message flow.
2. Business decisions should be decisions this context can make autonomously.
3. Surface language clashes if the same term means different things across contexts.
4. Use the user's language.
