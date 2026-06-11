# Skill: robo-proposal-context

## Purpose
Proposal의 Tactical Diff를 기반으로 그래프 DB 도메인 노드에서 **Impact Map**을 생성한다.
영향받는 노드 목록과 각 노드의 충돌 가능성(HIGH/MEDIUM/LOW)을 분석한다.

## Input (Human Prompt)
```
Proposal ID: PRO-NNN

Tactical Diff (변경 예정 도메인 요소):
[{...semanticDiff...}]

현재 시스템 구성 요소:
- id: US-001, type: UserStory, name: ...
- id: AGG-refund, type: Aggregate, name: ...
...
```

## Output Format
```json
[
  {
    "nodeId": "US-042",
    "nodeLabel": "UserStory",
    "nodeTitle": "전액 환불 처리",
    "conflictLevel": "MEDIUM",
    "reason": "부분 환불 추가 시 전액 환불 플로우와 분기 처리 필요"
  },
  {
    "nodeId": "AGG-refund",
    "nodeLabel": "Aggregate",
    "nodeTitle": "환불 Aggregate",
    "conflictLevel": "HIGH",
    "reason": "PartialRefundAmount VO 추가 및 불변 조건 추가 필요"
  },
  {
    "nodeId": null,
    "nodeLabel": "Policy",
    "nodeTitle": "환불 정책",
    "conflictLevel": "NONE",
    "reason": "관련 노드 없음"
  }
]
```

## Rules
1. **conflictLevel 판단 기준**:
   - HIGH: 동일 Aggregate/Command를 직접 수정하거나 새 Aggregate가 기존 Bounded Context에 추가되는 경우
   - MEDIUM: 연관된 UserStory·Feature 플로우에 분기 처리가 필요한 경우
   - LOW: BoundedContext 경계만 영향받는 경우
   - NONE: 연결된 도메인 노드가 없거나 영향 없는 경우
2. **nodeId 없는 요구사항**: `nodeId: null`, `conflictLevel: "NONE"`, `reason: "관련 노드 없음"` 으로 반환.
3. **출력은 JSON 배열**: ImpactMapEntry 목록만 반환.
4. **SSE 점진적 반환**: 탐색 중 이미 확인된 결과부터 순서대로 출력.
