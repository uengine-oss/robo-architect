# Contract: 단일 Process 탭 토글 + Event Modeling 형식 뷰

## 1. 단일 Process 탭 + BPM⇄EM 토글 (US1, FR-001/002)

| 항목 | 계약 |
|---|---|
| 탭 구성 | [App.vue](../../frontend/src/App.vue) `tabComponents`: `'Process' → ProcessPanel`, **`'Event Modeling'` 항목 제거** |
| 상단바 | [TopBar.vue](../../frontend/src/app/layout/TopBar.vue) `tabs`에서 'Event Modeling' 제거 |
| ProcessPanel | 내부 토글(BPM / Event Modeling). BPM=`BpmnPanel`, EM=`EventModelingPanel` 호스팅 |
| 공유 앵커 | 두 뷰가 같은 세션 그래프의 UI 노드 집합을 가리킴(복제 0) |
| 상태 | 선택 프로세스/세션 id를 ProcessPanel이 보유 → 토글 간 유지 |

**불변 규칙**:
- 상단 탭에 독립 "Event Modeling" 진입점 **0**.
- 토글 왕복 후 데이터 불일치/중복 **0**.
- 기존 EventModelingPanel·BpmnPanel 동작 회귀 **0**.

## 2. Event Modeling 형식 경량 렌더러 (US4, FR-007)

| 항목 | 계약 |
|---|---|
| 컴포넌트 | 신규 `EventModelingLane.vue` |
| 입력 | spec-039 `GET /api/graph/bpm-task/{id}/design-trace` 의 `{nodes, relationships}` |
| 레이아웃 | **가로 레인**: 좌→우 `UI → Command → Event → ReadModel`(타입별 정렬). 설계-궤적 컬럼 그래프 아님 |
| 노드 | spec-039 노드 컴포넌트(CommandNode/EventNode/UINode/ReadModel) 재사용 |
| 불변 | requirements 탭 `DesignTraceCanvas`(컬럼 그래프) **형식 그대로 유지** |

**불변 규칙**:
- Process 탭/뷰의 task 포함요소 = 가로 레인 형식.
- requirements 설계-궤적 형식 회귀 **0**.

## 3. 검증 (Playwright/수동)

1. 상단 탭에 'Event Modeling' 없음, Process 탭 토글로 BPM⇄EM 전환.
2. 토글 시 같은 UI 집합 유지(스크린샷 대비).
3. task 포함요소가 가로 레인(UI→Command→Event→ReadModel)으로 렌더.
4. requirements 설계 궤적은 기존 형식 유지.
