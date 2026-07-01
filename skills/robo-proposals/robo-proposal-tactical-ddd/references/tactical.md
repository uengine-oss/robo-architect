# Reference: Tactical

## Goal
Derive Aggregate Design Canvas artifacts from Define contexts.

## Aggregate Boundary
Use these questions:

- Must these entities change together in one transaction?
- Is this an invariant consistency boundary?
- Can a Value Object remain a Value Object instead of becoming an Aggregate?
- Is the Aggregate small enough to avoid unnecessary contention?

## Output

```json
{
  "TacticalArtifact": {
    "aggregates": [{
      "name": "Order",
      "description": "고객의 주문과 주문 항목을 관리한다",
      "boundaryRationale": "Order와 OrderLine은 주문 생성 시 한 트랜잭션 일관성이 필요하다",
      "stateTransitions": [{ "from": "Draft", "to": "Placed", "trigger": "PlaceOrder" }],
      "invariants": ["주문 항목은 1개 이상이어야 한다", "총액은 0보다 커야 한다"],
      "correctivePolicies": ["재고 부족 시 주문 생성 실패 이벤트를 남긴다"],
      "handledCommands": ["PlaceOrder", "CancelOrder"],
      "createdEvents": ["OrderPlaced", "OrderCanceled"],
      "throughput": {
        "commandHandlingRate": { "avg": "medium", "max": "high" },
        "totalClients": { "avg": "medium", "max": "high" },
        "concurrencyConflictChance": { "avg": "low", "max": "medium" }
      },
      "size": {
        "eventGrowthRate": { "avg": "low", "max": "medium" },
        "lifetime": { "avg": "30d", "max": "1y" },
        "eventsPersisted": { "avg": "5/order", "max": "20/order" }
      }
    }]
  }
}
```

## Rules
1. Each Aggregate should have at least two meaningful invariants when the domain allows it.
2. Commands and Events must agree with Define inbound/outbound messages and business decisions.
3. State transitions should name Command/Event triggers.
4. Do not model Money, Address, OrderLine, or other Value Objects as Aggregates unless they have their own lifecycle.
5. Use the user's language.
