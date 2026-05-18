<!-- SPECKIT START -->
Active feature plan: [specs/028-aggregate-tab-drilldown/plan.md](specs/028-aggregate-tab-drilldown/plan.md)

Read the plan for technologies, project structure, constitution gates, and architectural constraints relevant to current work. Companion artifacts in the same directory:
- spec.md (what & why — Design 탭과 Aggregate 탭 연결. US1 어그리거트 속성창의 "View Detail" 버튼 → Aggregate 탭으로 전환 + 해당 어그리거트 상세 포커스. US2 어그리거트 1개 선택 상태로 탭 수동 전환 시 자동 로드/포커스. US3 네비게이터에서 어그리거트 아이콘을 캔버스에 드롭(현재는 BoundedContext만 가능)·가산·중복 없음. US4 그루핑 박스에 옅은 노란색 틴트 + `«Aggregate»` 스테레오타입. 프론트엔드 전용, 백엔드·그래프 스키마 변경 없음)
- research.md (R1 `pendingFocus`+`focusAggregate()`를 `aggregateViewer` 스토어에, 탭 전환은 기존 `provide('activeTab')`, R2 `visibleAggregateIds: Set` 어그리거트 단위 가시성 필터, R3 bcId 해석 — Design 캔버스 `parentNode`/드래그 페이로드, 폴백 `GET /api/graph/expand-with-bc/{id}`, R4 US1+US2 통합 — 마운트 시 1회 소비 루틴 + "어그리거트 정확히 1개 선택" 가드, R5 `fitView({nodes:['agg-container-<id>']})`, R6 `--color-aggregate` 저투명 틴트·테마별 값, R7 기존 `error` ref + AggregatePanel 에러/재시도 블록 재사용)
- data-model.md (Neo4j/스키마 변경 없음. §1 `aggregateViewer` 스토어 신규 상태 `visibleAggregateIds`·`pendingFocus`, 신규 액션 `fetchAggregate`·`focusAggregate`·`consumeFocus`, `fetchAggregatesForBC`/`clearAllBCs`/`filteredBoundedContexts` 변경. §3 재사용 엔드포인트 페이로드. §4 캔버스 노드 id 규칙 `agg-container-${id}`)
- contracts/ui-contract.md (신규 HTTP 엔드포인트 없음. A 크로스탭 포커스 계약 — A.1 InspectorPanel "View Detail" 프로듀서, A.2 AggregatePanel 마운트 소비 루틴, A.3 네비게이터 어그리거트 드롭. B 재사용 엔드포인트 `full-tree`·`expand-with-bc`(폴백). C 그루핑 박스 시각 계약. D 범위 외)
- quickstart.md (manual smoke: 8 scenarios — S1 디자인탭 드릴다운, S2 어그리거트 전용 버튼, S3 탭 전환 선택 이월, S4 모호/빈 선택 무변경, S5 어그리거트 드롭·가산·중복없음, S6 BC 드롭 회귀없음, S7 노란 틴트+`«Aggregate»` 스테레오타입 양 테마, S8 누락 어그리거트 명확 상태)
<!-- SPECKIT END -->
