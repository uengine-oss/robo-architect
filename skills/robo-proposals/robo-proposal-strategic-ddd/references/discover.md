# Reference: Discover

## Goal
Identify domain events introduced or affected by the Proposal, in time order. Also identify pivotal events, hotspots, external systems, and actors.

## Questions
- What happened, phrased in past tense?
- Which events are pivotal boundary candidates?
- Which rules are ambiguous or disputed?
- Which events originate outside our system?

## Output

```json
{
  "DiscoverArtifact": {
    "events": [{ "name": "주문이 생성됐다", "actor": "고객", "external": false }],
    "pivotalEvents": ["주문이 확정됐다"],
    "hotspots": [{ "text": "재고 부족 시 주문 처리 정책", "disposition": "RESOLVE_NOW" }],
    "externalSystems": []
  }
}
```

## Rules
1. Events are past-tense facts, not commands or Aggregates.
2. Behavioral changes require at least one event.
3. Include at least one pivotal event unless the change is purely informational.
4. Use the user's language.
