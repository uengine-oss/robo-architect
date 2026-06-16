# Process (BPM) 탭 — 통합 검증 (초안)

> 다음 세션이 이어서 진행할 인벤토리·시나리오 **초안**. 결과는 모두 ⬜(미실행).
> 진행 방식은 [stories.md](stories.md)·[proposals.md](proposals.md) 참고(스펙+코드 인벤토리 → store↔라우트 확정 → 라이브 검증 → 실데이터 교차검증 → 이슈 기록).

- **activeTab 값**: `Process` (TopBar에서 BPM⇄Event Modeling 서브토글 → `Process`⇄`Processes`)
- **패널 컴포넌트**: [`BpmnPanel.vue`](../../../frontend/src/features/canvas/ui/BpmnPanel.vue)
- **프런트 store**: [`bpmn.store.js`](../../../frontend/src/features/canvas/bpmn.store.js)
- **백엔드**: [`canvas_graph/routes/bpmn_process.py`](../../../api/features/canvas_graph/routes/bpmn_process.py) + 하이브리드 [`ingestion/hybrid/`](../../../api/features/ingestion/hybrid/) (A2A→BPM 생성·Rule 매핑·ES 승격)
- **관련 스펙**: 011(process-flows·BPMN XML) · 022 · 036(BPMN rule-mapping) · 042(BPM↔EM 단일 그래프 두 투영) · 043(단일 Process탭+task=UI 일관성)
- **상태**: 🟡 초안 (인벤토리 완료, 라이브 검증 대기)

## 1. 탭의 의도/목표 (스펙 요약)

레거시 문서/코드에서 추출된 **BPM(Business Process Model)을 캔버스에 시각화**하고, 각 **BpmTask에 내재된 시스템 체인(Command→Event→Policy→ReadModel)**을 탐색·매핑하는 통합 뷰. 생성원은 **하이브리드 A2A 파이프라인**(외부 pdf2bpmn → BPM Process·Task 추출, ES 엔진이 Task별 Command·Event·Rule 귀속). 042/043 맥락: **단일 그래프의 BPM 투영**으로, UI를 공유 앵커로 BPM⇄Event Modeling을 **상단 서브토글**로 전환(activeTab `Process`⇄`Processes`). task ≡ UI 일관성, task 포함요소를 읽기 전용 모달(설계 궤적 재사용)로 표시. **하이브리드 한정**(비-하이브리드 무변경), 신규 영속 스키마 0건.

> ⚠️ CLAUDE.md상 042·043은 "구현·검증 완료". 인벤토리 조사에서 일부는 "(미구현 추정)"으로 나왔으나 **실제 구현 여부는 라이브에서 확정**할 것(특히 BPM⇄EM 토글, EventModelingLane 모달).

## 2. 보유 기능 목록 (코드 대조 초안)

| # | 기능 | 출처 스펙 | 핵심 컴포넌트 | 엔드포인트/store액션 |
|---|---|---|---|---|
| 1 | BPM 프로세스 목록 조회 | 011 | `BpmnPanel`, `bpmn.store` | `GET /api/graph/bpmn/process-flows` ← `fetchProcessFlows` |
| 2 | BPM XML 렌더(bpmn-js viewer) | 011 | `BpmnPanel` | `GET /api/graph/bpmn/process-flow/{startCommandId}` ← `addFlow`/`selectFlow` |
| 3 | 캔버스 zoom/pan/fit | 011 | `BpmnPanel` | `handleZoomIn/Out/FitViewport` |
| 4 | 요소 더블클릭 검사(hybrid vs legacy 분기) | 011, 036 | `BpmnPanel` | `element.dblclick` → `selectHybridTask` |
| 5 | Hybrid Task 인스펙터(우측) | 036, 042, 043 | `HybridTaskInspector.vue` | rule 조회·수동 assign/unassign/move·ES role |
| 6 | Task 포함요소 모달(설계 궤적, 읽기전용) | 042 US2 | 모달 + `DesignTraceCanvas`/`EventModelingLane` 재사용 | `GET /api/graph/bpm-task/{id}/design-trace` |
| 7 | Task Rule 재탐색(🔄 SSE) | 036, 042 | `HybridTaskInspector` | `GET /api/ingest/hybrid/task/{sid}/{taskId}/retrieve?force=true` ← `startAgentStream` |
| 8 | Process 전체 탐색(배치 SSE) | 036 | Navigator | `GET /api/ingest/hybrid/process/{sid}/{processId}/explore` ← `startProcessExplore` |
| 9 | Review 모달(매핑 승인/거부) | 036 | `HybridReviewModal.vue` | `/api/ingest/hybrid/review/{sid}/{taskId}/{ruleId}/(accept\|reject)` |
| 10 | Rule BC별 관리 모달 | 036 | `HybridBcRulesModal.vue` | 스냅샷 기반(read-only) |
| 11 | ES 승격(promote-to-es) | 042, 043 | `BpmnPanel` FAB + 모달 | `POST /api/ingest/hybrid/{sid}/promote-to-es` (ingestion SSE 재사용) |
| 12 | Drag&Drop(Navigator→Canvas) | 011, 042 | `BpmnPanel` | `addFlow`/`selectHybridProcess` (data.type 분기) |
| 13 | 하이브리드 세션 스냅샷/재수화 | 036, 042 | `bpmn.store` | `GET /api/ingest/hybrid/session/{sid}/snapshot` ← `rehydrateHybrid` |
| 14 | 중복 rule arbitration 토스트 | 042 | `BpmnPanel` | 우선순위 검증 후 `showToast` |
| 15 | (043) BPM⇄Event Modeling 서브토글 | 043 | TopBar 토글 | activeTab `Process`⇄`Processes` (라이브 확정) |

> store↔라우트 1:1 대조는 위 매핑을 다음 세션에서 curl/코드로 확정(stories 방식). 하이브리드 라우트 prefix는 `/api/ingest/hybrid/...`.

## 3. 검증 시나리오 (설계 — 다음 세션 실행)

> 전제: 백엔드/프런트 기동(`./dev.sh`), 하이브리드 세션 필요 시 문서 업로드(analyzer 모드)로 BPM 생성. `hybridSessionId`는 localStorage(`hybrid.session_id`)로 콜드로드 재수화.

### S1. 하이브리드 인제스천 → BPM 캔버스 렌더 — ⬜
- 문서 업로드(analyzer/하이브리드) → Phase 1~3 완료 → Process 탭 → Navigator 프로세스 목록 → dblclick/drag → BPM XML 렌더(swimlane, zoom).

### S2. Task 선택 → HybridTaskInspector — ⬜
- BPM 렌더 상태에서 Task dblclick → 우측 Inspector(task.name·actors·rules·탐색 버튼).

### S3. Task Rule 재탐색(SSE) — ⬜
- Inspector "🔄 재탐색"(force=true) → Navigator spinner + agent reasoning 진행 → rules 추가(optimistic) → 완료 토스트. (패널 닫아도 SSE 유지)

### S4. Task 포함요소 모달(설계 궤적) — ⬜
- Inspector "포함 요소 보기" → 읽기전용 모달에 Command·Event·ReadModel 체인(**Event Modeling 형식 레인**, 043). 캔버스 불변, 닫으면 원복.

### S5. Rule 수동 이동(move/unassign/assign) — ⬜
- Rule 카드 메뉴 → 다른 task로 이동 → optimistic 갱신, 양쪽 task rule count 반영. (실데이터 교차검증)

### S6. Process 전체 탐색(배치) — ⬜
- Navigator "🔍 전체 탐색" → 순차/병렬 탐색 + arbitration → **rehydrate 1회만(N+1 방지)** → 완료 토스트.

### S7. ES 승격(promote-to-es) — ⬜
- FAB "✨ 이벤트 스토밍 생성" → 모달(언어/UI 모드) → submit → `promote-to-es` → 새 ingestion 세션 SSE(Phase 4~5) → ES 그래프+ReadModel+UI 생성 → EM 뷰 전환.

### S8. BPM⇄Event Modeling 토글(043) — ⬜
- 상단 서브토글로 `Process`⇄`Processes` 전환 → 같은 데이터(hybridTasks/UI) 공유, 뷰 전용 복제 0. (Event Modeling 탭 문서와 교차)

## 4. 발견 이슈

| # | 심각도 | 증상 | 원인(추정) | 후속 |
|---|---|---|---|---|

## 5. 결론

- (초안) 다음 세션에서 §2 인벤토리를 store↔라우트로 확정하고 S1~S8 라이브 검증.
- **핵심 회귀 위험**: ① 하이브리드 한정 동작(hybridSessionId 필수, legacy BPMN과 혼재 허용) ② force 재탐색은 DB 쓰기 → 패널 닫아도 SSE 유지 ③ 배치 탐색 N+1 rehydrate 방지 ④ 040 미리보기 중 mutation 차단 ⑤ 042/043 신규 스키마 0건·task=UI 불변식(기존 세션은 재인제스천 필요할 수 있음).
- 교차: ES 승격 결과는 **Data/Design/Event Modeling 탭**과, task 포함요소 모달은 **설계 궤적(012/Stories S15)**과 일관 확인.
