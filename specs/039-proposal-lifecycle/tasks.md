# Tasks: Proposal Lifecycle Management (039)

**Input**: Design documents from `/specs/039-proposal-lifecycle/`

**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/api.md ✅, quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US6)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 디렉토리 구조 생성, .sandbox 격리, Neo4j 스키마 파일 초기화

- [X] T001 Create directory skeleton: `api/features/proposal_lifecycle/`, `api/features/proposal_lifecycle/routes/`, `api/features/proposal_lifecycle/services/`, `skills/robo-proposals/`, `frontend/src/features/proposals/`, `frontend/src/features/proposals/ui/`
- [X] T002 Add `.sandbox/` line to `.gitignore` (Git Worktree 루트 격리)
- [X] T003 [P] Create `docs/cypher/schema/03_node_types.cypher` — Proposal 노드 UNIQUE 제약 및 status/author 인덱스 추가 (data-model.md 참조)
- [X] T004 [P] Create `docs/cypher/schema/04_relationships.cypher` — `(p:Proposal)-[:EFFECT]->(n)` 관계 주석 추가 (data-model.md 참조)
- [X] T005 Create `api/features/proposal_lifecycle/__init__.py` and `api/features/proposal_lifecycle/routes/__init__.py` and `api/features/proposal_lifecycle/services/__init__.py` (빈 파이썬 패키지 초기화)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pydantic 계약, ID 생성기, 038 노드 초기화, 플랫폼 헬퍼 추출, 라우터 등록 — **이 phase가 완료되어야 모든 US 작업 가능**

⚠️ **CRITICAL**: 아래 태스크 완료 전에는 어떤 User Story 작업도 시작 불가

- [X] T006 Create `api/features/proposal_lifecycle/proposal_contracts.py` — `ProposalStatus`, `StrategicDiffOp`, `StrategicDiffEntry`, `StrategicDiff`, `ImpactMapEntry`, `ProposalResponse`, `CreateProposalRequest`, `SubmitProposalRequest`, `AcceptProposalRequest`, `DestroyProposalRequest`, `ClarificationAnswer`, `AnswerClarificationRequest`, `TestResultItem`, `TestRunResult` Pydantic 모델 (data-model.md Python 모델 절 구현)
- [X] T007 [P] Create `api/features/proposal_lifecycle/services/proposal_id_generator.py` — Neo4j에서 `MAX(p.id)` 조회 후 `PRO-NNN` 형식 MAX+1 반환 (038 CHG-NNN 패턴 동일)
- [X] T008 [P] Create `api/features/proposal_lifecycle/services/migration.py` — `RequirementChange`, `ChangeSet` 노드 전체 삭제 Cypher 실행 후 삭제 건수 출력 (quickstart Step 1)
- [X] T009 Create `api/platform/neo4j_helpers.py` — `load_domain_nodes(session)` 함수 추출 (038 `effect_analyzer.py`에서 승격, 양쪽에서 공용)
- [X] T010 Create `api/platform/skill_runner.py` — PTY 기반 스킬 실행 로직 (038 `skill_runner.py` 복사 후 `proposal_id` 컨텍스트 주입 지원 추가)
- [X] T011 Create `api/features/proposal_lifecycle/router.py` — 모든 routes 하위 라우터를 `/api/proposals` prefix로 집계하는 FastAPI 라우터
- [X] T012 Register proposal_lifecycle router in `api/main.py` — `from api.features.proposal_lifecycle.router import router as proposal_router` + `app.include_router(proposal_router)` 추가

**Checkpoint**: Foundation 완료 — Swagger `/docs`에서 `proposals` 태그 확인 가능

---

## Phase 3: User Story 1 — Proposal 생성: 자연어 입력 → 인텐트 분해 (Priority: P1) 🎯 MVP

**Goal**: 자연어 한 줄 입력 → AI 인텐트 분해(Strategic+Tactical Diff) → DRAFT Proposal 생성, Impact Map SSE 스트리밍

**Independent Test**: `curl -X POST /api/proposals/` 로 Proposal 생성 후 `curl -N /api/proposals/stream/PRO-001/intent` 로 `strategic_diff`, `tactical_diff`, `impact_map`, `done` 이벤트 수신 확인

### Implementation for User Story 1

- [X] T013 [P] [US1] Create `skills/robo-proposals/robo-proposal-intent/SKILL.md` — 입력(proposalId, originalPrompt, domainNodes JSON), 출력(`clarify` action 또는 `done` action with strategicDiff+tacticalDiff), 최대 5개 명확화 질문 순차 제시 동작 정의
- [X] T014 [P] [US1] Create `skills/robo-proposals/robo-proposal-context/SKILL.md` — 입력(proposalId, strategicDiff, tacticalDiff), 그래프 탐색으로 영향 노드 탐색, 출력(ImpactMap JSON with conflictLevel), SSE 점진적 스트리밍 동작 정의
- [X] T015 [US1] Implement `api/features/proposal_lifecycle/services/intent_runner.py` — `api/platform/skill_runner.py` 호출로 `robo-proposal-intent` 스킬 실행, 명확화/완료 응답 파싱, `clarificationLog` 누적, SKILL.md 출력 JSON → StrategicDiff + TacticalDiff 변환
- [X] T016 [US1] Implement `api/features/proposal_lifecycle/services/impact_builder.py` — `api/platform/skill_runner.py` 호출로 `robo-proposal-context` 스킬 실행, `api/platform/neo4j_helpers.py`로 도메인 노드 로드, ImpactMapEntry 목록 반환
- [X] T017 [US1] Implement `api/features/proposal_lifecycle/routes/proposals_crud.py` — `POST /api/proposals/` 엔드포인트: Proposal 노드 Neo4j 생성(`PRO-NNN`, DRAFT 상태), 백그라운드로 intent_runner 태스크 시작, `ProposalResponse` 반환
- [X] T018 [US1] Implement `api/features/proposal_lifecycle/routes/proposals_intent.py` — `GET /api/proposals/stream/{id}/intent` SSE 엔드포인트: `phase`, `clarification_needed`, `strategic_diff`, `tactical_diff`, `impact_map`, `done`, `error` 이벤트 스트리밍 (contracts/api.md SSE Event Types 참조)
- [X] T019 [P] [US1] Create `frontend/src/features/proposals/proposals.store.js` — Pinia 스토어: `proposals[]`, `currentProposal`, `intentStream` 상태, `createProposal()`, `subscribeToIntent()`, `answerClarification()` 액션
- [X] T020 [P] [US1] Create `frontend/src/features/proposals/ui/ProposalCreate.vue` — 자연어 입력 다이얼로그: textarea + 제출 버튼, 명확화 질문 단계 UI(선택형 옵션), SSE 인텐트 분해 진행 스피너
- [X] T021 [US1] Create `frontend/src/features/proposals/ui/IntentDecompositionView.vue` — Strategic Diff 섹션(Epic/Feature/UserStory 목록 Before/After), Tactical Diff 섹션(Aggregate/Command/Event/VO SemanticDiff), Impact Map conflictLevel 배지 표시

**Checkpoint**: US1 완료 — 자연어 입력 → SSE 인텐트 분해 → DRAFT Proposal 생성 흐름 독립 테스트 가능

---

## Phase 4: User Story 2 — Proposal 검토: Strategic·Tactical Diff 확인 및 수정 (Priority: P1)

**Goal**: Proposal 상세 화면에서 AI 생성 Diff 검토·수정, 연관 항목 충돌 경고 재계산, SUBMIT

**Independent Test**: Proposal 상세 화면에서 Strategic Diff 항목을 수정하면 연관 Tactical Diff 제거 제안이 표시되고, SUBMIT 후 상태가 SUBMITTED로 전환되면 완료

### Implementation for User Story 2

- [X] T022 [US2] Extend `api/features/proposal_lifecycle/routes/proposals_crud.py` — `GET /api/proposals/{id}` (상세 조회), `PUT /api/proposals/{id}/diff` (Strategic/Tactical Diff 수정 + 연관 항목 충돌 재계산), `POST /api/proposals/{id}/clarify` (명확화 답변 → intent_runner 재호출), `POST /api/proposals/{id}/submit` (DRAFT→SUBMITTED, strategicDiff null 시 400, 동일 노드 IMPLEMENTING 중인 Proposal 존재 시 409) 구현
- [X] T023 [P] [US2] Create `frontend/src/features/proposals/ui/ProposalDetail.vue` — Strategic Diff 섹션 + Tactical Diff 섹션 탭 레이아웃, 상태 뱃지(DRAFT/SUBMITTED/…), "Proposal 제출(SUBMIT)" 버튼, Impact Map 링크
- [X] T024 [P] [US2] Create `frontend/src/features/proposals/ui/ImpactMapView.vue` — 영향 노드 목록 테이블: nodeLabel, nodeTitle, conflictLevel(HIGH=빨강/MEDIUM=노랑/LOW=초록), reason 컬럼
- [X] T025 [US2] Update `frontend/src/features/proposals/proposals.store.js` — `fetchProposal(id)`, `updateDiff(id, {strategicDiff, tacticalDiff})`, `submitProposal(id)` 액션 추가, SUBMIT 후 상태 로컬 업데이트
- [X] T025a [US2] (FR-002a) 인텐트 분해 결과 **피드백 → 재생성**: `proposal_contracts.py`에 `IntentFeedbackRequest`·`ProposalResponse.intentFeedbackLog` 추가; `proposals_crud.py`에 `POST /api/proposals/{id}/intent/feedback`(DRAFT 한정, 피드백 누적, 비-DRAFT 409); `intent_runner.py`의 `_build_intent_prompt`에 `이전 분석 결과`+`사용자 피드백(재생성)` 섹션 추가 + `_load_intent_inputs`로 `intentFeedbackLog`·이전 diff 로드; `robo-proposal-intent/SKILL.md`에 피드백 재생성 규칙(Rule 7); `proposals.store.js`에 `submitIntentFeedback(id, feedback)`; `ProposalDetail.vue` Diff 탭에 "피드백 후 재생성" 박스 + 실시간 narration(인텐트 SSE 재구독); 그대로 제출도 가능

**Checkpoint**: US2 완료 — Proposal 상세 검토·수정·제출 흐름 독립 테스트 가능

---

## Phase 5: User Story 3 — 샌드박스 구현: Git Worktree 격리 환경에서 자동 코드 생성 (Priority: P2)

**Goal**: SUBMITTED Proposal → Git Worktree 생성 → Claude Code 구현 태스크 SSE 실시간 스트리밍 → IMPLEMENTING → TESTING 전환

**Independent Test**: SUBMITTED Proposal에서 `curl -N -X POST /api/proposals/PRO-001/implement` 로 `sandbox_creating → sandbox_ready → task_start → task_done → all_done` SSE 이벤트 수신 확인, `git worktree list`에서 `proposal/PRO-001` 브랜치 확인

### Implementation for User Story 3

- [X] T026 [US3] Implement `api/features/proposal_lifecycle/services/sandbox_manager.py` — `create_worktree(proposal_id)`: `git worktree add .sandbox/proposal/{id} -b proposal/{id}` subprocess 실행, `remove_worktree(proposal_id)`: worktree remove + branch delete, `merge_to_main(proposal_id)`: git merge, `reset_merge(proposal_id)`: git reset --hard, `cleanup_worktree(proposal_id)`, 디스크 공간 부족 시 오류 반환
- [X] T027 [P] [US3] Create `skills/robo-proposals/robo-proposal-implement/SKILL.md` — `extends: robo-change-tasks`, 입력(proposalId, strategicDiff, tacticalDiff, worktreePath), 샌드박스 Worktree에서 Claude Code 태스크 실행, 태스크별 `task_start/progress/done/failed` SSE 이벤트 출력 정의
- [X] T028 [US3] Implement `api/features/proposal_lifecycle/services/implement_runner.py` — `api/platform/skill_runner.py`로 `robo-proposal-implement` 스킬 실행, Proposal의 strategicDiff + tacticalDiff를 컨텍스트로 주입, worktreePath 환경변수 설정, SSE 이벤트 파싱 및 중계
- [X] T029 [US3] Implement `api/features/proposal_lifecycle/routes/proposals_sandbox.py` — `POST /api/proposals/{id}/implement` SSE 엔드포인트: sandbox_manager.create_worktree → implement_runner 실행 → IMPLEMENTING 상태 업데이트 → 완료 시 TESTING 전환 → SSE 스트리밍 (contracts/api.md 참조)
- [X] T030 [US3] Create `frontend/src/features/proposals/ui/SandboxProgressView.vue` — Worktree 상태 헤더(브랜치명, 경로), 태스크 목록(대기/진행중/완료/실패 아이콘), Claude Code 출력 로그 패널, 실패 태스크 "재시도" 버튼, SSE EventSource 수신
- [X] T031 [US3] Update `frontend/src/features/proposals/proposals.store.js` — `implementProposal(id)`: SSE 구독 + sandboxStatus/taskList 업데이트 액션 추가

**Checkpoint**: US3 완료 — 샌드박스 격리 구현 흐름 독립 테스트 가능

---

## Phase 6: User Story 4 — 자동 검증 및 PO 승인 (Accept/Destroy) (Priority: P2)

**Goal**: GWT 기반 자동 테스트 결과 표시 → PO Accept(Dual Merge) 또는 Destroy → ACCEPTED/DESTROYED 상태 전환

**Independent Test**: 구현 완료된 Proposal 상세 화면에서 인수 조건별 PASS/FAIL 표시 확인, Accept 후 메인 브랜치에 코드 반영 및 그래프 DB 노드 After 값 업데이트 확인

### Implementation for User Story 4

- [X] T032 [P] [US4] Create `skills/robo-proposals/robo-proposal-test/SKILL.md` — 입력(proposalId, strategicDiff, tacticalDiff, worktreePath), 그래프 DB UserStory GWT 인수 조건 파싱, LLM-as-judge 방식 PASS/FAIL 판정, `TestRunResult` JSON 출력 정의
- [X] T033 [US4] Implement `api/features/proposal_lifecycle/services/test_runner.py` — `api/platform/skill_runner.py`로 `robo-proposal-test` 스킬 실행, TestRunResult 파싱, Neo4j에 결과 저장, TESTING → PENDING_ACCEPTANCE 상태 전환
- [X] T034 [US4] Implement `api/features/proposal_lifecycle/routes/proposals_testing.py` — `GET /api/proposals/{id}/test-results` 엔드포인트: Neo4j에서 TestRunResult 조회 반환
- [X] T035 [US4] Implement `api/features/proposal_lifecycle/services/dual_merge.py` — `execute_dual_merge(proposal_id, actor)`: (1) sandbox_manager.merge_to_main → (2) Neo4j TX(apply_strategic_diff + apply_tactical_diff + status ACCEPTED) → 실패 시 sandbox_manager.reset_merge 보상 트랜잭션 + MERGE_FAILED 상태 전환 (plan.md Dual Merge 구현 순서 참조)
- [X] T036 [US4] Implement `api/features/proposal_lifecycle/routes/proposals_acceptance.py` — `POST /api/proposals/{id}/accept` (자기 승인 방지 + forceAcceptWithFailures 검증 + dual_merge 실행), `POST /api/proposals/{id}/destroy` (DESTROYED 전환 + worktree cleanup), `POST /api/proposals/{id}/retry-merge` (MERGE_FAILED → dual_merge 재실행 SSE) 구현
- [X] T037 [P] [US4] Create `frontend/src/features/proposals/ui/TestResultsView.vue` — 시나리오별 PASS/FAIL 테이블(storyTitle, scenario, result, reason), 전체 통과율 요약, 실패 항목 수 강조
- [X] T038 [US4] Create `frontend/src/features/proposals/ui/DualMergeView.vue` — "Accept" / "Destroy" 확인 다이얼로그, 실패 항목 리스크 경고 + 재확인 체크박스(`forceAcceptWithFailures`), MERGE_FAILED 시 "재시도" 버튼 표시
- [X] T039 [US4] Update `frontend/src/features/proposals/proposals.store.js` — `fetchTestResults(id)`, `acceptProposal(id, payload)`, `destroyProposal(id, payload)`, `retryMerge(id)` 액션 추가

**Checkpoint**: US4 완료 — 자동 테스트 결과 확인 + Accept/Destroy 흐름 독립 테스트 가능

---

## Phase 7: User Story 5 — Proposal 목록 조회 및 관리 (Priority: P2)

**Goal**: Proposals 탭에서 상태별 필터링 목록 조회, IMPLEMENTING/TESTING 상태 실시간 진행률 표시

**Independent Test**: Proposals 탭에서 상태 필터(DRAFT/SUBMITTED/IMPLEMENTING/TESTING/ACCEPTED/DESTROYED) 선택 시 해당 상태 목록만 표시되면 완료

### Implementation for User Story 5

- [X] T040 [US5] Extend `api/features/proposal_lifecycle/routes/proposals_crud.py` — `GET /api/proposals/` 엔드포인트: `status`(복수 허용), `author`, `limit`(default 50), `offset` 쿼리 파라미터 지원, Neo4j Cypher 필터 쿼리, `list[ProposalResponse]` 반환 (contracts/api.md 참조)
- [X] T041 [US5] Create `frontend/src/features/proposals/ui/ProposalsPanel.vue` — Proposal 목록(PRO-NNN ID, 제목, 상태 뱃지, 작성자, 생성일, 영향 노드 수), 상태 필터 탭바, IMPLEMENTING/TESTING 상태에 실시간 진행률 % 표시, DESTROYED 항목 클릭 시 Diff 이력 조회 전용 모드
- [X] T042 [US5] Wire `ProposalsPanel` into Requirements tab navigation — Requirements 탭 내 "Proposals" 메뉴 항목 추가 및 ProposalsPanel 라우팅 연결
- [X] T043 [US5] Update `frontend/src/features/proposals/proposals.store.js` — `fetchProposals({status[], author, limit, offset})` 액션, IMPLEMENTING/TESTING 상태 Proposal에 주기적 폴링으로 sandboxStatus 갱신

**Checkpoint**: US5 완료 — Proposals 탭 목록 조회·필터 흐름 독립 테스트 가능

---

## Phase 8: User Story 6 — Dual Merge 상세: 코드 + 그래프 DB 단일 트랜잭션 동기화 (Priority: P3)

**Goal**: Dual Merge 보상 트랜잭션 완전 구현, MERGE_FAILED retry, 사양 문서 자동 갱신, 동시 충돌 감지

**Independent Test**: Accept 후 `git log main`에서 샌드박스 커밋 확인 + Neo4j에서 해당 노드 After 값 100% 일치 확인

### Implementation for User Story 6

- [X] T044 [US6] Enhance `api/features/proposal_lifecycle/services/dual_merge.py` — `apply_strategic_diff(tx, proposal_id)`: StrategicDiff의 CREATE/MODIFY/DELETE 연산을 Neo4j 트랜잭션에 적용 (UserStory/Feature/Epic 노드 CREATE/MERGE/SET), `apply_tactical_diff(tx, proposal_id)`: TacticalDiff 항목별 EFFECT 관계에 저장된 SemanticDiff `ops` 순서대로 Aggregate/Command/Event 노드 속성 업데이트
- [X] T045 [US6] Enhance retry-merge in `api/features/proposal_lifecycle/routes/proposals_acceptance.py` — MERGE_FAILED → git 충돌 상태 확인 후 manual resolution 유도 또는 재머지 시도, SSE 스트리밍으로 진행 상태 전달
- [X] T046 [P] [US6] Add MERGE_FAILED status display to `frontend/src/features/proposals/ui/DualMergeView.vue` — MERGE_FAILED 상태 시 실패 단계(git_merge / graph_update) 표시, "재시도" 버튼 → retry-merge SSE 구독
- [X] T047 [US6] Add concurrent conflict detection in `api/features/proposal_lifecycle/routes/proposals_crud.py` — `POST /submit` 시 동일 그래프 노드를 수정하는 IMPLEMENTING 중인 Proposal 존재 시 409 + conflicting Proposal ID 목록 반환
- [X] T048 [US6] Implement spec docs auto-update in `api/features/proposal_lifecycle/services/dual_merge.py` — Accept 완료 후 `specs/` 디렉토리 내 도메인 용어집·컨텍스트 맵 마크다운 파일을 Proposal Diff 기반으로 자동 갱신 (plan.md Assumptions 참조)

**Checkpoint**: US6 완료 — Dual Merge 원자성 및 보상 트랜잭션 검증 가능

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: 시작 훅, 정책 검증, 세션 타임아웃, 로깅, 검증

- [X] T049 [P] Add startup hook in `api/main.py` — `@app.on_event("startup")` 핸들러에서 `git worktree prune` subprocess 실행으로 고아 Worktree 자동 정리
- [X] T050 [P] Add self-approval guard in `api/features/proposal_lifecycle/routes/proposals_acceptance.py` — Accept 요청자와 Proposal author가 동일하면 400 오류 반환 (038 정책 계승)
- [X] T051 [P] Add clarification session timeout in `api/features/proposal_lifecycle/services/intent_runner.py` — 5분 이상 답변 없으면 세션 만료, 현재 상태로 DRAFT 저장 후 SSE `done` 이벤트 전송
- [X] T052 [P] Add disk space check in `api/features/proposal_lifecycle/services/sandbox_manager.py` — `shutil.disk_usage()` 로 여유 공간 100MB 미만 시 WORKTREE_FAILED 오류 + Proposal DRAFT 복귀
- [X] T053 [P] Add orphan node handling in `api/features/proposal_lifecycle/services/impact_builder.py` — ImpactMap 생성 시 그래프 연결 없는 요구사항을 `conflictLevel: "NONE"`, `reason: "관련 노드 없음"` 으로 반환
- [X] T054 [P] Add ACCEPTED Proposal immutability lock in `api/features/proposal_lifecycle/routes/proposals_crud.py` — ACCEPTED 상태 Proposal에 대한 PUT /diff 요청 시 423 Locked 반환
- [X] T055 [P] Apply SmartLogger phase logging across services — `intent_start`, `intent_done`, `sandbox_created`, `implement_start`, `implement_done`, `merge_start`, `merge_done` 단계 로그 추가 (`api/features/proposal_lifecycle/services/*.py` 전체)
- [X] T056 Run quickstart.md validation — migration.py 실행 + schema cypher 적용 + curl로 Proposal 전체 생애주기(생성→인텐트→제출→구현→테스트→Accept) curl 스크립트 실행 및 각 단계 응답 검증

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 의존 없음 — 즉시 시작 가능
- **Foundational (Phase 2)**: Phase 1 완료 필요 — 모든 US 작업 차단
- **US1 (Phase 3)**: Phase 2 완료 필요
- **US2 (Phase 4)**: Phase 3 완료 필요 (GET /proposals/{id} 가 US1에서 생성된 Proposal 참조)
- **US3 (Phase 5)**: Phase 4 완료 필요 (SUBMITTED 상태 전환이 US2에서 구현됨)
- **US4 (Phase 6)**: Phase 5 완료 필요 (IMPLEMENTING→TESTING 전환이 US3에서 구현됨)
- **US5 (Phase 7)**: Phase 2 완료 후 병렬 진행 가능 (목록 조회는 독립적)
- **US6 (Phase 8)**: Phase 6 완료 필요 (Dual Merge 기반 기능 확장)
- **Polish (Phase 9)**: 원하는 US 완료 후 진행

### User Story Dependencies

- **US1 (P1)**: Foundation 완료 후 시작 — 다른 US에 의존 없음
- **US2 (P1)**: US1 완료 후 시작 — GET /proposals/{id} 상세 화면 필요
- **US3 (P2)**: US2 완료 후 시작 — SUBMITTED 상태 필요
- **US4 (P2)**: US3 완료 후 시작 — IMPLEMENTING→TESTING 전환 필요
- **US5 (P2)**: Foundation 완료 후 US1과 병렬 시작 가능
- **US6 (P3)**: US4 완료 후 시작 — Dual Merge 기반 기능 확장

### Parallel Opportunities

- Phase 1: T003, T004, T005 병렬 실행 가능
- Phase 2: T007, T008, T009, T010 병렬 실행 가능
- Phase 3: T013, T014 (SKILL.md 2개) 병렬, T019, T020 (Store + UI) 병렬
- Phase 4: T023, T024 (ProposalDetail + ImpactMapView) 병렬
- Phase 5: T026, T027 (sandbox_manager + SKILL.md) 병렬
- Phase 6: T032, T037 (SKILL.md + TestResultsView) 병렬
- Phase 9: T049–T055 모두 병렬 실행 가능

---

## Parallel Example: User Story 1

```bash
# 백엔드 스킬 파일 병렬 작성:
Task T013: "Create skills/robo-proposals/robo-proposal-intent/SKILL.md"
Task T014: "Create skills/robo-proposals/robo-proposal-context/SKILL.md"

# 프런트엔드 병렬 작성 (백엔드 API 완료 후):
Task T019: "Create frontend/src/features/proposals/proposals.store.js"
Task T020: "Create frontend/src/features/proposals/ui/ProposalCreate.vue"
```

---

## Implementation Strategy

### MVP First (User Story 1 + 2 Only)

1. Phase 1: Setup 완료
2. Phase 2: Foundation 완료 — Swagger에서 proposals 태그 확인
3. Phase 3: US1 완료 — Proposal 생성 + 인텐트 SSE 동작
4. Phase 4: US2 완료 — Diff 검토·수정·제출 동작
5. **STOP and VALIDATE**: US1+US2 독립 테스트
6. Demo 가능 상태

### Incremental Delivery

1. Setup + Foundation → 라우터 등록 확인
2. US1 → Proposal 생성 + SSE 인텐트 분해 동작 (Demo!)
3. US2 → Diff 검토·수정·제출 동작
4. US3 → 샌드박스 구현 SSE 동작
5. US4 → 자동 테스트 + Accept/Destroy 동작
6. US5 → 목록 조회·필터 동작
7. US6 → Dual Merge 원자성 강화
8. Polish → 안정화

---

## Notes

- [P] tasks = 서로 다른 파일, 의존 없음
- [Story] label = 해당 User Story 추적성
- 각 User Story는 독립적으로 완료·테스트 가능
- Git Worktree 경로는 반드시 `.sandbox/proposal/<PRO-NNN>/` — 메인 프로젝트 루트 직접 생성 금지
- Dual Merge는 보상 트랜잭션 순서 준수 (git merge 성공 확인 → Neo4j TX → 실패 시 git reset)
- 038 코드는 직접 임포트 금지 — `api/platform/` 승격 또는 `proposal_lifecycle/` 내 독립 복사 사용
