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

### S1. 하이브리드 인제스천 → BPM 캔버스 렌더 — ✅
- 문서 업로드(analyzer/하이브리드) → Phase 1~3 완료 → Process 탭 → Navigator 프로세스 목록 → dblclick/drag → BPM XML 렌더(swimlane, zoom).
- **라이브 결과**: input-resource PDF 2개 → 코드 분석 모드 Hybrid 인제스천 → process-gpt-bpmn-extractor(a2a)로 BPM 생성. Navigator에 프로세스 2개("자동납부 본인확인 요청 처리"·"자동납부 본인확인 결과 처리"), task 트리 + 하단 도메인 용어집 표시. dblclick → 캔버스 스윔레인 렌더 정상.
- **콘텐츠 정합성 교차검증(PDF 원문 ↔ 생성 BPM, session_id=`05ac3bb9`)**: 그래프 BpmProcess 2·BpmTask 19·BpmActor 4·Rule 43·Glossary 18.
  - proc0 "요청 처리" = 요청처리 PDF "5.To-Be 업무Flow" **12단계 1:1 정확 일치**(신청서접수→경로결정→사전등록은행조회→계좌정합성→모바일카드→카드사식별→방식결정→시도횟수→요청정보저장→외부의뢰→면제즉시처리→결과반환).
  - proc1 "결과 처리" = 결과처리 PDF **7단계 1:1 정확 일치**(결과수신→사전등록/간편결제조회→카드사보강→결과판정→이력적재→거부안내메시지→결과반환).
  - 내용·순서·요청/결과 분할 **모두 정확(PASS)**. 단 메타데이터 `source_pdf_name` 오귀속 1건 발견 → §4 B1.

### S2. Task 선택 → HybridTaskInspector — ✅
- BPM 렌더 상태에서 Task dblclick → 우측 Inspector(task.name·actors·rules·탐색 버튼).
- **라이브 결과**: Task dblclick → 우측 HybridTaskInspector 패널 정상 표시.

### S3. Task Rule 재탐색(SSE) — ✅ (단, 사용자 실제 수행은 batch=S6)
- Inspector "탐색하기"(최초) / "재탐색"(이미 rule 존재 시)(force=true) → Navigator spinner + agent reasoning 진행 → rules 추가(optimistic) + 검토 후보 표시 → (패널 닫아도 SSE 유지).
- **라이브 결과**: ① 진행상황 표시 정상 ② rule이 inspector에 나열 + 검토 후보 표시 ③ 패널 닫아도 SSE 유지 ✅.
- **토스트 정정**: 사용자가 본 "완료 토스트 없음"은 단일-task가 아니라 **batch 전체 재탐색(S6)**에서였고, batch는 토스트가 떠야 하나 arbitration이 덮어씀 → **B4**(S6 참조). (단일-task `AgentPersisted` 경로는 원래 토스트 없음: [bpmn.store.js:387-400](../../../frontend/src/features/canvas/bpmn.store.js#L387-L400))
- **Rule 매핑 관련성 교차검증(코드규칙 ↔ PDF/task)**: §4 B2 참조. 자동배정 16건 정밀도 우수, 미배정 27건 중 일부는 명백히 관련(리콜 갭).

### S4. Task 포함요소 모달(설계 궤적) — ⬜
- Inspector "포함 요소 보기" → 읽기전용 모달에 Command·Event·ReadModel 체인(**Event Modeling 형식 레인**, 043). 캔버스 불변, 닫으면 원복.

### S5. Rule 수동 이동(move/unassign/assign) — ✅
- Rule 카드 메뉴 → 다른 task로 이동 → optimistic 갱신, 양쪽 task rule count 반영. (실데이터 교차검증)
- **전제**: move/unassign ⋯ 메뉴는 **디버그 모드 전용**(`window.__setDebug(true)` 또는 `?debug=1`). assign(검토 후보 accept)은 일반 UI.
- **라이브 결과(그래프 교차검증)**:
  - **move**: "본인확인 방식 결정"(7)→"카드사 식별 및 정합성 검증"(0)으로 1건 이동 → 6 / 1. 2-task 중복 0(진짜 move), 총 엣지 16 유지 ✓
  - **unassign**: "방식 결정"에서 "인증구분 무인증('3')이 아니면…" 제거 → 6→5, 해당 규칙 linked=[], 총 엣지 16→15, 미할당 27→28 ✓
  - move·unassign·assign 모두 optimistic + 영속 + 정합성 정상.
- **결과 상태**(테스트 잔존): 방식결정 5 · 카드사식별 1 · 총 15엣지. (테스트 데이터라 잔존 무방; 필요시 정리)

### S6. Process 전체 탐색(배치) — ✅ (토스트 이슈 B4)
- Navigator "🔍 전체 탐색/재탐색" → 순차/병렬 탐색 + arbitration → **rehydrate 1회만(N+1 방지)** → 완료 토스트.
- **라이브 결과**(사용자가 실제 수행한 경로 — S3의 룰탐색은 이 batch였음): 진행상황 표시 정상, rule 16건 매핑(정밀도 검증). N+1 방지 ✓(batch 중 per-task rehydrate 스킵→`ProcessExploreEnd`서 1회: [bpmn.store.js:387-423](../../../frontend/src/features/canvas/bpmn.store.js#L387-L423)). arbitration: explored>0일 때 실행([router.py:380-384](../../../api/features/ingestion/hybrid/router.py#L380-L384)).
- **B4(낮음) → ✅수정**: **완료 토스트가 화면에 안 보임** — `ProcessExploreEnd`(완료 요약) 직후 `post_explore_arbitration`의 move 토스트(`⚖️ rule X가 A→B로 이동`)가 단일 `showToast` ref를 덮어쓰며 순차로 떴다 4s 내 사라짐 → 사용자가 보기 어려움. **수정**: 모든 토스트를 세션 이력(`toastHistory`)에 누적([bpmn.store.js showToast](../../../frontend/src/features/canvas/bpmn.store.js)) + BpmnPanel 하단우측 **🔔 알림 버튼/펼침 패널**(시간·메시지·비우기)로 펼쳐 보게 함. 휘발성 토스트는 유지(즉시 피드백), 이력은 영속(세션). 겹침 없음(FAB=상단중앙, 토스트=하단중앙, 로그=하단우측). **+후속 보강**: ① 수동 rule 액션(assign/move/unassign)도 토스트→이력 기록(`✅추가`/`⚖️이동`/`🗑️제거`) ② 이력을 **localStorage 영속**(세션 id 키 `hybrid.toastlog`)해 **새로고침에도 유지**(showToast마다 저장·rehydrate 복원·신규세션 클리어, B3와 동일 패턴).

### S7. ES 승격(promote-to-es) — ✅ (코어) / 🟡 (043 ReadModel role 별도검증)
- FAB "✨ 이벤트 스토밍 생성" → 모달(언어/UI 모드) → submit → `promote-to-es` → 새 ingestion 세션 SSE(Phase 4~5) → ES 그래프+ReadModel+UI 생성 → EM 뷰 전환.
- **라이브 결과**: 생성 완료 + EM 정상 렌더. 그래프 교차검증(session 05ac3bb9, 전부 0→생성): **BC 3 · Aggregate 7 · Command 21 · Event 37 · Policy 14 · ReadModel 11 · UI 26 · UserStory 19**.
- **BpmTask 척추**: `(:BpmTask)-[:PROMOTED_TO]->(:UserStory)` **19건** 존재(스펙 문서의 PROMOTED_FROM 표기와 달리 실제 관계명은 **PROMOTED_TO→UserStory**; 메모리 spec-039와 일치). UI attach: `(:UI)-[:ATTACHED_TO]->` Command 15 / ReadModel 11 = 26.
- **🟡 043 별도검증 필요**(E2): `ATTACHED_TO.role`(043의 유일 신규 영속 속성)이 **전부 빈 {}**, UI/ReadModel 노드에 screen/inline/system 구분 속성 없음. 043 분류는 design_trace 읽기시 산출(비영속)이라 노드 부재는 정상일 수 있으나, **inline ReadModel의 `role:'display'`는 영속이어야 함** → promote 경로가 043 UI생성을 태우는지 EM 탭 심화검증에서 확정.

### S8. BPM⇄Event Modeling 토글(043) — ⬜
- 상단 서브토글로 `Process`⇄`Processes` 전환 → 같은 데이터(hybridTasks/UI) 공유, 뷰 전용 복제 0. (Event Modeling 탭 문서와 교차)

## 4. 발견 이슈

| # | 심각도 | 증상 | 원인(추정) | 후속 |
|---|---|---|---|---|
| B1 | 낮음 → **✅수정** | **다중 PDF 업로드 시 `BpmProcess.source_pdf_name` 오귀속** — PDF 2개("요청처리"·"결과처리") 업로드 시 두 BpmProcess 모두 `...결과처리.pdf`로 찍힘. proc0("요청 처리")의 실제 내용은 요청처리 PDF에서 왔는데 메타데이터는 결과처리.pdf. (content/순서/`domain_keywords`는 정확 — 프로세스별 분리됨) | [`a2a_adapter.py _harvest_bundle_from_pdf2bpmn_neo4j`](../../../api/features/ingestion/hybrid/document_to_bpm/a2a_adapter.py): pdf2bpmn이 PDF별 `:Process`를 Neo4j에 기록 → 하베스터가 `WHERE session_id IS NULL`로 모든 `:Process`를 한 번에 수확하나 수확 후 stamp/relabel을 안 해, **다음 PDF의 harvest가 이전 Process를 재수확해 마지막 PDF의 source_pdf_name으로 일괄 재stamp** | **수정완료**: harvest가 수확한 `:Process`를 즉시 `:BpmnProcess` relabel + session_id stamp([a2a_adapter.py 수확 격리 블록](../../../api/features/ingestion/hybrid/document_to_bpm/a2a_adapter.py#L526-L548)) → PDF별 격리. 기존 세션 proc0 데이터도 교정. **재인제스천으로 E2E 검증 권장** |
| B6 | 낮음 → **✅수정** | **전체 재탐색 완료 토스트의 "Rule 매핑 총 N건" 과다 카운트** — 토스트는 "30"인데 실제 그래프 매핑은 17. `ProcessExploreEnd`가 **arbitration 이전** claim 합을 보고(같은 rule이 2프로세스/여러 task에 임시 claim되면 중복 카운트), 직후 arbitration이 dedupe(→17) | total_mappings는 task별 claim 합. arbitration 전 과다, 후 실제 | **수정완료**: `ArbitrationEnd`에서 rehydrate 후 **distinct 매핑 수로 "✅ 정리 완료 — 최종 Rule 매핑 N건" 보정 토스트**([bpmn.store.js ArbitrationEnd](../../../frontend/src/features/canvas/bpmn.store.js)). 탐색 토스트(정리 전)+최종 토스트가 B4 이력에 함께 남음 |
| E3 | 개선 → **✅적용** | **Navigator "미매핑 / Review" 섹션 접기/펼치기** (길어질 수 있어 사용자 요청) | — | **적용**: 섹션 헤더 클릭으로 토글(셰브론), 기본 펼침([NavigatorPanel.vue](../../../frontend/src/features/navigator/ui/NavigatorPanel.vue) `poolCollapsed`). 함께 BC→**"Rules by Task"** 전환(B5) |
| B5 | 낮음 → **✅수정** | **"Rules by Context"(디버그 전용)의 BC 그룹핑이 무력화** — 모달은 rule을 `context_cluster`(BC)로 그룹핑하나, BC 프리태깅이 폐기([HybridTaskInspector.vue:165](../../../frontend/src/features/canvas/ui/HybridTaskInspector.vue#L165) "각 rule이 agent로 ONE Task에 귀속되니 BC 태깅 제거")돼 **43개 전부 `context_cluster=None` → 항상 "미분류" 한 덩어리**. (별개로 "미매핑 28/매핑 15"는 Task REALIZED_BY 차원, 정상) | [HybridBcRulesModal.vue](../../../frontend/src/features/canvas/ui/HybridBcRulesModal.vue) `context_cluster` 기준 그룹핑인데 해당 속성 미설정 | **수정완료**: Navigator를 **"Rules by Task"**로 전환([NavigatorPanel.vue](../../../frontend/src/features/navigator/ui/NavigatorPanel.vue) `rulesByTask`) — task별 rule수 행, 클릭 시 모달이 그 task의 rule로 스코프([HybridBcRulesModal.vue](../../../frontend/src/features/canvas/ui/HybridBcRulesModal.vue), `bcRulesModalCluster`=taskId). 미매핑은 기존 "미매핑/Review" 섹션이 담당 |
| E1 | ~~낮음~~ → **정상(철회)** | ~~ES 승격 완료 시 EM 전체 체크~~ → **버그 아님**: 생성 과정을 **live mode로 캔버스에 실시간으로 하나씩 쌓아 표시**하므로, 완료 시점의 전체 렌더는 그 live 빌드업 결과와 일치하는 **정상 동작**. (생성 중 `isLiveMode=true`라 `onMounted` clearCanvas 미적용 → 완료 시 `stopLiveMode()`+`fetchEventModeling()`로 확정 렌더) | — | 수정 안 함. 빈 캔버스로 두면 방금 본 생성 결과가 사라짐 |
| E2 | ~~🟡조사~~ → **✅정상** | (S7) design-trace로 **043 구조 정상 확인**: task_61c580fa 트레이스 = `(:UI)-[:ATTACHED_TO]->(:Command)`(액션UI, US2) + `(:Event)-[:FEEDS]->(:ReadModel)` + `(:ReadModel)-[:RESULT_UI]->(:UI)`(screen 결과UI, US3). screen/inline/system은 **문자열 속성 아닌 구조 인코딩**(RESULT_UI=screen·role='display'=inline·없음=system) | 아까 본 `ATTACHED_TO.role` 빈값은 이 데이터 ReadModel이 전부 screen 타입(RESULT_UI 보유)이라 inline role='display' 부재일 뿐 | 시각 확정은 S4(EventModelingLane 모달). inline ReadModel 케이스는 EM S7에서 데이터 있으면 확인 |
| C2 | 낮음 → **✅수정** | **검토 후보 GWT 미포맷** — 인스펙터 "검토 가능한 후보" 카드의 Given/When/Then이 CSS 없이 raw로 표시 | 후보 GWT가 미정의 클래스 `.hti-rule__gwt` + `.hti-gwt__row` 누락([HybridTaskInspector.vue](../../../frontend/src/features/canvas/ui/HybridTaskInspector.vue#L538)). 배정 규칙은 정의된 `.hti-gwt`/`.hti-gwt__row` 사용 | **수정완료**: 후보도 `.hti-gwt`/`.hti-gwt__row` 재사용하도록 변경(HMR 반영) |
| C1 | 낮음 → **✅수정** | **인스펙터가 proc/함수명을 한글 설명보다 강조** — 비즈니스 규칙·검토 후보·매핑된 함수 3섹션 모두 `source_function`/`함수명`(proc, 예 `c300_call_zapamcom10050_proc`)을 bright+bold로 먼저 렌더, 한글 title/summary는 dim 보조로 죽어 proc명이 "타이틀"처럼 읽힘. 데이터엔 한글 title/summary 다 존재 — **CSS 시각적 우선순위 문제** | `.hti-rule__fn`/`.hti-fn__name`이 bright+bold(600), `.hti-rule__title`/`.hti-fn__summary`는 dim·일반두께([HybridTaskInspector.vue CSS](../../../frontend/src/features/canvas/ui/HybridTaskInspector.vue)). spec-036 "인지부하 최소화" 의도와 충돌 | **수정완료**(사용자 선택: 한글 설명 주연·proc muted 서브라벨): title/summary를 bright+bold 승격, source_function/함수명을 작은 회색 monospace로 강등(계속 표시). 후보는 동일 클래스라 자동 반영 |
| D1 | 낮음 → **✅수정** | **문서 근거 구절이 단어마다 줄바꿈** — PDF 추출이 시각적 줄마다 `\n`을 삽입(`'1. 자동납부 신청서\n접수\n고객 또는...'`)한 걸 CSS `white-space: pre-wrap`이 그대로 렌더 | passage `text`에 단어별 `\n` 박힘 + [HybridTaskInspector.vue](../../../frontend/src/features/canvas/ui/HybridTaskInspector.vue) `.hti-passage__body` pre-wrap | **수정완료**: `cleanPassage()` 헬퍼로 문장내 `\n`→공백 정리(불릿 `•` 줄바꿈 보존) + CSS `pre-line`. ※ 근본은 PDF 추출 아티팩트라 백엔드 정규화는 별도 후속 가능 |
| B3 | 중간 → **✅수정** | **검토 후보(task별 near-miss)가 새로고침 시 소실** — 인스펙터 "검토 가능한 후보"는 탐색 SSE(`AgentFinalMatches.rejects`)에서만 생성되고 스냅샷/rehydrate로 복원 안 됨. 콜드 리로드 후 후보 사라짐 → 재할당하려면 force 재탐색(LLM 비용 재발생) | 스냅샷 `review_queue`는 비어있고 `unassigned_rule_ids`(id만)만 영속. `rejectedRulesByTask`(task연관+점수+rationale)는 [bpmn.store.js:383-384](../../../frontend/src/features/canvas/bpmn.store.js#L383-L384) SSE 전용, rehydrate 미복원 | **수정완료**: rejects를 **localStorage 영속**(세션 id 키, `hybrid.rejects`)([bpmn.store.js](../../../frontend/src/features/canvas/bpmn.store.js) `_saveRejects`/`_loadRejects`) — set/clear/consume마다 저장, rehydrate서 복원(live 우선 merge), 신규세션 클리어. 재탐색 LLM 비용 없이 새로고침 후 후보 유지. (백엔드 Neo4j 영속은 재생성 가능한 파생상태라 과설계로 판단) |
| B2+ | 중간 ⬜ **미해결(완화 무효)** | **(B2 심화) near-miss 후보 랭킹도 리콜 실패** — "카드사 식별 및 정합성 검증" task(0건)의 검토 후보 3개는 모두 **다른 task에 이미 배정된 규칙**(간편결제 SKIP·계좌 내부인증→방식결정, 청구번호 누락→신청서접수)이라 올바른 reject. 그러나 명백히 관련된 "입력 카드사 코드…**정합성** 오류"(↔"**카드사** 식별 및 **정합성** 검증")는 **후보에조차 없음** = cosine<0.50으로 near-miss 풀에서도 탈락 | **진단**: 누락 카드 rule의 모듈(`root.zapamcom10140`)은 배정된 12건과 동일 = **모듈 prefilter 통과**. 즉 ②임베딩 코사인 단계에서 0.45 floor 미달 — 코드가 명시한 "한국어 단문 코사인 0.45~0.55 변별 약점"의 실제 사례([agentic_retriever.py](../../../api/features/ingestion/hybrid/mapper/agentic_retriever.py#L83) MIN_BL_INCLUSION). 임베딩=OpenAI API | **결정(2026-06-17)**: 원라인 버그 아닌 calibrated 튜닝 트레이드오프(floor↓ 시 task당 40+ 노이즈 reject 재발)이고, 현재 16건은 **정밀도 높음(incomplete-not-wrong)**. **완화 적용**: glossary가 실제로 해당 용어 보유(`카드사 식별 및 정합성 검증`→code['카드사','정합성'])라 회복 cap **2→4** 상향([_max_recoveries_per_task](../../../api/features/ingestion/hybrid/mapper/agentic_retriever.py#L55), `HYBRID_GLOSSARY_MAX_RECOVERIES` 기본 4) — 명백 용어겹침 rule이 2슬롯 cap에 밀리던 갭 완화, 검증기 비용 top_k 캡 불변·floor 0.45 미변경(노이즈 회귀 없음). **검증=force 전체 재탐색 후 누락 rule 재배정 확인 필요**. + UI 갭: 후보에 없는 미할당 규칙 수동 assign 정식 경로 없음 — 후속 |
| B2 | 중간 ⬜ **미해결(완화 무효)** | **Rule 매핑 리콜 갭** — 자동배정 16건은 PDF/task와 **정밀도 우수**(예: "당일 인증 3회 이상 오류"→[시도횟수확인], "기업은행 평생계좌 불가"→[계좌정합성], 방식결정 7건). 그러나 미배정 27건(전부 confidence=1.0) 중 **명백히 관련된 규칙이 0-rule task에 안 붙음**: "입력 카드사 코드 불일치 정합성 오류"→[카드사 식별 및 정합성 검증](0건), "당일 인증 횟수 조회 실패"→[시도횟수확인], "외부 인증 모듈 호출 실패"→[외부 인증기관 의뢰](0건), "간편결제사 조회 실패"→[사전등록은행/간편결제사 조회], 여러 인증구분 결정 규칙→[방식 결정] | confidence 균일 1.0이라 **임계값 기반 분리가 아님** — agentic retriever의 assign vs review-candidate 판정에서 리콜 부족. 미배정 다수는 인프라성(공통코드 조회·처리일자·전역변수 초기화)이라 정상이나, 위 일부는 진짜 누락 | **완화 시도→무효(실측)**: glossary 회복 cap 2→4 상향 후 **force 전체 재탐색했으나 누락 rule 4개 전부 여전히 미매핑**(카드사 코드 불일치·시도횟수 조회실패·외부모듈 호출실패·간편결제사 조회실패). 즉 갭이 회복-cap보다 **더 깊은 단계**(임베딩 후보선정 cosine<floor OR LLM validator reject). cap=4는 무해해 유지하나 **미해결**. 실질 보완은 review 모달/수동 assign(S5). 근본은 임베딩/validator/glossary 커버리지 후속 |

## 5. 결론

- (초안) 다음 세션에서 §2 인벤토리를 store↔라우트로 확정하고 S1~S8 라이브 검증.
- **핵심 회귀 위험**: ① 하이브리드 한정 동작(hybridSessionId 필수, legacy BPMN과 혼재 허용) ② force 재탐색은 DB 쓰기 → 패널 닫아도 SSE 유지 ③ 배치 탐색 N+1 rehydrate 방지 ④ 040 미리보기 중 mutation 차단 ⑤ 042/043 신규 스키마 0건·task=UI 불변식(기존 세션은 재인제스천 필요할 수 있음).
- 교차: ES 승격 결과는 **Data/Design/Event Modeling 탭**과, task 포함요소 모달은 **설계 궤적(012/Stories S15)**과 일관 확인.
