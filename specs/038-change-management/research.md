# Research: Requirement Change Management (038)

## D1 — 기존 change_management 코드와의 공존 전략

**Decision:** `api/features/change_management/` (OLD, `/api/change/*`)는 그대로 두고, 신규 기능은 `api/features/requirement_changes/` (`/api/requirement-changes/*`)에 독립 라우터로 구현한다.

**Rationale:** OLD 코드는 LangChain 기반 `CHANGED_TO` 관계 로직으로 Constitution X 위반이지만 현재 기동 중인 엔드포인트이다. 이를 한 번에 제거하면 다른 기능이 영향받을 수 있으므로 병렬 coexist 후 단계적 deprecation 예정. 신규 prefix `/api/requirement-changes/`를 사용하면 충돌 없음.

**Alternatives considered:** (a) OLD 코드 즉시 삭제 — 다른 frontend 코드가 `/api/change/*` 호출 가능성 있어 배제. (b) 같은 prefix 재사용 — 경로 충돌 위험으로 배제.

---

## D2 — RequirementChange 노드 ID 패턴

**Decision:** `CHG-NNN` 형식(3자리 0-padded 정수, e.g. CHG-001). Neo4j 노드 레이블 `RequirementChange`. ID는 기존 최대값에서 auto-increment.

**Rationale:** 프로젝트 전반에서 사람이 읽기 쉬운 ID 패턴을 사용함(US-001, REQ-001 등). CHG-NNN은 동일 패턴. 생성 시 `MATCH (n:RequirementChange) RETURN max(toInteger(replace(n.id, 'CHG-', ''))) AS max`로 다음 ID 계산.

**Alternatives considered:** UUID — 추적성 낮음. Auto-increment DB sequence — Neo4j에 시퀀스 없으므로 MAX+1 패턴 사용.

---

## D3 — EFFECT 관계 방향 및 대상

**Decision:** `(RequirementChange)-[:EFFECT {reason, impactLevel}]->(UserStory|BoundedContext|Aggregate)`

- 방향: Change → 영향받는 노드 (단방향)
- 대상: UserStory, BoundedContext(Feature), Aggregate — 세 레이블 모두 허용
- impactLevel: `HIGH` | `MEDIUM` | `LOW`
- reason: 자연어 설명 (AI 분석 or 사용자 입력)

**Rationale:** 방향이 Change → 대상이어야 Change 삭제 시 연결 정리가 쉽다(`DETACH DELETE`). 세 레이블을 모두 허용해야 Epic(BC)/Feature/UserStory 모두 포함 가능.

**Alternatives considered:** 양방향 관계 — 중복 관리 필요하므로 배제. 별도 EFFECT 노드 — 과도한 복잡성.

---

## D4 — Change 상태 전이 모델

**Decision:** `DRAFT → SUBMITTED → APPROVED | REJECTED → IMPLEMENTED`

- DRAFT: 생성 직후 기본 상태
- SUBMITTED: 작성자가 승인 요청
- APPROVED: 다른 사용자가 승인 (자기 승인 방지)
- REJECTED: 다른 사용자가 반려 (reject comment 포함)
- IMPLEMENTED: 구현 스킬 실행 완료 후 자동 전환

상태 이력은 Change 노드 속성 `statusHistory` (JSON 직렬화 리스트)에 저장. 별도 StatusHistory 노드 없음(그래프 복잡성 최소화).

**Rationale:** 별도 StatusHistory 노드를 만들면 조회 쿼리가 복잡해짐. JSON 속성에 직렬화하면 단일 노드 조회로 전체 이력 반환 가능. Constitution I 준수: 그래프가 진실의 원천.

**Alternatives considered:** StatusHistory 별도 노드 — 쿼리 복잡, 배제. Event Sourcing 패턴 — 현재 규모에 과도함.

---

## D5 — 자기 승인 방지 구현

**Decision:** `api/platform/identity.py`에서 현재 요청자 user_id를 읽어 `change.author != request.user_id` 조건 검증. 검증 실패 시 HTTP 403.

**Rationale:** 기존 `IdentityMiddleware`가 `request.state.user_id`를 설정함(이미 구현됨). 별도 Role-Based Auth는 v1 범위 밖.

---

## D6 — ChangeSet 구현

**Decision:** ChangeSet은 `ChangeSet` Neo4j 노드 레이블. `(ChangeSet)-[:CONTAINS]->(RequirementChange)`. ChangeSet 자체에도 `status`, `author`, `createdAt` 저장. ChangeSet 승인 시 포함된 모든 Change를 APPROVED로 전환.

**Rationale:** ChangeSet을 별도 노드로 만들어야 전체 묶음 단위 조회·승인이 가능. `CONTAINS` 관계로 그룹화.

---

## D7 — 구현 스킬 호출 (robo-change-tasks)

**Decision:** `skills/robo-changes/robo-change-tasks/SKILL.md`를 `claude -p` PTY 호출로 실행. 인수: `CHG-NNN`. 기존 `api/features/claude_code/`의 PTY 실행 패턴 재사용. SSE로 stdout 프록시 (Constitution III).

**Rationale:** Constitution X — 신규 AI 워크플로우는 Skill-First. 기존 `api/features/requirement_changes/services/skill_runner.py`(pyc만 존재)의 패턴을 소스로 재구현. 이미 spec 015/029에서 검증된 패턴.

**Skill 인수 포맷:** `claude -p --allowedTools mcp__neo4j__query <skill-path>/SKILL.md --change-id CHG-NNN --project-path <project-root>`

---

## D8 — 영향도 분석 (EFFECT 자동 생성) 전략

**Decision:** Change 생성 시 두 가지 방식으로 EFFECT 생성:
1. **AI 분석 모드** (PROMPT sourceType): `robo-change-specify` 스킬 호출 → 분석 결과로 EFFECT 관계 생성
2. **직접 수정 모드** (DIRECT_EDIT sourceType): 수정된 노드 ID를 직접 EFFECT 대상으로 설정 (신뢰도 1.0)

EFFECT 관계는 비동기 분석 완료 후 추가됨. 분석 중 Change 상태는 `DRAFT`로 유지.

**Rationale:** 직접 수정은 어떤 노드가 변경됐는지 이미 알고 있으므로 AI 분석 불필요. 프롬프트 입력은 AI가 영향 범위를 추론해야 함.

---

## D9 — 회귀 테스트 영향도 분석

**Decision:** 그래프 트래버설로 구현:
```cypher
MATCH (chg:RequirementChange {id: $id})-[:EFFECT]->(n)
OPTIONAL MATCH (n)-[:IMPLEMENTS|HAS_AGGREGATE|HAS_COMMAND*1..3]->(design)
OPTIONAL MATCH (test:Test)-[:TESTS_FOR]->(design)
RETURN n, design, test
```

`Test` 노드가 없으면 "영향받는 설계 요소" 목록만 반환. 마이크로서비스 간 계약 테스트: `BoundedContext`가 EFFECT 대상이면 Contract Test 플래그 추가. UI 포함 여부: `UserStory.ui = true` 속성 존재 시 E2E 플래그 추가.

**Alternatives considered:** AI 기반 테스트 목록 생성 — 그래프 트래버설이 더 신뢰할 수 있고 결정론적.

---

## D10 — 기존 037 RequirementChange 데이터 초기화

**Decision:** 앱 시작 시 또는 마이그레이션 스크립트로 기존 `RequirementChange` 노드 전체 삭제. `MATCH (n:RequirementChange) DETACH DELETE n` — 선택적 초기화 아닌 전체 교체.

**Rationale:** 037 스키마는 새 스펙과 호환되지 않음. Assumption에 명시됨.

---

## D11 — Frontend Changes 탭 진입점

**Decision:** `RequirementsPanel.vue`에 기존 탭(Tree, Chat 등) 옆에 "Changes" 탭 추가. `ChangesPanel.vue`를 탭 컨텐츠로. 다른 탭(UserStoryDetail, EpicDetail 등)에서 Change 생성 시 `requirements.store.js`의 `createChange()` 액션 호출 → 스토어에서 POST API 호출.

**Alternatives considered:** 별도 최상위 메뉴 — 요구사항 컨텍스트 내에 있어야 자연스러움. 기존 탭 구조에 통합이 적절.

---

## D12 — 선행 Change 반영 강제 여부

**Decision:** 구현 시작 시 미반영(APPROVED but not IMPLEMENTED) 선행 Change 목록을 사용자에게 제시하고 선택지 제공:
- "선행 Change도 함께 반영" → 선행 Change를 CHG 번호 오름차순으로 먼저 implement
- "현재 Change만 반영" → 경고 후 진행

선행 Change 판단 기준: `createdAt < current.createdAt AND status IN ['APPROVED']`.

**Rationale:** 순서 의존성 있는 Change가 있을 수 있으므로 강제 순서는 없되 선택권 제공.
