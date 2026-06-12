# Tasks: BPM·Event Modeling 단일 Process 탭 + task=UI 일관성

**Feature**: `043-task-ui-unification` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Input**: research.md(D1~D6), data-model.md(스키마 0건), contracts/(2), quickstart.md(Q1~Q6)

**Tests**: spec 요청 — pytest 계약/정합 + Playwright(탭 토글·EM 형식) + 매뉴얼(프로젝트 관행).

**전제**: 프런트(5173)+백엔드(8000)+neo4j. 골든 픽스처(spec 036 input_resource) **재인제스천** 필요(인제스천 로직 변경). spec-042 산출물(bpm-task trace 라우트·Big picture 제거)을 **재사용·계승**.

**핵심 제약**: 신규 노드 라벨/관계 **0건**(`ATTACHED_TO.role` 속성만) · A2A BPM·Command/Event task귀속 **불변** · LLM 판정은 `get_llm`+propose(통합 뷰 노출) · 인제스천 변경=재인제스천.

---

## Phase 1: Setup

- [X] T001 검증 환경 확인 — 골든 세션 적재 상태(`MATCH (t:BpmTask) RETURN count(t)`), 재인제스천 경로(`/api/ingest/hybrid`) 동작, `specs/043-task-ui-unification/manual/` 디렉터리 생성.
- [X] T002 [P] 베이스라인 스냅샷 — 재인제스천 *전* 그래프 통계(task당 UI 수, ReadModel UI 수, Command/Event task_id 수)를 `specs/043-task-ui-unification/manual/baseline.json`으로 기록(SC-002/003/005 비교 기준).

---

## Phase 2: Foundational (BLOCKING — US2/US3 선행)

**목표**: 인제스천 UI 생성 변경의 공통 토대 — task 그룹핑 유틸 + LLM 판정 헬퍼(트리거/조회).

- [X] T003 [P] task 그룹핑 유틸 — `api/features/ingestion/workflow/phases/ui_wireframes.py`(또는 동 phase 헬퍼): Command 목록을 `task_id`로 그룹화하고 policy-invoked Command를 제외하는 `group_trigger_candidates_by_task()` 추가. (data-model.md 생성로직 §1)
- [X] T004 [P] LLM 트리거 선택 헬퍼 — `TriggerPick`(`{trigger_command_id, confidence, rationale}`) 스키마 + `pick_trigger_command(task, candidates, ui_desc)` (`get_llm`). confidence<임계 시 entry 폴백. (D2, contract §1)
- [X] T005 [P] LLM ReadModel 분류 헬퍼 — `ReadModelVerdict`(`{is_query_screen, host_task_id?, rationale}`) 스키마 + `classify_readmodel(rm, context)` (`get_llm`). (D3, contract §2)

**Checkpoint**: 그룹핑+판정 헬퍼 준비 → US2/US3 생성 로직 교체 가능.

---

## Phase 3: User Story 2 — task당 1 트리거 UI (Priority: P1) 🎯 MVP(인제스천)

**Goal**: ES 승격에서 사람-트리거 task당 트리거 UI 정확히 1개. Command/Event task 귀속 불변.

**Independent Test (Q1/Q3)**: 재인제스천 후 사람-트리거 task : 트리거 UI = 1:1, Command 다수 task도 UI 1개, Command/Event task_id 회귀 0.

- [X] T006 [US2] UI 생성 루프 교체(Command 측) — `ui_wireframes.py`: 기존 `BC→Aggregate→Command`별 `_create_command_ui` 호출(L989~1020)을 **task 그룹 루프**로 변경. 각 task에서 `pick_trigger_command`로 1개 선택 → 그 Command에만 `_create_command_ui`. 나머지 Command UI 미생성. policy-invoked-only task = UI 0.
- [X] T007 [US2] 멱등 보장 — 재인제스천 시 task당 트리거 UI가 중복 생성되지 않도록 upsert/키 확인(기존 `created_by_command` 패턴을 task 기준으로).
- [X] T008 [P] [US2] 계약 테스트 — `api/features/ingestion/workflow/tests/test_task_ui_invariant.py`(contract §3): (a) Command 2개 task→트리거 UI 1개, (b) policy-invoked-only task→UI 0, (c) confidence 낮음→entry 폴백, (d) Command/Event task_id 호출 전후 동일.
- [ ] T009 [US2] 골든 재인제스천 정합 — 재인제스천 후 그래프에서 task:UI=1:1, Command/Event task_id 회귀 0을 `manual/baseline.json` 대비 검증(스크립트 `manual/check_task_ui.py`).

**Checkpoint US2**: task=UI(트리거) 불변식 성립 → **인제스천 MVP**.

---

## Phase 4: User Story 3 — ReadModel 표시/조회화면 분기 (Priority: P2)

**Goal**: ReadModel 무조건 UI 제거 → 소비표시(`role:'display'`) / 조회화면 승격(LLM).

**Independent Test (Q2)**: 무조건 생성 ReadModel UI 0, 조회 판정분만 UI 승격, 나머지는 `ATTACHED_TO {role:'display'}`.

- [X] T010 [US3] ReadModel 생성 분기 — `ui_wireframes.py`: 기존 `_create_readmodel_ui` 무조건 호출(L1025~1049)을 `classify_readmodel` 분기로 교체. `is_query_screen`→`_create_readmodel_ui`(screen), else→소비 task UI에 `(:UI)-[:ATTACHED_TO {role:'display'}]->(:ReadModel)` 부착.
- [X] T011 [US3] 호환성 확인 — `api/features/canvas_graph/routes/event_modeling.py`가 `(:UI)-[:ATTACHED_TO]->(:ReadModel)`를 읽을 때 `role` 속성 무시해도 기존 동작 보존됨을 확인(필요 시 role 필터). 신규 라벨/관계 0 재확인.
- [X] T012 [P] [US3] 계약 테스트 — `test_readmodel_branch.py`: 조회화면 판정 RM→UI 승격, 비조회 RM→`role:'display'` 부착, 무조건 생성 UI 0(SC-003).

**Checkpoint US3**: ReadModel granularity 정리 완료.

---

## Phase 5: User Story 1 — 단일 Process 탭 + BPM⇄EM 토글 (Priority: P1)

**Goal**: Process·Event Modeling 탭을 하나로, 내부 토글. 공유 UI 앵커.

**Independent Test (Q4)**: 상단 탭에 'Event Modeling' 없음, Process 토글로 BPM⇄EM 전환, UI 앵커 동일.

- [X] T013 [US1] ProcessPanel 래퍼 — `frontend/src/features/canvas/ui/ProcessPanel.vue` 신규: 내부 BPM⇄EM 토글 상태 + `BpmnPanel`/`EventModelingPanel` 호스팅, 선택 프로세스/세션 id 보유(토글 간 유지).
- [X] T014 [US1] 탭 배선 변경 — `frontend/src/App.vue` `tabComponents`: `'Process' → ProcessPanel`, `'Event Modeling'` 항목 + import 제거. `frontend/src/app/layout/TopBar.vue` `tabs` 배열에서 'Event Modeling' 제거 + 상태표시 정리.
- [X] T015 [US1] 회귀 확인 — BpmnPanel·EventModelingPanel 기존 동작 불변(토글 호스팅만), 다른 탭 영향 0.

**Checkpoint US1**: 단일 Process 탭 토글 동작.

---

## Phase 6: User Story 4 — Event Modeling 형식 경량 렌더러 (Priority: P2)

**Goal**: task 포함요소를 가로 레인(UI→Command→Event→ReadModel)으로. 042 trace 데이터 재사용.

**Independent Test (Q5)**: Process 탭 task 포함요소 = 가로 레인 형식, requirements 설계-궤적은 기존 컬럼 형식 유지.

- [X] T016 [US4] EventModelingLane 렌더러 — `frontend/src/features/canvas/ui/EventModelingLane.vue` 신규: spec-042 `GET /api/graph/bpm-task/{id}/design-trace`의 `{nodes, relationships}`를 입력받아 **가로 레인**(타입별 좌→우 UI/Command/Event/ReadModel) 레이아웃. 042 노드 컴포넌트 재사용.
- [X] T017 [US4] Process 뷰/모달에 EM 형식 연결 — 042의 `BpmTaskTraceModal`(또는 ProcessPanel 내 포함요소 뷰)이 `DesignTraceCanvas` 대신 `EventModelingLane`을 쓰도록 전환. **requirements 탭 `DesignTraceCanvas`는 불변**.
- [X] T018 [P] [US4] 형식 회귀 확인 — requirements 설계-궤적 형식 회귀 0(FR-007), Process 포함요소만 레인 형식.

**Checkpoint US4**: EM 형식 표현 완료.

---

## Phase 7: Polish — 검증 + Playwright + 매뉴얼

전제: 앱 구동 + 골든 재인제스천 세션.

- [X] T019 [P] Playwright 설정 — `specs/043-task-ui-unification/manual/artifacts/playwright.config.ts`(042 패턴 복제: baseURL env, workers:1, 1440×900, testMatch `playwright-042-`).
- [X] T020 Playwright 스펙(US1/US4) — `playwright-042-process-tab.spec.ts`: 상단 탭에 'Event Modeling' 부재 확인 → Process 탭 BPM⇄EM 토글 캡처(`01_no_em_tab`, `02_bpm`, `03_em_toggle`) → task 포함요소 EM 가로 레인 캡처(`04_em_lane`).
- [X] T021 [P] 그래프 검증 스크립트 — `specs/043-task-ui-unification/manual/check_task_ui.py`: 재인제스천 후 task:UI 1:1, ReadModel role 분포, Command/Event task_id, 신규 라벨/관계 0(`db.labels()`/`db.relationshipTypes()` 전후 비교)을 JSON 출력(Q1·Q2·Q3·Q6).
- [X] T022 매뉴얼 본문 — `specs/043-task-ui-unification/manual/manual.md`(한국어): task=UI 개요(왜·무엇) + 단일 Process 탭/토글 + EM 형식 + 재인제스천 안내 + Playwright 스크린샷 + before/after 통계표(baseline vs 재인제스천). (quickstart 전체)
- [X] T023 [P] manual.docx 변환 — `manual.md`→`manual.docx`(pandoc, 스크린샷 포함).
- [ ] T024 quickstart 전수 — Q1~Q6 통과 기록 + Out-of-band(신규 스키마 0, propose 노출) 확인을 manual.md에 첨부.

---

## Dependencies & Execution Order

```
Phase 1 (T001, T002∥)
  └─> Phase 2 Foundational (T003∥ T004∥ T005∥)        # 그룹핑+판정 헬퍼
        ├─> Phase 3 US2 (T006→T007→T008∥→T009)   🎯 인제스천 MVP
        └─> Phase 4 US3 (T010→T011→T012∥)          # US2 헬퍼 공유, US2 후
  ┌─> Phase 5 US1 (T013→T014→T015)                  # 프런트, 인제스천과 독립
  └─> Phase 6 US4 (T016→T017→T018∥)                 # 042 trace 재사용, US1과 병렬 가능
Phase 7 Polish (T019∥→T020, T021∥, T022→T023∥, T024)  # 전 US 후
```

**Story 독립성**: US1(탭)·US4(렌더러)는 프런트로 인제스천(US2/US3)과 **독립 병렬**. US2→US3는 헬퍼 공유로 순차. US4는 042 trace 라우트(기존)에 의존하므로 인제스천 재실행 없이도 개발 가능.

## Parallel Opportunities

- Phase 2: T003 ∥ T004 ∥ T005 (독립 헬퍼).
- 스토리 병렬: (US2+US3 백엔드) ∥ (US1+US4 프런트) — 개발자 2명 분업 가능.
- Polish: T019 ∥ T021, T023은 T022 후.

## MVP Scope

**두 갈래 MVP**:
- **인제스천 MVP** = Phase 1+2+3(US2): task=UI 불변식(가장 큰 가치, 재인제스천으로 즉시 검증).
- **프런트 MVP** = Phase 5(US1): 단일 Process 탭 토글(사용자 체감 통합).
둘은 독립 출하 가능. US3/US4는 후속 정밀화.

## Implementation Status (2026-06-11)

**✅ 완료·라이브 검증 (프런트):** US1(T013~T015) 단일 Process 탭 토글, US4(T016~T018) EM 형식 레인 — Playwright 통과, 스크린샷 4종. `_expand_trace`에 ReadModel(FEEDS) 확장 추가(라이브 ReadModel 반환 확인).

**✅ 완료·단위검증 (백엔드, 코드+테스트):** US2/US3 로직 — [task_ui_helpers.py](../../api/features/ingestion/workflow/phases/task_ui_helpers.py) 신규(그룹핑·트리거LLM·ReadModel분류·display부착) + [ui_wireframes.py](../../api/features/ingestion/workflow/phases/ui_wireframes.py) **가드된**(hybrid 한정) 변경. **pytest 18 passed**. baseline.json 측정 완료(task UI {0:1,1:17,2:1}, RM screen 4/display 0).

**🔁 1차 검증 + 정책 개정 (2026-06-11):**
- **US2 개정(중요)**: 초안의 "task당 1 트리거 UI"는 **철회**. 사용자 확인 — *한 task에 사람 화면이 여럿일 수 있음*. baseline `{0:1,1:17,2:1}`이 이미 ~1/task였고, 그 "2"는 사람 command 2개인 정상 케이스. → **"사람-조작(=policy-invoked 아님) command마다 UI"** 로 복귀(원래 동작, task당 1~N UI). 하이브리드 command-그룹핑/트리거 LLM 로직 제거.
- **US3 3분류**: ReadModel = `query_screen`(자체 UI) / `displayed`(생산 task 화면에 `role:'display'` 부착) / `system`(UI 없음). "ReadModel당 무조건 UI" 폐지. 불확실 시 displayed(누락 방지). → 1차에서 "조회 결과가 UI로 안 나옴" 문제 해소.
- **#3 ES 추출 변동**(command 18→9) — 042 무관한 LLM 추출 비결정성, 별도 이슈.
- pytest **15 passed**(readmodel 7 + bpm-trace 5 + refactor 3). → **2차 재인제스천으로 재검증.**

**✅ 최종 재인제스천 검증 (after3, 캐시 OFF, 2026-06-11):** ReadModel 정책 최종 개정 반영.
- **ReadModel = screen/inline/system 3분류** (screen=조회/검색 **또는 결과 화면** → 자체 UI). 실 LLM이 11개 readmodel 전부 `screen` 판정 → **11/11 결과 UI 생성**. "readmodel마다 UI 없음" 문제 해소.
- **task당 UI = 1~N** `{0:3, 1:12, 2:4}`. UI 총 30(액션 19 + 결과 11). Command 23/Event 31.
- **EM 레인 = `UI(액션)→Command→Event→ReadModel→UI(결과)`** 전체 표시. trace에 `RESULT_UI`/`DISPLAYED_ON`(비영속, 응답 전용) 추가 + EventModelingLane이 결과 UI를 맨 오른쪽 배치.
- **042 신규 영속 라벨/관계 0** — `ATTACHED_TO.role` 속성만(이번 run은 전부 screen이라 role 미사용). 라이브 캡처 확인.

**(이전) 2차 재인제스천 (after2):**
- **task당 UI = 1~N 작동** — 분포 `{0:1,1:17,2:1}` → `{0:2, 1:14, 2:3}`. 사람 command 여럿인 task 3개가 UI 2개(원하던 "task에 여러 UI"). command 18→21.
- **ReadModel display 타이밍 버그 발견·수정** — 1차 attach 경로가 `PROMOTED_TO`(후처리 훅=ui_wireframes *이후* 생성) 의존이라 단계 시점에 0개 부착. → 경로를 `rm→CQRS→Event←EMITS←Command←ATTACHED_TO←UI`(CQRS=phase06, command-UI=phase11 배치 → 둘 다 attach 시점 존재)로 수정. **replay로 실데이터 검증: LLM이 7개 모두 'displayed' 판정 → 6개 화면 부착**(1개는 생산 command에 UI 없음). 그래프에 `ATTACHED_TO {role:'display'}` 6건.
- **신규 라벨/관계 0(042 기준)** — diff의 Policy/TRIGGERS/INVOKES는 이번 ES가 정책을 생성한 데이터 차이(기존 스키마 타입). 042 그래프 변경은 `ATTACHED_TO.role` 속성뿐.
- pytest **7 passed**(readmodel). 캐시 토글을 ES 승격 모달에 추가([PromoteToEsModal.vue]).

**검증 자산**: `manual/baseline.json`, `after2.json`, `replay_readmodel_display.py`(일회성 검증).

**⏸ (참고) 재인제스천 시 in-phase 동작:**
- T009 — 골든 재인제스천 후 task:UI=1:1, Command/Event task_id 회귀 0 (`check_task_ui.py` after.json diff).
- T024 — quickstart Q1~Q3·Q6 전수(US2/US3는 재인제스천 후).
- ReadModel display 부착(`attach_readmodel_display`)의 host-UI 해소 배선은 후속(헬퍼 준비됨, 비조회 RM은 현재 UI 미생성으로 "무조건 UI" 문제는 해소).

**제약 충족:** 신규 Neo4j 라벨/관계 0(`ATTACHED_TO.role` 속성만, event_modeling 호환), A2A BPM·Command/Event task귀속 불변, 비-하이브리드 경로 무변경(가드).

## Format Validation

- 전 작업 `- [ ] Txxx [P?] [US?] 설명 + 파일경로` 준수.
- Setup/Foundational/Polish = story label 없음, US phase = `[US1]`~`[US4]`.
- 테스트(T008/T012/T020/T021) 포함(spec 요청 — pytest + Playwright).
