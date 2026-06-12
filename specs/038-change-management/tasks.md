# Tasks: Requirement Change Management (038)

**Input**: Design documents from `specs/038-change-management/`

**Prerequisites**: plan.md ✅ · spec.md ✅ · research.md ✅ · data-model.md ✅ · contracts/ ✅ · quickstart.md ✅

**Organization**: 7 User Stories (US1–US7) → 10 Phases. US1·US2 = P1 MVP. Tests not requested; skipped.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 신규 노드·관계 스키마 등록 및 모듈 골격 생성

- [x] T001 `docs/cypher/schema/03_node_types.cypher`에 `RequirementChange` 노드 정의 추가 (id·title·originalPrompt·author·createdAt·status·statusHistory·sourceType·changeSetId 속성, UNIQUE constraint)
- [x] T002 `docs/cypher/schema/03_node_types.cypher`에 `ChangeSet` 노드 정의 추가 (id·title·author·createdAt·status 속성, UNIQUE constraint)
- [x] T003 `docs/cypher/schema/04_relationships.cypher`에 `EFFECT` 관계 정의 추가 (RequirementChange→UserStory/BoundedContext/Aggregate, reason·impactLevel 속성)
- [x] T004 `docs/cypher/schema/04_relationships.cypher`에 `CONTAINS` 관계 정의 추가 (ChangeSet→RequirementChange)
- [x] T005 [P] `api/features/requirement_changes/__init__.py` 파일 생성 (빈 모듈)
- [x] T006 [P] `api/features/requirement_changes/routes/__init__.py` 파일 생성
- [x] T007 [P] `api/features/requirement_changes/services/__init__.py` 파일 생성
- [x] T008 [P] `skills/robo-changes/robo-change-specify/SKILL.md` 파일 생성 (frontmatter: extends·args·overrides 구조 선언, 본문은 Phase 5에서 작성)
- [x] T009 [P] `skills/robo-changes/robo-change-tasks/SKILL.md` 파일 생성 (frontmatter 선언, 본문은 Phase 8에서 작성)

**Checkpoint**: 스키마 파일 및 모듈 디렉터리 구조 완성

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 모든 US가 의존하는 Pydantic 계약·ID 생성·라우터·데이터 초기화

**⚠️ CRITICAL**: Phase 2 완료 전 어떤 US 구현도 시작 불가

- [x] T010 `api/features/requirement_changes/requirement_changes_contracts.py` 생성 — `ChangeStatus`·`ChangeSourceType`·`ImpactLevel`·`TaskStatus` Enum 및 모든 Request/Response Pydantic 모델 구현 (data-model.md 전체 내용 기준)
- [x] T011 `api/features/requirement_changes/services/change_id_generator.py` 생성 — Neo4j MAX+1 패턴으로 `CHG-NNN` 및 `CS-NNN` ID 자동 생성 함수 구현
- [x] T012 `api/features/requirement_changes/router.py` 생성 — prefix `/api/requirement-changes`, 하위 라우터 include 구조 정의 (라우터 파일들은 각 Phase에서 생성 후 여기 추가)
- [x] T013 `api/main.py` 수정 — `from api.features.requirement_changes.router import router as req_changes_router` 추가 및 `app.include_router(req_changes_router)` 등록
- [x] T014 기존 `RequirementChange` 노드 초기화 — `api/features/requirement_changes/services/` 아래 `migration.py` 작성: `MATCH (n:RequirementChange) DETACH DELETE n` + `MATCH (n:ChangeSet) DETACH DELETE n` Cypher 실행 함수 구현 후 앱 시작 lifespan에 조건부 등록 (env flag `RESET_CHANGE_DATA=true` 시에만 실행)

**Checkpoint**: `GET /api/requirement-changes/` 라우터가 등록되어 있고 서버가 기동되면 Phase 3 시작 가능

---

## Phase 3: User Story 1 — Change 목록 관리 및 조회 (Priority: P1) 🎯 MVP

**Goal**: Changes 탭에서 CHG-NNN 목록을 시간 역순 조회하고 단건 삭제 가능

**Independent Test**: `GET /api/requirement-changes/` 응답에 createdAt 역순 리스트가 오고, `DELETE /id` 후 목록에서 사라지면 완료

### Implementation

- [x] T015 `api/features/requirement_changes/routes/changes_crud.py` 생성 — `GET /` (목록, 역순, status 필터), `GET /{id}` (단건, effects 포함) 엔드포인트 구현. Neo4j Cypher: `MATCH (n:RequirementChange) OPTIONAL MATCH (n)-[e:EFFECT]->(t) RETURN n, collect({nodeId:id(t), ...}) ORDER BY n.createdAt DESC`
- [x] T016 `api/features/requirement_changes/routes/changes_crud.py` 수정 — `DELETE /{id}` 엔드포인트 추가. IMPLEMENTED 상태이면 HTTP 409. 아니면 `MATCH (n {id:$id}) DETACH DELETE n`
- [x] T017 `api/features/requirement_changes/router.py` 수정 — `changes_crud` 라우터 include
- [x] T018 [P] `frontend/src/features/requirements/ui/ChangesPanel.vue` 신규 생성 — Change 목록 v-data-table, 상태 배지(DRAFT=grey·SUBMITTED=blue·APPROVED=green·REJECTED=red·IMPLEMENTED=purple), 단건 클릭 시 ChangeDetail emit, 삭제 버튼
- [x] T019 [P] `frontend/src/features/requirements/ui/ChangeDetail.vue` 신규 생성 — CHG-NNN·제목·원본 프롬프트·작성자·생성일·상태·상태 이력 표시 (승인 버튼 등 액션은 US5에서 추가)
- [x] T02X `frontend/src/features/requirements/requirements.store.js` 수정 — `fetchChanges(filters)`, `fetchChangeById(id)`, `deleteChange(id)` 액션 추가 (`GET /api/requirement-changes/`, `DELETE /api/requirement-changes/{id}` 호출)
- [x] T02X `frontend/src/features/requirements/ui/RequirementsPanel.vue` 수정 — "Changes" 탭 추가: `<v-tab value="changes">Changes</v-tab>` + `<v-window-item value="changes"><ChangesPanel /></v-window-item>`

**Checkpoint**: Changes 탭에서 목록 조회·삭제가 작동하고 단건 상세 패널이 표시됨

---

## Phase 4: User Story 2 — Change 생성 3가지 진입점 (Priority: P1) 🎯 MVP

**Goal**: Changes 탭 직접 입력·자연어 프롬프트·탭 내 직접 수정 3가지 방법으로 Change 생성

**Independent Test**: 3가지 방법 각각으로 Change를 생성하고 CHG-NNN 레코드가 Changes 탭에 나타나면 완료

### Implementation

- [x] T022 `api/features/requirement_changes/routes/changes_crud.py` 수정 — `POST /` 엔드포인트 추가. `change_id_generator` 호출 → `RequirementChange` 노드 생성 (status=DRAFT, statusHistory=[]). `sourceType=DIRECT_EDIT`이면 `directAffectedNodeIds`로 EFFECT 즉시 생성 (impactLevel=HIGH, reason="직접 수정"). `sourceType=PROMPT`이면 EFFECT는 Phase 5(비동기)에서 처리 — 우선 빈 effects로 노드만 생성
- [x] T023 `api/features/requirement_changes/services/effect_analyzer.py` 생성 — `create_direct_effects(change_id, node_ids)` 함수: 주어진 node_ids 각각에 대해 `MATCH (n {id:$node_id}) CREATE (chg)-[:EFFECT {reason:"직접 수정", impactLevel:"HIGH"}]->(n)` Cypher 실행
- [x] T024 `frontend/src/features/requirements/requirements.store.js` 수정 — `createChange(payload)` 액션 추가 (`POST /api/requirement-changes/` 호출, 성공 시 fetchChanges 재호출)
- [x] T025 `frontend/src/features/requirements/ui/ChangesPanel.vue` 수정 — "추가 Change" 버튼 추가: 클릭 시 제목·프롬프트 입력 다이얼로그 열기, 저장 시 `store.createChange({sourceType: 'MANUAL', ...})` 호출
- [x] T026 `frontend/src/features/requirements/ui/UserStoryDetail.vue` 수정 — `onSave()` 핸들러에 `store.createChange({title: '${storyTitle} 직접 수정', sourceType: 'DIRECT_EDIT', directAffectedNodeIds: [storyId]})` 추가 (기존 저장 로직 뒤에 호출, 실패해도 저장은 완료 처리)
- [x] T027 `frontend/src/features/requirements/ui/EpicDetail.vue` 수정 — 동일 패턴으로 Epic(BoundedContext) 수정 시 DIRECT_EDIT Change 생성

**Checkpoint**: MANUAL·DIRECT_EDIT 방식 Change가 생성되어 Changes 탭에 표시됨. (PROMPT 방식 EFFECT는 Phase 5에서 완성)

---

## Phase 5: User Story 3 — EFFECT 영향도 분석 (Priority: P2)

**Goal**: PROMPT 타입 Change 생성 시 AI가 영향받는 UserStory·BC·Aggregate를 분석해 EFFECT 관계 자동 연결

**Independent Test**: PROMPT Change 생성 후 `/impact` 조회 시 EFFECT 목록이 반환되고 각 항목에 reason·impactLevel이 포함되면 완료

### Implementation

- [x] T028 `api/features/requirement_changes/services/skill_runner.py` 생성 — PTY 실행 + SSE 프록시 함수 구현. 기존 `api/features/claude_code/` PTY 패턴 참고. `run_skill_sse(skill_name, args_dict, sse_queue)` 시그니처
- [x] T029 `skills/robo-changes/robo-change-specify/SKILL.md` 본문 작성 — `extends: speckit-specify`. Override: "load-spec" 단계를 Change 컨텍스트 로드로 교체 (Neo4j에서 `--change-id`의 originalPrompt·현재 UserStory/BC/Aggregate 목록 조회). 출력: JSON `{changeId, effects: [{nodeId, nodeLabel, reason, impactLevel}]}`
- [x] T030 `api/features/requirement_changes/services/change_specify_parser.py` 생성 — `robo-change-specify` stdout JSON 파싱 → EFFECT 관계 Neo4j 생성 (`effect_analyzer.py`의 `create_effects_from_analysis(change_id, effects)` 호출)
- [x] T031 `api/features/requirement_changes/services/effect_analyzer.py` 수정 — `create_effects_from_analysis(change_id, effects: list[EffectItem])` 함수 추가: MERGE 방식으로 EFFECT 관계 생성 (중복 방지)
- [x] T032 `api/features/requirement_changes/routes/changes_impact.py` 생성 — `GET /{id}/impact` (EFFECT 관계 조회·반환) 및 `POST /{id}/analyze-impact` (SSE: robo-change-specify 스킬 호출 → stdout 파싱 → EFFECT 생성) 엔드포인트 구현
- [x] T033 `api/features/requirement_changes/router.py` 수정 — `changes_impact` 라우터 include
- [x] T034 `api/features/requirement_changes/routes/changes_crud.py` 수정 — `POST /` 엔드포인트에서 `sourceType=PROMPT`이면 `asyncio.create_task()`로 `analyze-impact` 비동기 트리거 (fire-and-forget)
- [x] T035 [P] `frontend/src/features/requirements/ui/ChangeImpactView.vue` 신규 생성 — EFFECT 목록 카드 표시: nodeLabel 아이콘(UserStory/BC/Aggregate 구분), impactLevel 뱃지, reason 텍스트, 클릭 시 해당 노드로 이동
- [x] T036 `frontend/src/features/requirements/ui/ChangeDetail.vue` 수정 — `<ChangeImpactView :changeId="change.id" />` 탭 추가, `store.fetchImpact(id)` 호출
- [x] T037 `frontend/src/features/requirements/requirements.store.js` 수정 — `fetchImpact(id)` 액션 추가 (`GET /api/requirement-changes/{id}/impact`)

**Checkpoint**: PROMPT Change의 EFFECT 관계가 AI 분석으로 자동 생성되고 ChangeImpactView에 표시됨

---

## Phase 6: User Story 4 — Change Set 관리 (Priority: P2)

**Goal**: 여러 Change를 하나의 ChangeSet으로 묶어 일괄 조회·승인·반영 가능

**Independent Test**: 두 개 Change를 ChangeSet으로 묶고 `GET /changesets/{id}`에서 changes 배열에 두 항목이 포함되면 완료

### Implementation

- [x] T038 `api/features/requirement_changes/routes/changes_changeset.py` 생성 — `POST /changesets/` (ChangeSet 생성·CONTAINS 관계 생성), `GET /changesets/{id}` (포함 Change 목록 포함), `POST /changesets/{id}/add` (Change 추가), `DELETE /changesets/{id}/changes/{change_id}` (Change 제거·독립 복귀) 엔드포인트 구현
- [x] T039 `api/features/requirement_changes/router.py` 수정 — `changes_changeset` 라우터 include
- [x] T040 `frontend/src/features/requirements/ui/ChangesPanel.vue` 수정 — Change 복수 선택 체크박스 + "ChangeSet 생성" 버튼 추가. 클릭 시 제목 입력 후 `store.createChangeSet(title, selectedIds)` 호출
- [x] T041 `frontend/src/features/requirements/requirements.store.js` 수정 — `createChangeSet(title, changeIds)`, `fetchChangeSet(id)` 액션 추가

**Checkpoint**: ChangeSet 생성·조회·Change 추가/제거가 작동함

---

## Phase 7: User Story 5 — 승인 워크플로우 (Priority: P2)

**Goal**: DRAFT→SUBMITTED→APPROVED/REJECTED 상태 전이 + 자기 승인 방지 + 상태 이력 누적

**Independent Test**: 사용자 A가 Submit → 사용자 B가 Approve → status=APPROVED + statusHistory에 두 항목 기록 확인. 사용자 A가 Approve 시도 → HTTP 403

### Implementation

- [x] T042 `api/features/requirement_changes/routes/changes_approval.py` 생성 — `POST /{id}/submit` (DRAFT→SUBMITTED, 작성자 본인만 가능), `POST /{id}/approve` (SUBMITTED→APPROVED, 자기 승인 방지), `POST /{id}/reject` (SUBMITTED→REJECTED, 자기 승인 방지) 엔드포인트 구현. 각 전이마다 `statusHistory` JSON 배열에 `{fromStatus, toStatus, at, actor, comment}` append (Neo4j property update)
- [x] T043 `api/features/requirement_changes/routes/changes_changeset.py` 수정 — `POST /changesets/{id}/submit`, `POST /changesets/{id}/approve`, `POST /changesets/{id}/reject` 엔드포인트 추가: 포함된 모든 Change에 일괄 전이 적용
- [x] T044 `api/features/requirement_changes/router.py` 수정 — `changes_approval` 라우터 include
- [x] T045 `frontend/src/features/requirements/ui/ChangeDetail.vue` 수정 — 상태별 액션 버튼 추가: DRAFT→"제출" (작성자), SUBMITTED→"승인"·"반려" (타인, `:disabled="change.author === currentUser"`), IMPLEMENTED→버튼 없음. 클릭 시 각 store 액션 호출
- [x] T046 `frontend/src/features/requirements/requirements.store.js` 수정 — `submitChange(id)`, `approveChange(id, comment)`, `rejectChange(id, comment)` 액션 추가

**Checkpoint**: 승인 워크플로우 완전 동작. 자기 승인 시 UI 비활성화 + API 403 확인

---

## Phase 8: User Story 6 — 구현 워크플로우 (Priority: P3)

**Goal**: APPROVED Change에서 "구현 시작" → robo-change-tasks 스킬 PTY 호출 → 태스크 목록 SSE 스트리밍 → IMPLEMENTED 전환

**Independent Test**: APPROVED Change에서 "구현 시작" 클릭 후 ChangeTasksView에 태스크 라인이 스트리밍되고 완료 시 status=IMPLEMENTED로 바뀌면 완료

### Implementation

- [x] T047 `skills/robo-changes/robo-change-tasks/SKILL.md` 본문 작성 — `extends: speckit-tasks`. Override: "load-spec" 단계를 `--change-id CHG-NNN` 기반 Neo4j 조회로 교체 (EFFECT 대상 노드, robo-change-plan 결과 조회). stdout 형식: `PHASE:planning`, `TASK:{id}:{title}:PENDING`, `TASK_DONE:{id}`, `PHASE:done`
- [x] T048 `api/features/requirement_changes/services/change_tasks_parser.py` 생성 — `robo-change-tasks` stdout 라인별 파싱: `PHASE:*` → SSE phase event, `TASK:*` → SSE task event, `TASK_DONE:*` → SSE task_done event, `PHASE:done` → Change status → IMPLEMENTED 업데이트
- [x] T049 `api/features/requirement_changes/routes/changes_tasks.py` 생성 — `GET /{id}/preflight` (미반영 선행 APPROVED Change 목록 반환: `createdAt < current.createdAt AND status='APPROVED'`) 엔드포인트 구현
- [x] T050 `api/features/requirement_changes/routes/changes_tasks.py` 수정 — `POST /{id}/implement` SSE 엔드포인트 추가: APPROVED 상태 검증 → `includePriorChangeIds` 있으면 순서대로 먼저 implement → `skill_runner.run_skill_sse('robo-change-tasks', {change_id: id})` → `change_tasks_parser` 라인별 파싱 → SSE event yield → 완료 시 status IMPLEMENTED 업데이트
- [x] T051 `api/features/requirement_changes/router.py` 수정 — `changes_tasks` 라우터 include
- [x] T052 [P] `frontend/src/features/requirements/ui/ChangeTasksView.vue` 신규 생성 — `EventSource` 연결 → `data.phase`, `data.tasks` 수신 → 태스크 목록 실시간 표시 (PENDING=grey·IN_PROGRESS=blue·DONE=green 아이콘), 완료 시 "구현 완료" 배너
- [x] T053 [P] `frontend/src/features/requirements/ui/ChangeDesignPlan.vue` 신규 생성 — robo-change-plan 결과(설계 변경 계획) 표시. changeId를 prop으로 받아 `GET /impact`에서 affectedAggregates 목록 표시 (Phase 5 EFFECT 데이터 재사용)
- [x] T054 `frontend/src/features/requirements/ui/ChangeDetail.vue` 수정 — APPROVED 상태 시 "구현 시작" 버튼 추가. 클릭 시: (1) preflight 조회 → (2) 선행 Change 있으면 확인 다이얼로그 → (3) ChangeTasksView 하단 영역에 표시하며 SSE 시작
- [x] T055 `frontend/src/features/requirements/requirements.store.js` 수정 — `implementChange(id, includePriorChangeIds)` 액션 추가 (EventSource 연결·진행 상태 스토어 반영), `fetchPreflight(id)` 액션 추가

**Checkpoint**: 구현 시작→SSE 태스크 스트리밍→IMPLEMENTED 전환 전체 흐름 동작 확인

---

## Phase 9: User Story 7 — 회귀 테스트 영향도 산출 (Priority: P3)

**Goal**: Change 적용 후 영향받는 테스트(단위·계약·E2E)를 그래프 트래버설로 자동 목록화

**Independent Test**: 구현 완료 Change의 `/regression` 조회 시 `impactedDesignNodes`, `hasContractTests`, `hasE2ETests` 필드가 포함된 응답 반환 확인

### Implementation

- [x] T056 `api/features/requirement_changes/services/regression_analyzer.py` 생성 — `analyze_regression(change_id) → RegressionAnalysis` 함수 구현:
  1. `MATCH (chg {id:$id})-[:EFFECT]->(n)` 로 EFFECT 대상 조회
  2. `OPTIONAL MATCH (n)-[:IMPLEMENTS|HAS_AGGREGATE|HAS_COMMAND*1..3]->(design)` 설계 노드 트래버설
  3. `OPTIONAL MATCH (test:Test)-[:TESTS_FOR]->(design)` 테스트 노드 조회
  4. EFFECT 대상 중 `BoundedContext` 있으면 `hasContractTests=True`
  5. EFFECT 대상 중 `UserStory {ui: true}` 있으면 `hasE2ETests=True`
  6. `Test` 노드 없으면 regressionTests 빈 배열 (impactedDesignNodes는 항상 반환)
- [x] T057 `api/features/requirement_changes/routes/changes_impact.py` 수정 — `GET /{id}/regression` 엔드포인트 추가: `regression_analyzer.analyze_regression(id)` 호출 → `RegressionAnalysis` 반환
- [x] T058 `frontend/src/features/requirements/ui/ChangeDetail.vue` 수정 — "회귀 테스트" 탭 추가: `store.fetchRegression(id)` 호출 → `hasContractTests`·`hasE2ETests` 뱃지 + `regressionTests` 목록 표시 (testType 아이콘: unit/contract/e2e 구분)
- [x] T059 `frontend/src/features/requirements/requirements.store.js` 수정 — `fetchRegression(id)` 액션 추가 (`GET /api/requirement-changes/{id}/regression`)

**Checkpoint**: Change 상세의 "회귀 테스트" 탭에서 영향받는 설계 노드 목록 및 테스트 항목 표시 확인

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: 관찰성·API 문서·회귀·마무리

- [x] T060 [P] `api/features/requirement_changes/routes/changes_crud.py`, `changes_approval.py`, `changes_tasks.py` 전체에 SmartLogger 추가 — 각 상태 전이(submit·approve·reject·implement) 시 `category="requirement_changes.*"` 로그 및 correlation_id 포함
- [x] T061 [P] FastAPI Swagger 자동 문서 확인 — `/docs`에서 `/api/requirement-changes/*` 전체 엔드포인트 노출 여부 확인, 누락 엔드포인트 tags/summary 보완
- [x] T062 기존 `/api/change/*` 엔드포인트 회귀 테스트 — `api/features/change_management/` 라우터가 여전히 정상 응답하는지 smoke test (서버 기동 후 `/api/change/history/US-001` 호출)
- [x] T063 `RequirementsPanel.vue` 기존 탭(Tree·Chat·Clarification 등) 회귀 확인 — Changes 탭 추가 후 기존 탭 렌더링 정상 여부 확인
- [x] T064 quickstart.md Q1–Q10 시나리오 순서대로 실행하여 전체 플로우 검증 (Change 생성→영향도→승인→구현→회귀)
- [x] T065 `CLAUDE.md` 수정 — Phase Progress를 Phase 2 Tasks ✅로 업데이트

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
    └─→ Phase 2 (Foundational) ⚠️ BLOCKS ALL
            ├─→ Phase 3 (US1 목록·삭제) ─→ Phase 4 (US2 생성)  ← P1 MVP
            ├─→ Phase 5 (US3 EFFECT 분석)
            ├─→ Phase 6 (US4 ChangeSet)
            ├─→ Phase 7 (US5 승인) ─→ Phase 8 (US6 구현) ─→ Phase 9 (US7 회귀)
            └─→ Phase 10 (Polish): 모든 Phase 완료 후
```

### User Story Dependencies

- **US1 (P1)**: Phase 2 완료 후 즉시 시작 가능 — 독립
- **US2 (P1)**: Phase 2 완료 후 시작, US1 ChangesPanel 필요 (탭 존재 전제)
- **US3 (P2)**: Phase 2 완료 후 시작 — US1·US2와 독립
- **US4 (P2)**: Phase 2 완료 후 시작 — US1 목록 UI 필요
- **US5 (P2)**: Phase 2 완료 후 시작 — US2 생성 필요 (승인할 Change가 있어야 테스트 가능)
- **US6 (P3)**: US5 완료 필요 (APPROVED 상태가 전제)
- **US7 (P3)**: US6 완료 필요 (IMPLEMENTED 후 회귀 분석 의미 있음)

### Within Each Phase

1. 백엔드 서비스 → 라우터 → router.py include → 프런트엔드 스토어 액션 → Vue 컴포넌트

### Parallel Opportunities

- Phase 1 내 T005–T009: 모두 서로 다른 파일, 병렬 가능
- Phase 3–6: Phase 2 완료 후 US3·US4는 US1·US2와 병렬 시작 가능
- 같은 Phase 내 [P] 마킹 태스크들: 동시 진행 가능

---

## Parallel Example: Phase 3 (US1)

```bash
# 백엔드와 프런트엔드를 병렬로 진행 가능
# Developer A (백엔드):
Task T015: changes_crud.py GET / + GET /{id}
Task T016: changes_crud.py DELETE /{id}

# Developer B (프런트엔드):
Task T018: ChangesPanel.vue 생성
Task T019: ChangeDetail.vue 생성 (기본)
```

---

## Implementation Strategy

### MVP (US1 + US2만 — P1 완성)

1. Phase 1: Setup (T001–T009)
2. Phase 2: Foundational (T010–T014)
3. Phase 3: US1 목록·삭제 (T015–T021)
4. Phase 4: US2 Change 생성 (T022–T027)
5. **STOP & VALIDATE**: Changes 탭에서 생성·조회·삭제 전체 플로우 확인

### Incremental Delivery

| 단계 | 완성 | 검증 |
|------|------|------|
| MVP | US1+US2 | Changes 탭 CRUD |
| +EFFECT | +US3 | PROMPT Change EFFECT 자동 분석 |
| +ChangeSet | +US4 | 묶음 관리 |
| +승인 | +US5 | 워크플로우 거버넌스 |
| +구현 | +US6 | 태스크 SSE 스트리밍 |
| +회귀 | +US7 | 테스트 영향도 |

---

## Notes

- [P] 태스크 = 서로 다른 파일, 의존성 없음 → 병렬 진행 가능
- [US*] 레이블 = 해당 태스크가 서비스하는 User Story
- `sourceType=PROMPT` EFFECT는 비동기(fire-and-forget), UI에서 polling 또는 재조회로 확인
- `RESET_CHANGE_DATA=true` 환경변수로 기존 RequirementChange/ChangeSet 초기화 트리거
- 기존 `/api/change/*` 엔드포인트는 건드리지 않음 (T062에서 회귀 확인)
- 총 태스크 수: **65개** | P1 MVP(Phase 1–4): **27개**
