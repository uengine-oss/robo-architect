# Process (Event Modeling) 탭 — 통합 검증 (초안)

> 다음 세션이 이어서 진행할 인벤토리·시나리오 **초안**. 결과는 모두 ⬜(미실행).
> 진행 방식은 [stories.md](stories.md)·[proposals.md](proposals.md) 참고. BPM 뷰는 [process-bpm.md](process-bpm.md)와 짝.

- **activeTab 값**: `Processes` (TopBar에서 BPM⇄Event Modeling 서브토글 → `Process`⇄`Processes`)
- **패널 컴포넌트**: [`EventModelingPanel.vue`](../../../frontend/src/features/eventModeling/ui/EventModelingPanel.vue) (대형 ~82K) + 레인 [`EventModelingLane.vue`](../../../frontend/src/features/eventModeling/ui/EventModelingLane.vue)(042)
- **프런트 store**: [`eventModeling.store.js`](../../../frontend/src/features/eventModeling/eventModeling.store.js)
- **백엔드**: [`canvas_graph/routes/event_modeling.py`](../../../api/features/canvas_graph/routes/event_modeling.py) (+ `canvas_event_triggers.py`, `gwt.py`, `/api/readmodel/{id}/cqrs`)
- **관련 스펙**: 006 · 010(swimlane) · 012(traceability) · 025(UI flow edges/Gateway·NEXT_UI) · 042(BPM↔EM 통합) · 043(task=UI, ReadModel screen/inline/system 3분류, EventModelingLane)
- **상태**: 🟡 초안 (인벤토리 완료, 라이브 검증 대기)

## 1. 탭의 의도/목표 (스펙 요약)

선택된 프로세스를 **Vertical Slice 형식(UI→Command→Event→ReadModel→UI 레인)**으로 시각화하는 이벤트 기반 설계 워크스페이스. 단일 ES 그래프의 **두 투영 중 Event Modeling 측**: BPM 뷰(사람-대면 UI 흐름, 시스템 체인 접힘)와 달리 같은 UI 노드를 앵커로 **그 아래 Command·Event·ReadModel을 펼침**. Actor→Command→Event→BC 4단 swimlane + UI-flow 레이어(025: NEXT_UI/Gateway). 043: task ≡ UI(쓰기/트리거 측) 일관화, ReadModel **screen(조회화면)/inline(소비표시)/system(없음) 3분류**, `EventModelingLane.vue`가 task 포함요소를 가로 레인으로 렌더.

> ⚠️ CLAUDE.md상 042·043 "구현·검증 완료"(task 1~N UI, ReadModel 결과UI). 인벤토리 조사 일부 "(추정)"은 라이브에서 확정.

## 2. 보유 기능 목록 (코드 대조 초안)

| # | 기능 | 출처 스펙 | 핵심 컴포넌트 | 엔드포인트/store액션 |
|---|---|---|---|---|
| 1 | 캔버스 로드(전체/프로세스별) | 006, 010 | `EventModelingPanel` | `GET /api/graph/event-modeling?bc_ids=...` ← `fetchEventModeling`/`fetchProcessList` |
| 2 | Swimlane 4단계 렌더(Actor→Command→Event→BC) | 010 | `EventModelingPanel` | 응답: `actorSwimlanes`·`interactionCommands`·`interactionReadModels`·`systemSwimlanes`·`flows` |
| 3 | Journey/Process 선택·다중선택 | 006 | Navigator + `EventModelingPanel` | `showCanvasItem`/`toggleCanvasItem` → `_rebuildCanvas` |
| 4 | 노드 클릭 → 인스펙터 | 012 | `EventModelingPanel` | `selectItem(id,type)`; ReadModel은 `GET /api/readmodel/{id}/cqrs` |
| 5 | 노드 추가(팔레트 드롭) | — | `EventModelingPanel` | `POST /api/graph/event-modeling/nodes` ← `addNode` |
| 6 | 노드 삭제 | — | 우클릭 메뉴 | `DELETE /api/graph/event-modeling/nodes/{type}/{id}` ← `deleteNode` |
| 7 | Event 드래그 재정렬(insert-shift) | — | `EventModelingPanel` | `PUT /api/graph/event-modeling/reorder` ← `moveEventToPosition` |
| 8 | Event 병렬 배치(수직 스택) | — | `EventModelingPanel` | `stackEventParallel` |
| 9 | Event 크로스-BC 이동 | — | `EventModelingPanel` | `PUT /api/graph/event-modeling/move-event` ← `moveEventToBC` |
| 10 | 관계 생성(Connect mode, 방향검증) | — | `EventModelingPanel` | `POST /api/graph/event-modeling/relations` ← `createRelation` |
| 11 | 관계 삭제 | — | 경로 우클릭 | `DELETE /api/graph/event-modeling/relations` ← `deleteRelation` |
| 12 | UI-flow 레이어(Gateway+NEXT_UI) | 025 | `EventModelingPanel` | `_read_ui_flow_layer` → `gateways`/`uiFlowEdges`; `journeyFilter`/`toggleUiFlowCurve` |
| 13 | 타입 필터(UI/Command/Event/ReadModel show/hide) | — | `EventModelingPanel` | `toggleTypeVisibility`/`isTypeVisible` |
| 14 | 검증 경고(no-emits/no-ui/no-cqrs) | — | `EventModelingPanel` | `validationWarnings` computed |
| 15 | EventModelingLane(task 포함요소 가로레인) | 042, 043 | `EventModelingLane.vue` | BPM task trace 모달에서 재사용(`/api/graph/bpm-task/{id}/design-trace`) |
| 16 | ReadModel 3분류 표시(screen/inline/system) | 043 | `EventModelingLane`/패널 | 분류는 UI 생성 단계 산출(`ui_wireframes.py`·`task_ui_helpers.py classify_readmodel`) |
| 17 | Chat 선택 동기화 / 040 미리보기 차단 | 040 | `EventModelingPanel`, store | `chatStore.setSelectedNodes`; `blockIfPreview('processes', …)` |

> store↔라우트 1:1 대조 + 관계방향 검증(`CONNECTABLE_TARGETS`/`_RELATION_MAP`)은 다음 세션 확정.

## 3. 검증 시나리오 (설계 — 다음 세션 실행)

> 전제: 백엔드/프런트 기동. ES 요소가 있어야 함(Stories S13 반영·DDD 마법사 산출물·문서 인제스천으로 시드 가능 — 현재 그래프에 Aggregate/Command/Event/ReadModel 존재).

### S1. EM 캔버스 초기 로드 — ⬜
- Processes 탭 → `fetchEventModeling` → swimlane 4단·경로 렌더, 타입필터 기본 전체 활성, 빈 그래프면 빈 상태.

### S2. Journey/Process 선택(토글·다중) — ⬜
- Navigator 항목 클릭/Ctrl+클릭 → 선택 프로세스만 필터 렌더(`_rebuildCanvas`), activeJourneyIds 갱신.

### S3. 노드 클릭 → 인스펙터 — ⬜
- Command/Event/ReadModel/UI 클릭 → 인스펙터, ReadModel은 CQRS 상세 로드, Chat 선택 동기화.

### S4. Event 재정렬/병렬/크로스-BC — ⬜
- Event 드래그(좌우=insert-shift, 하단35%=병렬, 타 BC=이동) → 연결 Command/ReadModel seq 동기화, 백엔드 반영.

### S5. 관계 생성/삭제(Connect mode) — ⬜
- connector 드래그로 노드 연결 → 방향검증(command→event 유효, command→readmodel 무효 토스트), 삭제도 확인.

### S6. UI-flow 레이어(025) — ⬜
- NEXT_UI/Gateway 엣지 렌더, journey 필터, 곡선⇄직선 토글. Gateway 다수 시 레이아웃 겹침 점검.

### S7. ReadModel 3분류(043) — ⬜
- screen(조회화면=자체 UI)/inline(소비 task 화면 표시)/system(UI 없음) 분류가 EM/레인에 맞게 표시되는지. (실데이터: 조회 US→ReadModel)

### S8. EventModelingLane(task 포함요소 레인) — ⬜
- (BPM 탭 S4와 연결) task 모달이 **컬럼 그래프가 아니라 Event Modeling 가로 레인**으로 렌더(UI액션→Command→Event→ReadModel→결과UI).

### S9. BPM⇄EM 토글 / 040 미리보기 차단 — ⬜
- 서브토글로 `Processes`⇄`Process` 전환 일관성. 미리보기 모드 중 mutation(`addNode`/`reorder`/…) silent 차단.

## 4. 발견 이슈

| # | 심각도 | 증상 | 원인(추정) | 후속 |
|---|---|---|---|---|

## 5. 결론

- (초안) 다음 세션에서 §2 인벤토리를 store↔라우트로 확정하고 S1~S9 라이브 검증.
- **핵심 회귀 위험**: ① 042 `EventModelingLane`(가로레인) — task 모달이 구 컬럼형으로 나오면 043 위반 ② 043 ReadModel 3분류(현재 부분 제어 추정) ③ 025 Gateway 레이아웃 겹침 ④ 040 미리보기 mutation 차단 ⑤ live ingestion 후 `fetchEventModeling` 재로드 시 노드 중복/손실 ⑥ Chat 선택 매핑 누락 타입.
- 교차: BPM 뷰(process-bpm.md)와 UI 노드 공유 일관성, 설계 궤적(Stories S15)·ES 승격(BPM S7) 결과와 정합.
