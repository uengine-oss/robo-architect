# Skill: robo-proposal-intent

## Purpose
자연어 요구사항을, ingestion 파이프라인 수준의 **깊고 완전히 연결된** 설계로 분해한다:
**Strategic Diff**(BoundedContext(=Epic)/Feature/UserStory/Process) + **Tactical Diff**(Aggregate/Command/Event/ReadModel/Policy) — 각 설계 노드는 **속성(Property)·BDD(GWT)·추적성(UserStory↔Command/ReadModel)**까지 포함한다.
요구사항이 모호할 때는 최대 5개의 선택형 명확화 질문을 순차 제시한다.

## 레퍼런스를 먼저 읽어라 (필수)
출력 전, 아래 파일들을 Read 도구로 읽고 그 규칙을 적용하라. (cwd = 저장소 루트)
- `skills/robo-proposals/robo-proposal-intent/references/output-schema.md` ← **출력 계약(가장 중요)**
- `skills/robo-proposals/robo-proposal-intent/references/traceability.md` ← tempId·참조·관계 연결(필수)
- `skills/robo-proposals/robo-proposal-intent/references/bounded-contexts.md`
- `skills/robo-proposals/robo-proposal-intent/references/aggregates.md`
- `skills/robo-proposals/robo-proposal-intent/references/commands-events.md`
- `skills/robo-proposals/robo-proposal-intent/references/properties.md`
- `skills/robo-proposals/robo-proposal-intent/references/gwt.md`
- `skills/robo-proposals/robo-proposal-intent/references/readmodels-policies.md`
- `skills/robo-proposals/robo-proposal-intent/references/invariants-ui.md`
- `skills/robo-proposals/robo-proposal-intent/references/journeys.md`
- `skills/robo-proposals/robo-proposal-intent/references/node-property-catalog.md`
- `skills/robo-proposals/robo-proposal-intent/references/relationship-catalog.md`

최소한 `output-schema.md`와 `traceability.md`는 **반드시** 읽어라. 나머지는 해당 단계에서 참고.

## Input (Human Prompt)
```
Proposal ID: PRO-NNN
원본 프롬프트: <user's natural language requirement>

현재 도메인 구성 요소 목록:
- id: US-001, type: UserStory, name: 결제 처리
- id: AGG-payment, type: Aggregate, name: 결제 Aggregate
...

사용자 명확화 답변: (있을 경우)  Q0: ... → A: ...
이전 분석 결과 / 사용자 피드백(재생성): (있을 경우)
```

## 분해 절차 (이 순서로 사고하라)
1. **요구사항 파악** → 동작형(Command) vs 조회형(ReadModel) UserStory 구분.
2. **BoundedContext(=Epic) 식별** — 단일 거대 BC 금지, core/supporting/generic 분류. (bounded-contexts.md)
3. **Feature 그룹핑** — 각 UserStory를 Feature에, Feature를 BC에.
4. **Aggregate 추출** — 이벤트-우선, rootEntity·VO·Enum·Exception. (aggregates.md)
5. **Command** — actor/category/inputSchema + **properties** + **userStoryRefs(IMPLEMENTS)** + **gwt**. (commands-events.md, gwt.md)
6. **Event** — 각 Command가 emit, version/payload + properties. (commands-events.md)
7. **ReadModel** — 조회형 UserStory마다, properties + userStoryRefs. (readmodels-policies.md)
8. **Policy** — 이벤트→명령 반응 흐름이 있으면(triggerEventId/invokeCommandId).
9. **Invariant** — 각 Aggregate의 핵심 불변식 + 검증 Command(verifyingCommandRefs). (invariants-ui.md)
10. **UI** — 사용자 접점 Command/ReadModel에 화면(`ui`). (invariants-ui.md)
11. **Journey** — 사용자 흐름이 뚜렷하면 최상위 `journeys`로 화면 단계·NEXT. (journeys.md)
12. **자가 검증** — traceability.md + invariants-ui.md 체크리스트를 모두 통과하는지 확인.

### FK(외래키) 표기
Property가 다른 노드를 참조하면 `isForeignKey:true` + `fkTargetHint:"<TargetType>:<TargetKey>:<TargetProp>"`
(예: `"Aggregate:menu:menuId"`). applier가 이를 실제 `Property ─REFERENCES→ Property`로 해소한다.

기존 노드는 입력 "도메인 구성 요소 목록"의 실제 id를 참조로 쓰고 `op/changeType:"MODIFY"`. 신규만 CREATE + tempId.

## Output Format
`output-schema.md`의 구조를 **정확히** 따른다. 최상위는
```json
{ "action": "done", "strategicDiff": { "version":1, "epics":[...], "features":[...], "userStories":[...], "processes":[...] }, "tacticalDiff": [ ... ] }
```
명확화가 필요하면:
```json
{ "action": "clarify", "questions": [ { "index":0, "text":"...", "options":["...","..."] } ] }
```

### 깊이 기준 (이 정도는 나와야 함)
- 모든 Command: `inputSchema` + `properties`(파라미터) + `userStoryRefs` + `gwt`(2~4 시나리오).
- 모든 Event: `commandId` + `version` + `payload` + `properties`.
- 모든 Aggregate: `rootEntity` + `properties` + (필요 시) VO/Enum/Exception.
- 조회형 UserStory: ReadModel로 표현(+userStoryRefs).
- 이름만 있는 빈 설계 노드 금지.

## 스트리밍 출력 방식 (필수)
JSON을 출력하기 **전에** 분석 과정을 한국어로 서술하라. 각 줄이 실시간 표시된다.
형식 `[태그] 내용`:
- `[요구사항]` `[도메인 검토]` `[BC 분해]` `[Aggregate]` `[Command/Event]` `[추적성]` `[판단]` `[생성]`
예시:
```
[요구사항] 음식 주문/메뉴 관리 — 주문자·점주 액터
[BC 분해] 메뉴 관리(supporting) + 주문(core) 2개 BC로 분리
[Command/Event] RegisterMenu→MenuRegistered, PlaceOrder→OrderPlaced(+속성·GWT)
[추적성] US 4개를 Command/ReadModel에 IMPLEMENTS로 연결
```
서술(4~8줄) 후 빈 줄을 두고 JSON을 출력하라. (레퍼런스 Read는 서술 전에 수행)

## Rules
1. **깊이·연결 우선**: 이 스킬의 목적은 ingestion 수준의 세부(속성·GWT·추적성)를 만드는 것이다. 얕은(이름만) 출력은 실패로 간주.
2. **tempId + 부모 ref 필수**: 모든 CREATE에 tempId와 부모 참조. (traceability.md)
3. **Epic = BoundedContext**: 별도 Epic 노드 없음. `epics`가 BC.
4. **기존 노드 재사용**: 도메인 목록과 일치하면 MODIFY(실제 id 참조).
5. **DDD 용어 유지**: UserStory/BoundedContext/Aggregate/Command/Event/ReadModel/Policy/Property.
6. **UserStory role/action/benefit 필수**, `entityTitle`은 `"<role>: <action>"`.
7. **명확화는 최대 5개**, 명확하면 바로 done.
8. **언어**: 생성 텍스트(이름·설명·AC)는 원본 프롬프트의 언어/사용자 언어 설정을 따른다.
9. **피드백 재생성**: 입력에 "이전 분석 결과"+"사용자 피드백(재생성)"이 있으면 피드백을 최우선 반영해 전체 diff를 다시 생성(지적 안 된 부분은 유지). 추가 clarify 만들지 말고 done으로 보정. narration에 `[피드백 반영]`.
