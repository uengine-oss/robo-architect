---
name: robo-proposal-tactical
description: BCC 에서 Aggregate 경계·불변식·상태전이·명령/이벤트·처리량을 도출하는 Tactical 스테이지(ddd-starter Step 8 + robo-proposal-plan 전술 규칙).
extends: robo-proposal-plan
---

# Skill: robo-proposal-tactical (Tactical — Aggregate Design Canvas)

## Purpose
ddd-starter Step 8(Code)의 Aggregate Design 을 적용한다. Define(BCC)을 입력으로 각 **Aggregate** 의 경계·불변식·상태전이·명령/이벤트·처리량을 도출한다. `robo-proposal-plan` 의 전술 분해 규칙(레퍼런스)을 상속하되, 여기서는 **스테이지 산출물(TacticalArtifact)** 형태로 낸다 — 아키텍처 결정은 이후 plan 단계가 수행한다.

## 먼저 읽어라
- `~/.claude/skills/ddd-starter/references/08-code.md`
- `skills/robo-proposals/robo-proposal-intent/references/aggregates.md`, `commands-events.md`, `invariants-ui.md`
- `skills/robo-proposals/robo-proposal-intent/references/properties.md`, `gwt.md`, `output-schema.md`
- `skills/robo-proposals/robo-proposal-intent/references/legacy-reference.md`

**`legacy-reference.md` 는 Read 도구로 반드시 직접 읽어라.** Human Prompt에
`INSPECTED LEGACY EVIDENCE` packet이 있으면 그 내용은 이전 단계가 이미 실제 MCP로 검토한
권위 근거다. packet의 같은 nodeId를 다시 검색/상세조회하지 않고, 필요한 함수가 없거나
근거 상태가 부족할 때만 MCP로 필요한 semantic evidence kind를 조회한다. 구조화 semantic slots와
flow/RULE을 먼저 읽고 complete source를 정상 생성 입력으로 재조회하지 않는다. 부족한 의미는
`missing_context`로 보존하며 Architect가 원문이나 이름으로 만들지 않는다.
packet이 없거나 MCP 도구가 없어도 이 단계는 Define 입력만으로 정상 진행한다. 레거시 조회와
`evidenceRefs`는 선택적 보강이며 Tactical 완료 조건이 아니다.

## Aggregate 경계 결정 (이 단계의 핵심)
- **함께 변해야 하는가? / 한 트랜잭션에서 일관성이 필요한가?** → Yes 면 한 Aggregate.
- 작게 유지(큰 Aggregate = 동시성 충돌·로딩 비용). **Value Object 는 Aggregate 로 모델링하지 않는다.**

## 채울 항목
State Transitions · Enforced Invariants(**2개 이상**) · Corrective Policies · Handled Commands · Created Events · Throughput.

## 출력 (최종 JSON)
narration(`[Aggregate]`/`[경계]`/`[불변식]`) 후 빈 줄, 그 다음:
```json
{
  "TacticalArtifact": {
    "aggregates": [{
      "name": "Order", "description": "한 회원의 한 번 결제 상품 묶음", "boundaryRationale": "Order+OrderLine 은 한 트랜잭션 일관성 필요",
      "legacyRefs": [{"nodeId": "code:<project>/<file>:<function>", "role": "derived-from",
                      "evidence": "주문 확정 트랜잭션 경계가 이 Aggregate 로 이동"}],
      "stateTransitions": [],
      "invariants": ["<입력 근거의 불변식 1>", "<입력 근거의 불변식 2>"],
      "correctivePolicies": [],
      "handledCommands": [
        {"name": "PlaceOrder", "fields": {"inputSchema": {}},
         "properties": [],
         "userStoryRefs": ["<Define의 실제 userStory.id>"],
         "gwt": [{"scenario": "정상 주문", "evidenceRefs": ["<exact RULE evidence_id>"],
                  "given": {"name": "Aggregate: Order", "fieldValues": {}},
                  "when": {"name": "Command: PlaceOrder", "fieldValues": {}},
                  "then": {"name": "Event: OrderPlaced", "fieldValues": {}}}],
         "legacyRefs": [{"nodeId": "code:<project>/<file>:<function>"}]},
        {"name": "ConfirmOrder", "fields": {"inputSchema": {}}, "properties": [],
         "userStoryRefs": ["<Define의 실제 userStory.id>"], "gwt": [], "legacyRefs": []}
      ],
      "createdEvents": [
        {"name": "OrderPlaced", "fields": {"payload": {}}, "properties": [], "legacyRefs": []},
        {"name": "OrderConfirmed", "fields": {"payload": {}}, "properties": [], "legacyRefs": []}
      ],
      "throughput": {"commandHandlingRate": {"avg": "50/s", "max": "100/s"}, "totalClients": {"avg": "1k", "max": "5k"}, "concurrencyConflictChance": {"avg": "low", "max": "med"}},
      "size": {"eventGrowthRate": {"avg": "5/order", "max": "20/order"}, "lifetime": {"avg": "7d", "max": "90d"}, "eventsPersisted": {"avg": "12", "max": "60"}}
    }]
  }
}
```

## Rules
0. **모든 aggregate/handledCommand/createdEvent 는 `legacyRefs` 배열을 가진다** — 이 실행에서
   실제 검색·검토한 nodeId 만, 대응 없으면 `[]`. Command/Event 는 `{name, legacyRefs}` 객체로
   낸다. 규칙 유래면 `rule:"<본 문장 그대로>"` 인용(형상: intent `output-schema.md`).
0-b. **Command/Event 를 다 만든 뒤 S3 배분을 반드시 수행하라**(`legacy-reference.md` S3).
   검색 후보를 하나씩 보며 "이 후보가 뒷받침하는 Command/Event 가 있나"를 묻는다 —
   요소에서 출발하면 잊고 넘어간다. **이름이 아니라 요약으로 판단**하라: `settlement_close`
   의 요약이 "정산 건을 마감 처리한다"면 그것이 `CloseSettlement`·`SettlementClosed` 의
   근거다(실측 누락 사례). Aggregate 에만 붙이고 하위 요소를 비워두지 않는다.
   배분 후에도 빈 요소만 S4 로 1회 재검색한다.
1. 각 Aggregate 의 invariant 은 **2개 이상**.
2. Value Object(Money, Address)는 Aggregate 가 아니다.
3. Commands/Events 는 Define 의 Inbound/Outbound 와 일치.
3-b. 모든 Command는 `{name, fields.inputSchema, properties, userStoryRefs, gwt, legacyRefs}`
   객체이며 `userStoryRefs`는 Define의 허용 ID를 1개 이상 사용하고, GWT는 정상 1개 이상과
   요구사항 또는 packet에 직접 근거가 있을 때만 추가한 경계/실패로 구성한다. 개수를 맞추려고
   정책이나 중복 시나리오를 만들지 않는다. `gwt.md`의 RULE 좌표·테이블
   샘플 계약을 따른다. 모든 Event는 `{name, fields.payload, properties, legacyRefs}` 객체다.
3-c. 출력 예시는 JSON 형상만 설명한다. 예시의 상태·숫자·ID는 근거가 아니며 절대 재사용하지 않는다.
   `fieldValues`는 packet의 RULE/SYMBOL/sample claim으로 입증되는 값만 넣고, 없으면 `{}`로 둔다.
   실제 필드 하나의 여러 값은 별도 시나리오로 나누고 suffix 합성 필드를 만들지 않는다.
   함수 반환 sentinel을 `cnt`/`status` 같은 다른 데이터 필드 값으로 쓰지 않는다.
   범위/미정의 분기의 대표 테스트값은 만들지 않으며, 실측값이 없으면 조건만 name에 남긴다.
   Then은 분기 중간 대입이 아니라 이후 공통 후처리·clamp·transaction까지 반영한 최종 결과다.
   packet을 실제 사용한 경우에만 각 scenario는 RULE evidence_id를 최소 1개 포함하고 사용한
   SYMBOL/CALL/TABLE evidence_id를 함께 남긴다. packet이 없으면 `evidenceRefs: []`, `legacyRefs: []`로
   둔다. 근거를 사용한 각 Command legacyRefs에 근거 함수·정확한 RULE evidenceId·ruleId·text 1개 이상·직접
   TABLE id 전부를 남긴다.
4. 코드를 작성하지 말 것 — 전술 설계 산출물만.
5. 언어는 사용자/프롬프트 언어를 따른다.
