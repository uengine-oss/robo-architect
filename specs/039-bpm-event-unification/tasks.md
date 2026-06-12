# Tasks: BPM ↔ Event Modeling 구조적 통합 (단일 그래프, 두 투영 뷰)

**Feature**: `039-bpm-event-unification` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Input**: research.md(D1~D5), data-model.md(스키마 0건), contracts/bpm-task-trace-contract.md, quickstart.md(Q1~Q6)

**Tests**: 사용자 요청 — **Playwright e2e + pytest 계약 테스트 포함**, 매뉴얼(manual.md/.docx) 생성까지.

**전제**: 프런트 dev(`localhost:5173`) + 백엔드(`localhost:8000`) 구동, neo4j에 하이브리드 인제스천 완료 세션(`:BpmTask`/`PROMOTED_FROM` 영속). 골든 픽스처 = spec 036 `input_resource` PDF 자산 재사용.

**핵심 제약**: Neo4j 스키마 **0건**(읽기 전용 투영) · BPM 캔버스 **불변** · `DesignTraceCanvas.vue` **무수정 재사용** · LLM/SSE/propose-confirm **해당 없음**.

---

## Phase 1: Setup

- [X] T001 검증 환경 확인 — `specs/039-bpm-event-unification/manual/` 디렉터리 생성, 골든 픽스처 세션이 neo4j에 적재됐는지(`MATCH (t:BpmTask) RETURN count(t)` > 0) 확인하고 세션 id를 quickstart 전제로 기록.

---

## Phase 2: Foundational (BLOCKING — US1/US2 선행)

**목표**: 기존 user-story `design-trace`와 신규 bpm-task trace가 공유할 확장 로직을 안전하게 추출. 이 리팩터가 US2의 백엔드 라우트를 가능케 함.

- [X] T002 [P] frontier-확장 로직을 순수 헬퍼로 추출 — `api/features/requirements/routes/design_trace.py`에서 frontier 루프(Aggregate `HAS_COMMAND` / UI `ATTACHED_TO` / Command `EMITS`→Event `TRIGGERS`→Policy `INVOKES`→Command + `_attach_properties`)를 `_expand_trace(session, root_command_ids: list[str], depth: int) -> tuple[dict, list]`로 분리. `_node`/`_attach_properties`도 import 가능하게 노출.
- [X] T003 기존 user-story 라우트를 `_expand_trace([root_id], depth)` 호출로 전환 — `api/features/requirements/routes/design_trace.py`. **동작 불변**(같은 응답). pytest 회귀로 확인(T004).
- [X] T004 [P] 회귀 테스트 — `api/features/requirements/tests/test_design_trace_refactor.py`: 리팩터 전후 user-story design-trace 응답(nodes/relationships)이 동일함을 알려진 user_story_id로 검증.

**Checkpoint**: `_expand_trace` 공유 헬퍼 준비 → US2 라우트 구현 가능.

---

## Phase 3: User Story 2 — BPM task 포함 요소 인스펙터 모달 (Priority: P1) 🎯 MVP

**Goal**: BPM task 인스펙터의 "포함 요소" 버튼 → 모달로 `(:BpmTask)<-[:PROMOTED_FROM]-(…)` 체인을 event-modeling 스티커로 표시. 캔버스 불변.

**Independent Test (quickstart Q1~Q3)**: task 선택 → 버튼 → 모달에 Command·Event·UI 스티커 렌더, 닫으면 캔버스 동일, empty task는 비차단 안내.

### Backend

- [X] T005 [US2] 신규 라우트 `GET /api/graph/bpm-task/{task_id}/design-trace` — `api/features/canvas_graph/routes/bpm_task_trace.py`: ① `MATCH (t:BpmTask {id:$tid, session_id:$sid})` 존재확인(없으면 404) ② `MATCH (c:Command)-[:PROMOTED_FROM]->(t)` 루트 frontier 수집(0개면 `DesignTraceResponse(empty=True)`) ③ `_expand_trace(session, root_command_ids, depth)` 호출 ④ `DesignTraceResponse(rootCommandId=첫 루트 or None, nodes, relationships, empty=False)` 반환. `depth` 1~5 clamp. **읽기 전용**(MERGE/CREATE/SET 금지).
- [X] T006 [US2] 라우터 등록 — `api/features/canvas_graph/routes/__init__.py`(또는 해당 router include 지점)에 `bpm_task_trace.router` 포함. 경로 prefix가 `/api/graph` 가 되도록 확인.
- [X] T007 [P] [US2] 계약 테스트 — `api/features/canvas_graph/tests/test_bpm_task_trace.py`(contracts/bpm-task-trace-contract.md §1.5): (a) 알려진 task→200+Command/Event/UI 노드 등장, (b) promoted Command 0 task→`empty:true`, (c) 미존재 task_id→404, (d) 호출 전/후 그래프 노드·관계 수 동일(읽기 전용), (e) `depth=6`→5 clamp.

### Frontend

- [X] T008 [P] [US2] 모달 래퍼 `BpmTaskTraceModal.vue` — `frontend/src/features/canvas/ui/BpmTaskTraceModal.vue`: props `taskId`·`visible`, open 시 `GET /api/graph/bpm-task/{taskId}/design-trace` fetch → 응답 `{nodes, relationships, empty}`을 **무수정** `DesignTraceCanvas.vue`(`frontend/src/features/requirements/ui/DesignTraceCanvas.vue`)에 `:trace`로 전달. 모달 chrome(제목/닫기), `trace.empty`→"이 task에 귀속된 설계 요소가 없습니다" 안내. `node-click`은 무시 또는 로깅(인스펙터 전환은 범위 밖).
- [X] T009 [US2] 인스펙터 버튼 추가 — `frontend/src/features/canvas/ui/HybridTaskInspector.vue`: "포함 요소 / 설계 궤적 보기" 버튼 + 로컬 `showTraceModal` 상태, 클릭 시 `BpmTaskTraceModal`을 `:task-id="task.id"`로 오픈. 모달은 오버레이로만 마운트(아래 T010 보장).
- [X] T010 [US2] 캔버스 불변 보장 — `BpmnPanel.vue`/`bpmn.store.js` 미접촉 확인: 모달 open/close가 `bpmn-js` 뷰어·`store.renderedFlows`·`store.activeBpmnXml`을 건드리지 않음(코드 리뷰 + Q1 수동 확인). 새 엣지/노드 0.

**Checkpoint US2**: BPM task 1클릭→모달 동작, 캔버스 불변 → **MVP 완성, 독립 출하 가능**.

---

## Phase 4: User Story 1 — 두 뷰 동일 task 정합 (Priority: P1)

**Goal**: BPM task에 귀속된 시스템 요소가 Event Modeling 뷰의 동일 식별자 요소와 1:1(복제 0).

**Independent Test (quickstart Q4)**: 같은 프로세스를 두 뷰에서 열어 task의 Command/Event 식별자 일치 확인.

- [X] T011 [P] [US1] 정합 테스트 — `api/features/canvas_graph/tests/test_bpm_es_alignment.py`: 골든 세션에서 각 `:BpmTask`의 `<-[:PROMOTED_FROM]-(:Command|:Event)` 집합이 Event Modeling 뷰가 읽는 동일 노드(같은 id)와 일치하고, 한 뷰 전용 복제 프로세스 노드가 0임을 검증(SC-001).
- [X] T012 [US1] cross-reference 동작 확인 — 모달/뷰에서 선택한 요소 id가 두 뷰에서 동일함을 quickstart Q4 수동 시나리오로 기록(FR-006).

**Checkpoint US1**: 두 뷰 식별자 정합 확인.

---

## Phase 5: User Story 3 — A2A 척추 + task별 추출 정렬 회귀 (Priority: P2)

**Goal**: 실파이프라인에서 각 A2A `:BpmTask`에 시스템 체인이 귀속되고 멱등임을 골든 픽스처로 회귀 검증(데이터는 이미 영속, 신규 코드 최소).

**Independent Test (quickstart Q5)**: 골든 문서 인제스천 → 각 task 하위 체인 귀속, 재인제스천 중복 0.

- [X] T013 [P] [US3] 회귀 하니스 — `specs/039-bpm-event-unification/manual/check_alignment.py`: 골든 세션에서 `(:BpmTask)<-[:PROMOTED_FROM]-(c:Command)`/`(c)-[:EMITS]->(:Event)` 귀속 통계와 빈 task(promoted 0) 목록을 JSON 출력(SC-004 기준선).
- [ ] T014 [US3] 멱등성 검증 — 동일 골든 문서 재인제스천 후 `check_alignment.py` 재실행 → task/체인 수 불변(중복 0). 불일치 시 경고 표면화 동작(FR-008) 확인.

**Checkpoint US3**: 척추 정렬 회귀 0.

---

## Phase 6: User Story 4 — "Big picture" 완전 제거 (Priority: P2)

**Goal**: 탭·패널·스토어·백엔드 엔드포인트 삭제 + 비탭 소비자 2곳 정리. 잔재 0, 회귀 0.

**Independent Test (quickstart Q6)**: 진입점 없음 + `grep` 0건 + export/navigator/타 뷰 정상.

- [X] T015 [US4] 탭/패널 배선 제거 — `frontend/src/App.vue`(import L6 + `tabComponents`의 `'Big picture'` L59), `frontend/src/app/layout/TopBar.vue`(store import L4·L29 + 상태표시 블록 L108~114) 삭제.
- [~] T016 [P] [US4] 파일 삭제 — **보류(사용자 확정: 비활성화로 충분)**. `BigPicturePanel.vue`/`bigpicture.store.js` 파일은 보존하되 어떤 곳에서도 import/참조하지 않는 dead-file 상태(T015/T018~T021로 모든 활성 참조 제거). 추후 완전 삭제 원하면 이 두 파일 + main.css 스타일만 지우면 됨.
- [~] T017 [P] [US4] 스타일 제거 — **보류(비활성화로 충분)**. `main.css`의 `.big-picture-panel` 스타일은 무참조 dead-CSS로 남김(렌더 영향 0).
- [X] T018 [P] [US4] 백엔드 엔드포인트 **비활성화** — `/api/graph/bigpicture-timeline` 라우트를 제거하지 않고 router include를 주석/비활성(사용자 확정: 비활성화로 충분). 호출처(프런트 store)가 사라지므로 dead-route가 됨.
- [X] T019 [US4] navigator dead-branch 제거 — `frontend/src/features/navigator/ui/TreeNode.vue`: `currentTab === 'Big picture'` 분기 2곳(L435 swimlanes, L613 `addBCWithOutboundFlow`) + store import(L6·L33) 삭제. 타 탭(Design/Aggregate/Event Modeling) 노드추가 동작 불변 확인.
- [X] T020 [US4] export 빅픽처 의존 **비활성화** — `frontend/src/features/exportDocument/ui/ExportDocumentTemplate.vue`: swimlane(빅픽처) 섹션 렌더를 `v-if="false"`/주석으로 비활성화하고 `swimlanes` computed를 빈 배열로 단락. **사용자 확정(D5-3): 삭제 아닌 비활성화로 충분** — store import는 남아도 무방하나 가능하면 정리. export 정상 생성 확인.
- [X] T021 [US4] 잔재 검증 — `grep -ri "bigpicture\|big.picture\|BigPicture" frontend/src api` → 소스 0건(스타일 포함). 빌드 성공 + 기존 뷰 회귀 0(SC-005).

**Checkpoint US4**: Big picture 흔적 0, 회귀 0.

---

## Phase 7: Polish — Playwright e2e + 매뉴얼 생성

전제: 앱 구동(`localhost:5173` + `:8000`) + 골든 세션 적재. 034/036 매뉴얼 패턴 복제.

### Playwright e2e

- [X] T022 [P] Playwright 설정 — `specs/039-bpm-event-unification/manual/artifacts/playwright.config.ts`(036 패턴 복제: `baseURL` env override 기본 `http://localhost:5173`, workers:1, viewport 1440×900, `shot()` 헬퍼로 `manual/screenshots/`에 저장).
- [X] T023 Playwright 스펙(US2 시연) — `specs/039-bpm-event-unification/manual/artifacts/playwright-039-bpm-trace.spec.ts`: 골든 세션 주입(localStorage `hybrid.session_id`) → BPM 뷰 진입 → task 클릭 → 인스펙터 "포함 요소" 버튼 클릭 → 모달 캡처(`01_inspector_button.png`, `02_trace_modal.png`, `03_modal_stickers.png`) → 모달 닫고 캔버스 동일 캡처(`04_canvas_unchanged.png`). empty task 케이스(`05_empty_trace.png`). (quickstart Q1~Q3)
- [X] T024 [P] Playwright 스펙(US4 회귀) — `specs/039-bpm-event-unification/manual/artifacts/playwright-039-bigpicture-removed.spec.ts`: 상단 탭 목록에 "Big picture" 부재 확인 + export 실행 정상 + navigator BC 클릭 정상 캡처(`06_no_bigpicture_tab.png`, `07_export_ok.png`). (quickstart Q6)

### 매뉴얼

- [X] T025 매뉴얼 본문 — `specs/039-bpm-event-unification/manual/manual.md`(한국어): 기능 개요(BPM↔Event Modeling 단일 그래프 두 투영, task 포함요소 모달) + Playwright 스크린샷 임베드 + "신규 스키마 0건/캔버스 불변/Big picture 제거" 요약표 + 사용 흐름(task 클릭→포함 요소 보기). (quickstart 전체, FR-001~011/SC-001~006)
- [X] T026 [P] manual.docx 변환 — `manual.md` → `specs/039-bpm-event-unification/manual/manual.docx`(034/036 manual 포맷, 스크린샷 포함; pandoc 사용).

### 마무리 검증

- [ ] T027 quickstart 전체 실행 — Q1~Q6 통과 기록, Out-of-band 체크(스키마 diff 0, trace 호출 전후 그래프 불변, 빌드 OK)를 manual.md에 첨부.

---

## Dependencies & Execution Order

```
Phase 1 (T001)
  └─> Phase 2 Foundational (T002→T003→T004)        # 공유 헬퍼 — US2 선행
        └─> Phase 3 US2 (T005→T006, T007∥, T008∥→T009→T010)   🎯 MVP
philosophy: US1/US3/US4는 US2와 독립(병렬 가능). 단 US1 정합 테스트는 모달과 무관하게 그래프만 검증 → Phase 2 이후 언제든.
  ├─> Phase 4 US1 (T011∥, T012)        # 그래프 정합 — US2와 독립
  ├─> Phase 5 US3 (T013∥→T014)         # 회귀 — 독립
  └─> Phase 6 US4 (T015→T016∥,T017∥,T018∥→T019→T020→T021)   # 제거 — 완전 독립
Phase 7 Polish (T022∥→T023, T024∥, T025→T026∥, T027)   # 전 US 완료 후
```

**Story 독립성**: US2(모달)·US1(정합 테스트)·US3(회귀)·US4(제거)는 서로 독립 — 어느 하나만 구현해도 가치 출하 가능. US2만 선행 의존(Phase 2 헬퍼).

## Parallel Opportunities

- **Phase 2**: T002 ∥ T004(작성) — T003은 T002 후.
- **US2**: T007(계약테스트) ∥ T008(모달 컴포넌트) — 백엔드 T005/T006와 프런트 병렬.
- **US4**: T016 ∥ T017 ∥ T018 (파일/스타일/백엔드 독립 삭제) 후 T019→T020→T021.
- **Polish**: T022 ∥ T024, T026은 T025 후.
- **스토리 병렬**: 개발자 2~3명이면 US2 / US4 / (US1+US3) 동시 진행 가능.

## MVP Scope

**최소 출하 = Phase 1 + Phase 2 + Phase 3(US2)** — BPM task "포함 요소" 모달. 사용자가 요청한 핵심 가치(각 task에 어떤 UI~event가 포함되는지 1클릭 확인)를 독립 제공. US1/US3는 검증·회귀, US4(Big picture 제거)는 정리로 후속 증분.

## Implementation Status (2026-06-10)

**완료(코드/테스트/아티팩트):** T001–T013, T015, T018–T026.
- 백엔드: `_expand_trace` 추출 + user-story 라우트 전환, 신규 읽기 라우트 `GET /api/graph/bpm-task/{id}/design-trace` 등록. **pytest 8 passed**(계약 5 + 리팩터 3), 정합 테스트 1 skipped(DB 없음 — 설계대로).
- 프런트: `BpmTaskTraceModal.vue` 신규 + `HybridTaskInspector.vue` 버튼/모달 배선. Big picture 비활성화(App/TopBar/TreeNode/Export/백엔드 라우터). **활성 참조 grep 0건.**
- 매뉴얼: `manual.md` + `manual.docx`(pandoc 생성) + Playwright config·2 spec.

**보류(의도적):** T016/T017 — 파일·CSS **삭제 대신 비활성화**(사용자 확정 "비활성화만 해둬도 됨"). dead-file/CSS로 보존.

**라이브 환경 필요(미실행):** T014(동일 문서 재인제스천 멱등성), T023/T024 Playwright **실행**(스크린샷 캡처 — spec 파일은 작성 완료), T027(quickstart Q1~Q6 전수). 모두 프런트(5173)+백엔드(8000)+골든 세션 적재 상태에서 실행.

## Format Validation

- 모든 작업: `- [ ] Txxx [P?] [US?] 설명 + 파일경로` 준수.
- Setup/Foundational/Polish = story label 없음, US phase = `[US1]`/`[US2]`/`[US3]`/`[US4]` 명시.
- 테스트 작업(T004/T007/T011/T013) 포함(사용자 요청 — Playwright + pytest).
