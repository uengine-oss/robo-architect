---
description: "Task list for Proposal Impact Artifact Preview (040)"
---

# Tasks: Proposal Impact Artifact Preview

**Input**: Design documents from `specs/040-proposal-impact-preview/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/preview-api.md](contracts/preview-api.md), [quickstart.md](quickstart.md)

**Tests**: 포함됨. US2(라이브 오염 0)는 회귀 테스트가 본질적 인수 조건이며, plan/quickstart 가 pytest(투영 무변경)·Playwright(E2E)를 필수로 규정.

**Organization**: 사용자 스토리(US1/US2/US3)별 단계. 신규 Neo4j 스키마·신규 Skill 없음(순수 read/projection).

> ## 구현 상태 (2026-06-11)
> - **백엔드 코어 ✅** — `overlay_apply.py`/`preview_projection.py`/`proposals_preview.py`(`/resolve`, `/preview/contexts/{bc}/full-tree`) + 라우터 등록. `neo4j_helpers.build_context_full_tree` 플랫폼 승격. 오버레이 단위 테스트 **5/5 통과** + write-Cypher 부재 게이트 통과.
> - **US1 (Data 오버레이) ✅** — 엔드투엔드 동작. `aggregateViewer.store` fetch 분기 + 상태 격리, `AggregatePanel` 포커스 watch, `ImpactMapView`/`IntentDecompositionView` "열기" 배선, `PreviewBanner`. `vite build` 통과.
> - **US2 (읽기 전용) ✅ 핵심** — mutation 가드(aggregateViewer 2종, eventModeling 5종), 상태 스냅샷/복원, write-Cypher 게이트. *DB 체크섬 회귀 + Playwright E2E 는 라이브 Neo4j 환경 필요(마커 처리).*
> - **US3 (4개 뷰어) ✅** — `WIRED_VIEWERS` 전체. data=오버레이, design/process/processes=라이브 읽기 전용 포커스(research D5). App.vue 오케스트레이션 + processes 포커스(fetch+selectItem). 미매핑 라벨 비활성+사유.
> - **US4 (편집 가능 미리보기) ✅** — 미리보기 편집을 라이브가 아니라 **Proposal.tacticalDiff** 에 반영. `preview_edit.py`(reconcile) + `proposals_preview_edit.py`(`PUT /preview/aggregate/{id}`, `POST /preview/chat-confirm`). Inspector 경로(aggregateViewer.store `updateAggregateProperties/EnumVo` → 제안 diff) + Chat 경로(modelModifier `confirmDrafts` → chat-confirm → `robo:preview-updated` → `applyPreviewTree`). **API 라운드트립 검증**: 속성 추가→tacticalDiff 반영→영속→라이브(EP-delivery) 무생성→원복. 헤디드 데모로 Inspector 편집 UI 활성 확인.
> - **잔여** — 라이브 full-tree 라우트를 공유 헬퍼로 이관(드리프트 제거), Chat *modify*(LLM) 단계의 temporary 노드 컨텍스트 보강(현재 confirm만 결정론 검증), Playwright 스펙 파일, README/Swagger, 성능 측정.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 병렬 가능(다른 파일, 미완 의존 없음)
- **[Story]**: US1 / US2 / US3 (Setup·Foundational·Polish 는 라벨 없음)

## Path Conventions

- 백엔드: `api/features/proposal_lifecycle/`, `api/platform/`
- 프런트: `frontend/src/features/`, `frontend/src/App.vue`
- 테스트: `frontend/tests/`, `api/features/proposal_lifecycle/tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 모듈 스캐폴드 생성(기존 039 인프라 위에 얹음, 신규 스키마/스킬 없음)

- [ ] T001 백엔드 preview 모듈 스켈레톤 생성: `api/features/proposal_lifecycle/routes/proposals_preview.py`, `api/features/proposal_lifecycle/services/preview_projection.py`, `api/features/proposal_lifecycle/services/overlay_apply.py` (빈 함수 시그니처 + docstring)
- [ ] T002 [P] 프런트 공용 스캐폴드 생성: `frontend/src/features/proposals/proposalPreview.js`, `frontend/src/features/proposals/ui/OpenInViewerLink.vue`, `frontend/src/app/ui/PreviewBanner.vue` (빈 셸)
- [ ] T003 [P] 테스트 파일 스켈레톤 생성: `api/features/proposal_lifecycle/tests/test_preview_projection.py`, `frontend/tests/verify-proposal-preview-aggregate.spec.ts`, `frontend/tests/verify-proposal-preview-readonly.spec.ts`, `frontend/tests/verify-proposal-preview-routing.spec.ts`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 모든 스토리가 공유하는 오버레이 투영 코어 + 프런트 오케스트레이션 골격

**⚠️ CRITICAL**: 이 단계 완료 전에는 어떤 스토리도 시작 불가

- [ ] T004 `overlay_apply.py`: source 판정 규칙(live / live+modified / temporary / conflict) + `PREVIEW:<pid>:<idx>` 결정론적 temp id 부여 + 제안 내 신규 노드 상호참조(제목 매칭) 해소 구현 (data-model §2)
- [ ] T005 `preview_projection.py`: `build_preview_for_target(proposal_id, viewer, target_node_id)` 오케스트레이션 골격 — 039 `ProposalResponse.from_neo4j` 로 diff 로드 + **read 전용 Neo4j 세션 헬퍼**(write 금지) + `PreviewEnvelope` 조립 (data-model §1)
- [ ] T006 `proposals_preview.py`: 라우터를 `/api/proposals/{proposal_id}/preview` 로 정의하고 `GET /resolve`(nodeLabel→viewer 매핑, renderable/reason) 구현 + `router.py` 에 등록 (contracts §1)
- [ ] T007 [P] 프런트 오케스트레이션 골격: `proposalPreview.js` `openPreview(proposalId, target)` → `robo:open-preview` emit; `App.vue` 에 수신 핸들러(탭 전환 + 대상 store `setPreviewSource` + focus 디스패치) 셸; `PreviewBanner.vue`("PRO-NNN 미리보기 — 라이브 아님 · 닫기") (contracts Frontend 이벤트 계약, FR-007)
- [ ] T008 [P] `OpenInViewerLink.vue`: nodeLabel→viewer 매핑 테이블 + `renderable=false` 시 비활성 + 사유 표시(끊긴 링크 금지) (data-model §4, FR-010)
- [ ] T009 preview 라우트에 correlation ID + `preview_projection_start` / `preview_projection_built`(노드 수, source 분포) 구조 로그 추가 (Constitution VII)

**Checkpoint**: 투영 코어·라우팅·프런트 이벤트 골격 준비 — 스토리 구현 시작 가능

---

## Phase 3: User Story 1 - 임팩트 항목에서 산출물 뷰어로 열기 (Priority: P1) 🎯 MVP

**Goal**: Impact/Diff 항목의 "열기" → **Data(Aggregate)** 뷰어가 오버레이 미리보기로 열리고 노드 포커스 + 신규/수정 배지

**Independent Test**: 신규 Aggregate 를 만드는 제안에서 임팩트 항목 "열기" → Data 탭에 해당 Aggregate 가 "신규" 배지 + 포커스로 렌더되는지 확인

### Tests for User Story 1 ⚠️ (먼저 작성, 실패 확인 후 구현)

- [ ] T010 [P] [US1] Playwright `frontend/tests/verify-proposal-preview-aggregate.spec.ts`: 신규 Aggregate "열기" → Data 탭 + 신규 배지 + 포커스, 기존 Aggregate VO 추가 → "추가" 표시 (US1-1, US1-2)
- [ ] T011 [P] [US1] pytest `api/features/proposal_lifecycle/tests/test_preview_projection.py::test_data_overlay_sources`: full-tree 응답에 `temporary`/`live+modified` source 와 temp id 가 포함되는지

### Implementation for User Story 1

- [ ] T012 [US1] `preview_projection.py` `read_live_slice('data', target)`: 라이브 BC full-tree 를 **read 트랜잭션**으로 로드(라이브 `/api/contexts/{bc}/full-tree` 형태) — 대상 Aggregate 의 bcId 해소 포함
- [ ] T013 [US1] `overlay_apply.py` Data 매핑: `obj_append`(valueObjects)·`list_append`(invariants/properties)·`changeType=CREATE`(Aggregate/Command/Event) 를 라이브 슬라이스 딥카피에 오버레이 + source/badge 태깅 (data-model §3 Data)
- [ ] T014 [US1] `proposals_preview.py`: `GET /preview/contexts/{bc_id}/full-tree` 및 `GET /preview/graph/expand-with-bc/{node_id}` 구현(라이브 형태 미러 + `source` 필드) (contracts §2)
- [ ] T015 [US1] `frontend/src/features/canvas/aggregateViewer.store.js`: 도메인 중립 `previewSource` ref + `setPreviewSource`/`clearPreviewSource` + fetch base 분기(`full-tree`/`expand-with-bc`) (data-model §4)
- [ ] T016 [US1] `frontend/src/App.vue`: `robo:open-preview` 의 `viewer='data'` 처리 — Data 탭 전환 + `aggregateViewer.setPreviewSource(...)` + `focusAggregate(targetNodeId, bcId)`
- [ ] T017 [US1] `OpenInViewerLink` 를 `frontend/src/features/proposals/ui/ImpactMapView.vue` 행과 `IntentDecompositionView.vue` 의 tactical(Aggregate/VO/Command/Event) 엔트리 + `ProposalDetail.vue` 에 배선
- [ ] T018 [US1] `PreviewBanner` 를 Data 탭에서 `previewSource` 활성 시 표시, "닫기" → `clearPreviewSource()` + 라이브 재적재 (FR-007)

**Checkpoint**: US1 단독으로 동작·검증 가능 (MVP). Data 오버레이 미리보기 완성.

---

## Phase 4: User Story 2 - 미리보기가 라이브 설계를 절대 오염시키지 않음 (Priority: P1)

**Goal**: 미리보기 조작/열고닫기가 라이브 Neo4j·라이브 탭을 전혀 바꾸지 않음(잔존물 0), 다중 제안 격리

**Independent Test**: 미리보기 열고 닫은 전후 라이브 Data 탭 Aggregate 수·내용 동일 + Neo4j 임시노드 0

### Tests for User Story 2 ⚠️

- [ ] T019 [P] [US2] pytest `test_preview_projection.py::test_preview_does_not_mutate_graph`: 미리보기 합성 전후 그래프 체크섬(노드/관계 카운트 + 속성 해시) 동일 (SC-003)
- [ ] T020 [P] [US2] pytest `test_preview_projection.py::test_no_write_cypher`: preview 모듈 소스에 `CREATE|MERGE|SET|DELETE` Cypher 키워드 부재 게이트 (Constitution I)
- [ ] T021 [P] [US2] Playwright `frontend/tests/verify-proposal-preview-readonly.spec.ts`: 열기→조작(클릭/확대)→닫기 후 라이브 Data 탭 스냅샷 동일 + 두 제안 동시 미리보기 상호 무간섭 (US2-1/2/3)

### Implementation for User Story 2

- [ ] T022 [US2] 모든 preview 핸들러가 Neo4j **read 트랜잭션 전용 세션** 사용하도록 `proposals_preview.py`/`preview_projection.py` 감사·강제 (write 경로 차단)
- [ ] T023 [US2] 프런트 readOnly 가드: `previewSource` 활성 시 뷰어 스토어의 mutation 액션(addNode/deleteNode/createRelation/move*/properties 저장 등)을 **no-op + 콘솔 경고** — 우선 `aggregateViewer.store.js` 에 적용 + 공용 가드 패턴 확립
- [ ] T024 [US2] 상태 격리: 미리보기 진입 시 라이브 store 상태 스냅샷/복원 또는 별도 미리보기 상태로 분리하여 닫을 때 라이브 무손상 + 다중 제안 격리 (US2-3)

**Checkpoint**: US1·US2 모두 독립 동작. 라이브 오염 0 보장.

---

## Phase 5: User Story 3 - 여러 산출물 타입을 일관되게 열기 (Priority: P2)

**Goal**: Aggregate(Data) 외 UI(Design)·Process·Journey(Processes)도 동일 "열기"로 적절 뷰어에서 확인(오버레이 또는 라이브 read-only 포커스)

**Independent Test**: Process 변경 항목 "열기" → Process 뷰어 포커스; 매핑 없는 항목 → "열기" 비활성 + 사유

### Tests for User Story 3 ⚠️

- [ ] T025 [P] [US3] Playwright `frontend/tests/verify-proposal-preview-routing.spec.ts`: Process 변경 항목 → Process 탭 포커스, UI 라이브 노드 → Design read-only, 매핑 없는 항목 → 비활성+사유 (US3-1/2/3)

### Implementation for User Story 3

- [ ] T026 [P] [US3] `preview_projection.py` `read_live_slice('process', …)` + `overlay_apply` Process 매핑(`strategicDiff.processes.fields.steps.after`) + `GET /preview/graph/bpmn/process-flows`·`/process-flow/{start_command_id}` 구현 (contracts §3, data-model §3 Process)
- [ ] T027 [P] [US3] `preview_projection.py` `read_live_slice('design', …)`(expand-with-bc read-only 포커스; tacticalDiff UI 있으면 오버레이) + Design preview 엔드포인트
- [ ] T028 [P] [US3] `preview_projection.py` `read_live_slice('processes', …)`(event-modeling read-only 슬라이스; 가용 시 오버레이) + `GET /preview/graph/event-modeling` 구현 (contracts §4)
- [ ] T029 [US3] `frontend/src/features/canvas/canvas.store.js`·`bpmn.store.js`·`frontend/src/features/eventModeling/eventModeling.store.js` 에 `setPreviewSource`/`clearPreviewSource` + fetch 분기 + readOnly 가드(T023 패턴) 추가
- [ ] T030 [US3] `App.vue` 오케스트레이션을 `viewer='design'|'process'|'processes'` 로 확장(각 탭 전환 + 대상 store setPreviewSource + 해당 focus/select 호출)
- [ ] T031 [US3] `OpenInViewerLink` 매핑 확장(UI/Screen/UiFlow→design, Process/BpmnFlow→process, Journey/EventModel/ReadModel→processes) + 미매핑 비활성, 모든 diff/impact 엔트리에 배선 완료
- [ ] T032 [US3] `/resolve` 와 각 엔드포인트가 ACCEPTED/DESTROYED 제안 시 직렬화 스냅샷 + `_preview.contextNote`("이미 반영됨"/"폐기됨") 첨부 (contracts 공통 규약, Edge Case)

**Checkpoint**: 4개 뷰어 모두 일관된 "열기"로 동작.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 엣지 케이스·문서·성능 마감

- [ ] T033 [US3] conflict 엣지 케이스: `MODIFY` 대상이 라이브에서 삭제됐을 때 `source:conflict` + badge "충돌" 로 깨지지 않게 처리 + pytest 추가 (Edge Cases)
- [ ] T034 [P] `README`/Swagger API 요약에 `/api/proposals/{id}/preview/*` 엔드포인트 반영 (Constitution Dev Workflow)
- [ ] T035 [P] 성능 점검: 단일 BC 슬라이스+오버레이 합성 p95 < 2s, "열기"→포커스 < 2s 측정 (SC-004)
- [ ] T036 [quickstart.md](quickstart.md) 수동 검증 시나리오 전체 실행(US1~US3 Acceptance 매핑 표)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup(P1)**: 의존 없음 — 즉시 시작
- **Foundational(P2)**: Setup 완료 후 — 모든 스토리 차단(특히 T004/T005/T006)
- **US1(P3)**: Foundational 후 시작 — MVP
- **US2(P4)**: US1 의 Data 뷰어가 있어야 오염-0 을 검증(같은 P1 안전 요건). T022/T023 일부는 US1 스토어 위에 가드 추가
- **US3(P5)**: Foundational 후 시작 가능하나 T023(readOnly 가드 패턴)·T015(스토어 패턴) 재사용을 위해 US1/US2 후가 효율적
- **Polish(P6)**: 원하는 스토리 완료 후

### User Story Dependencies

- **US1(P1)**: 다른 스토리 의존 없음 (Foundational 만)
- **US2(P1)**: US1 의 뷰어/스토어 위에 read-only 가드·테스트를 얹음(개념적으로 US1 직후)
- **US3(P2)**: Foundational 의존. 프런트 패턴(T015/T023) 재사용 위해 US1/US2 후 권장, 백엔드 read_live_slice(T026-28)는 [P] 병렬 가능

### Within Each User Story

- 테스트(T010/T011, T019-21, T025) 먼저 작성·실패 확인 후 구현
- 백엔드 슬라이스/오버레이 → preview 엔드포인트 → 프런트 스토어 주입 → App.vue 오케스트레이션 → UI 링크 배선 → 배너
- 스토리 완료 후 다음 우선순위로

### Parallel Opportunities

- Setup: T002, T003 병렬
- Foundational: T007, T008 병렬(프런트 골격) / T004-06 백엔드는 T004→T005→T006 순서
- US1 테스트 T010, T011 병렬
- US2 테스트 T019, T020, T021 병렬
- US3 백엔드 read_live_slice T026, T027, T028 병렬(서로 다른 뷰어)
- Polish T034, T035 병렬

---

## Parallel Example: User Story 1

```bash
# US1 테스트 동시 작성:
Task: "Playwright verify-proposal-preview-aggregate.spec.ts (신규 배지+포커스)"
Task: "pytest test_data_overlay_sources (temporary/live+modified source)"
```

## Parallel Example: User Story 3 backend slices

```bash
Task: "read_live_slice('process') + BPMN preview 엔드포인트"
Task: "read_live_slice('design') + expand-with-bc preview 엔드포인트"
Task: "read_live_slice('processes') + event-modeling preview 엔드포인트"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 Setup → 2. Phase 2 Foundational(차단 코어) → 3. Phase 3 US1(Data 오버레이 미리보기) → **검증·데모**

### Incremental Delivery

1. Setup + Foundational → 골격 준비
2. US1 → Data 오버레이 미리보기 (MVP, 데모)
3. US2 → 라이브 오염 0 보장(안전 게이트)
4. US3 → 4개 뷰어 전체 + 매핑/폴백
5. Polish → 엣지/문서/성능

### Constitution 안전 게이트 (상시)

- preview 경로 read 트랜잭션 전용 + write Cypher 부재 테스트(T020/T022)는 US2 의 핵심이자 머지 차단 기준.
- 뷰어 스토어는 proposals 직접 임포트 금지 — `robo:open-preview` 이벤트 경유(T007/T016/T030) (Principle V).

---

## Notes

- [P] = 다른 파일·무의존. [Story] = 추적용.
- 신규 Neo4j 라벨/관계/제약/인덱스 **없음**, 신규 Skill **없음**(순수 read/projection).
- 미리보기는 어떤 경로로도 라이브 그래프에 쓰지 않는다(US2/Constitution I) — 의심되면 멈추고 read-only 감사.
- 각 태스크 또는 논리 그룹 후 커밋.
