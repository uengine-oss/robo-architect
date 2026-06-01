---
description: "Task list for 035 DDD 발견 마법사 & 도메인 캔버스"
---

# Tasks: DDD 발견 마법사 & 도메인 캔버스

**Input**: Design documents from `specs/035-ddd-discovery-canvases/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (모두 존재)

**Tests**: 백엔드 contract/integration 테스트만 선택적으로 포함(기존 `clarification_agent/tests/` 패턴). 프런트는 quickstart 수동 검증.

**Organization**: User Story별 페이즈. 마법사는 **신규 생성기 없이 기존 ingestion 설계 기계를 오케스트레이션**(D13), 진실의 원천=그래프, 신규 노드 라벨/관계 0건(속성 추가만).

**Reuse map** (구현 전 필독):
- 세션/SSE/answer→apply: `api/features/requirements/clarification_agent/clarification_session.py` (spec 030)
- 이원화 엔진/preflight: `api/features/requirements/routes/child_story_generation.py` + `generation/local_tooling` (spec 034)
- BC/Aggregate 캔버스 렌더·투영: `api/features/ddd_spec/` (`renderers/bc_canvas.py`, `renderers/aggregate_spec.py`, `projection.py`, `service.py`)
- BC 생성/수정: `api/features/requirements/routes/bounded_context_crud.py`
- 분류: `api/features/contexts/router.py`
- 증분 설계: `api/features/ingestion/workflow/incremental_design_runner.py` + `POST /api/ingest/user-stories/design`
- 마무리/미반영: `api/features/requirements/routes/design_reflect.py` (spec 034)
- 진행 모달: `frontend/src/features/requirementsIngestion/ui/RequirementsIngestionModal.vue`
- 요구사항 탭: `frontend/src/features/requirements/ui/{RequirementsPanel,EpicDetail,UserStoryDetail}.vue`
- Aggregate 인스펙터: `frontend/src/features/canvas/ui/AggregateViewerInspector.vue` (spec 028)

---

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 의존성 확인 — spec 034의 `generation/`(child_story/ddd_validation/design_reflect), `generation/local_tooling`, `requirementGenerationEngine` 토글, `bounded_context_crud`가 작업 트리에 커밋/머지되었는지 점검하고 미커밋이면 먼저 정리 (`api/features/requirements/`, `frontend/src/features/requirements/`)
- [ ] T002 [P] `docs/cypher/schema/03_node_types.cypher`의 `Event` 주석에 `pivotal`/`hotspot` 속성, `BoundedContext` 주석에 `purpose`/`domainRoles`/`ubiquitousLanguage`/`businessDecisions`/`assumptions`/`version`/`classification(core|supporting|generic)`, `Aggregate` 주석에 `description`/`stateTransitions`/`correctivePolicies`/`throughput` 속성 의미 문서화 (신규 라벨/관계 없음)
- [ ] T003 [P] `api/features/requirements/generation/` 디렉터리에 `ddd_wizard_engine.py`·`ddd_export_engine.py` 빈 모듈 스캐폴드, `api/features/requirements/ddd_wizard/` 패키지(`__init__.py`,`wizard_session.py`,`step_prompts.py`) 스캐폴드, `routes/ddd_wizard.py`·`routes/pivotal_events.py` 빈 라우터 스캐폴드
- [ ] T004 [P] `frontend/src/features/requirements/ui/`에 `DddWizardPanel.vue`·`BcCanvasTab.vue`·`AggregateCanvasTab.vue`·`PivotalEventMarker.vue` 빈 컴포넌트 스캐폴드

---

## Phase 2: Foundational (Blocking Prerequisites)

**모든 User Story가 의존하는 공용 계약·상태·배선.**

- [ ] T005 [P] `api/features/requirements/requirements_contracts.py`에 마법사 DTO 추가 — `ProfileAnswer`, `WizardStartRequest/Response`, `WizardStepRef`, `WizardStepPlan`, `WizardAnswerRequest`, `WizardProposal`, `WizardConfirmRequest/Response`, `WizardSessionDTO` (data-model §2.1)
- [ ] T006 [P] `requirements_contracts.py`에 공용 DTO 추가 — `GraphChangePreview`(model_modifier `DraftChange`와 정합), 캔버스/내보내기/분류 DTO(`BcCanvasDTO`,`BcCanvasPatchRequest`,`AggregateCanvasDTO`,`AggregateCanvasPatchRequest`,`CanvasGenerateRequest`,`PivotalToggleRequest/Response`,`SubdomainProposeRequest`,`SubdomainProposal`,`StrategizeQuestionDTO`,`DddExportRequest/Response`,`DddImportRequest`,`DddImportPreview`,`DddImportConfirmRequest`) (data-model §2.2–2.6)
- [ ] T007 마법사 세션 상태머신 — `api/features/requirements/ddd_wizard/wizard_session.py`에 `clarification_session.py` 패턴 복제: 휘발성 in-process dict, 상태 `profiling→step_running→awaiting_answers→proposing→confirmed`(+`discarded/failed`), `completedSteps`/`artifacts` 보존(재개), SSE용 `asyncio.Queue` (data-model §4)
- [ ] T008 `routes/ddd_wizard.py`·`routes/pivotal_events.py`를 `api/features/requirements/router.py`에 `include_router` 등록
- [ ] T009 [P] 엔진 선택·preflight 헬퍼 — `generation/ddd_wizard_engine.py`에서 spec 034 `local_tooling.probe()`·`get_llm` 재사용 래퍼(`resolve_engine(engine)`, 미설치 시 409 `local_tooling_unavailable`), `SmartLogger` 단계 로그 + correlation ID (research D2, FR-014/015)
- [ ] T010 [P] 프런트 store 골격 — `frontend/src/features/requirements/requirements.store.js`에 마법사/캔버스/내보내기 액션 스텁(`startWizard`,`streamWizardStep`,`answerWizard`,`confirmWizardStep`,`fetchBcCanvas`,`patchBcCanvas`,`fetchAggregateCanvas`,`patchAggregateCanvas`,`togglePivotal`,`exportDdd`) + Accept-Language 헤더(spec 031)

**Checkpoint**: 계약·세션·배선 준비 완료 → 각 User Story 병렬 착수 가능.

---

## Phase 3: User Story 1 — DDD 발견 마법사(8단계 옵트인) (P1) 🎯 MVP

**Goal**: 맨땅/에픽 양쪽에서 프로파일링→추천 단계→옵트인 진행, 단계 산출물 propose→confirm으로 그래프 반영. 후반 단계는 기존 설계 기계 오케스트레이션.

**Independent Test**: 빈 프로젝트에서 마법사를 열어 프로파일링 4문항 답 → 추천 단계(최소 0→1→2→3) 수행 → `.ddd` 산출물 + propose→confirm된 BC 후보가 트리에 나타남.

- [ ] T011 [P] [US1] 프로파일링→단계 추천 로직 — `ddd_wizard/step_prompts.py`에 `ddd-starter` 인테이크 4문항 + 단계 추천 트리(그린필드/브라운필드/단일기능/학습 × 경험 × 팀규모), 단계 메타(key/title/optional/recommended) (spec FR-002/003, research D1)
- [ ] T012 [US1] `POST /ddd-wizard/start` — `routes/ddd_wizard.py`: `WizardStartRequest` 수신, `scope=="epic"`이면 `epicId` 필수 검증, 세션 생성, `recommendedPlan` 반환 (contracts/wizard-contract §마법사)
- [ ] T013 [US1] `GET /ddd-wizard/{sessionId}/step/{stepKey}/stream` (SSE) — `EventSourceResponse`로 `reasoning`/`step_started`/`artifact`/`proposal`/`done`/`error` 송출, `child_story_generation.py` 스트림 패턴 재사용 (FR-022/028, research D3)
- [ ] T014 [US1] `POST /ddd-wizard/{sessionId}/answer` — 답변 또는 붙여넣은 문서 수신 → 세션 입력 갱신(질문/문서 두 입력 방식 모두) (FR-004)
- [ ] T015 [US1] `POST /ddd-wizard/{sessionId}/step/{stepKey}/confirm` — `acceptedChangeIds` 기반 그래프 반영; 빈 목록=무변경(FR-016); **단계별 위임**: Decompose→`bounded_context_crud` 호출, Code/설계→`incremental_design_runner`(`/api/ingest/user-stories/design`) 호출, 마무리→`design_reflect` (FR-025, research D13)
- [ ] T016 [US1] `GET /ddd-wizard/{sessionId}` — 세션 상태/완료 단계/산출물 조회(재개) (FR-020)
- [ ] T017 [US1] `generation/ddd_wizard_engine.py` 오케스트레이션 — 단계 루프(reference 질문→답 수집→초안 생성→게이트 체크→다음 단계), in-process는 `get_llm`, claude-ide는 `ddd-starter` 스킬 호출(`claude_code`/robo-spec MCP, spec 029) (research D2/D13)
- [ ] T018 [P] [US1] `DddWizardPanel.vue` — 프로파일링 4문항 UI → 단계 체크리스트(가감) → EventSource로 단계 진행·추론 스트림·산출물 미리보기·propose→confirm 버튼; 미설치 엔진 시 설치 안내+in-process 전환 제안 (FR-015)
- [ ] T019 [US1] 진입구 배선 — `RequirementsPanel.vue`에 "DDD 마법사" 진입(트리 비어있을 때 강조) + 에픽 추가 다이얼로그 진입; "문서 업로드" 모달↔마법사 상호 링크 (FR-024)
- [ ] T020 [US1] clear 충돌 가드 — 마법사는 전체 `/api/ingest/upload`(clear)를 트리거하지 않음을 보장; 사용자가 마법사 후 "문서 업로드"(전체) 실행 시 `RequirementsIngestionModal`에 "모델 재구축" 사전 경고 표시 (FR-027, research D14)
- [ ] T021 [P] [US1] (test) `api/features/requirements/ddd_wizard/tests/test_wizard_session.py` — 세션 상태 전이·재개 보존·빈 confirm 무변경 단위 테스트

**Checkpoint**: 마법사 단독으로 맨땅→BC 후보 도출 가능(MVP).

---

## Phase 4: User Story 2 — 피보탈 이벤트 기반 EventStorming & 서브도메인 (P1)

**Goal**: 빅픽처 이벤트 수집 → 피보탈/핫스팟 표시 → 피보탈 경계로 서브도메인→BC 후보 도출. 기존 커맨드 중심 도출과 보완·dedup.

**Independent Test**: 이벤트 10+ 입력 시 피보탈·핫스팟 구분 표시, 피보탈 경계 서브도메인 맵 생성.

- [ ] T022 [P] [US2] `Event.pivotal`/`hotspot` 속성 토글 — `routes/pivotal_events.py`: `POST /pivotal-events/toggle` (`PivotalToggleRequest`→그래프 SET, 신규 라벨 없음) (data-model §1.1, research D7)
- [ ] T023 [US2] 빅픽처 이벤트 도출 — `ddd_wizard_engine.py` Discover 단계: 시간순 이벤트 수집(질문/문서) + 트리거(사용자/시간/외부) 분류 + 피보탈/핫스팟 후보 LLM 표시 (FR-007)
- [ ] T024 [US2] 기존 이벤트 dedup/병합 — Discover 산출 이벤트와 기존 `events_from_user_stories`/`commands` EMITS 이벤트 비교 → 중복 병합 후보 제시(대체 아님) (FR-009/026, research D14)
- [ ] T025 [US2] `POST /ddd-wizard/{sessionId}/subdomains/propose` — `routes/pivotal_events.py`: 피보탈 경계로 서브도메인(BC 후보) 산출(`SubdomainProposal[]`), 확정은 기존 `POST /bounded-context` (FR-008, research D8)
- [ ] T026 [P] [US2] `PivotalEventMarker.vue` + Discover UI — 이벤트 타임라인에 피보탈⭐·핫스팟🔥 배지·토글; `DddWizardPanel`의 Discover/Decompose 단계에 장착
- [ ] T027 [US2] 중복 이벤트 병합 UI — Discover 단계에서 병합 후보를 사용자에게 표시·선택

**Checkpoint**: 피보탈 기반 서브도메인 도출이 마법사 안에서 동작.

---

## Phase 5: User Story 3 — Bounded Context Canvas & BC 상세 화면 (P1)

**Goal**: BC 생성/클릭 시 전용 상세 화면(탭) + Canvas 탭. 자동생성=ddd_spec 재사용, 편집=속성 PATCH(관계 보존), 그래프 동기화.

**Independent Test**: 임의 BC 클릭 → 상세 화면 + Canvas 탭에서 책임·유비쿼터스 언어·인/아웃바운드 표시·편집·저장 후 유지.

- [ ] T028 [P] [US3] `GET /api/contexts/{bcId}/canvas` — `contexts/router.py`: `BoundedContextProjection`(purpose/strategic/inbound·outbound flows/key_terms) 투영을 `BcCanvasDTO`로 반환 (contracts/canvas-contract, research D4)
- [ ] T029 [US3] `PATCH /api/contexts/{bcId}/canvas` — 속성만 SET(purpose/domainRoles/ubiquitousLanguage/businessDecisions/assumptions), 관계 보존, `If-Match` 낙관적 버전(412) (research D9, data-model §1.2)
- [ ] T030 [US3] 캔버스 자동생성 위임 — `CanvasGenerateRequest`→기존 `POST /api/ddd-spec/generate-bounded-context`·`bc_canvas.py` 호출, 초안 propose→confirm 후 PATCH 반영, 엔진 토글 적용·SSE (FR-012/014)
- [ ] T031 [US3] `EpicDetail.vue` 탭화 — `UserStoryDetail.vue` 탭 패턴 적용: [Overview | Canvas | Clarify | AI편집 | History], BC 전용 상세 셸 (FR-011)
- [ ] T032 [P] [US3] `BcCanvasTab.vue` — 책임/전략분류/유비쿼터스 언어·충돌/인·아웃바운드(투영)/비즈니스 결정/가정 표시·편집, 자동생성 버튼(SSE 진행), 저장 PATCH
- [ ] T033 [US3] 설계 캔버스 BC 클릭 진입 — `frontend/src/features/canvas/ui/CanvasWorkspace.vue`에서 현재 무동작인 BC 노드 클릭 → `robo:switch-tab`(Requirements)+선택으로 `EpicDetail` Canvas 탭 오픈 (FR-011)
- [ ] T034 [P] [US3] (test) `api/features/contexts/tests/test_bc_canvas.py` — canvas GET 투영·PATCH 속성-only·관계 보존·If-Match 충돌 테스트

**Checkpoint**: BC 상세+캔버스가 트리·설계 캔버스 양쪽에서 열림.

---

## Phase 6: User Story 4 — 비즈니스 컨텍스트 & 핵심 액터 정의 (P2)

**Goal**: Understand 단계 3개 질문 그룹 → 핵심 액터 식별 → 산출물·그래프 반영.

**Independent Test**: Understand 단계만 수행 → 비즈니스 컨텍스트 문서 + 핵심 액터 목록 생성.

- [ ] T035 [US4] Understand 단계 프롬프트 — `step_prompts.py`에 비즈니스 본질·사용자/이해관계자·목표 3그룹 질문 + 문서 추출 모드(붙여넣기→액터/목표/차별점 추출) (FR-006, research D1)
- [ ] T036 [US4] 핵심 액터 식별·매핑 — `ddd_wizard_engine.py` Understand 단계: 응답/문서에서 액터 추출, 기존 그래프 표현(role/페르소나)에 매핑, 불가 항목은 `.ddd/01-business-context.md`로만(라벨 0) (data-model §1.4)
- [ ] T037 [P] [US4] `DddWizardPanel.vue` Understand 단계 UI — 3그룹 질문 + 문서 붙여넣기 입력, 식별 액터 목록 표시·확인

**Checkpoint**: Understand 단계가 독립 가치(이해관계자 정렬 문서) 제공.

---

## Phase 7: User Story 5 — Aggregate Design Canvas 탭 (P2)

**Goal**: Aggregate 상세에 Canvas 탭(상태전이/커맨드/이벤트/불변조건). 자동생성=aggregate_spec 재사용, spec 027 불변조건 동기화.

**Independent Test**: 임의 Aggregate 상세 → Canvas 탭에서 상태전이·커맨드·이벤트·불변조건 표시·편집·저장 후 유지.

- [ ] T038 [P] [US5] `GET /api/aggregates/{aggregateId}/canvas` — `AggregateProjection`(commands/events/policies/invariants) + 상태전이/보정정책/throughput 속성을 `AggregateCanvasDTO`로 반환 (contracts/canvas-contract, research D5)
- [ ] T039 [US5] `PATCH /api/aggregates/{aggregateId}/canvas` — 속성만 SET(description/stateTransitions(JSON·Mermaid)/correctivePolicies/throughput), `If-Match`; 불변조건은 spec 027 표현 재사용(중복 모델 금지) (research D6/D9, data-model §1.3)
- [ ] T040 [US5] 캔버스 자동생성 위임 — `CanvasGenerateRequest`→기존 `POST /api/ddd-spec/generate-aggregate`·`aggregate_spec.py`, propose→confirm 후 PATCH (FR-013/014)
- [ ] T041 [P] [US5] `AggregateCanvasTab.vue` — 상태전이 Mermaid 렌더, 커맨드·이벤트·불변조건·보정정책·throughput 표시·편집; `AggregateViewerInspector.vue`(spec 028)에 탭 슬롯으로 장착 (FR-013)
- [ ] T042 [P] [US5] (test) `api/features/.../tests/test_aggregate_canvas.py` — canvas GET 투영·PATCH 속성-only·spec 027 불변조건 충돌 없음 테스트

**Checkpoint**: Aggregate 캔버스가 드릴다운 위에 동작.

---

## Phase 8: User Story 6 — Core/Supporting/Generic 전략 분류 (P2)

**Goal**: Strategize 분류 질문으로 3분류, BC 속성 저장, 컨텍스트 맵/캔버스 배지.

**Independent Test**: 서브도메인 목록 분류 질문 답 → core/supporting/generic 저장 + 컨텍스트 맵 배지 구분.

- [ ] T043 [US6] 분류 enum 3분류 확장 — `api/features/contexts/router.py`의 `Classification = Literal["core","supporting"]`→`[...,"generic"]`, GET/PATCH 가드(422) 갱신 (FR-010, research D10)
- [ ] T044 [P] [US6] `POST /api/requirements/strategize/questions` — 서브도메인/BC 목록에 분류 질문(`ddd-starter` Step4 휴리스틱: "외부 아웃소싱 시 고객이 알아챌까?") 산출(`StrategizeQuestionDTO[]`) (contracts/classification-export-contract)
- [ ] T045 [US6] Strategize 단계 통합 — `ddd_wizard_engine.py`에서 분류 제안→확인→`PATCH /contexts/{id}/classification` 위임
- [ ] T046 [P] [US6] 분류 배지 UI — 컨텍스트 맵 + `BcCanvasTab.vue`에 core🔴/supporting🟡/generic⚪ 배지·색상 (FR-023)

**Checkpoint**: 핵심 도메인 식별이 시각화됨.

---

## Phase 9: User Story 7 — 그래프 → .ddd 내보내기(보조) (P3)

**Goal**: 현행 그래프를 `.ddd/` 마크다운으로 내보내기; 선택적 가져오기(diff→propose→confirm).

**Independent Test**: 그래프 BC/Aggregate 존재 시 내보내기 실행 → `.ddd/` 단계별 마크다운 생성.

- [ ] T047 [US7] `ddd_export_engine.py` — `ddd_spec` 렌더러(bc_canvas/aggregate_spec/context_map/domain_terms) 출력 경로를 `.ddd/`로 매개변수화하여 `00-plan`~`08-aggregates/` 생성; 기존 `specs/bounded-contexts/` 경로 무회귀 (research D11/R2)
- [ ] T048 [US7] `POST /api/requirements/ddd-export` — `DddExportRequest`(outputDir/steps?)→`DddExportResponse`(writtenFiles/skipped) (contracts/classification-export-contract)
- [ ] T049 [P] [US7] (선택) 가져오기 — `POST /ddd-import/preview`(diff `GraphChangePreview[]`) + `POST /ddd-import/confirm`(`model_modifier` apply 재사용, 충돌 안내) (FR-017/018)
- [ ] T050 [P] [US7] 내보내기 UI — `DddWizardPanel.vue`/`RequirementsPanel.vue`에 "그래프 → .ddd 내보내기" 버튼·결과 표시

**Checkpoint**: `.ddd` 보조 산출물 왕복 가능.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [ ] T051 [P] DDD 검증 연계 — 마법사 단계 게이트에서 spec 034 `ddd_validation`(wrong_bc/oversized_feature/spec_conflict) 비차단 호출 (research D12)
- [ ] T052 [P] 언어 정책 검증 — 모든 생성 산출물(마법사/캔버스/내보내기)이 기어 아이콘 BCP-47 설정을 따르는지 확인 (FR-021, spec 031, [[project_generation_language_policy]])
- [ ] T053 [P] 관찰성 — 신규 엔진/라우트에 `SmartLogger` 단계 로그 + correlation ID 일관 적용 (Constitution VII)
- [ ] T054 [P] Swagger/README — 신규 엔드포인트가 `/docs`에 정확한 모델로 노출되는지, README API 요약 갱신 (Dev Workflow)
- [ ] T055 [P] 스키마 diff 회귀 — 신규 Neo4j 노드 라벨/관계 0건 확인(속성 추가만) (SC-006)
- [ ] T056 quickstart 전구간 수동 검증 — Q1–Q15 (특히 Q11 무변경 보장, Q13 병행, Q14 설계 기계 재사용, Q15 clear 경고)

---

## Dependencies & Execution Order

- **Phase 1 Setup** → **Phase 2 Foundational** → User Story 페이즈들 → **Phase 10 Polish**.
- **Foundational(T005–T010)은 모든 US의 블로킹 전제** — 계약·세션·라우터 배선·엔진 헬퍼·store 골격.
- **US 간 의존**:
  - US1(마법사 셸)은 US2/US4/US6의 단계 UI 호스트 → US1의 T013–T018이 먼저면 US2/US4/US6 단계 통합이 매끄럽다(필수는 아님: 각 US 백엔드는 독립 테스트 가능).
  - US2 T025(서브도메인→BC)·US3은 `bounded_context_crud` 공유(읽기/쓰기 독립).
  - US3/US5 캔버스는 `ddd_spec` 재사용으로 상호 독립(병렬 가능).
  - US6 T043(enum 확장)은 US3 분류 배지(T046)보다 먼저.
  - US7은 다른 US 산출물(그래프 상태) 위에서 동작 → 마지막.
- **권장 순서**: Setup → Foundational → US1 → US3 → US2 → US6 → US5 → US4 → US7 → Polish.

## Parallel Execution Examples

- **Setup 병렬**: T002, T003, T004 동시.
- **Foundational 병렬**: T005, T006 동시(같은 파일이면 순차) → T007 → T008 → T009, T010 동시.
- **US1 내부**: T011, T018, T021 [P] 병렬; 라우트 T012→T013→T014→T015→T016 순차(같은 파일).
- **US3 vs US5**: 서로 다른 파일/렌더러 → 두 스토리 백엔드·프런트 병렬 진행 가능.
- **Polish**: T051–T055 모두 [P].

## Implementation Strategy

- **MVP = US1**(마법사로 맨땅→BC 후보) + US3(BC 캔버스). 사용자가 명시 요청한 핵심.
- **증분 인도**: US1/US3(P1) → US2(P1 피보탈) → US6/US5/US4(P2) → US7(P3).
- **핵심 원칙**: 신규 생성기 0 — 마법사는 기존 ingestion 설계 기계(`incremental_design_runner`)·`bounded_context_crud`·`ddd_spec`·`design_reflect`를 오케스트레이션. clear 경로(`/api/ingest/upload`) 비트리거.
