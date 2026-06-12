# Phase 0 Research: BPM ↔ Event Modeling 통합

모든 결정은 현재 코드 확인에 근거함. spec의 미결(NEEDS CLARIFICATION) 0건이었고, 본 문서는 plan을 위한 구현 결정(D1~D5)을 확정한다.

---

## D1. task → Command/UI 연결 경로 — **정정(2026-06-10 라이브 실측)**

**결정**: task의 Command는 **`(:BpmTask)-[:PROMOTED_TO]->(:UserStory)-[:IMPLEMENTS]->(:Command)`** 로 도달하고, UI는 거기서 `(:UI)-[:ATTACHED_TO]->(:Command)` 로 잇는다. 라우트는 대체 스키마 `(:Command)-[:PROMOTED_FROM]->(:BpmTask)` 도 함께 커버한다.

**근거(실측)**: 라이브 세션 `0dcf8cc7` 그래프 조회 결과 — `BpmTask-[:PROMOTED_TO]->UserStory` 20건, `UserStory-[:IMPLEMENTS]->Command` 20건, `UI-[:ATTACHED_TO]->Command` 18건, `Command-[:EMITS]->Event` 31건. 반면 **`Command-[:PROMOTED_FROM]->BpmTask` 는 0건(관계 자체 부재)**. 최초 가정(`PROMOTED_FROM`)이 틀렸고, [event_modeling.py](../../api/features/canvas_graph/routes/event_modeling.py)가 쓰는 BC-앵커 경로(`HAS_AGGREGATE→HAS_COMMAND→EMITS`)와 BpmTask는 `PROMOTED_TO→UserStory→IMPLEMENTS` 로만 연결된다. → 라우트의 루트 쿼리를 두 스키마 union으로 수정([bpm_task_trace.py](../../api/features/canvas_graph/routes/bpm_task_trace.py)).

**대표 UI 선택 규칙**: 한 task에 UI가 여럿이면 — (a) sequence상 가장 이른 Command에 붙은 UI를 대표로, (b) 없으면 첫 Command의 첫 UI, (c) UI가 0이면 **"System"** 라벨. 단, *모달은 대표 UI 1개로 축약하지 않고 전체 UI~체인을 보여준다* — "대표 UI"는 BPM task의 표시 라벨 용도일 뿐.

**대안 기각**: UserStory 경유(`UI→…→UserStory→PROMOTED_FROM→BpmTask`)는 간접·다대다라 모호. `ATTACHED_TO` 직결 경로가 더 정확.

---

## D2. BPM task trace 엔드포인트 — **기존 design_trace의 일반화(읽기 전용)**

**결정**: 신규 라우트 `GET /api/graph/bpm-task/{task_id}/design-trace` 를 추가한다. 로직은 [design_trace.py](../../api/features/requirements/routes/design_trace.py)와 **동일한 확장**을 쓰되, 루트 frontier만 바꾼다:

- 기존: `UserStory -[:IMPLEMENTS]-> Command` 1개를 루트로.
- 신규: `MATCH (c:Command)-[:PROMOTED_FROM]->(t:BpmTask {id, session_id})` 로 얻은 **모든 Command를 루트 frontier**로.

이후 확장(`Aggregate-[:HAS_COMMAND]`, `UI-[:ATTACHED_TO]`, `Command-[:EMITS]->Event-[:TRIGGERS]->Policy-[:INVOKES]->Command`)과 `_node`/`_attach_properties`/`DesignTraceResponse`(`{nodes, relationships, empty}`)를 그대로 공유한다.

**구현 방식**: `design_trace.py`의 frontier-확장 루프를 `_expand_trace(session, root_command_ids, depth)` 순수 헬퍼로 추출해 두 라우트가 공유(중복 0). 기존 user-story 라우트는 `_expand_trace([root_id], depth)` 호출로 동작 불변.

**근거**: 데이터·렌더 형태가 이미 동일. session_id 스코프와 `:BpmTask {id, session_id}` 매칭은 [persistence.py](../../api/features/ingestion/hybrid/event_storming_bridge/persistence.py)·`explore_service.py`의 기존 패턴과 일치.

**Empty 처리**: task에 promoted Command가 0이면 `DesignTraceResponse(empty=True, nodes=[], relationships=[])` 반환 → 프런트가 기존 empty 안내 재사용.

**대안 기각**: 프런트에서 여러 user-story design-trace를 합치는 방식은 N+1 호출·중복 dedup 부담. 단일 task 라우트가 단순.

---

## D3. 인스펙터 버튼 + 모달 — **`HybridTaskInspector.vue` + 신규 얇은 래퍼**

**결정**:
- 버튼은 [HybridTaskInspector.vue](../../frontend/src/features/canvas/ui/HybridTaskInspector.vue)에 추가(이미 `store.selectedHybridTask`로 선택된 BPM task를 보여주는 패널 — BPM 뷰의 task 클릭이 여기로 배선됨: `BpmnPanel.vue` `selectHybridTask`).
- 신규 `BpmTaskTraceModal.vue`(얇은 래퍼): 버튼 클릭 시 `GET /bpm-task/{id}/design-trace` 호출 → 응답 `{nodes, relationships, empty}`을 **무수정** [DesignTraceCanvas.vue](../../frontend/src/features/requirements/ui/DesignTraceCanvas.vue)에 `:trace` prop으로 전달. 모달 chrome(닫기/제목)만 자체 보유.

**근거**: `DesignTraceCanvas.vue` L18은 이미 `trace: Object` prop을 받고 내부 fetch가 없는 순수 표현 컴포넌트이며 `node-click`을 emit한다. 재사용에 컴포넌트 수정이 전혀 필요 없다. 노드 컴포넌트(CommandNode/EventNode/PolicyNode/AggregateNode/UINode)도 그대로 렌더.

**캔버스 불변 보장**: 모달은 오버레이로만 마운트, `bpmn-js` 뷰어/`store.renderedFlows`를 건드리지 않는다(FR-004).

---

## D4. BPM 뷰의 진실 출처 — **하이브리드 `:BpmTask`(A2A), 011 process-flows는 생성원 아님**

**결정**: 본 피처의 BPM "task"는 하이브리드 A2A 산출 `:BpmTask`다. [bpmn.store.js](../../frontend/src/features/canvas/bpmn.store.js) L32의 `/api/graph/bpmn/process-flows`(011, entry-Command 기반)는 **BPM 생성원으로 쓰지 않는다**(FR-013). BPM 뷰어는 A2A의 `bpmn_xml`을 렌더하고, task 클릭은 `selectHybridTask`로 `:BpmTask`에 매핑된다.

**근거**: spec 확정(BPM=A2A 단일 경로). `BpmnPanel.vue`가 이미 `hybridTasks`/`selectedHybridTaskId`를 1급으로 다루고 있어 추가 배선 불필요.

**범위 메모**: 011 `process-flows`/`process-flow/{id}` 라우트·소비자 제거 여부는 본 피처 범위 밖(별도 정리). 본 피처는 그것을 *생성원에서 배제*만 하고 삭제하지 않는다 — 회귀 위험 차단.

---

## D5. "Big picture" 제거 범위 + 비탭 소비자 처리

**전수 참조**(코드 확인):
- 탭/패널: `App.vue` L6·L59, `TopBar.vue` L4·L29·L108~114, `BigPicturePanel.vue`(파일), `bigpicture.store.js`(파일), `main.css` `.big-picture-panel` 스타일.
- 백엔드: `/api/graph/bigpicture-timeline`(store가 호출).
- **비탭 소비자 2곳**:
  - `TreeNode.vue` L33·L435·L613 — `currentTab === 'Big picture'` 분기에서만 `bigPictureStore.swimlanes`/`addBCWithOutboundFlow` 사용.
  - `ExportDocumentTemplate.vue` L6·L10·L87 — `swimlanes = bigPictureStore.swimlanes`.

**결정**:
1. **탭/패널/스토어/스타일/백엔드 엔드포인트 삭제** — 진입점이 이미 숨김이라 사용자 영향 0.
2. **`TreeNode.vue`** — 탭이 사라지면 `currentTab === 'Big picture'` 분기는 도달 불가 dead-branch. 해당 `else if` 두 곳과 import만 삭제(다른 탭 동작 불변).
3. **`ExportDocumentTemplate.vue`** — `swimlanes`가 채우던 export 섹션은 "Big picture" 투영 그 자체이므로 **해당 섹션을 export에서 제거**(개념 제거와 일관). 의존 import/computed 삭제.

**확인 필요(사용자 컨펌 포인트, 비차단)**: D5-3은 export 산출물에서 swimlane(빅픽처) 섹션을 *드러내는* 변경이다. 사용자가 "Big picture 의미 없음 → 제거" 방침을 export까지 적용하길 원한다는 합리적 기본값으로 진행하되, quickstart Q6에서 회귀 확인 시 명시한다. 만약 export에 빅픽처 섹션을 남기길 원하면 대체 출처는 canvas/event-modeling swimlane 투영으로 전환.

**근거**: 미사용 코드·인지부하 제거(헌법 정신·인지부하 최소화 제약). 비탭 소비자가 conditional dead-branch라 회귀 위험 낮음.

---

## 종합

- 신규 그래프 스키마/관계 **0건** — 전부 기존 영속 엣지의 읽기.
- 신규 백엔드 라우트 1개(읽기), 프런트 신규 1개(모달 래퍼), 재사용 2개(`design_trace` 헬퍼, `DesignTraceCanvas`), 삭제 2개(빅픽처).
- LLM 호출·스트리밍·propose/confirm **해당 없음** → Constitution PASS 유지.
