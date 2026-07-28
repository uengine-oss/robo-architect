# Data Model

```json
{
  "version": 2,
  "stage": "INTENT",
  "retrieves": [{
    "query": "...",
    "database": "neo4j",
    "searchedNodes": [{"id":"...","name":"...","label":"...","summary":"...","relevance":0.0,"rulesCount":1}],
    "inspections": [{"nodeId":"...","ok":true,"name":"...","label":"...","source":{"file_path":"...","start_line":1,"end_line":2}}],
    "at": "..."
  }]
}
```

Invariants:

- searched와 inspected는 별도 사실이며 inspected가 searched의 부분집합이라고 가정하지 않는다.
- UI count는 모든 stage의 두 ID 집합 합집합이다.
- source line은 Analyzer 응답을 그대로 저장하며 UI가 재계산하지 않는다.
- 구형 `nodes`는 read adapter에서 `searchedNodes`로만 해석한다.

