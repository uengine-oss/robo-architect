# Feature Specification: BPM ↔ Event Modeling 구조적 통합 (단일 그래프, 두 투영 뷰)

**Feature Branch**: `042-bpm-event-unification`

**Created**: 2026-06-10

**Status**: Draft

**Input**: User description: "BPM과 Event Modeling의 구조적 통합 — 단일 그래프, 두 투영 뷰. BPM task=사용자 관여 화면 단위(UI 스티커), task 간 흐름=UI↔UI(NEXT_UI/Gateway), 그 UI가 촉발하는 Command→Event→Policy→ReadModel 체인=task 안에 접힌 시스템 프로세스(collapsed subprocess). BPM 뷰=UI 펼침·시스템 체인 접힘, Event Modeling 뷰=시스템 체인 펼침. 둘은 동일 그래프의 두 투영. 'Big picture' 제거."

## 배경 (Context)

현재 시스템은 동일한 업무 프로세스를 **두 개의 단절된 모델**로 표현한다.

1. **Event Modeling 뷰** — `UI → Command → Event → Policy → ReadModel → UI` 데이터 흐름을 가로로 펼쳐 보여준다. event-policy-event 묶음은 *시스템 내부에서 일어나는 흐름*이지, 사용자가 직접 관여하는 비즈니스 흐름 그 자체가 아니다.
2. **BPM 뷰** — 두 갈래로 생성된다. (a) 레거시 코드·문서 업로드 시 **첫 단계**로 외부 pdf2bpmn A2A 서비스(Process GPT BPM exporter)가 문서에서 BPMN을 추출해 `ProcessBundle`/`BpmSkeleton`을 만든다(하이브리드 인제스천). (b) 별도로 event storming 그래프에서 내부 도출되는 BPMN은 **task를 entry-point Command로** 잡는다.

문제는 두 모델이 *의미적으로 같은 프로세스*를 표현하는데도 서로 연결되지 않고, BPM의 task 정의가 "사용자 관여 단계"가 아니라 "시스템 명령"에 묶여 있다는 점이다. 또한 효용이 사라진 **"Big picture" 뷰**(탭은 이미 숨김, `BigPicturePanel`/`bigpicture.store` 잔존)가 코드에 남아 인지 부하와 유지보수 비용을 발생시킨다.

**확정된 방향(사용자):** 진실의 원천은 단일 Neo4j 그래프 하나다. BPM 뷰와 Event Modeling 뷰는 같은 그래프의 **두 가지 투영(projection)** 이며, 표현 차이는 *렌더링(접기/펼치기)* 으로만 만든다 — 신규 노드 라벨/관계 추가는 최소화한다.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 두 뷰가 같은 프로세스를 가리킨다 (단일 그래프 투영) (Priority: P1)

모델러가 한 Bounded Context를 BPM 뷰에서 보다가 Event Modeling 뷰로 전환한다. 두 뷰는 **동일한 프로세스**를 서로 다른 추상화 수준으로 보여준다 — BPM 뷰는 사용자 관여 단계(UI)를 task로 펼치고 그 안의 시스템 체인을 접어 두며, Event Modeling 뷰는 그 시스템 체인을 펼쳐 보여준다. 한 뷰에서 노드를 선택하면 다른 뷰의 대응 요소가 동일하게 식별된다.

**Why this priority**: 통합의 핵심 가치. 두 모델이 같은 진실의 원천을 가리킨다는 보장이 없으면 나머지 통합 작업이 무의미하다. 단일 그래프 투영은 가장 작으면서 독립적으로 가치 있는 단위다.

**Independent Test**: 완전히 모델링된 BC 하나를 골라 BPM 뷰의 한 프로세스와 Event Modeling 뷰를 나란히 열고, BPM task가 가리키는 UI와 Event Modeling 행의 UI가 동일 식별자임을 확인한다. 두 뷰 사이에 데이터 중복(서로 다른 노드로 표현된 같은 개념)이 없음을 확인한다.

**Acceptance Scenarios**:

1. **Given** BPM 뷰와 Event Modeling 뷰에 모두 표현되는 한 프로세스, **When** 사용자가 BPM 뷰의 task를 선택한다, **Then** 그 task는 Event Modeling 뷰의 동일 UI 노드(같은 노드 식별자)에 대응한다.
2. **Given** 두 투영 뷰, **When** 같은 프로세스를 양쪽에서 연다, **Then** 두 뷰가 읽는 데이터는 동일한 그래프 노드/관계 집합에서 나온다(한 뷰 전용으로 복제된 프로세스 노드가 존재하지 않는다).
3. **Given** 그래프의 프로세스가 수정된다(예: 새 UI 추가), **When** 두 뷰를 다시 연다, **Then** 두 뷰 모두 추가를 반영한다 — 한쪽만 갱신되는 일이 없다.

---

### User Story 2 - BPM task의 "포함 요소" 를 인스펙터 모달로 열람 (Priority: P1)

모델러가 BPM 뷰에서 한 task(`BpmTask`)를 선택하면 인스펙터에 **"포함 요소 / 설계 궤적 보기" 버튼**이 있다. 누르면 **모달**이 열려, 그 task에 귀속된 UI·Command·Event·Policy·ReadModel 체인이 **event-modeling 스티커 형태로** 표시된다(= Event Modeling 뷰가 보여주는 그 task의 "시스템 프로세스"). 이 열람은 **BPM 캔버스 자체를 바꾸지 않는다** — 캔버스에 새 엣지/노드를 그리지 않고, requirements 탭의 "설계 궤적"(spec 026)과 동일한 읽기 전용 패턴으로 모달에서만 보여 인지 부하를 최소화한다.

각 task는 표현상 그 task의 **대표 UI(얼굴)** 로 라벨링되며, task 간 순서는 기존 `BpmSequence`(A2A 산출)를 따른다. UI가 없는 시스템 전용 task는 "System"으로 표기한다.

**Why this priority**: "BPM=비즈니스 흐름, Event Modeling=시스템 흐름"의 의미 정합을, *캔버스 재설계 없이* 기존 그래프 관계(`PROMOTED_FROM`)와 기존 설계-궤적 렌더러를 재사용해 실현하는 핵심. 사용자가 "이 task 안에 무엇이 들어있나"를 한 번의 클릭으로 확인한다.

**Independent Test**: 완전 모델링된 프로세스에서 BPM task 하나를 선택해 인스펙터 버튼을 누르고, 모달에 그 task에 귀속된 Command·Event·UserStory·(있으면)UI 체인이 event-modeling 스티커로 나타나며 BPM 캔버스에는 변화가 없음을 확인한다.

**Acceptance Scenarios**:

1. **Given** 시스템 체인(Command→Event→…)이 귀속된 BPM task, **When** 인스펙터의 "포함 요소" 버튼을 누른다, **Then** 모달이 열려 그 task의 `(:BpmTask)<-[:PROMOTED_FROM]-(…)` 서브그래프가 event-modeling 스티커로 렌더링된다.
2. **Given** 모달이 열린 상태, **When** 모달을 닫는다, **Then** BPM 캔버스는 처음과 동일하다(새 엣지/노드 0, 레이아웃 불변).
3. **Given** 귀속된 시스템 체인이 없는 task, **When** 버튼을 누른다, **Then** 모달은 "이 task에 귀속된 설계 요소가 없습니다"를 비차단으로 안내한다(설계 궤적 empty 패턴 재사용).
4. **Given** 어떤 UI에도 연결되지 않은 시스템 전용 task, **When** BPM 뷰에 표시한다, **Then** 그 task는 **"System" 레인/라벨**로 표기되고 모달 열람도 동일하게 동작한다.

---

### User Story 3 - A2A BPM task를 척추로, 시스템 체인을 task별 추출로 정렬 (Priority: P2)

사용자가 레거시 코드·문서를 업로드하면 **첫 단계로 외부 A2A 서비스가 BPM(프로세스·task)을 생성**한다. 이것이 단일 그래프의 척추(spine)다. 이어서 event storming은 **각 task를 바탕으로** UI·Command·Event·Policy·ReadModel을 추출하여 해당 task 아래에 귀속시킨다. 따라서 BPM과 Event Modeling은 *별도 정렬 작업* 없이 **태생적으로 같은 task로 정렬**되어, 하나의 그래프에서 두 뷰가 투영된다. (BPM 생성 경로는 A2A 단일이며, spec 011식 "task=entry Command" 내부 도출은 BPM 생성원으로 쓰지 않는다.)

**Why this priority**: 단일 그래프 보장(US1)이 실파이프라인에서 성립하려면 시스템 체인이 올바른 A2A task에 귀속돼야 한다. US1/US2가 데모 그래프에서 성립한 뒤 실인제스천으로 확장하는 단계.

**Independent Test**: 레거시 문서+코드를 하이브리드 인제스천에 통과시키고, A2A가 만든 각 BPM task 아래에 그 task에서 추출된 UI·Command 체인이 귀속되어 있는지, BPM 뷰와 Event Modeling 뷰가 동일 task 집합을 공유하는지 그래프에서 확인한다.

**Acceptance Scenarios**:

1. **Given** A2A가 BPM 프로세스·task를 생성한 뒤 event storming이 실행, **When** 하이브리드 인제스천이 끝난다, **Then** 각 task 아래에 그 task에서 추출된 UI·Command·Event 체인이 귀속되어 BPM/Event Modeling 두 뷰가 동일 task 집합에서 투영된다.
2. **Given** 어떤 task에서 UI·Command 추출이 모호해 비는 경우, **When** 인제스천이 그 구간에 도달, **Then** 빈 추출이 경고로 표면화되고(중복 프로세스/task 무단 생성 금지) 사용자 확인 흐름으로 넘어간다.
3. **Given** 동일 문서를 재인제스천, **When** 실행이 끝난다, **Then** A2A task와 그 하위 추출이 멱등(idempotent)으로 갱신되어 프로세스/task가 중복 생성되지 않는다.

---

### User Story 4 - "Big picture" 뷰 완전 제거 (Priority: P2)

효용이 사라진 "Big picture" 뷰를 탭·패널·스토어·관련 배선까지 코드에서 완전히 제거한다. 사용자에게 노출되는 잔재가 없고, 다른 뷰(BPM/Event Modeling/Requirements 등)의 동작에 영향이 없다.

**Why this priority**: 인지 부하·유지보수 비용 제거. 통합의 일부지만 다른 US와 독립적으로 출하 가능. 이미 탭이 숨겨져 있어 회귀 위험이 낮다.

**Independent Test**: 애플리케이션을 띄워 "Big picture" 진입점이 어디에도 없음을 확인하고, 코드베이스에 `BigPicturePanel`/`bigpicture.store`/관련 상태 참조가 남지 않았으며 빌드·기존 뷰가 정상임을 확인한다.

**Acceptance Scenarios**:

1. **Given** 통합 후 애플리케이션, **When** 모든 탭/메뉴를 살펴본다, **Then** "Big picture" 진입점이 존재하지 않는다.
2. **Given** 제거 작업 완료, **When** 코드베이스를 검색한다, **Then** `BigPicturePanel`·`bigpicture.store` 및 그 전용 상태/스타일 참조가 남아 있지 않다.
3. **Given** 제거 후, **When** 기존 export/문서 생성 등 Big picture 스토어를 참조하던 기능을 실행한다, **Then** 오류 없이 동작한다(의존 제거 또는 대체 완료).

---

### Edge Cases

- task에 UI가 없을 때 대표 얼굴을 "System"으로 표기 — 모달은 UI 없이 Command/Event 체인만 보여준다.
- 한 task에 대표 UI 후보가 여럿일 때(UserStory 여러 개 경유) 어느 UI를 얼굴로 고르는가? (plan에서 확정)
- task에 귀속된 시스템 요소가 0건일 때 모달의 empty 안내(설계 궤적 empty 패턴 재사용).
- task별 체인이 매우 클 때 모달 렌더 상한(설계 궤적의 bounded-depth/필드 축약 패턴 재사용).
- Big picture 스토어를 참조하던 export/문서 템플릿 기능이 끊기지 않도록 대체 데이터 출처가 필요한가?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 시스템은 BPM 뷰와 Event Modeling 뷰를 **단일 그래프의 두 투영**으로 제공해야 하며, 한 뷰 전용으로 같은 프로세스를 복제한 노드를 만들지 않아야 한다.
- **FR-002**: BPM 뷰에서 하나의 **task(`BpmTask`)는 사용자 관여 단계**이며, 표현상 그 task의 **대표 UI(얼굴)** 로 라벨링한다. UI가 없는 시스템 전용 task는 **"System"** 으로 표기한다. task 간 순서는 기존 `BpmSequence`(A2A 산출)를 따른다.
- **FR-003**: BPM task 인스펙터는 **"포함 요소 / 설계 궤적 보기" 버튼**을 제공해야 하며, 누르면 **모달**로 그 task에 귀속된 UI·Command·Event·Policy·ReadModel 체인을 **event-modeling 스티커 형태**로 보여야 한다. 이 열람은 requirements 탭의 설계-궤적(spec 026)과 동일한 **읽기 전용** 패턴·렌더러를 재사용한다.
- **FR-004**: 이 열람은 **BPM 캔버스를 변경하지 않아야 한다** — 캔버스에 새 엣지/노드를 그리지 않고, 모달 안에서만 표시한다(인지 부하 최소화).
- **FR-005**: 모달이 보여주는 task별 체인은 **기존 그래프 관계만으로** 구성해야 한다 — `(:BpmTask)<-[:PROMOTED_FROM]-(:Command|:Event|:UserStory|:Aggregate|:ReadModel|:Policy)` 및 `(:Command)-[:EMITS]->(:Event)` 등 이미 영속된 traceability 엣지를 조회한다(신규 영속 0건, 읽기 전용).
- **FR-006**: 한 뷰/모달에서 요소를 선택하면 다른 뷰의 대응 요소가 **동일 식별자로 식별**되어야 한다(두 뷰의 cross-reference).
- **FR-007**: BPM(프로세스·task) 생성은 **외부 A2A 서비스를 단일 경로**로 한다. event storming은 **각 A2A task를 바탕으로** UI·Command·Event·Policy·ReadModel을 추출해 해당 task 아래에 귀속시켜야 하며, 결과는 재인제스천 시 멱등이어야 한다.
- **FR-008**: 특정 task에서 UI·Command 추출이 모호해 비는 경우, 시스템은 **중복 프로세스/task를 무단 생성하지 않고** 경고로 표면화한 뒤 사용자 확인 흐름으로 넘겨야 한다.
- **FR-009**: 시스템은 "Big picture" 뷰의 진입점·패널·전용 스토어·관련 배선을 **완전히 제거**해야 하며, 잔재가 사용자에게 노출되지 않아야 한다.
- **FR-010**: Big picture 스토어에 의존하던 기존 기능(예: 문서 export)은 제거 후에도 오류 없이 동작해야 한다(의존 제거 또는 대체).
- **FR-011**: 통합은 **신규 Neo4j 노드 라벨/관계를 0건** 추가해야 한다. task별 포함 요소 조회는 기존 `:BpmTask` 노드와 기존 `PROMOTED_FROM`/`EMITS`/`IMPLEMENTS` 등 이미 영속된 관계만으로 달성한다(신규 매핑 관계 신설 금지).
- **FR-012**: 두 뷰 중 어느 것을 통해서든 프로세스에 가해지는 LLM 기반 변경은 **propose → confirm** 절차를 따라야 한다.
- **FR-013**: spec 011의 "task=entry Command" 내부 BPMN 도출은 **BPM 생성원으로 사용하지 않는다**(BPM은 A2A 단일 경로). Command 추출은 각 A2A task를 바탕으로 수행한다. 011의 BPMN 뷰/export 경로가 여전히 소비되는 부분이 있다면 새 task=UI 투영으로 정합되도록 조정한다.

### Key Entities *(기존 그래프 재사용 — 신규 라벨 0건)*

- **`BpmTask` (척추)**: A2A가 생성한 BPM task. 단일 그래프의 척추이며, BPM 뷰·Event Modeling 뷰가 공유하는 정렬 단위. 표현상 대표 UI(또는 "System")로 라벨링.
- **`BpmSequence`**: A2A 산출 task 순서. BPM 뷰의 task 간 흐름 출처.
- **traceability 엣지(`PROMOTED_FROM`/`EMITS`/`IMPLEMENTS`)**: 각 task에 귀속된 Command/Event/UserStory/Aggregate/Policy/ReadModel을 잇는 **이미 영속된** 관계. task별 포함 요소 모달의 데이터 출처.
- **시스템 체인(Command/Event/Policy/ReadModel/UserStory)**: 한 task에 귀속된 내부 흐름. 인스펙터 모달에서 event-modeling 스티커로 열람.
- **UI(스티커)**: task의 대표 얼굴. task→UI 연결 경로(직접 vs UserStory 경유)는 plan에서 확정.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 완전 모델링된 BC에서 BPM task에 귀속된 시스템 요소가 Event Modeling 뷰의 동일 식별자 요소와 **100% 일치**한다(한 뷰 전용 복제 프로세스 0건).
- **SC-002**: 모달이 보여주는 task별 포함 요소는 그래프의 `(:BpmTask)<-[:PROMOTED_FROM]-(…)` 결과와 **100% 일치**한다(누락·과포함 0건).
- **SC-003**: 모델러가 BPM task의 포함 요소를 확인하는 데 **버튼 1클릭 → 모달**로 가능하며, BPM 캔버스는 불변(엣지/노드 추가 0).
- **SC-004**: 레거시 업로드 인제스천 후 각 A2A task에 시스템 체인이 귀속되어, 같은 task가 BPM/Event Modeling 두 뷰에서 일관되게 나타나는 비율이 기준 골든 픽스처에서 **회귀 0건**이다.
- **SC-005**: "Big picture" 진입점·패널·스토어가 코드베이스에서 **0건** 잔존하고, 제거 후 기존 뷰·export 기능에 회귀가 **0건**이다.
- **SC-006**: 통합으로 추가된 신규 Neo4j 노드 라벨/관계 수가 **0건**(불가피 시 최소, 명시적 승인)이다.

## Assumptions

- 진실의 원천은 단일 Neo4j 그래프이며, BPM/Event Modeling은 그 투영이라는 사용자 확정 방향을 따른다.
- BPM task의 1차 정체성은 **`BpmTask`**(A2A 산출)이며, 표현상 그 task의 대표 UI(얼굴)로 라벨링한다. task 간 순서는 `BpmSequence`를 따른다.
- task별 포함 요소는 **캔버스가 아니라 인스펙터 버튼 → 모달**로, requirements 설계-궤적(spec 026)과 동일한 읽기 전용 패턴으로 보여준다(인지 부하 최소화). 데이터는 이미 영속된 traceability 엣지를 조회한다(읽기 전용, 신규 영속 0건).
- BPM(프로세스·task) 생성은 **pdf2bpmn A2A 서비스(Process GPT BPM exporter) 단일 경로**다. event storming은 각 A2A task를 바탕으로 UI·Command 체인을 추출해 그 task에 귀속시키므로, 두 뷰는 태생적으로 같은 task로 정렬된다(별도 정렬 관계 불필요).
- spec 011의 Command 기반 내부 BPMN 도출은 BPM 생성원이 아니다(대체).
- "Big picture" 탭은 이미 UI에서 숨겨져 있어 제거의 사용자 영향이 낮다.
- 신규 노드 라벨/관계 0건은 프로젝트 헌법(I·II)에 따른 강한 선호이며, 정렬을 위해 불가피한 경우에만 최소한으로 예외를 둔다.
- 모든 LLM 기반 변경은 propose→confirm(헌법 IV)을 따른다.

## Dependencies

- **spec 026** (requirements-tab design-trace) — **핵심 재사용**: `/api/requirements/user-story/{id}/design-trace` 엔드포인트 + `DesignTraceCanvas.vue`의 `{nodes, relationships}` 렌더링·empty·bounded-depth 패턴. BPM task용 트레이스 모달이 이 패턴을 미러링.
- **spec 036** (하이브리드 BPM 인제스천) — `document_to_bpm`(A2A) + `event_storming_bridge`(BpmTask 척추 + `PROMOTED_FROM` 영속). US2/US3 데이터 기반.
- **spec 011** (BPMN process export) — 기존 BPMN 뷰/인스펙터(`BpmInspectorPanel.vue`). 버튼이 붙는 위치. Command 기반 도출은 BPM 생성원에서 제외(FR-013).
- **spec 010** (GWT) — Command별 GWT, 모달 스티커 구성 요소.
- **spec 022** (event-storming → DDD) — 그래프→산출물 투영 패턴 참고.
