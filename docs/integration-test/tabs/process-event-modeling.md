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

### S1. EM 캔버스 초기 로드 — ✅
- Processes 탭 → `fetchEventModeling` → swimlane 4단·경로 렌더, 타입필터 기본 전체 활성, 빈 그래프면 빈 상태.
- **라이브 결과**(BPM S7 승격 데이터): BPM⇄EM 토글로 뷰 전환 정상, **swimlane 4단(Actor→Command→Event→BC/ReadModel) 구조 정상**, 타입필터 정상(기본 전체), UI→Command→Event→ReadModel 흐름선 정상, **토글 전환 매끄러움**(S9 일부 선확인).

### S2. Journey/Process 선택(토글·다중) — ✅
- Navigator 항목 클릭/Ctrl+클릭 → 선택 프로세스만 필터 렌더(`_rebuildCanvas`), activeJourneyIds 갱신.
- **라이브 결과**: Navigator "User Journeys" 섹션에 엔트리 Command 기준 프로세스 체인 **12개** 렌더(현 그래프 uiFlowEdges=0이라 journey 묶음 없이 process 항목; entryCmds=21−9 policy-invoked=12, [eventModeling.store.js `_buildProcessChains`](../../../frontend/src/features/eventModeling/eventModeling.store.js#L97)). **단일 클릭→`showCanvasItem` 캔버스 교체 정상**(그 프로세스 한 줄기만), **Ctrl/⌘+클릭→`toggleCanvasItem` 다중 그룹 체크/빼기 정상**(여러 프로세스 동시 표시, 체크마크 누적/제거). `_rebuildCanvas`로 캔버스 노드 집합이 선택 프로세스 합집합으로 재구성됨.
- **혼동 주의(비이슈)**: S2의 "토글"은 **프로세스 단위 캔버스 구성 토글**(User Journeys 항목)이고, 노드 **타입별 show/hide 필터**(기능 #13 `toggleTypeVisibility`)는 별개 — 후자는 이미 검증됨.

### S3. 노드 클릭 → 인스펙터 — 🟡 (로드 정상, 2건 발견)
- Command/Event/ReadModel/UI 클릭 → 인스펙터, ReadModel은 CQRS 상세 로드, Chat 선택 동기화.
- **라이브 결과**: 타입별 인스펙터 로드 정상. 단 2건 발견 → §4 EM1·EM2.

## 4. 발견 이슈

| # | 심각도 | 증상 | 원인(추정) | 후속 |
|---|---|---|---|---|
| EM10 | 중간 → **✅수정(자유좌표 저장)** | **노드 팔레트로 수동 추가·배치한 노드가 "배치한 대로" 영속 안 됨** — 어느 레인/열에 놓아도 비-Event는 위치가 새로고침에 유지 안 됨 | EM 레이아웃이 **관계 파생**(열=Event sequence, 레인=BC/actor)이라 관계 없는 노드는 orphan → `_rebuildCanvas`가 체인 step만 렌더 → 미표시. 백엔드 `/nodes`: event만 `sequence` 저장, command/readmodel/ui는 미저장 | **결정 변경(사용자)**: 처음엔 "자동 관계 생성"(앵커 Event에 EMITS/FEEDS/ATTACHED_TO)으로 구현했으나, **한 BC 다중 프로세스에서 옆 프로세스가 열리는 문제 + 의도않은 관계가 모델에 영속(노드 삭제 시에만 제거)되는 오염** 때문에 **자유좌표 저장으로 전환**(연결은 사용자가 Connect 모드로 직접). **수정완료**: ① add([event_modeling.py `add_event_modeling_node`](../../../api/features/canvas_graph/routes/event_modeling.py))가 **자동 관계 0건**, 4타입 모두 노드에 `sequence` 직접 저장(Command는 구조상 필수인 Aggregate 귀속만 — `anchorEventId`의 Aggregate>BC 첫 Agg). ② read([`get_event_modeling`](../../../api/features/canvas_graph/routes/event_modeling.py))가 loose 노드를 stored sequence로 배치 — command(EMITS 없으면 `unlinked_offset`→stored), loose ReadModel(CQRS 없으면 skip→stored seq 포함), **orphan UI fetch**(`HAS_UI` & no `ATTACHED_TO`, 기존 read는 가져오지도 않았음), seq 압축에 loose seq 포함. ③ frontend [`_buildProcessChains`](../../../frontend/src/features/eventModeling/eventModeling.store.js)가 **어떤 체인에도 안 잡힌 loose 노드(event/readmodel/ui)를 단일-노드 체인으로 emit** → 기존 렌더/선택 기구 재사용(loose command는 이미 entry 체인). `addNode`/`refreshKeepingSelection`의 activeItemIds 체인 등록 보강과 합쳐 편집 저장에도 유지. API검증: 4타입 add→**관계 0건**·stored seq 배치·EM read 표출 확인, 오염 없음(flows 베이스라인 유지). **+Navigator 보강**: loose 단일-노드 체인이 "User Journeys" 목록에 개별 항목으로 쏟아지던 것 — loose 체인에 `loose:true` 태깅 후 [NavigatorPanel](../../../frontend/src/features/navigator/ui/NavigatorPanel.vue) `emJourneys`(=journeyChains 중 비-loose)로 목록·카운트 필터(실제 프로세스만 표시). loose는 캔버스 렌더용으로만 유지(Load All/추가 직후 표출). **+loose X 드래그**: 잘못 놓은 미연결 노드를 삭제·재추가 없이 끌어 옮기게 — Event만 X이동 가능하던 것을 **loose(미연결) Command/ReadModel/UI도 X 드래그**(저장 sequence만 갱신, insert-shift·종속 없음) 허용. 연결된 노드는 Event 기준 슬라이스 정렬 유지라 드래그 비활성(`looseNodeIds`=flows로 판정). 신규 [`PUT /node-sequence`](../../../api/features/canvas_graph/routes/event_modeling.py) + store `moveNodeToSequence` + 카드 `draggable`(loose·비-connect만)·`onLaneDrop`. API검증: seq 2→6 영속·표출 ✅. **+2버그 수정(드래그 안 됨)**: ① 레인 dragover `dropEffect='copy'`인데 node-move 드래그가 `effectAllowed='move'`라 **효과 불일치로 drop 미발화** → `effectAllowed='all'`로 수정. ② loose 노드 stored가 **이벤트 timeline 압축(seq_remap)에 휘말려 엉뚱한 열로** → loose Command/RM/UI는 압축 비대상으로 분리, **stored를 표시열로 직접** 사용(`loose_cmd_stored` 후단 대입, used_seqs 제외). API검증: orphan event seq=34 압축 상황에서도 loose c3→3·r10→10·드래그 c3→7 정확 ✅. 라이브 확인 대기 |
| EM1 | 중간 → **✅수정** | **ReadModel CQRS 상세가 인스펙터에 표시 안 됨** — ReadModel 클릭 시 CQRS(어떤 Event가 이 ReadModel에 INSERT/UPDATE하는지·필드 매핑·where조건)가 안 보임 | 데이터·엔드포인트는 정상(`/api/readmodel/{id}/cqrs`가 operations 반환), store `selectItem`이 `selectedItemDetail`로 fetch까지 함([eventModeling.store.js:450-453](../../../frontend/src/features/eventModeling/eventModeling.store.js#L450-L453)). **그러나 표시 컴포넌트 부재** — EM 인스펙터는 `InspectorPanel`인데 CQRS 섹션 없음, EM 패널 템플릿에도 inline 렌더 없음 → fetch 결과 orphaned. 전용 편집기 `ReadModelCQRSConfigModal`/`ReadModelCQRSEditor`는 존재하나(orphaned) 노드 클릭에 미연결 | **수정완료**: InspectorPanel **탭 바 우측에 `⚡ CQRS` 버튼**(ReadModel일 때, Properties/출처 탭과 나란히·우측정렬)→`ReadModelCQRSConfigModal` 모달 오픈([InspectorPanel.vue](../../../frontend/src/features/canvas/ui/InspectorPanel.vue)). 읽기 엔드포인트(`/cqrs`·`/cqrs/events`) 200. 공유 컴포넌트라 EM·Design 공통. (인라인 시도는 모달 내 provisioning 라디오가 인스펙터 필드와 sync 안 돼 모달로 확정 — provisioning 결정/영속은 인스펙터 properties 필드, 모달은 CQRS 연산 표시·편집) |
| EM2 | ~~낮음~~ → **정상(해소)** | ~~UI Template이 HTML 코드로~~ → **Preview 탭에서 시각 미리보기 정상 표시**(사용자 재확인). 아까는 다른 탭(properties/template)을 본 것. UI 노드 sceneGraph 풍부(50~114KB)로 와이어프레임 렌더됨 | — | 비이슈 |
| EM7 | 낮음 → **✅수정** | **인스펙터 헤더 Reload 버튼이 세로로 위 치우침** — 아이콘만 있는 Reload(↻)가 텍스트 Save(저장)보다 위에 떠 보임 | `.inspector-panel__actions`에 CSS 규칙 부재 → 버튼들이 inline-block **baseline 정렬**(아이콘 vs 텍스트 baseline 차이) | **수정**: actions=`flex+align-items:center`, btn=`inline-flex` 중앙정렬([InspectorPanel.vue:5319](../../../frontend/src/features/canvas/ui/InspectorPanel.vue#L5319)). 공유 컴포넌트라 Design 탭도 개선 |
| EM6 | 개선 → **✅적용** | **UI 인스펙터가 Preview 탭으로 포커스되지 않음** — UI 노드 인스펙터를 열면 Properties로 떨어짐(시각 미리보기 아님) | 노드 전환 시 `nodeLabel`이 비동기 로드라 `props.initialTab` watcher가 **옛 라벨로 normalize → 'properties'** 폴백, label이 'UI'로 와도 재적용 없음 ([InspectorPanel.vue:680/695](../../../frontend/src/features/canvas/ui/InspectorPanel.vue#L680)) | **수정**: `nodeLabel` 해소 시 `initialTab` 재적용 watcher 추가 → UI는 Preview로 포커스. 라벨 변경 시에만 발화(수동 탭 전환 보존). 공유 컴포넌트라 Design 탭도 일관 |
| EM4 | 중간 → **✅수정** | **UI displayName 저장 거부** — UI 노드 displayName 수정·저장 시 `field not allowed for UI: displayName` 에러 | [`model_change_application.py:331` `_ALLOWED_UPDATE_FIELDS_BY_LABEL`](../../../api/features/model_modifier/model_change_application.py#L331)에서 **UI만 displayName이 허용목록에 없음**(Command/Event/Policy/Aggregate/ReadModel/BC는 다 허용, UI는 wireframe/attachment 메타만) | **수정완료**: UI 허용목록에 `displayName` 추가 |
| EM5 | 높음 → **✅수정** | **Event 인스펙터 열기 시 500 (expand-with-bc KeyError)** — Event "본인확인 방식 결정 실패" 등 인스펙터 진입 시 `GET /api/graph/expand-with-bc/{id}` 500 | **cross_bc Policy 6/14개가 `id` 프로퍼티 없이 생성**됨([promote_to_es.py:393 `_create_cross_bc_policies`](../../../api/features/ingestion/hybrid/event_storming_bridge/promote_to_es.py#L393)가 name/kind/bc_id만 SET, `id` 누락) → expand-with-bc가 `record["pol"]["id"]` 접근 시 KeyError | **수정완료 3갈래**: ①승격 쿼리에 `ON CREATE SET p.id = randomUUID()` ②기존 6개 backfill(randomUUID) ③[expand-with-bc Event 브랜치](../../../api/features/canvas_graph/routes/canvas_expansion.py) id 접근 방어(`.get("id")`, 없으면 skip). 재호출 200 확인 |
| EM3 | 중간 → **✅수정** | **인스펙터 편집이 그래프엔 저장되나 EM 캔버스에 반영 안 됨(되돌아 보임)** — Command `CheckAuthenticationAttemptLimit` displayName을 "…Test"로 변경→저장 시 캔버스가 옛값으로 리렌더. **그래프 교차검증: 새 값 영속됨**(updatedAt 갱신) = 저장은 성공, **캔버스 미갱신**이 원인 | EM·Design 둘 다 `@updated="() => {}"`(no-op)이고 InspectorPanel은 `canvasStore` 중심(EM은 `eventModeling.store` 별개)이라 편집 후 EM 캔버스가 stale | **수정완료**: store에 **`refreshKeepingSelection()`**(데이터 refetch + **선택 보존** 재구성, [eventModeling.store.js](../../../frontend/src/features/eventModeling/eventModeling.store.js))추가, EM `@updated`→`onInspectorUpdated`([EventModelingPanel.vue](../../../frontend/src/features/eventModeling/ui/EventModelingPanel.vue))에 배선. **+ 캔버스 재구성 시 스크롤(pan)이 0으로 리셋되던 것**도 보정 — 편집 전 `scrollLeft/Top` 저장→refetch→`nextTick` 후 복원(줌 `zoomLevel`은 재구성이 안 건드려 유지). 편집→그래프 저장→캔버스 즉시 반영 + **보던 위치·줌 유지**. (저장 자체는 EM/Design 동일 경로로 원래 정상) |

### S4. Event 재정렬/병렬/크로스-BC — ✅
- Event 드래그(좌우=insert-shift, 하단35%=병렬, 타 BC=이동) → 연결 Command/ReadModel seq 동기화, 백엔드 반영.
- **라이브 결과**: cross-BC ✅. 동일 BC 재정렬(EM8 수정 후 ✅) · 병렬(EM9 수정 후 ✅) · **새로고침 영속 ✅** · 연결 Command/RM/UI 동반 ✅ · 회귀 없음. (EM8: 빈 레인 드롭 재정렬 미처리 / EM9: 읽기가 이벤트 열을 Command 기준으로 덮어쓰던 방향 역전 수정)

## 4. 발견 이슈 (추가)

| # | 심각도 | 증상 | 원인 | 후속 |
|---|---|---|---|---|
| EM9 | 높음 → **✅수정** | **Event 재정렬/병렬이 새로고침 시 되돌아감** — 그래프엔 `evt.sequence` 저장되나(영속 OK), 읽기가 무시 | **읽기 방향 역전**: `cmd_sequence=min(연결 Event seq)`로 Command가 Event를 따라오게 해놓고, 그 다음 `evt_col=cmd_sequence`로 **이벤트 표시 열을 다시 Command 기준으로 덮어씀**([event_modeling.py:446](../../../api/features/canvas_graph/routes/event_modeling.py#L446)) → 같은 Command 이벤트가 한 열에 묶여 개별 이동 무시. + persist가 병렬(같은 seq)을 고유 1..N로 펼침 | **수정**: ① 읽기 `evt_col=자기 storedSequence`(Event authoritative, Command/RM/UI는 min으로 따라옴) ② [`_persistEventSequences`](../../../frontend/src/features/eventModeling/eventModeling.store.js) dense-rank로 **같은 display seq=같은 저장 seq**(병렬 보존). 라운드트립 검증: storedSeq 변경이 읽기 display에 반영됨 |
| EM8 | 중간 → **✅수정** | **동일 BC 내 Event 시퀀스 재정렬이 안 됨**(cross-BC는 정상) | Event를 **빈 레인 공간에 드롭**하면 `onBcLaneDrop`이 처리하는데 거긴 **cross-BC 이동만** 있고 same-BC 재정렬이 없음(이벤트 카드에 정확히 드롭=`onEvtDrop`만 reorder). 빈 공간 드롭 시 아무 동작 안 함 | **수정**: [`onBcLaneDrop`](../../../frontend/src/features/eventModeling/ui/EventModelingPanel.vue)에 same-BC 분기 추가 — 드롭 X로 시퀀스 산출(`(x-HEADER_W)/SEQ_STEP_W`, 팔레트 드롭과 동일 math) → `moveEventToPosition` 호출 |

### S5. 관계 생성/삭제(Connect mode) — ✅
- connector 드래그로 노드 연결 → 방향검증(command→event 유효, command→readmodel 무효 토스트), 삭제도 확인.
- **라이브 결과**: 연결 거부(방향 검증) 정상. **Command→UI 거부도 정상** — 모델이 방향성 체인(UI→Command→Event→ReadModel→UI)이라 UI는 Command에 **UI→Command(ATTACHED_TO)**로 붙음(Command→UI는 없음). 사용자 확인: 현행 유지. 연결 모드 전부 정상.

### S6. UI-flow 레이어(025) — ✅ (임시데이터 검증)
- NEXT_UI/Gateway 엣지 렌더, journey 필터, 곡선⇄직선 토글. Gateway 다수 시 레이아웃 겹침 점검.
- **초기 상태**: 그래프에 **NEXT_UI 0·Gateway 0**(하이브리드 승격은 vertical slice만 생성, 화면간 흐름·Gateway는 025라는 별도 생성원). 실데이터로는 검증 불가(버그 아님).
- **임시데이터 검증**: BC `ExternalIdentityVerification` 아래 임시 `Journey`+`JourneyStep`(기존 UI 3개 SHOWS)+gateway 분기+`NEXT` 엣지 시딩(`_read_ui_flow_layer`→`read_ui_flow_for_bcs` 경로). EM 읽기 `gateways=1`(exclusive '인증 결과 분기')·`uiFlowEdges=3`(UI→GW, GW→UI[인증 성공], GW→UI[인증 실패]). **라이브: 다이아몬드 게이트웨이 노드 + NEXT_UI 흐름선 + 조건 라벨 정상 렌더, journey 필터 노출, 곡선/직선 토글 정상** ✅(사용자 확인). 검증 후 임시데이터 제거(베이스라인 복원).

### S7. ReadModel 3분류(043) — ✅ (screen 실데이터 + inline/system 임시데이터)
- screen(조회화면=자체 UI)/inline(소비 task 화면 표시)/system(UI 없음) 분류가 EM/레인에 맞게 표시되는지.
- **분류 결정 요소(영속)**: 노드 문자열 속성 아님. **`(:UI)-[:ATTACHED_TO]->(:ReadModel)` 관계의 유무 + `role` 속성** 단 2비트 — role=null → **screen**(자체 결과 화면), role='display' → **inline**(소비 화면에 표시), ATTACHED_TO UI 없음 → **system**. 생성 단계 [task_ui_helpers.py `classify_readmodel`](../../../api/features/ingestion/workflow/phases/task_ui_helpers.py#L80)(LLM이 name/desc/query_keys로 판정)이 이 구조를 결정. 읽기 [design_trace.py:219](../../../api/features/requirements/routes/design_trace.py#L219)가 role로 응답관계(`RESULT_UI`/`DISPLAYED_ON`/`FEEDS`)로 환원.
- **screen**: 실데이터 11개 RM 모두 `ATTACHED_TO`(role=null) → `RESULT_UI`로 결과UI 보유. S8에서 확정.
- **inline/system(임시데이터)**: task_a66306d0 레인에 3종 동시 시딩 — RM `2a4a3c39`에 `role='display'` SET(→inline `DISPLAYED_ON`), 임시 RM을 UI없이 CQRS→FEEDS만 연결(→system). 백엔드 trace 교차검증: `RESULT_UI`1(screen)·`DISPLAYED_ON`1(inline)·system RM은 `FEEDS`만 — 정확 일치. **단 프런트 레인이 screen/inline을 동일 렌더 → EM11 발견·수정**(아래). 검증 후 임시데이터 제거.

### S8. EventModelingLane(task 포함요소 레인) — ✅
- (BPM 탭 S4와 연결) task 모달이 **컬럼 그래프가 아니라 Event Modeling 가로 레인**으로 렌더(UI액션→Command→Event→ReadModel→결과UI).
- **라이브 결과(스크린샷 + 백엔드 design-trace 교차검증, task_a66306d0)**: 모달 "포함 요소·설계 궤적"이 **가로 레인 형식**으로 정확히 렌더 — 액션UI→Command(2)→Event(4)→ReadModel(2)→결과UI(2) + Policy 체인. 백엔드 trace(`ATTACHED_TO`1·`EMITS`4·`FEEDS`4·`RESULT_UI`2·`TRIGGERS`1·`INVOKES`1)와 노드/관계 수 정확 일치. 043 US4(가로레인)·US3(screen 결과UI) 충족. (Policy=EM5에서 id 수정한 cross-BC 정책 — 정상 trace 확인)

### S9. BPM⇄EM 토글 / 040 미리보기 차단 — ✅
- 서브토글로 `Processes`⇄`Process` 전환 일관성. 미리보기 모드 중 mutation(`addNode`/`reorder`/…) silent 차단.
- **라이브 결과**: 토글 전환 일관성 정상(S1에서 확인 — 같은 데이터 공유·매끄러움). 040 미리보기 mutation 차단(`blockIfPreview('processes',…)`) **다른 세션에서 정상 확인**.

## 4. 발견 이슈

| # | 심각도 | 증상 | 원인(추정) | 후속 |
|---|---|---|---|---|
| EM16 | 높음 → **✅수정** | **재승격(ES 승격 재실행) 시 기존 ES를 안 비우고 위에 덧쌓여 전부 2배 중복** — Command/Event/ReadModel/UI 같은 이름이 2개씩, maxSequence 29→54. 중복 상태에서 배치/이동 등 모든 게 꼬임 | 승격 POST([router.py `promote_start`](../../../api/features/ingestion/hybrid/router.py#L504))가 ingestion 세션만 만들고 **clear 안 함**. `clear_promoted_nodes`는 DELETE/`/reset`에서만 호출 → 같은 세션 재승격 시 중복 | **수정완료**: `promote_start` 시작에 `clear_promoted_nodes(session_id)` 추가 → 재승격이 idempotent(기존 ES 비우고 새로 생성, BpmTask 척추 미포함·`ALL_CLEARED_LABELS`만). 현재 중복분은 다음 재승격에서 자동 정리, untagged 수동잔재(New*)는 별도 제거 |
| EM15 | 중간 → **✅수정(거부+알림)** | **연결 시 기존 요소가 사라지거나 대체됨** — 이미 UI 붙은 Command/ReadModel에 새 UI 연결, 또는 이미 발행 Command 있는 Event에 새 Command 연결 시 기존 게 캔버스에서 사라짐 | EM 읽기가 **Command/ReadModel당 UI 1개**(`if cmd_id not in cmd_uis` 첫 UI만)·**Event당 발행 Command 1개**(`event_to_cmd` 마지막만)로 표시 → 2번째 부착은 cmd_uis에도·orphan 쿼리에도 안 잡혀 **표시에서 소실**(데이터는 그래프에 둘 다 존재, 표시 충돌). 사용자 결정: **거부+알림** | **수정완료**: `create_relation`이 카디널리티 초과(2번째 UI/Command·2번째 UI/ReadModel·UI당 2번째 대상·2번째 발행 Command) 시 `{error, reason:'cardinality'}` 반환(idempotent 재연결은 허용). 프런트 `createRelation`이 error 응답 시 optimistic flow 제거+토스트. API검증: RM 중복UI·이미연결 UI 거부, 빈 Command 성공 ✅ |
| EM14 | 중간 → **✅수정** | **노드 추가·드래그 시 드롭한 열이 아니라 한 칸 오른쪽(사이)에 떨어짐** — 기존 요소 우측에 추가하면 두 요소 사이로 들어가고, 끝/특정 열로 못 옮김(loose를 non-loose 열과 정렬 불가). 모든 레인 공통 | 드롭 열 공식 `Math.round((x-HEADER_W)/SEQ_STEP_W)+1`의 off-by-one — `seqX(seq)=HEADER_W+(seq-1)*STEP+STEP/2`의 올바른 역함수는 `floor(...)+1`인데 `round`라 열 중앙(x=seqX(N)) 드롭이 N+1로 샘(JS `Math.round(N-0.5)=N`→+1) | **수정완료**: X 기반 드롭 3곳(`seqFromX` loose드래그·`tryPaletteDrop` 팔레트·`onBcLaneDrop` 이벤트 reorder) 모두 `Math.round`→`Math.floor`. 이제 드롭한 열에 정확히 안착(열 전체 폭→그 열). 이벤트 카드 드롭(`onEvtDragOver`)은 카드 좌/우 절반 기준이라 별개·정상 |
| EM13 | 중간 → **✅수정** | **EM Connect로 만든 UI 부착(ui→command·readmodel→ui)이 Design 탭에 안 보임** — 연결했는데 Design에서 해당 Command/ReadModel에 UI가 안 붙음 | Design 탭([canvas_event_triggers.py:231](../../../api/features/canvas_graph/routes/canvas_event_triggers.py#L231))은 UI 부착을 **그래프 `ATTACHED_TO` 관계가 아니라 UI 노드의 `attachedToId` 속성**으로 렌더. EM `create_relation`은 그래프 관계만 만들고 `attachedToId` 속성 미설정 → Design 미표시 | **수정완료**: `create_relation`이 ATTACHED_TO 생성 시 UI의 `attachedToId`/`attachedToType` 속성도 SET(UI→Command=Command, ReadModel→UI=ReadModel), `delete_relation`은 해제 시 비움. 기존 연결 backfill. API검증 ui→command attachedToId 세팅 ✅ |
| EM12 | 높음 → **✅수정** | **Connect 모드로 ui→command·readmodel→ui 연결 시 연결선이 안 남고(편집/재구성/새로고침에 사라짐), 체인 불완전** — command→event(EMITS)·event→readmodel(CQRS)는 되는데 **UI가 관여하는 ATTACHED_TO만 전부 실패** | ① 백엔드 [create_relation/delete_relation](../../../api/features/canvas_graph/routes/event_modeling.py)이 `sourceType`을 `.capitalize()`하는데 **`'ui'.capitalize()='Ui'`**(≠`'UI'`) → `_VALID_RELATIONS`의 `('UI','Command')`·`('ReadModel','UI')` 키와 불일치 → **관계 미생성**(silent). `'Readmodel'→'ReadModel'` 정규화는 있었으나 `'Ui'→'UI'` 누락. ② 프런트 [`createRelation`](../../../frontend/src/features/eventModeling/eventModeling.store.js)이 POST 후 refetch 안 해 optimistic flow가 다음 `_rebuildCanvas`(stale `data.flows`)에서 소실 | **수정완료**: ① 백엔드에 `_LABEL_FIX={'Readmodel':'ReadModel','Ui':'UI'}` 정규화 추가(create·delete 양쪽) — API검증: testUI→testCommand `ATTACHED_TO` 생성 ✅. ② 프런트 `createRelation`이 POST 후 `fetchProcessList`→연결된 노드 체인을 `activeItemIds` 등록→재구성 → 연결선이 재구성·새로고침에도 유지. **③ ReadModel→UI 방향 역전 버그**: 읽기는 결과 UI를 `(UI)-[:ATTACHED_TO]->(ReadModel)`로 찾는데(UI가 소스), `create_relation`은 `(ReadModel)-[:ATTACHED_TO]->(UI)`를 만들어 readmodel-to-ui 흐름이 안 잡힘(선 안 보임) → `_REVERSED_RELATIONS={('ReadModel','UI')}` 추가로 드래그 방향의 역으로 저장(create·delete 양쪽), 기존 역방향 2건 교정. API검증 정방향 생성 ✅. **+UX**: 연결 방향 배너를 상단 복귀+**토글 시 4.5s 표시 후 자동 숨김**(편집 방해 최소화), 팔레트 추가 시 **"독립 노드로 추가됨 — 연결 모드로 흐름을 이어야 기존 프로세스에 합쳐짐" 토스트**(독립 프로세스 안내) |
| EM11 | 중간 → **✅수정** | **레인(EventModelingLane)에서 ReadModel screen/inline/system 3분류가 시각적으로 구분 안 됨** — screen(`RESULT_UI`)과 inline(`DISPLAYED_ON`)이 동일하게 "RM→우측 UI(회색 실선)"로 렌더, system은 UI 부재로만 암묵 추정. 043 US3 "3분류 표시" 의도가 레인에 미반영 | [EventModelingLane.vue:40-51·90](../../../frontend/src/features/canvas/ui/EventModelingLane.vue#L40)에서 `RESULT_UI`·`DISPLAYED_ON`을 동일 처리(둘 다 결과UI 칼럼·동일 엣지), 점선은 `ATTACHED_TO`만. ReadModelNode에 분류 마커 없음. 백엔드 분류는 정확(앞서 교차검증) | **수정완료**: 레인에 `rmClassById`(DISPLAYED_ON→inline·RESULT_UI→screen·없음→system) 추가 → ① RM 노드 **색 링**(screen 초록·inline 주황·system 회색) ② RM→UI **엣지 색/점선/라벨**(screen=초록실선'결과 화면'·inline=주황점선'표시(inline)') ③ 좌하단 **범례**([EventModelingLane.vue](../../../frontend/src/features/canvas/ui/EventModelingLane.vue)). 프런트 전용, 공유 ReadModelNode 무수정 |

## 5. 결론

- (초안) 다음 세션에서 §2 인벤토리를 store↔라우트로 확정하고 S1~S9 라이브 검증.
- **핵심 회귀 위험**: ① 042 `EventModelingLane`(가로레인) — task 모달이 구 컬럼형으로 나오면 043 위반 ② 043 ReadModel 3분류(현재 부분 제어 추정) ③ 025 Gateway 레이아웃 겹침 ④ 040 미리보기 mutation 차단 ⑤ live ingestion 후 `fetchEventModeling` 재로드 시 노드 중복/손실 ⑥ Chat 선택 매핑 누락 타입.
- 교차: BPM 뷰(process-bpm.md)와 UI 노드 공유 일관성, 설계 궤적(Stories S15)·ES 승격(BPM S7) 결과와 정합.
