---
description: "Task list for Requirements Tab implementation"
---

# Tasks: Requirements Tab

**Input**: Design documents from `/specs/026-requirements-tab/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/rest-api.md, quickstart.md

**Tests**: 자동화 테스트는 명세에서 명시적으로 요구하지 않음. 검증은 quickstart.md의 수동 스모크 + 마지막 단계의 Playwright 스모크 1건으로 수행한다(Polish 단계).

**Organization**: 작업은 user story 단위로 그룹화되어 각 story를 독립적으로 구현·검증할 수 있다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 병렬 가능(다른 파일, 미완 작업에 비의존)
- **[Story]**: 소속 user story (US1~US6)
- 모든 작업에 정확한 파일 경로 포함

## Path Conventions

웹 애플리케이션 미러 구조: 백엔드 `api/features/`, 프런트 `frontend/src/features/`. 그래프 스키마 `docs/cypher/schema/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 신규 feature 모듈 골격 생성 및 라우터/탭 등록 준비

- [X] T001 백엔드 feature 모듈 골격 생성 — `api/features/requirements/__init__.py`, `api/features/requirements/router.py`(prefix `/api/requirements`, tag `requirements`, 빈 include), `api/features/requirements/routes/__init__.py`
- [X] T002 `api/main.py`에 `api/features/requirements/router.py`의 router를 include하여 Swagger `/docs` 노출
- [X] T003 [P] 프런트 feature 폴더 골격 생성 — `frontend/src/features/requirements/ui/` 디렉터리와 빈 `frontend/src/features/requirements/requirements.store.js`(Pinia store 스켈레톤)

**Checkpoint**: 모듈 골격 준비 — Foundational 단계 시작 가능

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 모든 user story가 의존하는 그래프 스키마·DTO·인제스트 페이즈·탭 등록. 이 단계 완료 전 user story 작업 불가.

**⚠️ CRITICAL**: 이 단계가 끝나야 user story 구현 시작 가능

- [X] T004 `docs/cypher/schema/03_node_types.cypher`에 `Feature` 노드 타입 정의 추가(id/key/name/description/boundedContextId/source/sequence/createdAt/updatedAt + MERGE 생성 패턴) — data-model.md §1.1
- [X] T005 [P] `docs/cypher/schema/04_relationships.cypher`에 `HAS_FEATURE`(BC→Feature)·`HAS_USER_STORY`(Feature→UserStory, 속성 source/confidence/createdAt) 관계 정의 추가 — data-model.md §1.2
- [X] T006 [P] `docs/cypher/schema/01_constraints.cypher`에 `Feature.id`/`Feature.key` UNIQUE 제약, `docs/cypher/schema/02_indexes.cypher`에 `Feature(boundedContextId)`·`Feature(name)` 인덱스 추가 — data-model.md §1.3
- [X] T007 Pydantic DTO 작성 — `api/features/requirements/requirements_contracts.py`에 트리(`AcceptanceCriterionDTO`/`UserStoryNodeDTO`/`FeatureNodeDTO`/`EpicNodeDTO`/`RequirementsTreeDTO`), Feature·UserStory CRUD, propose/confirm/move/delete, `DesignTraceResponse`, `ImpactFinding`/`ImpactReportDTO`, `GenerationWarning` 코드 3종 정의 — data-model.md §2
- [X] T008 [P] `api/features/ingestion/event_storming/neo4j_ops/features.py` 생성 — `Feature` MERGE + `HAS_FEATURE`/`HAS_USER_STORY`(`source` 인자) bulk upsert, `source='manual'` 관계 비클로버 보존 헬퍼
- [X] T009 `feature_grouping` 인제스트 페이즈 추가 — `api/features/ingestion/ingestion_contracts.py`의 `IngestionPhase` enum에 `GROUPING_FEATURES` 추가, `api/features/ingestion/workflow/phases/feature_grouping.py` 생성(BC별 User Story 묶음을 LLM으로 Feature 그룹 도출, `ingestion_llm_runtime` 사용) — research.md R3
- [X] T010 `api/features/ingestion/ingestion_workflow_runner.py`에서 BC 분류 페이즈 직후 `feature_grouping` 페이즈 호출 + SSE `GROUPING_FEATURES` 진행률/Feature 카운트 이벤트 emit, `phase_logger`에 `agent.requirements.feature_grouping.*` 로깅
- [X] T011 프런트 탭 등록 — `frontend/src/app/layout/TopBar.vue`의 tabs 배열 맨 앞에 `Requirements` 추가, `frontend/src/App.vue`의 `tabComponents`에 `'Requirements' → RequirementsPanel` 매핑 추가
- [X] T012 `frontend/src/features/requirements/requirements.store.js` 구현 — 트리/선택 US/괘적/영향도 리포트 상태 + `/api/requirements/*` API 클라이언트 함수
- [X] T013 `frontend/src/features/requirements/ui/RequirementsPanel.vue` 셸 생성 — 좌측 트리 슬롯 + 우측 상세 슬롯 + 하단 임베드 캔버스 영역 레이아웃

**Checkpoint**: 그래프 스키마·DTO·인제스트 페이즈·탭 골격 준비 — user story 구현 병렬 시작 가능

---

## Phase 3: User Story 1 - 요구사항을 Epic→Feature→User Story로 탐색 (Priority: P1) 🎯 MVP

**Goal**: Requirements 탭에서 Epic(BC)→Feature→User Story→Acceptance Criteria 4단계 트리 드릴다운과 User Story 본문·인수조건 표시.

**Independent Test**: 인제스트된 데이터로 탭을 열어 4단계 트리가 펼쳐지고 US 클릭 시 "As a..I want..so that.." + 인수조건이 렌더되는지 확인(quickstart S1).

- [X] T014 [US1] `api/features/requirements/tree_service.py` 구현 — Epic(BC)→Feature→UserStory→GWT 4단계 집계 Cypher, Feature 없는 US는 BC별 "미분류 Feature" 버킷·BC 없는 US는 최상위 "미분류" 버킷 처리, AC는 `UserStory-[:IMPLEMENTS]->Command-[:HAS_GIVEN|HAS_WHEN|HAS_THEN]->*`에서 도출 — research.md R8
- [X] T015 [US1] `api/features/requirements/routes/requirements_tree.py` 생성 — `GET /api/requirements/tree` 라우트(`RequirementsTreeDTO` 반환), `api/features/requirements/router.py`에 include, `requirements.tree.*` 로깅
- [X] T016 [P] [US1] `frontend/src/features/requirements/ui/RequirementsTree.vue` 구현 — 4단계 드릴다운 트리(기존 `TreeNode` 패턴 재사용), 노드 클릭 시 store에 선택 US 설정
- [X] T017 [P] [US1] `frontend/src/features/requirements/ui/UserStoryDetail.vue` 구현 — "As a {role} I want {action} so that {benefit}" 문장 + 인수조건(GWT) 가독성 렌더, Command 미연결/AC 없음 안내
- [X] T018 [US1] `RequirementsPanel.vue`에 `RequirementsTree`·`UserStoryDetail` 배치, store의 트리 fetch를 마운트 시 호출

**Checkpoint**: User Story 1 독립 동작·검증 가능 (MVP)

---

## Phase 4: User Story 2 - User Story 설계 괘적을 탭 내부 캔버스에서 확인 (Priority: P1)

**Goal**: User Story 클릭 시 연결 Command 기점의 command-aggregate-event-policy-command-aggregate 괘적을 탭 내부 캔버스에 렌더.

**Independent Test**: Command 연결 US 클릭 → 괘적만 렌더, 미연결 US → "연결된 설계 없음", 다른 US 클릭 → 교체(quickstart S2).

- [X] T019 [US2] `api/features/requirements/routes/design_trace.py` 생성 — `GET /api/requirements/user-story/{id}/design-trace`, `UserStory-[:IMPLEMENTS]->Command` 기점에서 `HAS_COMMAND`/`EMITS`/`TRIGGERS`/`INVOKES` 체인 제한 깊이(쿼리 `depth` 기본 2) BFS 순회, Design 탭 `expand-with-bc`와 동일 `{nodes, relationships}` 포맷 반환, `empty` 플래그 처리 — research.md R6
- [X] T020 [US2] `api/features/requirements/router.py`에 `design_trace` 라우트 include + `requirements.design_trace.*` 로깅
- [X] T021 [US2] `frontend/src/features/requirements/ui/DesignTraceCanvas.vue` 구현 — Design 탭 Vue Flow 캔버스 컴포넌트/노드 타입 재사용 래퍼, `{nodes, relationships}` 수신 후 기존 레이아웃(`addNodesWithLayout` 패턴) 적용
- [X] T022 [US2] `requirements.store.js`에 design-trace fetch 액션 추가, `RequirementsPanel.vue`에 `DesignTraceCanvas` 임베드 + US 선택 변경 시 괘적 재로딩/교체

**Checkpoint**: User Story 1·2 독립 동작

---

## Phase 5: User Story 3 - 신규 요구사항을 문서/자연어로 추가 (Priority: P1)

**Goal**: 탭 내 문서 업로드(증분 upsert) + 자연어 입력(propose→confirm)으로 Feature·User Story 추가.

**Independent Test**: 업로드 시 자동 삭제 다이얼로그 미표시·기존 데이터 보존, 자연어 propose→confirm 후에만 트리 추가(quickstart S3·S4).

- [X] T023 [US3] `api/features/requirements/feature_grouping_llm.py` 구현 — 자연어 입력 텍스트를 User Story로 분해 + BC/Feature 제안, 불확실 시 `requirement_unclear`/`bc_unresolved`/`feature_unresolved` 경고, `ingestion_llm_runtime` 사용
- [X] T024 [US3] `api/features/requirements/routes/user_story_crud.py` 생성 — `POST /api/requirements/user-story/propose`(그래프 미변경, LLM 초안 반환), `POST /api/requirements/user-story/confirm`(UserStory 생성 + `IMPLEMENTS`(BC) + `HAS_USER_STORY`(Feature, `source='manual'`)), null BC/Feature 시 미분류 — research.md R4, contracts §3
- [X] T025 [P] [US3] `api/features/requirements/routes/feature_crud.py` 생성 — `POST /api/requirements/feature`(Feature + `HAS_FEATURE` `source='manual'` 생성, 404 BC 미존재) — contracts §2
- [X] T026 [US3] `api/features/requirements/router.py`에 `user_story_crud`·`feature_crud` 라우트 include + `requirements.user_story.*`/`requirements.feature.*` 로깅
- [X] T027 [P] [US3] `frontend/src/features/requirements/ui/AddRequirementDialog.vue` 구현 — 문서 업로드 / 자연어 입력 탭, 자연어는 propose 결과 검토·수정 화면 후 confirm, 수동 입력은 confirm 직접 호출
- [X] T028 [US3] `frontend/src/features/requirementsIngestion/ui/RequirementsIngestionModal.vue` 수정 — 업로드 전 기존 데이터 삭제 확인 다이얼로그·`/api/graph/clear` 호출 제거(증분 upsert 기본, `analyzer` 모드와 동일 흐름) — research.md R5
- [X] T029 [US3] `RequirementsPanel.vue`에 "요구사항 추가" 진입 + 문서 업로드 버튼 배치(탭 영역 내), `AddRequirementDialog` 연결, 추가 후 트리 갱신

**Checkpoint**: User Story 1·2·3 독립 동작

---

## Phase 6: User Story 4 - User Story 재배치 및 Feature/User Story 삭제 (Priority: P2)

**Goal**: 트리 drag-n-drop으로 US를 다른 Feature로 이동, Feature/User Story 삭제(Feature 삭제 시 하위 US 처리 선택).

**Independent Test**: US 드래그 시 소속 변경·영속화, Feature 삭제 시 disposition 선택 프롬프트(quickstart S5).

- [X] T030 [US4] `user_story_crud.py`에 `PATCH /api/requirements/user-story/move`(기존 `HAS_USER_STORY` detach 후 대상 Feature MERGE `source='manual'`, 타 BC Feature면 `IMPLEMENTS`(BC) 갱신·`boundedContextChanged`)·`DELETE /api/requirements/user-story` 추가 — contracts §4
- [X] T031 [US4] `feature_crud.py`에 `DELETE /api/requirements/feature` 추가 — `userStoryDisposition` `unassign`(하위 `HAS_USER_STORY`만 detach) / `delete`(하위 US까지 삭제) — contracts §2
- [X] T032 [US4] `RequirementsTree.vue`에 User Story drag-n-drop 핸들러 추가 — 드롭 시 store의 move 액션 호출
- [X] T033 [US4] `RequirementsTree.vue`/`RequirementsPanel.vue`에 Feature·User Story 삭제 UI 추가 — Feature 삭제 시 하위 US 처리(미분류/함께 삭제) 선택 프롬프트, store 삭제 액션 연결

**Checkpoint**: User Story 1~4 독립 동작

---

## Phase 7: User Story 5 - 추가·삭제 시 영향도 자동 분석 및 보고 (Priority: P2)

**Goal**: US 추가/삭제·Feature 삭제 시 백그라운드 비차단 영향도 분석(중복·충돌·설계 영향) 후 리포트.

**Independent Test**: 유사 US 추가 후 작업 비차단으로 진행, 사후 중복 경고 리포트 표시(quickstart S6).

- [X] T034 [US5] `api/features/requirements/impact_hook.py` 구현 — 기존 `change_management`의 impact analysis(4-path traversal)·`impact_propagation_engine`·`related_search`(중복 탐지) 재사용 호출, `ImpactReportDTO` 산출 — research.md R7
- [X] T035 [US5] `api/features/requirements/routes/impact_report.py` 생성 — `GET /api/requirements/impact-report/{report_id}`(상태/findings), `GET .../stream`(SSE), 리포트 상태 저장/조회 — contracts §6
- [X] T036 [US5] T024(confirm)·T030(move/delete)·T031(feature delete) 라우트에서 mutation 응답 후 `impact_hook`을 백그라운드 태스크로 트리거, `impactReportId` 즉시 반환
- [X] T037 [US5] `api/features/requirements/router.py`에 `impact_report` 라우트 include + `requirements.impact.*` 로깅
- [X] T038 [P] [US5] `frontend/src/features/requirements/ui/ImpactReportPanel.vue` 구현 — 비차단 리포트 패널/배지, findings 없으면 미표시, store가 폴링 또는 SSE로 결과 수신
- [X] T039 [US5] `requirements.store.js`에 영향도 리포트 폴링/SSE 수신 액션 추가, `RequirementsPanel.vue`에 `ImpactReportPanel` 배치

**Checkpoint**: User Story 1~5 독립 동작

---

## Phase 8: User Story 6 - 요구사항 데이터 명시적 삭제 (Priority: P3)

**Goal**: 업로드와 무관한 별도 삭제 버튼으로 요구사항 데이터를 확인 절차 후 삭제.

**Independent Test**: 별도 삭제 버튼 → 확인 후 데이터 삭제, 업로드 시 자동 삭제 없음(quickstart S7).

- [X] T040 [US6] `RequirementsPanel.vue`에 별도 "데이터 삭제" 버튼 추가 — 확인 다이얼로그 후 기존 `DELETE /api/ingest/clear-all` 호출, 완료 시 트리·store 초기화
- [X] T041 [US6] T028 변경 검증 — 업로드 경로에 자동 삭제 동작이 남아 있지 않음을 확인하고, 명시 삭제만 데이터를 비우도록 store 흐름 정리

**Checkpoint**: 전 User Story 독립 동작

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: 다중 story 영향 마무리·검증

- [X] T042 [P] `frontend/components.d.ts` 갱신 — 신규 Requirements 컴포넌트 타입 반영
- [X] T043 [P] README의 API 요약 섹션에 `/api/requirements` prefix 추가, Swagger `/docs` 노출 확인
- [ ] T044 회귀 확인 — 기존 Design/Event Modeling/BPMN 탭 정상 동작, Requirements 탭이 별도 모드로 간섭 없음
- [X] T045 `frontend/tests/requirements-tab.spec.ts` Playwright 스모크 작성 — quickstart S1~S7 핵심 흐름 커버
- [ ] T046 quickstart.md 7개 시나리오 수동 검증 수행 및 결과 기록

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 의존 없음 — 즉시 시작
- **Foundational (Phase 2)**: Setup 완료 후 — 모든 user story 차단
- **User Stories (Phase 3~8)**: Foundational 완료 후 시작. Foundational 이후 병렬 가능(인력 여유 시) 또는 우선순위 순차(P1→P2→P3)
- **Polish (Phase 9)**: 대상 user story 완료 후

### User Story Dependencies

- **US1 (P1)**: Foundational 후 시작 — 타 story 비의존
- **US2 (P1)**: Foundational 후 시작 — US1의 트리 선택과 통합되나 독립 검증 가능(직접 US id로 호출)
- **US3 (P1)**: Foundational 후 시작 — 독립
- **US4 (P2)**: Foundational 후 시작 — US1 트리 UI에 기능 추가(같은 `RequirementsTree.vue` 파일 편집 → US1과 순차 권장)
- **US5 (P2)**: T036이 US3·US4의 mutation 라우트를 편집하므로 US3·US4 후 진행 권장
- **US6 (P3)**: T041이 T028(US3)에 의존 — US3 후 진행

### Within Each User Story

- 모델/스키마 → 서비스 → 엔드포인트 → 프런트 통합 순
- 같은 파일을 편집하는 작업은 [P] 없음 — 순차

### Parallel Opportunities

- Setup: T003은 T001/T002와 병렬
- Foundational: T005·T006·T008은 병렬(T004와 다른 파일); T011·T012·T013은 백엔드 작업과 병렬
- US1: T016·T017 병렬(다른 컴포넌트 파일)
- US3: T025·T027 병렬
- US5: T038 병렬
- Foundational 완료 후 US1·US2·US3는 서로 다른 파일군이라 팀이 병렬 진행 가능

---

## Parallel Example: Foundational Phase

```bash
# 스키마 파일 동시 작성:
Task: "04_relationships.cypher에 HAS_FEATURE/HAS_USER_STORY 추가"   # T005
Task: "01_constraints.cypher / 02_indexes.cypher에 Feature 제약·인덱스 추가"  # T006
Task: "neo4j_ops/features.py 작성"                                  # T008
```

## Parallel Example: User Story 1

```bash
# US1 프런트 컴포넌트 동시 작성:
Task: "RequirementsTree.vue 구현"      # T016
Task: "UserStoryDetail.vue 구현"        # T017
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 Setup 완료
2. Phase 2 Foundational 완료 (전 story 차단 — 필수)
3. Phase 3 US1 완료
4. **STOP & VALIDATE**: quickstart S1로 US1 독립 검증
5. 준비되면 데모

### Incremental Delivery

1. Setup + Foundational → 기반 완성
2. US1(트리 탐색) → 검증 → 데모 (MVP)
3. US2(설계 괘적) → 검증 → 데모
4. US3(요구사항 추가) → 검증 → 데모
5. US4·US5·US6 순차 추가 → 각 단계 검증
6. 각 story는 이전 story를 깨지 않고 가치 추가

### Parallel Team Strategy

Foundational 완료 후: 개발자 A=US1, B=US2, C=US3 병렬. US4는 US1과 같은 트리 파일을 편집하므로 A가 US1 후 이어서, US5는 US3·US4 후, US6은 US3 후 진행.

---

## Notes

- [P] = 다른 파일·미완 작업 비의존
- [Story] 라벨로 작업↔user story 추적
- 신규 노드/관계는 코드 이전에 `docs/cypher/schema/`에 반영(Constitution 개발 워크플로 게이트)
- 자연어 추가는 propose→confirm 2단계 유지(Constitution IV)
- 각 작업 또는 논리 그룹 후 커밋
- 체크포인트마다 story 독립 검증 가능
