# Reference: 추적성 & 참조 연결 (가장 중요)

요구사항(UserStory)과 설계(Command/ReadModel/Aggregate/Event)가 **반드시 연결**되어야 한다.
연결이 없으면 설계 변경의 영향이 요구사항으로, 요구사항이 구현으로 추적되지 않는다.

## tempId 규칙
- 모든 CREATE 항목에 배치 내 고유 `tempId`(strategic) / `nodeId`(tactical) 부여.
  권장 접두사: `EP-`(=BC), `FT-`, `US-`, `AGG-`, `CMD-`, `EVT-`, `RM-`(ReadModel), `POL-`(Policy).
- 자식은 부모의 tempId를 참조한다. 기존 노드면 입력 목록의 **실제 id**를 쓴다.

## 연결 맵 (어떤 ref가 어떤 관계가 되는가)
| 항목 | ref 필드 | → 관계 |
|---|---|---|
| feature | epicId | BoundedContext ─HAS_FEATURE→ Feature |
| userStory | featureId | Feature ─HAS_USER_STORY→ UserStory |
| userStory | boundedContextId | UserStory ─IMPLEMENTS→ BoundedContext |
| aggregate | boundedContextId | BoundedContext ─HAS_AGGREGATE→ Aggregate |
| command | aggregateId | Aggregate ─HAS_COMMAND→ Command |
| **command** | **userStoryRefs** | **UserStory ─IMPLEMENTS→ Command** |
| event | commandId | Command ─EMITS→ Event |
| readModel | boundedContextId | BoundedContext ─HAS_READMODEL→ ReadModel |
| readModel | userStoryRefs | UserStory ─IMPLEMENTS→ ReadModel |
| policy | boundedContextId | BoundedContext ─HAS_POLICY→ Policy |
| policy | triggerEventId | Event ─TRIGGERS→ Policy |
| policy | invokeCommandId | Policy ─INVOKES→ Command |

## 필수 체크 (출력 전 자가 검증)
- [ ] 모든 UserStory가 Feature(featureId)와 BC(boundedContextId)에 연결됐다.
- [ ] 모든 동작형 UserStory가 하나 이상의 Command 또는 ReadModel의 `userStoryRefs`에 등장한다(IMPLEMENTS).
- [ ] 모든 Aggregate가 BC에, 모든 Command가 Aggregate에, 모든 Event가 Command에 연결됐다.
- [ ] 모든 설계 노드가 properties를 갖는다(빈 노드 없음).
- [ ] 모든 Command가 gwt를 갖는다.
