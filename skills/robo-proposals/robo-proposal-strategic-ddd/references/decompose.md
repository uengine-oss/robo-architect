# Reference: Decompose

## Goal
Group Discover events into domain-language subdomains. Assign one-line responsibilities, adjacency, and coupling notes.

## Questions
- Which events naturally belong together?
- Which pivotal events suggest boundaries?
- Does each subdomain have coherent language and responsibility?
- Does changing one subdomain force another to change?

## Output

```json
{
  "DecomposeArtifact": {
    "subDomains": [
      { "name": "주문", "responsibility": "주문 접수와 상태 관리를 책임진다", "eventRefs": ["주문이 생성됐다"] }
    ],
    "adjacency": [{ "from": "주문", "to": "상품" }],
    "couplingNotes": ["주문과 상품은 재고 변경 이벤트로 느슨히 결합한다"]
  }
}
```

## Rules
1. Use domain terms, not REST, Kafka, Controller, Service, or table names.
2. Every important event should belong to a subdomain.
3. A one-subdomain result is allowed only with a clear coupling note.
4. Use the user's language.
