# Reference: Strategize

## Goal
Classify each affected subdomain as `CORE`, `SUPPORTING`, or `GENERIC`, reusing existing strategic memory when provided.

## Questions
- Would customers feel a difference if we build this ourselves instead of buying it?
- Is there a mature external solution?
- What is the real differentiator in this Proposal?
- Is any classification different from existing memory? If yes, explain why.

## Output

```json
{
  "StrategizeArtifact": {
    "classifications": [
      { "subDomain": "주문", "kind": "CORE", "rationale": "구매 전환과 직접 연결된다", "buildVsBuy": null },
      { "subDomain": "상품", "kind": "SUPPORTING", "rationale": "주문을 지원하는 카탈로그 관리", "buildVsBuy": null }
    ],
    "differentiation": {
      "valueProposition": "빠른 주문과 정확한 재고 반영",
      "differentiator": "주문 안정성",
      "personas": ["고객", "판매자"]
    }
  }
}
```

## Rules
1. Every affected subdomain must have kind `CORE`, `SUPPORTING`, or `GENERIC`.
2. Recheck suspicious all-Core or all-Generic results.
3. Generic subdomains should include build-vs-buy candidates when obvious.
4. Use the user's language.
