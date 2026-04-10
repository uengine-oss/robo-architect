# Event Modeling Viewer

**References:**
- https://eventmodeling.org/posts/what-is-event-modeling/
- https://jeasthamdev.medium.com/event-modeling-by-example-c6a4ccb4ddf6
- https://www.youtube.com/watch?v=SYD0NEO3_90

---

## 핵심 구조: Vertical Slice

```
UI (Input)    ← 사용자 화면에서 액션 발생         [Actor swimlane]
    ↓ ATTACHED_TO
Command       ← 사용자 의도 (좌측 배치)           [Interaction swimlane]
    ↓ EMITS
Event         ← 발생한 사실 (타임라인 좌→우)      [BC swimlane]
    ↓ TRIGGERED_BY (CQRS)
ReadModel     ← 조회 데이터 투영 (우측 배치)       [Interaction swimlane]
    ↓ ATTACHED_TO
UI (Output)   ← 결과 화면                         [Actor swimlane]
```

### Policy(Automation) 연결

Policy는 "이벤트에 반응하여 시스템이 자동으로 Command를 트리거"하는 패턴.
Event Modeling/Event Storming 이론에서 **BC 경계와 무관**하게 적용됨.

```
Event → TRIGGERS → Policy → INVOKES → Command
```

- **cross-BC**: OrderPlaced(OrderMgmt) → Policy → RequestPayment(Payment) — BC 간 느슨한 결합
- **same-BC**: NotificationFailed(Notification) → Policy → ResendNotification(Notification) — BC 내 반응형 자동 흐름

사용자가 직접 호출하는 Command는 UI→Command로 표현되고,
이벤트에 반응하여 시스템이 자동 트리거하는 Command는 반드시 Policy를 거침.

---

## Ingestion 체인 (구현됨)

워커: `api/features/ingestion/ingestion_workflow_runner.py` (Event Modeling 체인).

```
0. Ingestion 시작 → Event Modeling 탭 전환 + live 모드

1. Parsing
2. UserStory 추출
3. UserStory 시퀀스 할당 (전체 US → LLM 일괄 순서 부여)
4. Event 추출 (per UserStory, Command 없이) — `events_from_user_stories`
   - US sequence 순 처리, 이벤트별 timeline_seq 부여 (전역 카운터)
   - US 내 여러 이벤트는 order 필드로 시간순 정렬
   - Neo4j: UserStory -[:HAS_EVENT]-> Event

5. BoundedContext 식별
   - US에 IMPLEMENTS 할당
   - BC 페이즈 완료 시: US→BC + US→Event 경로로 BC -[:HAS_EVENT]-> Event 자동 생성
   - SSE EventBCAssigned → 프론트에서 Event가 BC swimlane으로 이동

6. Aggregate 추출 (per BC)
   - 프롬프트에 해당 BC의 이벤트 목록 포함
   - LLM 출력: covered_event_names
   - Neo4j: Aggregate -[:SCOPE_EVENT]-> Event

7. Command 추출 (per Aggregate)
   - 프롬프트에 available_events (SCOPE_EVENT + HAS_EVENT) 포함
   - LLM 출력: emits_event_names
   - 생성 직후 기존/동명 Event에 EMITS 연결 (별도 링크 전용 페이즈 없이 커맨드 페이즈에서 처리)

8. ReadModel 추출 (per BC)
   - 프롬프트에 BC 이벤트(Neo4j HAS_EVENT 조회) + cross-BC 이벤트 포함
   - LLM 출력: trigger_event_names
   - 생성 직후 link_readmodel_to_event()로 CQRS 관계 생성
     (ReadModel -[:HAS_CQRS]-> CQRSConfig -[:HAS_OPERATION]-> CQRSOperation -[:TRIGGERED_BY]-> Event)
   - ID 규칙: CQRSConfig.id = "CQRS-{rmId}", CQRSOperation.id = "CQRS-OP-{rmId}-INSERT-{evtId}"
   - 기존 ReadModelCQRSEditor와 호환

9. Properties → References → Policies → GWT → UI Wireframe
```

---

## 타임라인 순서 도출

- Event의 `timeline_seq` (전역 카운터)가 유일한 X축 기준
- Command sequence = EMITS된 Event의 storedSequence
- ReadModel sequence = CQRS trigger Event의 storedSequence
- UI sequence = 연결된 Command/ReadModel의 sequence
- EMITS 없는 Command → maxSequence + 1부터 부여 (끝에 배치)
- BFS 기반 열 부여 제거됨
- **병렬 흐름 지원 (구현됨)**: 동일 Command가 EMITS하는 성공/실패 이벤트(예: `OrderPlaced` / `OrderPlacementFailed`)는 API 응답 시 동일 sequence로 그룹핑됨 (그룹 내 최소 sequence로 통일). 프론트엔드에서 동일 sequence 카드를 Y축 스택 배치

---

## API

- `GET /api/graph/event-modeling` — 전체 스윔레인 데이터
- `GET /api/graph/event-modeling?bc_ids=id1,id2` — 지정 BC + Policy 체인으로 연결된 BC만 확장 포함 (`api/features/canvas_graph/routes/event_modeling.py`)
- `PUT /api/graph/event-modeling/reorder` — Event 간 `sequence` 스왑 반영 (캔버스 드래그 정렬)

---

## 프론트엔드 레이아웃

### Swimlane 구조
- Actor swimlane (상단): Actor별 UI 카드
- Interaction swimlane (중간): Command(좌) / ReadModel(우) **좌우 배치**
- System swimlane (하단): BC별 Event 카드
- 수직 여백: `SWIMLANE_PAD=18`, `SWIMLANE_GAP=16`, `SWIMLANE_MIN_H=100`, `INTERACTION_BASE_H=96` (동적: 동일 시퀀스 Command/ReadModel 개수에 따라 확장)
- 스윔레인 헤더: JS 기반 `translateX(scrollLeft/scale)` 동기화로 좌우 스크롤 시 고정

### X좌표 정렬
- 동일 시퀀스의 Command/ReadModel/Event/UI는 같은 X 중심 (`seqX - CARD_W/2`)
- 같은 시퀀스에 Command + ReadModel 공존 시: Command 좌측, ReadModel 우측 오프셋
- 공존 시 UI(input)는 Command 쪽(좌), UI(output)는 ReadModel 쪽(우), Event는 Command 쪽(좌) 정렬

### 색상 (Design viewer 통일)
- Command: 파랑 `--color-command` (#5c7cfa)
- Event: 주황 `--color-event` (#fd7e14)
- ReadModel: 초록 `--color-readmodel` (#40c057)
- UI: 흰색

### 연결선 (`EventModelingPanel.vue`)
- **경로**: 직각 꺾임(orthogonal) — `stepPath()` (수직→수평→수직), `hStepPath()` (수평→수직→수평)
  - 꺾이는 모서리에 radius 6px 둥글기 적용
  - 같은 구간(corridor)의 겹치는 수평선은 midY/midX를 8px 간격으로 오프셋하여 분리
- **앵커 규칙**
  - UI → Command: UI 하단 중심 → Command 상단 중심
  - Command → Event: Command 하단 중심 → Event **상단** 중심
  - Event → ReadModel: Event **하단** 중심 → ReadModel 상단 중심 (아래로 꺾어서 올라감, 여러 선은 간격 분리)
  - ReadModel → UI(output): ReadModel 상단 중심 → UI 하단 중심
  - Event → 다음 Command (Policy chain): Event 우측 → Command 좌측, 수평 직각 경로
- **색**
  - UI → Command: 파랑
  - Command → Event: 주황
  - Event → ReadModel: 초록
  - ReadModel → UI(output): 초록
  - Event → Command (Policy chain): 빨강
- **호버 하이라이트**: 노드 호버 시 연결된 노드·선 강조 (두께 3, opacity 1), 나머지 dim (opacity 0.08/0.15)

### 캔버스 툴바
- 줌: 축소 / % / 확대 / 초기화
- **타입 필터**: **E / C / R / UI** 버튼 — 라벨 옆에 해당 타입 **노드 개수** 표시, 클릭 시 표시 토글
  - 꺼진 타입의 카드는 숨김
  - Actor / BC 스윔레인은 UI·Event 필터에 맞춰 **통째로 숨김** (빈 스윔레인으로 남지 않도록 세로 위치 재계산)
  - Interactions 행은 Command 또는 ReadModel **하나라도 켜져 있으면** 표시; 둘 다 끄면 행 숨김
  - 엣지는 **양끝 타입이 모두 보일 때만** 그림 (Interactions 행이 없으면 커맨드/RM 관련 선 없음)

### 프로세스 단위 캔버스 제어
- `_allResponse`: API 전체 응답 보관 (Navigator 프로세스 목록용)
- `canvasProcessIds`: 캔버스에 표시 중인 프로세스 ID Set
- `fetchProcessList()`: 전체 데이터 fetch → `_allResponse` 저장 (캔버스 변경 없음)
- `fetchEventModeling()`: 전체 데이터 fetch + 모든 프로세스 캔버스에 표시
- `addProcessToCanvas(id)` / `removeProcessFromCanvas(id)` / `toggleProcessOnCanvas(id)`
- `_rebuildCanvas()`: 선택된 프로세스 기반으로 swimlane refs 재구성 + 시퀀스 압축 (deep clone + 연속 번호 재매핑)
- Navigator에서 캔버스에 올라간 프로세스는 체크 표시 + 배경색으로 구분
- 탭 진입 시 Navigator가 `fetchProcessList()` 자동 호출, 캔버스는 비어있는 상태
- 프로세스 더블클릭(토글) 또는 드래그 앤 드롭으로 캔버스에 추가/제거

### 실시간 렌더링 (Ingestion 중)
- SSE 이벤트 → `eventModeling` 스토어로 노드 실시간 추가
- Ingestion 시작 → Event Modeling 탭 자동 전환 + `startLiveMode()`
- EventBCAssigned → Event가 BC swimlane으로 이동
- Ingestion 완료 → `stopLiveMode()` + `fetchEventModeling()` 전체 재로드

### 검증 경고 (클라이언트)
- **EMITS 없는 Command**, **UI로 들어오지 않는 Command**, **ReadModel CQRS에 연결되지 않은 Event**를 집계
- 해당 노드 카드에 마우스를 올리면 툴팁으로 경고 문구 표시

### 인스펙터
- ReadModel 클릭: CQRS trigger event 목록 표시 (`/api/readmodel/{id}/cqrs`)
- Command 클릭: Actor, Aggregate 표시
- Event 클릭: Command 표시

### Event 순서 (캔버스)
- 같은 BC 내 Event 카드를 드래그 앤 드롭으로 다른 Event에 놓으면 **sequence 스왑** 후 `reorder` API 호출

---

## CQRS 관계

- ReadModel 생성 시 trigger_event_names로 LLM이 관련 Event 지정 (cross-BC 포함)
- CQRS 관계 없는 ReadModel은 Interaction/Actor swimlane에 배치하지 않음
- CQRS 관계 있을 때만 Event→ReadModel→UI(output) 연결 표시
- ReadModel은 다른 BC의 Event도 구독 가능 (프롬프트에 cross-BC 이벤트 포함)

---

## 알려진 이슈

### EMITS 없는 Command (개선됨)
- LLM이 emits_event_names에서 이벤트 이름을 정확히 매칭하지 못하는 경우 발생
- Event는 한글(음식점 계정 등록됨), Command는 영문(RegisterRestaurantAccount)으로 생성되어 이름 불일치
- **개선 1**: 프롬프트에 "MUST be copied EXACTLY character-for-character" + 한글/영문 번역 금지 명시
- **개선 2**: `link_command_to_event_by_name` Neo4j 쿼리에 name → displayName → 대소문자 무시 fallback 추가

### ReadModel CQRS 링크 실패 (개선됨)
- `link_readmodel_to_event`에서 Event name 정확 일치만 → 한글/영문 불일치 시 CQRS 관계 미생성
- **개선**: name → displayName → 대소문자 무시 fuzzy matching 적용 (Command EMITS와 동일)
- **프롬프트 강화**: trigger_event_names "MUST be copied EXACTLY character-for-character" 명시

### Policy phase 스킵 / 미생성 (개선됨)
- **근본 원인**: Policy phase가 이벤트 목록을 `ctx.events_by_agg`에서 가져옴 → 이것은 `Command→EMITS→Event` sync 기반 → EMITS 실패 시 빈 목록 → LLM에 이벤트 없는 프롬프트 → 즉시 완료(스킵)
- **개선 1**: Neo4j에서 `BC→HAS_EVENT→Event` 직접 조회로 변경 (EMITS 의존 제거). Phase 4에서 UserStory 기반 생성된 Event는 BC에 HAS_EVENT로 항상 연결되어 있으므로 조회 보장
- **개선 2**: `_create_policy_with_links`에서도 Neo4j 전체 Event 조회로 fuzzy match 후보 빌드
- **개선 3**: 프롬프트에 정확한 이름 복사 강조 (한글/영문 번역 금지)
- **개선 4**: `_fuzzy_match()` 도입 — name 정확일치 → displayName 일치 → 대소문자 무시 → 포함관계 순으로 fallback
- **개선 5**: 이벤트 없으면 명확한 로그 + 조기 종료 (디버깅 용이)
- Policy가 생성되면 Event→TRIGGERS→Policy→INVOKES→Command 관계가 만들어져 cross-BC 프로세스 연결됨
- **주의**: 대규모 시나리오에서 Neo4j 전체 Event 조회 시 컨텍스트 오버플로우 가능 → 청킹 필요 (후속 과제)

### Event→ReadModel 먼 시퀀스 연결
- 정상 동작: OrderPlaced(seq=10) → MonthlyRevenueReport ReadModel(seq=70) 등
- 긴 수평·대각 연결선으로 표시됨

---

## 미구현 / 후속 과제

### Phase 4: 사용자 인터랙션
- [x] Event 드래그로 동일 BC 내 순서 스왑 (스왑만; 그리드 스냅·병렬 스택은 미구현)
- [x] 병렬 배치 (같은 column 내 위아래) — API(`event_modeling.py`) 3a-2 단계에서 같은 Command가 EMITS하는 이벤트들의 sequence를 그룹 내 최소값으로 통일. 프론트엔드의 기존 Y축 스택 로직(`evtCardPos`, `cmdStackIndex`)이 동일 sequence 카드를 위아래로 배치
- [ ] Ingestion 일시정지 중 조작 → resume 시 반영
- [x] 각 노드 더블 클릭 시 Design viewer와 동일 수준 인스펙터에서 수정 반영

### Phase 5: 후속 기능
- [x] Navigator에서 프로세스 단위 더블클릭/드래그로 캔버스에 추가 (BC 단위 → 프로세스 단위로 변경)
- [x] Event Modeling 기반 검증 힌트 (누락 흐름 감지 + 호버 툴팁); 서버 검증/차단은 별도
- [ ] BDD 시나리오 연계

### UI & Layout 개선점
- [x] 동일 시퀀스 상에서 서로 직접 연결될 노드끼리의 x좌표는 동일하도록
  - Command/ReadModel을 Event와 동일 X 중심 정렬; 같은 시퀀스에 둘 다 있을 때만 좌우 오프셋
- [x] Event modeling에서의 좌측 네비게이터에서는 bc 단위가 아닌, 하나의 프로세스 단위별로
  - entry Command(Policy invoke가 아닌)에서 BFS → Event → Policy chain 추적하여 프로세스 플로우 그룹핑
  - 탭 진입 시 `fetchProcessList()` 자동 호출 → Navigator에 프로세스 목록 즉시 표시
  - 캔버스는 비어있는 상태로 시작
  - 프로세스 더블클릭 → `toggleProcessOnCanvas()` (토글)
  - 프로세스 드래그 → 캔버스에 드롭하여 추가
  - 선택된 프로세스의 Command/Event/ReadModel/UI + 관련 flows만 캔버스에 렌더
  - cross-BC 연결은 `fetchEventModeling()` (bc_ids 없이 전체 fetch)으로 자연 포함
  - Navigator에서 프로세스 펼침 → step 클릭 시 인스펙터 연동
- [x] 스윔레인의 네이밍(bc, actor, interaction) 부분은 좌우 스크롤이 되어도 고정적으로 시점에 따라오도록
  - CSS sticky → JS 기반 translateX 동기화 (transform: scale 충돌 방지)
- [x] command로부터 emit된 관계가 없는 단독으로 존재하는 Event
  - Phase 4 (events_from_user_stories)에서 UserStory 기반으로 먼저 생성된 Event
  - Phase 7 (Command 추출)에서 LLM이 emits_event_names를 정확히 매칭하지 못하면 EMITS 관계 미생성
  - **개선 완료**: ① Event phase 네이밍 규칙 강제(영문 PascalCase), ② Command phase available_events에 displayName 포함하여 정확한 name 복사 유도, ③ EMITS 0건 시 BC-wide substring fuzzy 재시도, ④ 2차 재생성에서 NO EMITS Command 0건 달성
  - 백엔드에서는 `WHERE NOT (()-[:EMITS]->(evt))` 쿼리로 명시적으로 포함하여 누락 없이 표시
- [x] 각 노드별 hover 시, 연결 관계의 강조 표시가 어색함 (해당 노드에서 out 되는 선과 target 노드만 강조되어야 하는데, 해당 노드의 이전 요소들도 일부 같이 강조됨)
  - **개선**: `highlightedIds`를 outgoing 방향만 수집하도록 변경 (sourceId === hoveredItemId일 때만 targetId 추가). `isPathHl`도 srcId === hoveredItemId인 엣지만 강조
- [x] Policy phase가 바로 중단되면서 아예 생성이 안됌. (policy를 통해 서로 다른 bc 간의 프로세스들이 이어져야 불필요한 프로세스 단위의 세분화 쪼개짐이 해소됨) - ui > command > event > "policy(other bc) > ~~"
  - **개선**: BC→HAS_EVENT + events_by_agg 모두 비어있을 때 Neo4j에서 전체 Event 직접 조회하는 최종 fallback 추가. `_create_policy_with_links`에서 invoke_command Neo4j fallback도 추가
- [x] 불규칙 하게 최하단에 이벤트에서 나오는 선들이 끊겨보임.
  - **개선**: `totalHeight`에 Event→ReadModel 엣지 확장 공간(20 + count*8 px) 반영

### Ingestion 컨텍스트 오버플로우 대응 (후속)
- [x] `bounded_contexts` phase — 전체 US + Events를 한 번에 → chunking 구현됨 (split_list_with_overlap, chunk_size=30, overlap=3, accumulated BC context 전달)
- [x] `user_story_sequencing` phase — 전체 US 한 번에 순서 매김 → chunking 추가 (chunk_size=60, overlap=5, 이전 청크의 `{us_id: sequence}` 매핑을 다음 청크에 전달하여 일관성 유지)
- [x] `properties` phase — per-Agg/BC 단위지만 큰 Aggregate에서 위험 → chunking 추가 (commands를 chunk_size=15로 분할, 이전 청크에서 생성된 property 요약을 다음 청크에 전달)
- [x] `aggregates` phase — per-BC지만 BC에 이벤트 다수 시 위험 → intra-BC chunking 추가 (events를 chunk_size=30으로 분할, 이전 청크에서 생성된 aggregate + covered_events를 다음 청크에 전달)
- [x] `policies` phase — 기존 events-only chunking 개선: ① events 청크에 관련된 BC의 US/commands만 필터링하여 중복 오버헤드 제거, ② accumulated policy에 trigger_event → invoke_command + BC 쌍 상세 정보 포함하여 정합성 강화

### Event Modeling의 자유로운 수정
- [x] ui, command, readmodel, event 등의 자유로운 추가 및 삭제가 가능해야함. (팔레트 구현 필요)
- [x] event를 드래그하여 위치를 서로 shuffling하면서 위치를 바꿀 수 있어야함. (sequence가 서로 바뀌는게 아니라, 옮겨진 event에 따라 이후의 이벤트들이 하나씩 뒤로 자연스럽게 이동되어야 하며, 옮겨진 Event와 함께 연결된 command, readmodel, ui도 함께 움직여야함)
- [x] 시퀀스 변경 뿐만 아니라, 스윔레인에서 bounded context 끼리 서로 이동 가능해야함.
- [x] 드래그 이동이 가능한 것은 event only + event의 이동에 따라서 연결된 노드들이 함께 위치 변경 업데이트
- [ ] 정합성을 떨어 뜨리는 수정 액션에 대해 구조화하여 제어 및 알림 처리 (맞지 않는 릴레이션 방향 등)

### 출처 역추적 (Source Traceability)
- [ ] **US 생성 시 원본 소스 추출**: UserStory가 어떤 원본 텍스트 구간(chunk/paragraph)을 기반으로 생성되었는지 추출·저장
  - 현재 `source_unit_id` (analyzer_graph), `source_screen_name` (figma)는 있지만, rfp 소스의 텍스트 위치 추적은 미구현
  - US 추출 LLM 응답에 `source_text_ref` (원본 텍스트의 시작~끝 위치 또는 핵심 인용문) 필드 추가
- [ ] **노드별 역추적 체인 조회 API**: 임의의 노드(Command, Event, ReadModel, Policy 등)에서 역방향으로 원본 소스까지 추적
  - 경로: `Node → Aggregate → BC → UserStory → 원본 텍스트 구간`
  - API: `GET /api/graph/traceability/{node_id}` → 역추적 체인 + 원본 소스 하이라이트 정보 반환
- [ ] **프론트엔드 역추적 패널**: 노드 클릭 시 인스펙터에서 "출처" 탭으로 원본 소스 구간 표시
  - 원본 텍스트에서 해당 구간 하이라이트
  - 중간 노드 체인(US → BC → Aggregate → ...) 시각화
- [ ] **청킹과 역추적 연계**: 청킹 처리 시 각 청크의 원본 텍스트 위치(start_char, end_char)를 보존하여 역추적 가능하도록 메타데이터 저장
- [ ] **병렬 처리 고려사항**: BC 간 / Aggregate 간 외부 루프 병렬화는 역추적 체인에 영향 없음 (구조적 관계는 처리 순서와 무관). 단, cross-unit 중복 방지 품질이 약간 저하될 수 있으므로 병렬화는 처리 시간이 실제 병목이 될 때 적용

### Figma 연동
- [ ] Figma 인증 정보를 통한 api 연동 (프로젝트 목록 불러오기 및 추가하기)
- [ ] 이벤트 스토밍에서 생성된 각각의 ui요소들이 Figma 프로젝트의 각각의 레이어로 화면들을 추가할 수 있게 api 연동
- [ ] Figma에서 수정한 각 레이어들의 화면들을 그대로 다시 ui로 덮어씌우기 (ui 노드 name을 figma의 화면 이름으로 연결정보를 만들면 되지 않을까?)

### 코드 분석 Ingestion 품질 개선 (구현됨)
- [x] **US 생성 — 관련 함수 그룹핑**: `build_grouped_unit_contexts()`로 같은 테이블/접두사 함수를 Union-Find로 묶어 배치 LLM 호출. 함수당 US 1:1 → 그룹당 통합 US
- [x] **Events Phase — BL 컨텍스트 주입**: `events_from_user_stories.py`가 BL Given/When/Then을 `<business_rules>` 섹션으로 프롬프트에 주입. 분기별 과생성 방지 규칙 추가 (내부 검증/타입 체크는 별도 이벤트 아님)
- [x] **Policies Phase — coupled_domain 활용**: BL의 coupled_domain에서 cross-function 호출 패턴을 `<cross_domain_coupling_hints>` 섹션으로 Policy 프롬프트에 주입. "source BC → target domain" 직접 제공
- [x] **BC 과다 생성 방지**: `bounded_contexts.py`에 analyzer_graph 전용 통합 가이드 주입 — 함수명 접두사 기준 그룹핑, 같은 테이블 READS/WRITES 그룹핑, 목표 5~15개 BC
- [x] **Events → BC 연계**: Phase 4에서 추출된 이벤트의 도메인 클러스터링 힌트를 Phase 5(BC 식별) 프롬프트에 주입. PascalCase 접두사 기반 자동 그룹핑. 전 source_type 공통 적용

### External System(당장 고려 x)
- [ ] 톱니바퀴 아이콘

---

## Phase별 생성기 개선 분석

> 초기 분석: 7 BC, 67 Event, 41 Command, 21 ReadModel, 10 Policy.
> 1차 개선 후 재생성: 7 BC, 69 Event, 35 Command, 22 ReadModel, **2 Policy** (퇴행 발견 → 2차 개선 진행).

### Phase 4: Event 추출 (`events_from_user_stories.py`)

**현재 방식**: per-UserStory 단위로 LLM에 이전 생성 이벤트 목록을 누적 전달하여 중복 방지.

**발견된 문제**:
- **Orphan Event 18개** — Command가 EMITS하지 않는 이벤트가 전체의 27%. 특히 `AvailableOrdersListedByLocation`, `RestaurantListSearchedByLocation` 등 조회형 이벤트와 `~Failed` 실패 이벤트 다수
- **Command phase에서 매칭 불가한 이벤트 생성** — Event는 한글/영문 혼재, 이후 Command phase에서 이름 불일치로 EMITS 실패

**개선 제안**:
- [x] **이벤트 네이밍 규칙 강제**: Event phase 프롬프트에 `name`은 반드시 영문 PascalCase, 한글/특수문자 금지 명시. `displayName`에만 로컬라이즈 라벨. Command phase의 `available_events`에 `name (displayName: ...)` 형태로 둘 다 표시하여 LLM이 정확한 name을 복사하도록 유도. `emits_event_names` 규칙도 "name 부분만 복사, displayName 사용 금지" 명확화
- [x] **실패 이벤트 쌍 네이밍 규칙**: Event phase 프롬프트에 "Failure event name = success name stem + Failed" 패턴 명시 (예: `OrderPlaced → OrderPlacementFailed`)
- [ ] **조회형 이벤트 분류 태그**: `RestaurantListSearchedByLocation` 같은 Query 성격 이벤트는 `eventType: "query"` 태그를 부여하여, 이후 Command phase에서 ReadModel 쪽 Read Command로 매칭하도록 힌트 제공

### Phase 5: BoundedContext 식별 (`bounded_contexts.py`)

**현재 방식**: 전체 US + Events를 한 번에 LLM에 전달하여 그룹핑.

**발견된 문제**:
- BC 식별 자체는 양호 (7개 BC가 도메인에 적합)
- 그러나 **PaymentProcessing이 3개 이벤트만 보유** — `PlaceOrder`(OrderManagement)가 `PaymentSucceeded`/`PaymentFailed`를 직접 EMITS하고 있어 결제 도메인이 빈약함. BC 경계가 이벤트 소유권과 불일치

**개선 제안**:
- [x] **BC 경계 검증 규칙 추가**: `link_command_to_event_by_name()`에서 Command와 Event의 BC를 비교. cross-BC EMITS 발생 시 WARN 로그 (차단→경고로 완화, 1차 시도에서 차단이 Policy 퇴행 유발)
- [ ] **BC별 최소 이벤트 수 경고**: 특정 BC의 이벤트가 3개 이하면 해당 BC가 독립 BC로 적합한지 LLM에 재검토 요청 (필요한 작업인지 다시 검토)

### Phase 6: Aggregate 추출 (`aggregates.py`)

**현재 방식**: per-BC 단위로 해당 BC의 이벤트 목록을 컨텍스트에 포함. cross-BC 동명 Aggregate 자동 병합.

**발견된 문제**:
- **AdminMonitoringAndAnalytics에 4개 Aggregate** (`UserSanctioning`, `ReportFiltering`, `StatisticsVisualization`, `AbnormalActivityDetection`) — 하지만 `UserSanctioning`과 `AbnormalActivityDetection`에 연결된 Command가 EMITS 없음 → Aggregate가 있지만 실질적으로 비어있는 상태
- `covered_event_names` 매칭이 실패하면 Aggregate는 존재하나 SCOPE_EVENT가 없는 유령 Aggregate 가능

**개선 제안**:
- [x] **Aggregate 생성 후 SCOPE_EVENT 검증**: `_create_aggregate_with_links()`에서 `link_aggregate_to_event_by_name()` 성공 건수 추적. 0건이면 WARN 로그 (`ingestion.workflow.aggregates.scope_event_zero`)
- [x] **조회 전용 BC Aggregate 최소화**: Aggregate 프롬프트(`EXTRACT_AGGREGATES_PROMPT`)에 `query_only_bc` 섹션 추가 — 조회만 하는 BC는 Aggregate를 0~1개로 제한. CQRS Read side는 Aggregate 없이 ReadModel만으로 충분

### Phase 7: Command 추출 (`commands.py`)

**현재 방식**: per-Aggregate 단위. available_events(SCOPE_EVENT + HAS_EVENT)를 프롬프트에 포함. `emits_event_names`로 LLM이 이벤트 이름 반환 → `link_command_to_event_by_name()`에서 fuzzy match(name→displayName→case-insensitive).

**발견된 문제**:
- **EMITS 없는 Command 5개**: `EnableAbnormalActivityDetection`, `SanctionUserForAbnormalActivity`, `NotifyOnDeliveryStatusChange`, `SynchronizeMenuToCustomerApp`, `UpdateDeliveryStatus`
- **Policy invoke 대상 Command가 BC에 미소속** — `SynchronizeMenuToCustomerApp` 등 10개 Command가 Policy에 의해 생성되었지만 `HAS_COMMAND` 관계 없음
- **중복 역할 Command**: `NotifyOnDeliveryStatusChange` vs `SendDeliveryStatusChangeNotification` 공존 (전자는 EMITS 없음)
- **BC 경계 위반 EMITS**: `PlaceOrder`(OrderManagement)가 `PaymentSucceeded`(PaymentProcessing 소속 Event)를 직접 발생
- **과도한 EMITS**: `VisualizeOrderStatistics`/`VisualizeSalesStatistics`/`VisualizeUserStatistics` 3개가 각각 Report Filtering 이벤트 6개를 공통 EMITS → 하나의 Command가 6개 이벤트를 발생시키는 비정상 구조

**개선 제안**:
- [x] **EMITS 0건 Command BC-wide fuzzy 재시도**: 1차 링크 0건 시, 해당 BC의 전체 Event를 Neo4j에서 가져와 substring 기반 fuzzy matching 재시도. LLM 재호출 없이 이름 불일치 보정 (`ingestion.workflow.commands.emits_retry_success`)
- [x] **cross-BC EMITS 경고**: Phase 5 BC 경계 검증 — warn-only (차단→경고로 완화)
- [x] **Command 중복 검출 강화**: `_existing_command_display_names` dict 추가. already_created_commands 프롬프트에 displayName 포함 + "Semantic Duplicate Detection" 규칙 추가 (NotifyX vs SendXNotification 등)
- [x] **EMITS 상한 규칙**: `_create_command_with_links()`에서 EMITS 성공 건수 추적. 3개 초과 시 WARN 로그 (`ingestion.workflow.commands.emits_excessive`). 0건 시에도 WARN (`ingestion.workflow.commands.emits_zero`)

### Phase 8: ReadModel 추출 (`readmodels.py`)

**현재 방식**: per-BC 단위. BC 내 이벤트 + cross-BC 이벤트를 프롬프트에 포함. `trigger_event_names`로 CQRS 체인(ReadModel→CQRSConfig→CQRSOperation→Event) 생성.

**발견된 문제**:
- **CQRS 미연결 이벤트 20개**: 특히 `MenuItemSelected`, `MenuItemDetailsViewed`는 사용자 행동 이벤트인데 ReadModel 투영 없음 → 장바구니/메뉴상세 화면 누락
- **PaymentProcessing의 ReadModel 빈약**: `PaymentApprovalStatus`는 `PaymentApprovalRejected`만 구독 → `PaymentRequestValidated` 성공 시 결제 승인 상태 표시 누락
- `PaymentRequestValidationResult` ReadModel이 존재하지만 이것은 내부용이고, 사용자에게 보여줄 결제 결과 ReadModel이 OrderManagement에 부족

**개선 제안**:
- [x] **CQRS 미연결 이벤트 보고**: ReadModel phase 완료 후, `TRIGGERED_BY` 관계가 없고 `~Failed`로 끝나지 않는 Event 집계 → WARN 로그 (`ingestion.workflow.readmodels.cqrs_orphan_events`)
- [ ] **조회 이벤트의 ReadModel 자동 연결 힌트**: Phase 4에서 `eventType: "query"`로 태깅된 이벤트가 있다면, ReadModel 프롬프트에 "이 이벤트는 조회 결과이므로 반드시 ReadModel에서 구독해야 한다" 가이드 추가
- [ ] **cross-BC ReadModel 구독 검증**: ReadModel이 다른 BC의 Event를 구독할 때, 해당 Event가 실제 프로세스 상 연관되는지(같은 UserStory 기반) 검증. 무관한 BC 이벤트 구독 방지

### Phase 9: Policy 추출 (`policies.py`)

**현재 방식**: 전체 Event/Command/BC를 LLM에 전달. cross-BC만 생성 규칙. `_fuzzy_match()`로 이벤트/커맨드 4단계 매칭. invoke 대상 Command가 없으면 Neo4j fallback 조회.

**발견된 문제**:
- **Policy invoke Command가 BC에 미소속** — 10개 전체 Policy의 target Command에 `HAS_COMMAND` 관계 없음. Policy phase에서 새 Command를 생성하는 것이 아니라 기존 Command를 참조해야 하는데, 기존에 없는 Command 이름을 LLM이 반환하면 Neo4j에 Command만 생성되고 BC 소속 없이 부유
- **핵심 프로세스 연결 누락**:
  - `PaymentSucceeded` → 배달 배정 Policy 없음 (결제→배달 흐름 단절)
  - `PaymentSucceeded` → 주문 상태 업데이트 Policy 없음
  - `OrderPlaced` → 결제 요청 Policy 없음 (주문→결제 흐름 단절)
- **고립 BC**: PaymentProcessing, AdminMonitoringAndAnalytics, UserAccountManagement에서 outgoing Policy 0개

**개선 제안**:
- [x] **Policy invoke Command의 BC 소속 보장**: Policy 생성 완료 후, `(:Policy)-[:INVOKES]->(cmd)` 중 `(:Aggregate)-[:HAS_COMMAND]->(cmd)` 관계가 없는 Command를 탐지하여 target BC의 첫 번째 Aggregate에 자동 `HAS_COMMAND` 연결 (`ingestion.workflow.policies.cmd_bc_fix`)
- [x] **Policy 프롬프트 대폭 강화**: 1차 개선에서 10→2 퇴행 발생 → 프롬프트에 "Mandatory cross-BC flow categories" 섹션 추가 (Order→Payment, Payment→Order, Order→Notification 등 체크리스트). N×(N-1) BC 쌍 전수 검토 유도. 5개 미만 Policy 시 재검토 가이드
- [ ] **필수 cross-BC 흐름 검증**: Phase 완료 후, 주요 비즈니스 플로우(주문→결제→배달→알림) 경로가 Policy chain으로 연결되는지 그래프 탐색으로 검증. 단절 지점 발견 시 해당 구간의 Event-Command 쌍을 LLM에 제시하며 Policy 생성 재시도
- [x] **BC 고립 경고**: Policy 생성 완료 후, outgoing Policy 0개이면서 Command를 보유한 BC를 탐지하여 WARN 로그 (`ingestion.workflow.policies.bc_isolated`)
- [x] **EMITS 없는 Command와 Policy 연계**: Policy 프롬프트에 `<commands_without_emits>` 섹션 추가 — EMITS 관계 없는 Command 목록을 별도 컨텍스트로 제공하여 Policy invoke 후보로 활용
- [x] **same-BC Policy 허용 (INFO 로그)**: Event Modeling/Event Storming 이론에서 Policy(Automation)는 "이벤트에 반응하여 시스템이 자동으로 Command를 트리거"하는 패턴이며 BC 경계와 무관. same-BC 내 반응형 흐름(예: `NotificationFailed→ResendNotification`)도 Policy가 정당한 표현. 생성 시 INFO 로그 기록. 프롬프트에서는 cross-BC 우선 유도하되 intra-BC reactive 흐름도 허용

---

## 1차 개선 후 재생성 결과 (2차 개선 대응)

### 개선 확인된 항목
- ✅ cross-BC EMITS 위반: 다수 → **0건**
- ✅ 비실패 Event CQRS ReadModel 미연결: 다수 → **0건**
- ✅ 과도한 EMITS (>3): 3개 Command × 6건 → **최대 2건**
- ✅ 중복 Command: 있었음 → **0건**
- ✅ Policy invoke Command BC 미소속: 10건 → **0건**
- ✅ Aggregate 수: 14 → 12 (조회 BC 최소화)

### 퇴행 발견 → 2차 개선
| 항목 | 이전 | 1차 후 | 원인 | 2차 대응 |
|------|------|--------|------|----------|
| Policy | 10 | **2** | cross-BC EMITS 차단 부작용 + 프롬프트 변경에 의한 LLM 출력 변화 | ① EMITS guard를 warn-only로 완화, ② Policy 프롬프트에 "Mandatory cross-BC flow categories" + BC 쌍 전수 검토 가이드 추가, ③ 5개 미만 Policy 시 재검토 유도 |
| EMITS | 69 | 37 | Event-Command 이름 불일치 (Event phase 근본 문제) | Command EMITS 0건 시 BC-wide substring fuzzy 재매칭 재시도 로직 추가 |
| Orphan Event | 18 | 35 | EMITS 감소 연쇄 | 위 EMITS 재시도로 개선 기대 |
| SCOPE_EVENT 0 Aggregate | ? | 2개 | Event phase에서 해당 도메인 이벤트 미생성 | Event phase 개선 시 해소 예정 (후속) |

### 2차 개선 후 재생성 결과

| 항목 | 초기 | 1차 | **2차** | 평가 |
|------|------|-----|---------|------|
| Events | 67 | 69 | **80** | 더 풍부 |
| Commands | 41 | 35 | **40** | 회복 |
| EMITS | 69 | 37 | **82** | ✅ fuzzy retry 효과 |
| Policies | 10 | 2 | **13** (cross 8 + same 5) | ✅ 초기 대비 30% 증가 |
| Orphan Events | 18 (27%) | 35 (51%) | **14 (18%)** | ✅ 최저치 |
| NO EMITS Commands | 5 | 7 | **0** | ✅ 완전 해소 |
| Non-fail Event no CQRS | 다수 | 0 | **1** | ✅ 유지 |
| SCOPE_EVENT 0 Aggregate | ? | 2 | **0** | ✅ 완전 해소 |
| cross-BC EMITS | 다수 | 0 | **0** | ✅ 유지 |
| Policy invoke CMD BC 미소속 | 10 | 0 | **0** | ✅ 유지 |

**핵심 비즈니스 플로우 완성 확인:**
- `SelectPaymentMethod` → `PaymentMethodSelected` → Policy → `RequestPayment` (Payment BC)
- `OrderPaymentSucceeded` → Policy → `AcceptOrderAssignment` (Delivery BC)
- `OrderPaymentSucceeded` → Policy → `SendOrderNotification` (Restaurant BC)
- `DeliveryStatusChanged*` → Policy → `SendDeliveryStatusChangeNotification` (Notification BC)
- `OrderPaymentFailed` → Policy → `SendOrderStatusChangeNotification` (Notification BC)

**잔여 이슈:**
- same-BC Policy 5건 → 이벤트 모델링에서 intra-BC 반응형 흐름도 연결선으로 표현되므로 허용. cross-BC 우선 유도로 프롬프트 조정 완료
- 과도한 EMITS (VisualizeXStatistics 6건) → EMITS 상한 경고 로그는 남지만 차단하지는 않음
- `MenuItemSelected` CQRS ReadModel 미연결 1건
