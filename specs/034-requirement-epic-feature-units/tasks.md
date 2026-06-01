---
description: "Task list for 034-requirement-epic-feature-units"
---

# Tasks: Epic/Feature 등록·뷰·편집, 하위 US 자동 생성, DDD 검증, 설계 자동 반영

**Input**: Design documents from `/specs/034-requirement-epic-feature-units/`

**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅ (3 files), quickstart.md ✅

**Tests**: 본 기능은 TDD를 명시적으로 요청하지 않음. 검증은 Playwright e2e(`frontend/tests/`) + quickstart 수동 스모크 + 핵심 백엔드 pytest로 한다. 테스트 태스크는 각 스토리에 경량으로 포함하고, 전수 contract-test-first는 생략.

**Domain mapping (전체 공통)**: Epic = `BoundedContext` 노드, Feature = `Feature` 노드, US = `UserStory` 노드. **신규 노드 라벨/관계 0건.** 모든 LLM 변경은 propose→confirm(HITL). 장시간 생성은 SSE.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일·무의존 → 병렬 가능
- **[Story]**: US1–US7 (Setup/Foundational/Polish는 라벨 없음)

## Path Conventions (this repo)

- Backend: `api/features/<feature>/...`
- Frontend: `frontend/src/features/requirements/...`, `frontend/src/app/...`
- Desktop(Electron): `desktop/src/...`
- Skills: `skills/robo-spec/...`
- Tests: `frontend/tests/*.spec.ts` (Playwright), `api/features/requirements/tests/` (pytest)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 신규 파일 스캐폴딩 및 라우터/스토어 배선 준비. 기존 프로젝트이므로 경량.

- [~] T001 백엔드 신규 라우트 모듈 빈 스텁 생성 및 `api/features/requirements/router.py`에 등록 — `routes/bounded_context_crud.py`✅(구현됨, router.py 등록 완료); `routes/epic_feature_propose.py`·`routes/child_story_generation.py`·`routes/ddd_validation.py`·`routes/design_reflect.py` 미생성(후속)
- [~] T002 [P] 프런트 신규 컴포넌트 빈 스텁 생성 — `EpicEditForm.vue`·`FeatureEditForm.vue` ✅구현; `EpicDetail,FeatureDetail,GeneratedStoriesReview,ValidationFindings,DesignReflectPrompt.vue` 미생성(후속)
- [ ] T003 [P] Playwright e2e 스펙 파일 생성(빈 describe 블록) — `frontend/tests/requirement-epic-feature.spec.ts`
- [ ] T004 [P] 백엔드 pytest 디렉터리/`__init__` 준비 — `api/features/requirements/tests/test_epic_feature_units.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 여러 스토리가 공유하는 DTO·SSE·스토어 상태 일반화. ⚠️ 완료 전 스토리 구현 시작 금지.

- [ ] T005 공유 응답 DTO 정의 — `api/features/requirements/requirements_contracts.py`에 `FeatureDTO`(id,key,name,description,boundedContextId,source)·`BoundedContextDTO`(id,key,name,displayName,description) 추가 (US1·2·3 공통)
- [ ] T006 [P] SSE 진행 스트리밍 헬퍼 — `api/features/requirements/streaming.py` 신설, `sse_starlette.EventSourceResponse` 래퍼 + 취소 감지(클라 disconnect) (`api/features/ingestion`의 `/stream` 패턴 차용; US5·US7 공통, research D10)
- [ ] T007 [P] 프런트 스토어 선택 상태 일반화 — `frontend/src/features/requirements/requirements.store.js`에 `selectedNode {type:'epic'|'feature'|'userStory', id}` 와 `clarityScope {scopeType, scopeId}` state + `selectNode(type,id)` 액션 골격 추가(기존 `selectedUserStoryId` 호환 유지) (US2·US4 공통)
- [ ] T008 [P] 프런트 HTTP 호출 헬퍼 확인/확장 — `frontend/src/app/http.js` 경유로 SSE(EventSource) 호출 유틸 추가(identity 헤더 유지) (US5·US7 공통)

**Checkpoint**: 공유 DTO·SSE·스토어 골격 준비 완료 → 스토리 병렬 착수 가능.

---

## Phase 3: User Story 1 - Epic/Feature/US 3-granularity 등록 (Priority: P1) 🎯 MVP

**Goal**: "+"에서 Epic/Feature/User Story 단위를 골라 AI 제안 또는 수동으로 등록.

**Independent Test**: "+"로 Epic→Feature→User Story를 차례로 등록해 트리에 3단계가 모두 나타나는지(quickstart Q1–Q5).

### Backend (US1)

- [X] T009 [P] [US1] Epic(BC) 생성 요청/응답 모델 — `requirements_contracts.py`에 `BoundedContextCreateRequest{name,description?}` / `...Response{boundedContext:BoundedContextDTO}` 추가 (name 공백 검증) ✅ `BoundedContextDTO`도 추가
- [X] T010 [P] [US1] Epic/Feature 제안 모델 — `requirements_contracts.py`에 `EpicProposeRequest/Response`+`EpicProposal`, `FeatureProposeRequest/Response`+`FeatureProposal` 추가 ✅
- [X] T011 [US1] `POST /api/requirements/bounded-context` 구현 — `routes/bounded_context_crud.py`에서 기존 `ingestion/event_storming/neo4j_ops/bounded_contexts.py:create_bounded_context()` 래핑(MERGE on key, key/displayName 서버 도출), 201 반환, correlation 로깅 ✅ pytest 통과
- [X] T012 [US1] `POST /api/requirements/epic/propose`·`/feature/propose` 구현 — `routes/epic_feature_propose.py`에서 user-story propose 패턴(provider-agnostic `get_llm`) 재사용해 후보 반환(미확정), 빈 배열 허용(폴백) (contract A4/A5) ✅ 실 LLM 검증(배송→배송관리·반품회수관리 분해)
- [ ] T013 [US1] 확정 경로 검증 — Feature 확정은 기존 `POST /api/requirements/feature`(feature_crud.py) 재사용 가능 확인/보강, Epic 확정은 T011 사용 (회귀 0건)

### Frontend (US1)

- [~] T014 [US1] 스토어 액션 추가 — `requirements.store.js`에 `createEpic(name,desc)`(`POST /bounded-context`)✅, `createFeature`(기존)✅; `proposeEpic`/`proposeFeature`(AI)는 후속(엔드포인트 미구현)
- [~] T015 [US1] `AddRequirementDialog.vue` 확장 — Epic/Feature/User Story **단위 선택** + Epic/Feature **수동 폼**(소속 Epic 선택 포함), 취소 시 무변경 ✅; AI 제안 탭은 후속 (FR-001/003/004)
- [X] T016 [US1] AI 제안 후보 검토 UI — 제안 목록 표시·수정·확정/취소, 후보 0건/실패 시 수동 탭 폴백 (FR-006) — AddRequirementDialog에 AI 제안 탭 + 후보 검토·추가·폴백 ✅
- [ ] T017 [P] [US1] e2e — `frontend/tests/requirement-epic-feature.spec.ts`에 Q1–Q5(단위 선택·Epic 수동·Feature 소속·AI 제안 폴백·US 회귀) 시나리오 추가

**Checkpoint**: Epic/Feature/US를 한 흐름에서 등록 가능(MVP). 기존 US 등록 회귀 없음.

---

## Phase 4: User Story 2 - Epic·Feature 전용 뷰 패널 (Priority: P2)

**Goal**: 트리에서 Epic/Feature 선택 시 전용 뷰(이름·설명·출처 + 하위 목록·요약) 표시. US는 기존 상세 유지.

**Independent Test**: Epic/Feature 노드 선택 시 전용 뷰가 ≤2초 내 뜨고 하위 목록이 보이는지(quickstart Q6–Q7).

### Backend (US2)

- [~] T018 [P] [US2] Epic 상세 — 별도 `GET` 엔드포인트 대신 트리 DTO에 `description` 추가(`EpicNodeDTO`+`tree_service`)로 클라이언트가 트리에서 파생 ✅(엔드포인트 불필요로 단순화)
- [~] T019 [P] [US2] Feature 상세 — Feature DTO에 이미 name/description/source/userStories 존재 → 트리에서 파생 ✅(별도 엔드포인트 불필요)

### Frontend (US2)

- [X] T020 [US2] `RequirementsPanel.vue` 분기 — `store.selectedNode.type`에 따라 `EpicDetail`/`FeatureDetail`/`UserStoryDetail`(기존) 렌더 (FR-007/008/009) ✅
- [X] T021 [P] [US2] `EpicDetail.vue` 구현 — 이름·설명 + 하위 Feature 목록/요약(US 카운트), 빈 상태 CTA, 편집 버튼 (FR-007, US2-AC4) ✅
- [X] T022 [P] [US2] `FeatureDetail.vue` 구현 — 이름·설명·source + 하위 User Story 목록, 빈 상태 CTA, 편집 버튼 (FR-008) ✅
- [X] T023 [US2] 트리 선택 배선 — `RequirementsTree.vue`에서 Epic/Feature 행 클릭→`select-epic/select-feature`→`store.selectEpic/selectFeature`; caret는 토글; US 선택 회귀 유지 + 선택 하이라이트 ✅
- [ ] T024 [P] [US2] e2e — Q6–Q7(Epic 뷰·Feature 뷰·US 회귀·빈 상태)을 e2e 스펙에 추가 — 후속(Playwright)

**Checkpoint**: Epic/Feature 전용 뷰 동작. US 상세 회귀 없음.

---

## Phase 5: User Story 3 - Epic·Feature 편집 패널 (Priority: P2)

**Goal**: Epic/Feature 이름·설명 편집·저장, 즉시 반영, 검증/취소, 하위 연결 보존.

**Independent Test**: Feature 이름을 편집·저장 후 새로고침 없이 트리·뷰 반영 + 하위 US 유지(quickstart Q8).

### Backend (US3)

- [X] T025 [P] [US3] 편집 모델 — `requirements_contracts.py`에 `FeatureUpdateRequest{featureId,name?,description?}`/`Response`, `BoundedContextUpdateRequest{boundedContextId,name?,description?}`/`Response` 추가(name 공백 422) ✅
- [X] T026 [P] [US3] ops 확장 — `ingestion/event_storming/neo4j_ops/features.py`에 `update_feature(feature_id,name,description)`, `.../bounded_contexts.py`에 `update_bounded_context(id,name,description)` 추가(**속성만 SET, `HAS_FEATURE`/`HAS_USER_STORY` 보존; key 불변**) (FR-012) ✅
- [X] T027 [US3] `PATCH /api/requirements/feature` 구현 — `routes/feature_crud.py` 확장, 404/422 처리, T026 호출 (FR-010/011/012) ✅ pytest 통과
- [X] T028 [US3] `PATCH /api/requirements/bounded-context` 구현 — `routes/bounded_context_crud.py` 확장, 404/422, 낙관적 존재 점검(외부 변경/삭제 안내) (FR-010/011, research D7) ✅ pytest 통과

### Frontend (US3)

- [X] T029 [US3] 스토어 액션 — `requirements.store.js`에 `updateEpic(id,{name,description})`(`PATCH /bounded-context`), `updateFeature(id,{...})`(`PATCH /feature`) + 트리 즉시 갱신 + 422/404 detail 표면화 ✅
- [X] T030 [P] [US3] `EpicEditForm.vue` 구현 — 트리 Epic 행의 ✎ 버튼에서 모달 진입, 저장/취소, 필수 검증 (FR-010/011) ✅ (Detail 토글은 US2 후속)
- [X] T031 [P] [US3] `FeatureEditForm.vue` 구현 — 트리 Feature 행의 ✎ 버튼에서 모달 진입, 저장/취소, 필수 검증 ✅
- [ ] T032 [P] [US3] e2e — Q8(저장 즉시반영·검증차단·취소·하위 연결 보존)을 e2e 스펙에 추가

**Checkpoint**: Epic/Feature 편집 동작, 관계 보존.

---

## Phase 6: User Story 4 - 선택 범위에 따른 clarification radar 필터링 (Priority: P3)

**Goal**: Epic/Feature/Project 선택에 따라 radar가 그 범위로 필터링·갱신. 빈 범위는 중립 상태.

**Independent Test**: 서로 다른 Feature 선택 시 radar 점수가 범위에 맞게 달라지는지(quickstart Q9). **백엔드 변경 없음**(clarity scope 이미 지원).

- [X] T033 [US4] 스토어 scope 배선 — `selectEpic`→`fetchClarityScores('bounded_context',id)`, `selectFeature`→`('feature',id)`, `selectUserStory`→`('project','*')` (FR-013/014) ✅
- [X] T034 [US4] 라디오 배선 — `EpicDetail`/`FeatureDetail`에 `ClarityRadar` 렌더(해당 scope), `store.clarityScores` 없으면 빈 안내(오류 아님) (FR-015) ✅
- [ ] T035 [P] [US4] e2e — Q9(Feature 전환·Epic 합산·전체·빈 범위 중립)을 e2e 스펙에 추가 — 후속(Playwright)

**Checkpoint**: radar 범위 필터링 동작, 잘못된 범위 혼입 0건.

---

## Phase 7: User Story 5 - 하위 US 자동 생성(이원 엔진, 제안→확인) (Priority: P1)

**Goal**: Epic/Feature 등록 직후 하위 US 후보 자동 제안 → 선택 확정. 엔진은 Settings에서 in-process LLM / Claude IDE 선택, 후자 미설치 시 설치 안내.

**Independent Test**: Feature 등록 후 하위 US 후보가 제안되고 선택분만 트리에 반영(quickstart Q11–Q12).

### Settings 토글 (US5)

- [X] T036 [P] [US5] 프런트 Settings 토글 — `frontend/src/app/layout/SettingsPanel.vue`에 `requirementGenerationEngine: 'in-process'|'claude-ide'` 추가 + localStorage 저장 (FR-020) ✅
- [ ] T037 [P] [US5] Electron Settings 필드 — `desktop/src/shared/ipc-contract.ts` `DesktopSettings`에 `requirementGenerationEngine` 추가, `desktop/src/main/settings.ts` 기본값 `'in-process'` + 마이그레이션 (research D14) — 웹은 localStorage로 처리; Electron 필드는 후속

### Backend (US5)

- [X] T038 [P] [US5] 생성/확정 모델 — `requirements_contracts.py`에 `GeneratedStory`, `GenerateChildStoriesResponse`, `ConfirmChildStoriesRequest/Response` 추가 ✅ (SSE Progress/LocalToolingStatus는 후속)
- [X] T039 [US5] `POST /api/requirements/generate-stories/{scope_type}/{scope_id}` — `routes/child_story_generation.py`에서 **in-process** `get_llm().with_structured_output()`로 Epic/Feature 컨텍스트 기반 후보 생성(언어 일치, 중복 회피), 실패 시 빈 배열 폴백 ✅ 실 LLM 검증(5건 한국어 생성) — SSE 진행표시는 후속(현재 동기)
- [X] T040 [US5] `POST /api/requirements/child-stories/confirm` — 선택 후보만 기존 UserStory 영속 경로(create_user_story+link_bc+link_feature)로 저장, 트리 갱신 ✅ 실 검증(2건 저장→트리 반영)
- [X] T041 [US5] `GET /api/requirements/local-tooling/status` — `shutil.which("claude")` + speckit/robo-spec 스킬 존재 점검+ ~/.claude/skills·프로젝트 .claude/skills의 speckit-specify 점검, `LocalToolingStatus` 반환 (FR-021) ✅ 실 검증(claude✓ speckit✓)
- [X] T042 [US5] Claude IDE 엔진 경로 — `api/features/claude_code/router.py` 확장: T041 preflight 통과 시 로컬 `claude`로 speckit-specify(또는 robo 스킬) 헤드리스 실행 → robo-spec MCP로 그래프 컨텍스트 사용 → 미설치면 생성 차단+설치 안내 ✅; 설치 시 `claude --print --output-format json` 헤드리스 생성 ✅ 실검증(6건 생성), 실패 시 in-process 폴백 (research D8/D9)

### Frontend (US5)

- [X] T043 [US5] 스토어 액션 — `requirements.store.js`에 `generateChildStories(scopeType,scopeId)`, `confirmChildStories({boundedContextId,featureId,stories})` ✅ + `generationEngine`/`setGenerationEngine`/`checkLocalTooling` ✅
- [~] T044 [US5] 트리거 배선 — EpicDetail/FeatureDetail의 "✨ 하위 US 자동생성" 버튼 → 생성→리뷰 모달 ✅ (등록 직후 자동 호출은 후속)
- [X] T045 [P] [US5] `GeneratedStoriesReview.vue` 구현 — 후보 선택/수정/확정, 생성 중 오버레이, 0건/실패 폴백 안내 ✅ (claude-ide 설치 안내는 후속)
- [ ] T046 [P] [US5] e2e — Q11(in-process)·Q12(Claude IDE+설치 안내)를 e2e 스펙에 추가

**Checkpoint**: Epic/Feature 등록 시 하위 US 자동 제안→확정 동작, 두 엔진 전환·설치 안내.

---

## Phase 8: User Story 6 - DDD 적합성·입도·spec 정합성 검증 (Priority: P2)

**Goal**: 추가·생성물의 BC 배치/Feature 입도/기존 spec 충돌 검증 + 비차단 교정안 제안. 스킬 부재 시 robo-spec `robo-validate`로 충당.

**Independent Test**: 엉뚱한 BC에 큰 Feature 추가 시 부적합 감지 + 재배치/분할 제안(quickstart Q13).

### Backend (US6)

- [X] T047 [P] [US6] 검증 모델 — `requirements_contracts.py`에 `ValidateRequest`, `ValidationFinding`(kind:wrong_bc|oversized_feature|spec_conflict), `CorrectionProposal`, `ValidateResponse{ok,findings,source}` 추가 ✅
- [X] T048 [US6] `POST /api/requirements/validate` (in-process) — `routes/ddd_validation.py`에서 그래프(BC 목록 + 대상 BC의 Feature·US)로 `get_llm().with_structured_output()` 검증, `ValidationFinding[]` 산출, 비차단, 언어 일치 (FR-024/025/026/028) ✅ 실 LLM 검증(과대 feature→split 감지, 적합 feature→ok=true)
- [ ] T049 [P] [US6] robo-spec 검증 스킬 — `skills/robo-spec/robo-validate/SKILL.md` 신설(`extends: speckit-specify` override 또는 독립 스킬), 입력=대상+BC목록+기존 spec, 출력=`ValidationFinding[]` (FR-027, contract B2)
- [ ] T050 [US6] MCP 컨텍스트 노출 — `api/features/robo_spec/mcp_server.py`에 검증용 컨텍스트 툴(기존 `list_design_elements`/`get_bc_design` 재사용 + 필요 시 기존 spec 조회 툴 추가) 및 설치 포함(`claude_code/router.py:_install_robo_spec` 복사 목록에 robo-validate 반영)

### Frontend (US6)

- [X] T051 [US6] 스토어 액션 — `requirements.store.js`에 `validateRequirement(payload)` 추가 ✅
- [~] T052 [US6] 검증 트리거 배선 — EpicDetail/FeatureDetail의 "🔎 DDD 검증" 버튼 → 검증→결과 모달 ✅ (등록/자동생성 흐름 자동 연결은 후속). Feature DTO에 `boundedContextId` 추가
- [X] T053 [P] [US6] `ValidationFindings.vue` 구현 — 부적합 유형별 경고 + 교정안(재배치/분할/정합) 표시, 적합 시 "적합합니다", 비차단 (FR-028) ✅
- [ ] T054 [P] [US6] e2e — Q13(재배치·분할·충돌·강행 허용·적합 통과·스킬 폴백)을 e2e 스펙에 추가

**Checkpoint**: DDD·정합성 검증·교정안 동작, 스킬 부재 시에도 끊김 없음.

---

## Phase 9: User Story 7 - 요구사항 변경의 설계 자동 반영 (Priority: P3)

**Goal**: Event Modeling/Design 탭 진입 시 미반영 US 식별 → 프롬프트 → 동의 시 기존 설계 파이프라인으로 journey/Aggregate 생성·변경(제안→확인).

**Independent Test**: 설계 없는 US 생성 후 Design 탭 이동 시 프롬프트, 동의 시 설계 생성·확인 반영(quickstart Q14).

### Backend (US7)

- [~] T055 [P] [US7] US7 모델 — `requirements_contracts.py`에 `PendingDesignResponse`+`PendingUS`, 추가 + `DesignReflectRequest`·`ReflectedDesign`·`DesignReflectResponse` ✅
- [X] T056 [US7] `GET /api/requirements/user-stories/pending-design` — `routes/design_reflect.py`에서 범위 내 US 중 `routes/design_trace.py`의 `IMPLEMENTS→Command` 부재(empty)인 것만 반환 (FR-030, research D12) ✅ 실 검증(64건 미반영 US 식별)
- [X] T057 [US7] `POST /api/requirements/design/reflect` — `routes/design_reflect.py`에서 US별로 in-process LLM이 Aggregate(기존 재사용/신규)→Command→Event 설계 생성·영속 + US-IMPLEMENTS→Command 링크 (FR-032/033) ✅ 실검증(MemberAccount 재사용, design-trace 반영)
- [X] T058 [US7] 확정 경로 — 프롬프트 "예"가 HITL 게이트(사용자 동의 후 생성). reflect는 직접 영속(propose→apply 단일화) (FR-033) ✅

### Frontend (US7)

- [X] T059 [US7] 탭 진입 훅 — `frontend/src/App.vue` watch(activeTab)에서 대상이 'Event Modeling'(`EventModelingPanel`)/'Design'(`CanvasWorkspace`)이면 `pending-design` 조회 (FR-030, contract B1) ✅
- [X] T060 [US7] 스토어 액션 — requirements 스토어(또는 공유 스토어)에 `fetchPendingDesign(scope?)`, ✅; `reflectDesign` ✅(배치 cap), 세션 "묻지 않기"는 App.vue 처리 (FR-034)
- [X] T061 [P] [US7] `DesignReflectPrompt.vue` 구현 — "설계에 반영하시겠습니까?"(대상 US 목록), 아니오→무변경, "이번 세션 묻지 않기" ✅; 예→reflectDesign(설계 생성·반영, 진행 오버레이) ✅ (FR-031/032/033/034)
- [ ] T062 [P] [US7] e2e — Q14(프롬프트·동의 생성·거절·무대상·반복억제)을 e2e 스펙에 추가

**Checkpoint**: 미반영 US 식별→설계 자동 반영(확인 후) 동작, 기존 설계 흐름 회귀 없음.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: 회귀·관측성·언어 정책·문서·스키마 불변 검증.

- [ ] T063 [P] 언어 정책 — 모든 신규 LLM 산출물(Epic/Feature 제안·자동생성 US·DDD 교정안·설계 변경 텍스트)이 사용자 언어 설정(기어 아이콘, 기본=브라우저 로캘)을 따르는지 점검·보정 (FR-017, [[project_generation_language_policy]])
- [ ] T064 [P] 관측성 — 신규 라우트/에이전트에 correlation ID + 단계 로깅(start/decision/error) 적용 확인 (Constitution VII)
- [ ] T065 [P] 백엔드 pytest — `api/features/requirements/tests/test_epic_feature_units.py`에 핵심 엔드포인트(PATCH feature/bc, validate, pending-design) 단위 테스트 추가
- [ ] T066 수동 배치 보호 검증 — 수동 등록/배치(Feature.source·HAS_USER_STORY.source = manual)가 자동 재분류에 덮어써지지 않음 확인 (FR-016, quickstart Q10)
- [ ] T067 스키마 불변 검증 — `docs/cypher/schema/` diff 0건, 신규 노드 라벨/관계 0건 확인 (SC-010, FR-035)
- [ ] T068 회귀 검증 — 기존 User Story 추가/상세/명확화 + Event Modeling/Design/change-plan·apply 흐름 회귀 없음 (SC-006)
- [ ] T069 Swagger 문서 — 신규 엔드포인트가 `/docs`에 정확한 req/resp 모델로 노출되는지 확인 (개발 워크플로 게이트)
- [ ] T070 quickstart 전체 스모크 실행 — `specs/034-requirement-epic-feature-units/quickstart.md` Q1–Q14 + Out-of-band 점검 수행

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (P1)**: 의존 없음 — 즉시 시작.
- **Foundational (P2)**: Setup 후 — **모든 스토리 차단**(T005 DTO, T006 SSE, T007 스토어 골격).
- **User Stories (P3–P9)**: Foundational 후 시작. 권장 순서 = 우선순위(US1·US5=P1 → US2·US3·US6=P2 → US4·US7=P3).
- **Polish (P10)**: 원하는 스토리 완료 후.

### User Story Dependencies (독립성 유지가 원칙, 단 현실적 결합 표기)

- **US1 (P1)**: Foundational만 의존. (MVP 핵심)
- **US2 (P2)**: Foundational + 선택 상태(T007). US1과 독립 테스트 가능(기존 데이터로도 뷰 검증).
- **US3 (P2)**: US2 뷰(편집 토글 진입점)에 자연 결합 — 단 PATCH 엔드포인트는 독립 검증 가능.
- **US4 (P3)**: T007 선택 상태 의존. 백엔드 무변경. US2와 함께 쓰면 자연스러움.
- **US5 (P1)**: Foundational(T006 SSE) + **US1의 Epic/Feature 등록 트리거**에 결합(T044). 엔진/Settings는 독립.
- **US6 (P2)**: 등록/생성 흐름(US1/US5)에 검증을 끼움 — 단 `POST /validate`는 독립 호출로 검증 가능.
- **US7 (P3)**: Foundational(T006) + 기존 change_management. US1–6과 독립(설계 미반영 US만 있으면 동작).

### Within Each Story

- 모델 → ops/서비스 → 엔드포인트 → 프런트 배선 → e2e.
- SSE 엔드포인트(T039/T057)는 T006 완료 후.

### Parallel Opportunities

- Setup: T002·T003·T004 병렬.
- Foundational: T006·T007·T008 병렬(T005 먼저 권장).
- 스토리 간: Foundational 후 US1/US5(같은 팀이면 순차, 다른 팀이면 병렬), US2·US3·US4·US6·US7 병렬 가능.
- 각 스토리 내 [P] 모델·컴포넌트·e2e 병렬.

---

## Parallel Example: User Story 1

```bash
# 모델(병렬):
Task: "T009 BoundedContextCreate 모델 in requirements_contracts.py"
Task: "T010 Epic/Feature Propose 모델 in requirements_contracts.py"
# 이후 엔드포인트(T011→T012→T013)는 순차, 프런트(T014–T016)·e2e(T017)
```

## Parallel Example: Foundational

```bash
Task: "T006 SSE 헬퍼 in api/features/requirements/streaming.py"
Task: "T007 스토어 selectedNode/clarityScope 골격 in requirements.store.js"
Task: "T008 EventSource 호출 유틸 in frontend/src/app/http.js"
```

---

## Implementation Strategy

### MVP First (US1 + US5)

1. Phase 1 Setup → Phase 2 Foundational.
2. Phase 3 US1(등록) → **STOP & VALIDATE**(Q1–Q5).
3. Phase 7 US5(자동 생성, in-process 엔진 우선) → 검증(Q11). Claude IDE 엔진은 후속.
4. 데모: "Epic/Feature 등록 시 하위 US 자동 제안" = 핵심 가치.

### Incremental Delivery

1. Foundational → US1(등록) → US2(뷰) → US3(편집) → US4(radar) → US5(자동생성) → US6(검증) → US7(설계 반영).
2. 각 단계 독립 검증·데모. Constitution III(SSE)·IV(propose→confirm)는 US5/US7에서 필수.

### Notes

- [P] = 다른 파일·무의존. 같은 파일(`requirements_contracts.py`, `requirements.store.js`, `router.py`)을 만지는 태스크는 순차 처리(충돌 방지).
- 신규 노드 라벨/관계 0건 — 의심되면 즉시 중단하고 설계 재확인.
- 각 태스크/논리 그룹 후 커밋. 체크포인트에서 스토리 독립 검증.
