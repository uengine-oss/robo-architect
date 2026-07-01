# Reference: Connect

## Goal
Classify context interactions as Event, Command, or Query. Prefer event-driven pub/sub unless immediate freshness or directed work is required.

## Decision Guide
| Situation | Pattern |
| --- | --- |
| Sender does not need to know listeners and no immediate response is needed | `EVENT` |
| Sender directs a specific context to do work | `COMMAND` |
| Sender needs a fresh value immediately | `QUERY` |

## Coupling Checks
- Bidirectional sync dependency is forbidden.
- Sync chain depth greater than 3 is risky.
- One context talking directly to five or more contexts deserves a warning.

## Output

```json
{
  "ConnectArtifact": {
    "interactions": [
      { "from": "주문", "to": "상품", "message": "ProductStockReserved", "kind": "EVENT", "sync": false, "rationale": "주문 후 재고 반영은 비동기로 충분" }
    ],
    "couplingWarnings": [],
    "messagingChannel": "Kafka"
  }
}
```

## Rules
1. Default to `EVENT` and `sync:false`.
2. Default messaging channel is Kafka unless Constitution/memory says otherwise.
3. Do not hide coupling risks.
4. Use the user's language.
