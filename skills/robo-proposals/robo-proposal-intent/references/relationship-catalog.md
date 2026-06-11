# Reference: 관계 카탈로그 (in-scope)

applier가 ref 필드로부터 자동 생성하는 관계. 방향과 출처 ref를 정확히 알고 ref를 채운다.

## 요구사항 계층
- `BoundedContext ─HAS_FEATURE→ Feature`  ← feature.epicId
- `Feature ─HAS_USER_STORY→ UserStory`    ← userStory.featureId
- `UserStory ─IMPLEMENTS→ BoundedContext` ← userStory.boundedContextId

## 설계 계층
- `BoundedContext ─HAS_AGGREGATE→ Aggregate` ← aggregate.boundedContextId
- `Aggregate ─HAS_COMMAND→ Command`          ← command.aggregateId
- `Command ─EMITS→ Event`                    ← event.commandId
- `BoundedContext ─HAS_READMODEL→ ReadModel` ← readModel.boundedContextId
- `BoundedContext ─HAS_POLICY→ Policy`       ← policy.boundedContextId

## 추적성 (요구↔설계 — 핵심)
- `UserStory ─IMPLEMENTS→ Command`   ← command.userStoryRefs[]
- `UserStory ─IMPLEMENTS→ ReadModel` ← readModel.userStoryRefs[]

## 속성 / BDD
- `(Aggregate|Command|Event|ReadModel) ─HAS_PROPERTY→ Property` ← node.properties[]
- `Command ─HAS_GIVEN|HAS_WHEN|HAS_THEN→ (Given|When|Then)`     ← command.gwt[]

## 반응 정책 (BC간 협력)
- `Event ─TRIGGERS→ Policy`   ← policy.triggerEventId
- `Policy ─INVOKES→ Command`  ← policy.invokeCommandId

## 불변식 / 화면
- `Aggregate ─HAS_INVARIANT→ Invariant` ← aggregate.invariants[]
- `Invariant ─VERIFIED_BY→ Command`     ← invariant.verifyingCommandRefs[]
- `BoundedContext ─HAS_UI→ UI`          ← command/readModel.ui (BC는 자동 해소)
- `UI ─ATTACHED_TO→ (Command|ReadModel)` ← command/readModel.ui

## 화면 흐름 / FK
- `BoundedContext ─HAS_JOURNEY→ Journey` ← journey.boundedContextId
- `Journey ─HAS_STEP→ JourneyStep`       ← journey.steps[]
- `JourneyStep ─NEXT→ JourneyStep`       ← step.next[]
- `JourneyStep ─SHOWS→ UI`               ← step.commandRef/readModelRef (그 요소의 UI)
- `Property ─REFERENCES→ Property`        ← property.fkTargetHint (FK 해소)

> 이제 ingestion 노드 타입 패리티 도달. (Figma 바인딩 등 외부 연동만 별도.)
