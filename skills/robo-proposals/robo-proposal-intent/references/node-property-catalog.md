# Reference: 노드별 속성 카탈로그 (in-scope)

설계 노드가 실제로 어떤 필드를 갖는지(그래프 스키마 기준). 출력 시 `fields`/`properties`에 채운다.

## BoundedContext (= Epic)
name, displayName, description, classification(core|supporting|generic)

## Feature
name, displayName, description (부모: BoundedContext)

## UserStory
role, action, benefit, acceptanceCriteria[], priority, status, displayName

## Aggregate
name, rootEntity, description, valueObjects(JSON), enumerations(JSON), exceptions(JSON)
+ properties → HAS_PROPERTY

## Command
name(PascalCase 명령형), displayName, actor, category(Create|Update|Delete|Process|Business Logic|External Integration), description, inputSchema(JSON)
+ properties(파라미터) → HAS_PROPERTY
+ gwt → HAS_GIVEN/WHEN/THEN

## Event
name(과거형), displayName, version(semver), payload(JSON), description, isBreaking(기본 false)
+ properties(페이로드) → HAS_PROPERTY

## ReadModel
name, displayName, description, actor, isMultipleResult(bool), provisioningType
+ properties(조회 필드) → HAS_PROPERTY

## Policy
name, displayName, description, condition(트리거 조건)

## Property (HAS_PROPERTY 자식)
name(camelCase), type, description, displayName, isKey, isForeignKey, isRequired, fkTargetHint, parentType, parentId

## GWT (Given/When/Then 자식)
name, description, fieldValues(JSON: 속성명→테스트값), scenario, parentType, parentId

## Invariant (HAS_INVARIANT 자식 / Aggregate)
declaration(한 문장 규칙), name, description, aggregateId, seq, source
+ VERIFIED_BY → Command (verifyingCommandRefs)

## UI (BC ─HAS_UI→, ─ATTACHED_TO→ Command/ReadModel)
name, description, template, attachedToId, attachedToType, attachedToName, userStoryId, designSource
