# Skill: robo-proposal-test

## Purpose
샌드박스 구현을 두 축으로 검증한다:
- **① 인수 조건(GWT) 검증** — UserStory의 Given-When-Then 시나리오를 **LLM-as-judge**로 코드에 대해 판정.
- **② 구조 검증(Tactical Diff ↔ 구현체)** — Proposal의 Tactical Diff(Aggregate/Command/Event/VO 의도된 변경)가 실제 구현체에 반영됐는지 **robo-sync 추출기**로 구조를 추출해 비교. (실제 스펙 ↔ 구현체 일치 검증)

## Input (Human Prompt)
```
Proposal ID: PRO-NNN
샌드박스 경로: /path/to/.sandbox/proposal/PRO-NNN  ← 아래 <SANDBOX>

검증할 인수 조건(GWT):
[ { "storyId": "...", "storyTitle": "...", "scenario": "Given ... When ... Then ..." } ]

Tactical Diff (구조 검증용):
[ { "nodeId":"AGG-refund","nodeLabel":"Aggregate","nodeTitle":"환불 Aggregate",
    "changeType":"MODIFY",
    "semanticDiff":{"v":1,"ops":[{"field":"valueObjects","op":"obj_append",
       "obj_name":"PartialRefundAmount","obj_data":{"name":"PartialRefundAmount","type":"Long"}}]} } ]
```

## Output Format (TestRunResult JSON)
```json
{
  "proposalId": "PRO-NNN",
  "totalScenarios": 4,
  "passed": 3,
  "failed": 1,
  "skipped": 0,
  "items": [
    {
      "scenarioId": "SC-001",
      "category": "acceptance",
      "storyId": "US-new-1",
      "storyTitle": "고객이 부분 환불을 요청할 수 있다",
      "scenario": "Given 주문 완료 상태, When 부분 금액 입력, Then 환불 요청 생성",
      "result": "PASS",
      "reason": null
    },
    {
      "scenarioId": "SC-003",
      "category": "structural",
      "storyId": "AGG-refund",
      "storyTitle": "환불 Aggregate",
      "scenario": "PartialRefundAmount VO(Long)가 구현체에 존재",
      "result": "FAIL",
      "reason": "src/payment/Refund.ts에 PartialRefundAmount VO 없음 (추출 결과 fields에 미포함)"
    }
  ]
}
```

## ① 인수 조건(GWT) 판정 프로토콜
1. 샌드박스 경로가 있으면 해당 코드 파일을 읽어 시나리오 구현 여부 확인.
2. **Given** 전제 상태 / **When** 액션(API·함수) / **Then** 결과가 코드에서 처리·반환되는지 확인.
3. 확인 불가면 `result: "SKIPPED"`. 각 항목 `category: "acceptance"`.

## ② 구조 검증 프로토콜 (Tactical Diff ↔ 구현체)
Tactical Diff의 각 요소가 샌드박스 구현체에 의도대로 반영됐는지 robo-sync 추출기로 비교한다.

각 Tactical Diff 항목마다:
1. `nodeTitle`/`nodeLabel`과 `semanticDiff.ops`를 보고, 해당 요소의 구현 파일을 샌드박스에서 찾는다(Grep/Glob). 예: "환불 Aggregate" → `<SANDBOX>/src/**/Refund*.{ts,py}`.
2. 찾은 파일의 **실제 구조**를 robo-sync 추출기로 추출(절대 경로 사용 — 현재 작업 경로가 샌드박스가 아니므로):
   - TypeScript: `node <SANDBOX>/.claude/skills/robo-sync/extractors/ts_extract.mjs <SANDBOX>/<file>`
   - Python: `python <SANDBOX>/.claude/skills/robo-sync/extractors/python_extract.py <SANDBOX>/<file>`
   추출기는 `{kind, name, fields}` JSON을 stdout으로 출력한다.
3. `semanticDiff.ops`의 의도(예: `obj_append` VO 추가, 필드 추가/수정/삭제, Command/Event 파라미터)가 추출된 실제 구조에 반영됐는지 비교:
   - 의도된 VO/필드/커맨드가 구현체에 존재·일치 → **PASS**.
   - 누락 또는 타입 불일치 → **FAIL** (reason에 무엇이 어떻게 다른지 명시).
   - 파일을 못 찾거나 추출 실패 → **SKIPPED** (reason: 사유).
4. 각 항목을 `items`에 `category: "structural"`, `storyId`=요소 id, `storyTitle`=요소명(nodeTitle), `scenario`=검증한 의도로 추가.

추출기가 없거나(다른 언어 등) Tactical Diff가 비어 있으면 구조 검증은 생략하고 인수 조건만 판정한다.

## Rules
- LLM 판단이므로 100% 정확성 보장 없음. FAIL 시 반드시 `reason`에 근거 제시.
- `totalScenarios = passed + failed + skipped` (acceptance + structural 합산).
- 시나리오 ID는 `SC-NNN` 순번. 각 item은 `category`("acceptance"|"structural")를 가진다.
- 최종 출력은 TestRunResult JSON 한 덩어리.
