# Feature Specification: BPM·Event Modeling 단일 Process 탭 통합 + task=UI 일관성

**Feature Branch**: `042-task-ui-unification`

**Created**: 2026-06-11

**Status**: Draft

**Input**: User description: "BPM·Event Modeling 단일 Process 탭 통합 + task=UI 일관성 — 단일 Process 탭 + BPM⇄Event Modeling 토글, ES 승격 시 UI를 task당 1 트리거 화면으로 생성(현 Command당 1개), ReadModel은 별도 UI 없이 소비 task 화면에 표시 데이터로 부착, task 포함요소를 Event Modeling 형식(가로 레인)으로 표현."

## 배경 (Context)

spec-039는 BPM task의 포함 요소를 **읽기 전용 모달**로 보여주는 브리지 뷰어였다(신규 스키마 0건, 라이브 검증 완료). 그 과정에서 라이브 그래프(세션 `0dcf8cc7`) 실측으로 두 가지 **구조적 한계**가 드러났다:

1. **두 뷰가 다른 앵커로 그려짐** — BPM 뷰는 `:BpmTask`(+`NEXT` 시퀀스), Event Modeling 뷰는 `:BoundedContext`(`HAS_AGGREGATE→HAS_COMMAND→EMITS`) 기준. 둘은 `(:BpmTask)-[:PROMOTED_TO]->(:UserStory)-[:IMPLEMENTS]->(:Command)` 한 줄기 실로만 이어져 있다.
2. **task↔UI 불일치** — UI가 task가 아니라 **Command/ReadModel 기준**으로 생성된다([ui_wireframes.py](../../api/features/ingestion/workflow/phases/ui_wireframes.py): *"1 UI per Command, 1 UI per ReadModel"*). 실측: UI 22 = `ATTACHED_TO` Command 18 + ReadModel 4. task당 UI가 0~2개로 흔들린다(17 task=1 UI, 1 task=2 UI(2 command), 1 task=0 UI).

**확정 방향(사용자):** BPM = 사람이 트리거하는 **UI들의 흐름 집합**, Event Modeling = **UI를 포함**해 그 UI가 촉발하는 **시스템 내부 흐름**. 둘은 같은 정보의 두 면이므로 **UI를 공유 앵커**로 삼아 **task ≡ UI(쓰기/트리거 측)** 로 일관화한다. Command/Event는 이미 task 기반(각 DTO에 `task_id`)이라 유지하고, **흔들리는 건 UI 한 가지**다.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 단일 Process 탭에서 BPM ⇄ Event Modeling 전환 (Priority: P1)

모델러가 `Process` 탭 하나를 연다. 탭 안의 토글로 **BPM 뷰**(사람-대면 UI 흐름, 시스템 체인 접힘)와 **Event Modeling 뷰**(같은 UI + 그 아래 Command·Event·ReadModel 펼침)를 전환한다. 두 뷰는 **같은 UI 집합**을 가리키며, 토글은 "접기/펼치기"의 차이일 뿐 서로 다른 데이터를 보지 않는다.

**Why this priority**: 통합의 사용자 진입점. 두 탭이 분리돼 있으면 "같은 프로세스의 두 면"이라는 모델이 사용자에게 전달되지 않는다. 단일 탭+토글이 가장 작으면서 즉시 가치 있는 단위.

**Independent Test**: `Process` 탭을 열어 BPM⇄Event Modeling 토글 시, 선택한 프로세스의 **UI 노드 집합이 두 뷰에서 동일**(같은 식별자)하고, 별도 "Event Modeling" 탭이 더는 존재하지 않음을 확인한다.

**Acceptance Scenarios**:

1. **Given** 통합된 `Process` 탭, **When** 모든 상단 탭을 본다, **Then** 독립 "Event Modeling" 탭은 없고 Process 탭 내부 토글로만 진입한다.
2. **Given** 한 프로세스를 BPM 뷰에서 보다가 토글, **When** Event Modeling 뷰로 전환, **Then** 동일 UI 노드들이 앵커로 유지되고 그 아래 시스템 체인이 펼쳐진다.
3. **Given** 토글 왕복, **When** BPM으로 돌아온다, **Then** 같은 UI 흐름이 그대로 보인다(데이터 불일치·중복 0).

---

### User Story 2 - task당 1 트리거 UI (인제스천 불변식) (Priority: P1)

레거시 업로드 인제스천의 ES 승격 단계에서, **각 사람-트리거 task가 정확히 1개의 트리거 UI(화면)** 를 갖도록 생성한다. 그 화면이 task의 Command(들)를 일으킨다. 시스템 전용(사람 트리거 없는) task는 UI를 만들지 않는다. (A2A BPM 생성은 그대로 두고, 변경은 ES UI 생성 단계만.)

**Why this priority**: "task ≡ UI" 일관성의 데이터 기반. 현재 UI가 Command당 생성돼 task당 0~2개로 흔들리는 것을 task당 1개로 고정해야 BPM=UI흐름이 성립한다.

**Independent Test**: 골든 문서를 인제스천 후, 사람-트리거 task 수와 트리거 UI 수가 **1:1**(±0)이며, Command가 여러 개인 task도 트리거 UI는 1개임을 그래프에서 확인한다.

**Acceptance Scenarios**:

1. **Given** Command 2개를 가진 task("카드사 식별 및 정합성 검증"류), **When** ES 승격이 끝난다, **Then** 그 task의 트리거 UI는 **1개**이고 두 Command 모두 그 화면이 일으키는 것으로 표현된다.
2. **Given** 사람 트리거가 없는 시스템 전용 task, **When** ES 승격이 끝난다, **Then** 그 task엔 UI가 생성되지 않는다("System").
3. **Given** Command/Event 생성, **When** 승격 결과를 본다, **Then** Command/Event의 task 기반 귀속(`task_id`)은 **그대로 유지**된다(변경 0). task당 Command 다수는 정상.
4. **Given** 동일 문서 재인제스천, **When** 실행이 끝난다, **Then** task당 1 UI가 멱등으로 유지된다(UI 중복·증식 0).

---

### User Story 3 - ReadModel: 소비 화면 표시 + 조회/검색 화면은 task로 승격 (Priority: P2)

ReadModel(읽기/CQRS 측)은 **"ReadModel당 1 UI 무조건 생성"을 하지 않는다**. 대신 두 경우로 나뉜다:
- **표시 데이터**: 어떤 action 화면이 그 ReadModel을 조회·표시하면, 그 **소비 task의 화면(UI)에 표시 데이터로 부착**한다(N:M, 재사용 가능). 한 화면 = 쓰기(Command) + 읽기(ReadModel 표시).
- **조회/검색 화면**: ReadModel이 그 자체로 **사람이 보는 조회·검색 목적 화면**(검색/목록 뷰 등)이면 — LLM 휴리스틱 판단 — **그 ReadModel은 자체 task-UI(조회 단계)로 승격**된다.

ReadModel은 `task_id`가 없고 `trigger_event_keys`/`bc_key`로 정의되는 재사용 읽기 뷰다.

**Why this priority**: UI granularity 정리의 나머지 절반. "무조건 ReadModel당 UI"는 화면을 파편화하지만, 반대로 진짜 조회 화면을 데이터로만 묻으면 사람-단계를 놓친다. 둘을 구분해야 task=UI가 정확해진다.

**Independent Test**: 인제스천 후, ReadModel에 **무조건 생성된** 독립 UI는 없고(소비 표시로 전환), 조회/검색 화면으로 판정된 ReadModel만 task-UI로 승격됐는지 확인한다.

**Acceptance Scenarios**:

1. **Given** action 화면이 소비만 하는 ReadModel, **When** UI 생성이 끝난다, **Then** 전용 UI 없이 그 소비 task 화면의 표시 데이터로 연결된다.
2. **Given** 검색/목록처럼 사람이 직접 조회하는 ReadModel, **When** UI 생성이 끝난다, **Then** 그 ReadModel은 조회 task-UI로 승격되어 화면(=task)으로 나타난다.
3. **Given** 같은 ReadModel을 여러 화면이 조회, **When** 각 화면을 본다, **Then** N:M로 표시될 수 있다(중복 노드 생성 아님).

---

### User Story 4 - task 포함요소를 Event Modeling 형식으로 표현 (Priority: P2)

spec-039의 task 포함요소 모달/뷰는 설계-궤적(DDD/이벤트스토밍 스티커의 컬럼 그래프) 형식이라 부자연스럽다. 이를 **Event Modeling 형식(가로 레인: UI→Command→Event→ReadModel)** 으로 보여준다. requirements 탭의 설계-궤적(`DesignTraceCanvas`)은 그대로 두고, Process 탭/모달용 **경량 event-modeling 스타일 렌더러**를 신설한다.

**Why this priority**: 표현 일관성. 같은 데이터를 BPM/Event Modeling 맥락에선 event-modeling 형식으로 보는 게 자연스럽다. US1 토글과 결합해 완성도를 높인다.

**Independent Test**: Process 탭에서 task 포함요소를 열면 가로 레인(UI→Command→Event→ReadModel) 형식으로 렌더되고, requirements 탭의 설계-궤적은 기존 형식 그대로임을 확인한다.

**Acceptance Scenarios**:

1. **Given** 한 task의 포함요소, **When** Process 탭/뷰에서 연다, **Then** UI→Command→Event→ReadModel 가로 레인 형식으로 표시된다(설계-궤적 컬럼 그래프 아님).
2. **Given** requirements 탭, **When** 설계 궤적을 본다, **Then** 기존 `DesignTraceCanvas` 형식이 그대로 유지된다(회귀 0).

---

### Edge Cases

- task에 Command가 여러 개일 때, 트리거 UI는 **어느 Command(entry)** 에 붙는가? (US2 명확화)
- ReadModel을 표시할 task 화면을 **소비 기준 vs 생산 기준** 중 무엇으로 고르는가? (US3 명확화)
- 사람 트리거가 모호한 task(반-자동)는 UI를 만드는가/"System"인가?
- 기존(재인제스천 전) 세션은 여전히 Command당 UI 상태 — 통합 뷰가 그걸 어떻게 다루는가(혼재 허용/안내)?
- 한 화면(UI)이 트리거하는 Command가 여러 개이고 표시하는 ReadModel도 여러 개일 때 레인 렌더 상한.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 분리된 `Process` 탭과 `Event Modeling` 탭을 **단일 `Process` 탭**으로 통합하고, 내부 **BPM⇄Event Modeling 토글**을 제공해야 한다. 독립 "Event Modeling" 탭 진입점은 제거한다.
- **FR-002**: 두 뷰는 **동일 UI 노드 집합을 공유 앵커**로 사용해야 한다 — BPM 뷰=UI 흐름(시스템 체인 접힘), Event Modeling 뷰=같은 UI + 시스템 체인 펼침. 뷰 전용 복제 0.
- **FR-003**: ES 승격 단계는 **사람-조작 command마다 UI 1개**(policy-invoked=시스템 command 제외)를 생성한다. 한 task는 사람 스텝 수만큼 **1~N개 UI**를 가질 수 있다(한 화면 강제 아님). 사람 command가 없는 task는 UI 없음("System"). *(개정: 초안의 "task당 1 트리거 UI"는 사용자 피드백으로 철회 — task에 사람 화면이 여럿일 수 있음.)*
- **FR-004**: ReadModel(조회 결과)은 **3분류**로 처리한다: **query_screen**(사람이 직접 여는 조회/검색 화면)→자체 UI 승격; **displayed**(결과가 화면에 표시됨)→생산 task 화면에 `ATTACHED_TO {role:'display'}`로 부착; **system**(시스템 내부에서만 소비)→UI 없음(레인 FEEDS로만). "ReadModel당 무조건 1 UI"는 폐지. 판정은 LLM(`get_llm`), 불확실 시 보수적으로 displayed(사람이 봐야 할 결과 누락 방지).
- **FR-005**: Command/Event의 task 기반 귀속(`task_id`)과 task당 다수 Command는 **변경 없이 유지**해야 한다.
- **FR-006**: A2A BPM(프로세스·task) 생성 경로는 **변경하지 않아야** 한다.
- **FR-007**: task 포함요소 뷰/모달은 **Event Modeling 형식(UI→Command→Event→ReadModel 가로 레인)** 으로 렌더해야 한다. requirements 탭의 설계-궤적(`DesignTraceCanvas`)은 불변.
- **FR-008**: task에 Command가 여러 개일 때, **LLM 휴리스틱**으로 "사람이 실제 조작하는" Command를 판단해 그곳에 트리거 UI를 부착해야 한다(propose→confirm). 결정 불가 시 entry(첫/대표) Command로 폴백.
- **FR-009**: ReadModel은 기본적으로 **소비 기준**(그 ReadModel을 조회·표시하는 task 화면)에 표시 데이터로 부착한다. **단, ReadModel이 그 자체로 조회·검색 목적의 화면**(예: 검색/목록 뷰)인 경우 — LLM 휴리스틱 판단 — **그 ReadModel은 자체 task-UI**(조회/검색 단계)를 가질 수 있다. 즉 "ReadModel당 1 UI 무조건 생성"은 제거하되, ReadModel이 진짜 조회 화면이면 화면(=task)으로 승격한다.
- **FR-010**: UI granularity 변경의 스키마 범위(기존 `:UI`/`ATTACHED_TO`만으로 0건 vs 트리거/조회 구분용 속성·관계 최소 추가)는 **plan 단계에서 `ui_wireframes.py` 구조를 확인한 뒤 확정**한다. 신규 0건 지향.
- **FR-011**: 기존(재인제스천 전) 세션은 task↔UI가 1:1이 아닐 수 있다 — 통합 뷰는 이를 오류 없이 표시하고, 재인제스천 시 불변식이 적용되어야 한다.
- **FR-012**: 모든 LLM 기반 변경(UI 설명/와이어프레임 생성 등)은 **propose → confirm** 절차를 따라야 한다.

### Key Entities

- **`BpmTask`**: 사람-대면 업무 단계. BPM 흐름의 단위(`NEXT` 시퀀스). 표현상 트리거 UI로 대표.
- **`UI`(트리거 화면)**: task당 1개. 그 task의 Command(들)를 일으키고, 소비하는 ReadModel(들)을 표시. 두 뷰의 공유 앵커.
- **`Command`/`Event`**: 이미 task 기반(`task_id`). 화면이 일으키는 시스템 흐름. (변경 없음)
- **`ReadModel`**: 읽기/CQRS 측. 전용 UI 없음. 소비 task 화면에 표시 데이터로 부착(N:M).
- **`UserStory`**: `(:BpmTask)-[:PROMOTED_TO]->(:UserStory)-[:IMPLEMENTS]->(:Command)` 브리지(기존).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 상단 탭에 독립 "Event Modeling" 탭이 **0개**, Process 탭 토글로만 두 뷰 진입. 두 뷰의 UI 노드 집합 동일성 **100%**.
- **SC-002**: 재인제스천 후 사람-트리거 task : 트리거 UI = **1:1**(불일치 0). Command 다수 task도 트리거 UI 1개.
- **SC-003**: "ReadModel당 무조건 생성된" 독립 UI **0개**. 소비 ReadModel은 소비 화면에 표시로 연결, 조회/검색 ReadModel만 task-UI로 승격(판정 결과가 픽스처 기대와 일치).
- **SC-004**: task 포함요소가 **Event Modeling 형식(가로 레인)** 으로 렌더되고, requirements 설계-궤적 형식 회귀 **0**.
- **SC-005**: Command/Event의 `task_id` 귀속 회귀 **0**(기존 세션 대비 동일).
- **SC-006**: 통합으로 추가된 신규 Neo4j 노드 라벨/관계 수 **0건 지향**(불가피 시 명시·최소).

## Assumptions

- BPM=사람-트리거 UI 흐름 / Event Modeling=UI+시스템 흐름이라는 사용자 확정 정의를 따른다.
- task=UI는 **쓰기/트리거 측**의 불변식이다. 읽기 측 ReadModel은 기본 N:M 표시, 단 조회·검색 화면인 경우 자체 task-UI로 승격(LLM 판정).
- 트리거 UI 부착 Command 선택과 ReadModel의 조회-화면 판정은 **LLM 휴리스틱**(propose→confirm). 트리거는 결정 불가 시 entry Command 폴백.
- UI granularity의 스키마 범위(신규 0건 vs 최소 속성)는 plan에서 `ui_wireframes.py` 확인 후 확정.
- Command/Event는 이미 task 기반이므로 변경하지 않는다(`task_id`, "Story = Task × source_function cluster").
- A2A BPM 생성은 변경하지 않는다. 변경은 ES 추출/UI 생성 단계만.
- 인제스천 로직 변경이므로 **기존 세션은 재인제스천**이 필요하다(즉시 소급 적용 아님).
- 모든 LLM 변경은 propose→confirm.

## Dependencies

- **spec 039** (bpm-event-unification) — bpm-task trace 라우트·모달·`HybridTaskInspector` 버튼. 본 피처가 Event Modeling 형식 뷰로 확장·이전.
- **ui_wireframes.py** (ingestion) — UI 생성 단계. 핵심 변경 지점(Command당 → task당).
- **event_modeling.py / EventModelingPanel.vue** — Event Modeling 형식·데이터. 경량 렌더러의 참조.
- **spec 025** (NEXT_UI/Gateway) — UI 흐름 개념(BPM 뷰의 UI↔UI 흐름 투영 시 참고).
- **spec 022** (event-storming→DDD) — 그래프→산출물 투영 패턴.
