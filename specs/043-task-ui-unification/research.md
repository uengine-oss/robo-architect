# Phase 0 Research: task=UI 통합

코드 확인 기반 결정(D1~D6). spec의 명확화 3건은 specify 단계에서 해소됨.

---

## D1. task=UI(트리거) — **신규 스키마 0, UI를 줄이는 방향**

**결정**: [ui_wireframes.py](../../api/features/ingestion/workflow/phases/ui_wireframes.py)의 UI 생성을 **Command 루프 → task 그룹**으로 바꾼다. 각 task의 (policy-invoked 아닌) Command들을 모아 **트리거 1개만** 골라 UI 생성(`_create_command_ui`), 나머지 Command엔 UI 미생성.

**근거**: 현재 L989~1020은 `BC→Aggregate→Command`로 돌며 Command마다 UI 생성. Command는 `task_id`를 가짐([contracts.py](../../api/features/ingestion/hybrid/contracts.py) `CommandDTO.task_id`)이므로 **task_id로 그룹핑**이 자명. 이미 `policy_invoked_command_ids`를 스킵하는 로직(L998)이 있어 "사람 트리거가 아닌 Command 배제"의 토대가 존재. UI를 *줄이는* 변경이라 **기존 `:UI`/`ATTACHED_TO`/`HAS_UI`만 사용 → 신규 라벨/관계 0**.

**대안 기각**: UI를 task 노드에 직접 ATTACHED — task↔Command 관계 신설 필요(스키마 증가). 트리거 Command에 붙이면 기존 `UI-ATTACHED_TO->Command` 그대로 재사용.

---

## D2. 트리거 Command 선택 — **LLM 휴리스틱 + entry 폴백** (FR-008)

**결정**: task의 Command 후보 중 "사람이 실제 조작하는" 것을 **in-process LLM(`get_llm`)** 으로 판정해 그 Command에 트리거 UI 부착. 판정 실패/모호 시 **entry(시퀀스 첫/대표) Command**로 폴백.

**근거**: 사용자 확정(휴리스틱). task 1개당 1회 호출이라 비용은 기존 Command별 와이어프레임 생성보다 **감소**(task 수 ≤ Command 수). 프롬프트 입력 = task명·설명 + 후보 Command 목록(name/description) + 해당 US의 ui_description.

**출력 계약**: `{trigger_command_id, confidence, rationale}`. confidence 낮으면 entry 폴백 + 통합 뷰에 표식(propose).

---

## D3. ReadModel — 표시 vs 조회화면 (FR-009) + 표현

**결정**:
- **소비 표시**: action 화면이 조회하는 ReadModel은 그 task UI에 `(:UI)-[:ATTACHED_TO {role:'display'}]->(:ReadModel)` 로 연결(표시 데이터, N:M).
- **조회/검색 화면**: LLM이 "사람이 직접 보는 조회/검색 화면"으로 판정한 ReadModel만 자체 UI 승격 — 기존 `(:UI)-[:ATTACHED_TO]->(:ReadModel)`(role 없음 = screen).
- "ReadModel당 무조건 UI 생성"(현 `_create_readmodel_ui` 무조건 호출) 제거 → 판정 통과분만.

**표현 결정(Constitution)**: 표시 vs 화면 구분은 **`ATTACHED_TO` 엣지의 `role` 속성**(`display`/`screen` 또는 무속성=screen)으로. **신규 라벨/관계 0**, 속성만 추가 → I·II 충족. (event_modeling.py가 `(rmUi:UI)-[:ATTACHED_TO]->(rm)`를 읽으므로, role 무시하면 기존 동작 보존·점진 적용 가능.)

**판정 입력**: ReadModel name/description + `trigger_event_keys` + query_keys + 그것을 조회하는 화면 맥락. 출력 `{is_query_screen: bool, host_task_id?, rationale}`.

**대안 기각**: 신규 `DISPLAYS` 관계 — 라벨/관계 증가. `ATTACHED_TO`+role이 최소.

---

## D4. propose→confirm 지점 (Constitution IV)

**결정**: 트리거/조회 판정은 **생성 단계에서 자동 적용하되(기존 와이어프레임 생성과 동급), 결과를 통합 Process 뷰에서 사용자에게 노출**한다. 사용자는 (a) 트리거 UI가 잘못 붙은 task를 다른 Command로 이동, (b) 표시/조회화면 오판을 토글로 교정할 수 있다. per-item 동기 confirm은 인제스천 SSE 흐름을 막으므로 **"생성 후 통합 뷰에서 propose→수정"** 패턴.

**근거**: 인제스천은 본질적으로 자동 생성. 기존에도 와이어프레임은 자동 생성 후 인스펙터에서 수정. 동일 패턴 유지가 일관적.

---

## D5. 단일 Process 탭 + 토글 (US1)

**결정**: 신규 `ProcessPanel.vue`(래퍼)가 내부 토글로 `BpmnPanel`(BPM)·`EventModelingPanel`(EM)을 전환. [App.vue](../../frontend/src/App.vue) `tabComponents`에서 `'Process'` → `ProcessPanel`, `'Event Modeling'` 항목 제거. [TopBar.vue](../../frontend/src/app/layout/TopBar.vue) `tabs` 배열에서 'Event Modeling' 제거.

**근거**: 두 패널 모두 기존 컴포넌트라 래퍼+토글로 최소 변경. 두 뷰의 UI 앵커 공유는 같은 세션 그래프를 읽으므로 자연 성립(BpmnPanel=BPM task/UI, EventModelingPanel=UI+체인).

**상태 공유**: 선택된 프로세스/세션 id를 ProcessPanel이 보유해 토글 간 유지.

---

## D6. Event Modeling 형식 경량 렌더러 (US4)

**결정**: 신규 `EventModelingLane.vue` — spec-042 `GET /api/graph/bpm-task/{id}/design-trace`의 `{nodes, relationships}`를 입력받아 **가로 레인(UI→Command→Event→ReadModel)** 으로 렌더. `DesignTraceCanvas`(컬럼 그래프)는 requirements용으로 유지.

**근거**: [EventModelingPanel.vue](../../frontend/src/features/eventModeling/ui/EventModelingPanel.vue)는 `useEventModelingStore` 강결합 싱글톤(actor swimlane·sequence)이라 단일 task 스코프 재사용 곤란. trace 데이터는 이미 있으므로 레인 레이아웃만 신규(node 타입별 열 → 좌→우 UI/Command/Event/ReadModel 시퀀스).

**재사용**: spec-042 trace 라우트·노드 컴포넌트(CommandNode/EventNode/UINode 등) 재사용, 레이아웃만 EM 스타일로.

---

## 종합

- 신규 Neo4j **라벨/관계 0** (ReadModel role 속성만, 선택적·후방호환).
- 백엔드: `ui_wireframes.py` task-그룹 재구성 + LLM 판정 2종.
- 프런트: ProcessPanel(토글)·EventModelingLane(EM 렌더) 신규, 나머지 재사용.
- 인제스천 변경 → **기존 세션 재인제스천 필요**. Command/Event·A2A BPM 불변.
