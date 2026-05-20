# Feature Specification: Requirements Tab

**Feature Branch**: `026-requirements-tab`
**Created**: 2026-05-17
**Status**: Draft
**Input**: User description: "BPMN·이벤트 모델링·디자인 탭 앞에 'Requirements' 탭을 추가. 왼쪽 트리는 Epic(BC)→Feature→User Story→Acceptance Criteria로 드릴다운. user story 클릭 시 'I want~ so that~'과 인수조건을 보기 좋게 표시하고, 연결된 command 설계 괘적을 탭 내부 캔버스에 가시화. 신규 요구사항 추가(문서/자연어), 문서 업로드 버튼을 이 탭으로 이동, 업로드는 증분 upsert(자동 삭제 금지)·삭제는 별도 버튼. user story drag-n-drop으로 feature 이동, feature/user story 삭제. 추가·삭제 시 영향도 분석 자동 수행."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 요구사항을 Epic→Feature→User Story로 탐색 (Priority: P1)

기획자가 새 "Requirements" 탭을 열면 왼쪽에 요구사항 전용 트리가 나타난다. 트리는 Epic(Bounded Context)을 최상위로, 그 아래 Feature, 그 아래 User Story, 그 아래 Acceptance Criteria 순으로 드릴다운된다. User Story 노드를 클릭하면 오른쪽 영역에 "As a … I want … so that …" 문장과 인수조건이 읽기 좋은 형태로 표시된다.

**Why this priority**: 요구사항을 구조적으로 보고 이해하는 것이 이 탭의 핵심 가치이며, 다른 모든 기능(추가/이동/삭제/영향도)의 진입점이다. 이것만 있어도 기획자가 요구사항 현황을 파악하는 MVP가 성립한다.

**Independent Test**: 이미 인제스트된 데이터가 있는 상태에서 Requirements 탭을 열어 트리가 Epic→Feature→User Story→Acceptance Criteria 4단계로 펼쳐지고, User Story 클릭 시 본문이 표시되는지 확인.

**Acceptance Scenarios**:

1. **Given** 인제스트된 요구사항 데이터가 존재, **When** 기획자가 Requirements 탭을 연다, **Then** 왼쪽 트리에 Epic(BC) 목록이 표시되고 각 Epic을 펼치면 Feature, User Story, Acceptance Criteria가 순서대로 드릴다운된다.
2. **Given** Requirements 탭이 열려 있음, **When** 기획자가 트리에서 User Story를 클릭한다, **Then** 오른쪽 상세 영역에 "As a {role} I want {action} so that {benefit}" 문장과 해당 User Story의 인수조건이 보기 좋게 렌더링된다.
3. **Given** User Story가 어떤 Feature에도 속하지 않음, **When** 트리를 본다, **Then** 해당 User Story는 "미분류(Unassigned)" 그룹 아래에 표시된다.

---

### User Story 2 - User Story의 설계 괘적을 탭 내부 캔버스에서 확인 (Priority: P1)

기획자가 User Story를 클릭하면, 그 User Story가 구현하는 Command를 기점으로 이어지는 설계 괘적(policy→command→event 흐름)이 Requirements 탭 내부 캔버스 영역에 간략하게 렌더링된다. 괘적은 해당 Command와 연결된 aggregate·event·policy·후속 command·aggregate만 포함한다.

**Why this priority**: 요구사항이 "어떻게 구현되고 있는지"를 같은 화면에서 보는 것이 기획자에게 큰 가치를 주며, 요구사항과 설계의 연결을 검증하는 핵심 흐름이다.

**Independent Test**: Command에 연결된 User Story를 클릭하여 탭 내부 캔버스에 command-aggregate-event-policy-command-aggregate 괘적만 표시되고 무관한 노드는 제외되는지 확인.

**Acceptance Scenarios**:

1. **Given** User Story가 Command에 `IMPLEMENTS`로 연결됨, **When** 해당 User Story를 클릭한다, **Then** Requirements 탭 내부 캔버스에 그 Command에서 출발하는 설계 괘적(연결된 aggregate, event, policy, 후속 command/aggregate)만 로딩되어 표시된다.
2. **Given** User Story가 어떤 Command에도 연결되지 않음, **When** 해당 User Story를 클릭한다, **Then** 캔버스는 "연결된 설계 없음" 상태를 안내하고 본문 정보만 표시된다.
3. **Given** 괘적 캔버스가 표시됨, **When** 다른 User Story를 클릭한다, **Then** 캔버스가 새 User Story의 괘적으로 교체된다.

---

### User Story 3 - 신규 요구사항을 문서/자연어로 추가 (Priority: P1)

기획자가 Requirements 탭에서 신규 요구사항을 추가한다. 문서 업로드 또는 자연어 입력으로 새 Feature와 User Story를 만들 수 있다. 문서 업로드 버튼은 이 탭 안에 배치되며, 업로드는 기존 데이터를 삭제하지 않고 증분(upsert) 방식으로 병합된다. LLM이 신규 User Story를 BC와 Feature로 자동 분류하고, 기획자는 이후 트리에서 수동 조정할 수 있다.

**Why this priority**: 이 탭은 기획자의 작업 공간이며, 요구사항을 추가·확장하는 능력이 핵심이다. 기존 자동 삭제 동작을 증분 upsert로 바꾸는 것은 데이터 보존 측면에서 중요하다.

**Independent Test**: 기존 데이터가 있는 상태에서 Requirements 탭의 업로드 버튼으로 새 문서를 올려, 기존 데이터가 유지된 채 신규 User Story가 추가되고 BC/Feature로 자동 분류되는지 확인.

**Acceptance Scenarios**:

1. **Given** Requirements 탭이 열려 있고 기존 요구사항 데이터가 존재, **When** 기획자가 탭 내 문서 업로드 버튼으로 새 문서를 올린다, **Then** 기존 데이터는 삭제되지 않고 신규 요구사항이 증분으로 병합되며 트리에 추가된다.
2. **Given** Requirements 탭, **When** 기획자가 자연어로 새 요구사항을 입력한다, **Then** 신규 User Story가 생성되고 LLM이 BC·Feature로 분류하여 트리의 해당 위치에 배치된다.
3. **Given** 신규 추가가 완료됨, **When** 영향도 분석이 백그라운드에서 실행된다, **Then** 기존 User Story와의 중복·충돌이나 설계 영향이 발견되면 보고된다(User Story 5 참조).

---

### User Story 4 - User Story 재배치 및 Feature/User Story 삭제 (Priority: P2)

기획자가 트리에서 User Story를 다른 Feature 아래로 drag-n-drop 하여 옮길 수 있고, Feature나 User Story를 삭제할 수 있다. 삭제 시 영향도 분석이 백그라운드로 수행되어 설계상 영향을 보고한다.

**Why this priority**: 요구사항 구조를 정리하고 유지보수하는 기능. 탐색·추가가 먼저 동작해야 의미가 있으므로 P2.

**Independent Test**: 트리에서 User Story를 다른 Feature로 드래그하여 소속이 바뀌고, Feature 삭제 시 확인 절차를 거쳐 제거되는지 확인.

**Acceptance Scenarios**:

1. **Given** 트리에 여러 Feature가 존재, **When** 기획자가 User Story를 다른 Feature 노드로 drag-n-drop 한다, **Then** 해당 User Story의 Feature 소속이 변경되어 새 위치에 표시되고 변경이 영속화된다.
2. **Given** 트리에서 Feature를 선택, **When** 기획자가 삭제를 요청한다, **Then** 삭제 확인 절차 후 Feature가 제거되며, Feature 하위 User Story의 처리 방식(미분류로 이동 또는 함께 삭제)을 기획자가 선택한다.
3. **Given** User Story를 삭제, **When** 삭제가 완료된다, **Then** 영향도 분석이 백그라운드로 실행되어 연결된 설계(Command 등)에 미치는 영향을 보고한다.

---

### User Story 5 - 추가·삭제 시 영향도 자동 분석 및 보고 (Priority: P2)

기획자가 요구사항을 추가하거나 삭제하면, 시스템이 백그라운드에서 영향도 분석을 수행한다. 기존 User Story와의 중복·충돌, 설계상의 영향을 분석하여 문제가 발견되면 비차단 방식으로 리포트한다. 작업 흐름은 분석을 기다리지 않고 계속 진행된다.

**Why this priority**: 요구사항 품질을 자동으로 지켜주는 안전망. 추가/삭제 기능에 의존하므로 P2.

**Independent Test**: 기존 User Story와 의도적으로 유사한 User Story를 추가하고, 백그라운드 분석 후 중복 경고 리포트가 비차단으로 나타나는지 확인.

**Acceptance Scenarios**:

1. **Given** 기존 User Story와 유사·중복되는 신규 User Story 추가, **When** 백그라운드 영향도 분석이 완료된다, **Then** 중복 가능성이 리포트 패널/배지 형태로 비차단 알림된다.
2. **Given** 요구사항 추가·삭제 작업, **When** 영향도 분석이 실행 중이다, **Then** 기획자는 분석 완료를 기다리지 않고 다른 작업을 계속할 수 있다.
3. **Given** 영향도 분석에서 설계 충돌이나 영향이 발견됨, **When** 분석이 끝난다, **Then** 영향받는 요소(중복 User Story, 영향받는 Command/Event 등)가 리포트에 명시된다.
4. **Given** 분석 결과 문제가 없음, **When** 분석이 끝난다, **Then** 별도 경고 없이 정상 상태로 표시된다.

---

### User Story 6 - 요구사항 데이터 명시적 삭제 (Priority: P3)

기획자가 별도의 삭제 버튼으로 요구사항 데이터를 명시적으로 비울 수 있다. 업로드 동작은 더 이상 자동으로 데이터를 삭제하지 않으므로, 전체 초기화는 의도적인 별도 액션으로만 가능하다.

**Why this priority**: 안전 장치 성격의 보조 기능. 증분 upsert가 기본 동작이 된 뒤 보완으로 필요하므로 P3.

**Independent Test**: 업로드와 무관하게 삭제 버튼을 눌러 확인 절차 후 데이터가 비워지는지 확인.

**Acceptance Scenarios**:

1. **Given** Requirements 탭에 데이터가 존재, **When** 기획자가 별도 삭제 버튼을 누른다, **Then** 확인 절차 후 요구사항 데이터가 삭제된다.
2. **Given** 문서 업로드를 진행, **When** 업로드가 시작된다, **Then** 어떤 자동 삭제 확인 다이얼로그도 나타나지 않고 증분 병합만 수행된다.

---

### Edge Cases

- User Story가 BC에는 분류되었으나 Feature가 없을 때 → 해당 Epic 아래 "미분류 Feature" 그룹에 표시.
- User Story가 BC와 Feature 모두 없을 때 → 트리 최상단 "미분류" 그룹에 표시.
- Command에 GWT(인수조건)가 아직 생성되지 않은 User Story → 인수조건 영역에 "인수조건 없음" 안내.
- drag-n-drop으로 User Story를 다른 BC의 Feature로 이동 시 → BC 소속도 함께 변경되며, 영향도 분석이 트리거된다.
- 자연어 입력이 모호하여 BC/Feature 자동 분류가 불확실할 때 → User Story는 생성하되 "미분류"로 두고 경고 표시.
- 영향도 분석이 백그라운드에서 실패하거나 지연될 때 → 작업은 정상 진행되고 분석 상태만 "분석 실패/지연"으로 표시.
- 하나의 Feature를 삭제할 때 하위에 User Story가 남아 있는 경우 → 하위 User Story를 미분류로 이동할지 함께 삭제할지 선택을 요구.
- 동일 문서를 다시 업로드(재인제스트)할 때 → 증분 upsert로 동일 요구사항은 중복 생성되지 않고 병합된다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 시스템은 기존 탭 목록(BPMN, Event Modeling, Big picture, Design, Aggregate, Claude Code)의 맨 앞에 "Requirements" 탭을 추가해야 한다.
- **FR-002**: Requirements 탭은 왼쪽에 요구사항 전용 트리를 표시하며, 트리는 Epic(Bounded Context) → Feature → User Story → Acceptance Criteria의 4단계 드릴다운 구조를 가져야 한다.
- **FR-003**: 트리는 디자인 뷰의 BC 단위 좌측 트리와 동일한 BC 분류를 따르되, Aggregate/Command/Event 등 설계 노드 대신 User Story만 노출해야 한다.
- **FR-004**: 사용자가 트리에서 User Story를 클릭하면, "As a {role} I want {action} so that {benefit}" 문장과 인수조건을 가독성 있는 형태로 표시해야 한다.
- **FR-005**: 시스템은 User Story의 인수조건으로, 해당 User Story가 구현하는 Command에 연결된 Given-When-Then(GWT)을 표시해야 한다.
- **FR-006**: 문서 최초 입력 시 User Story 분해 과정에서, 시스템은 User Story를 Bounded Context로 분류함과 동시에 Feature 묶음으로도 그룹화해야 한다.
- **FR-007**: 시스템은 Feature 개념을 BC와 User Story 사이의 그룹 단위로 모델에 도입하고, BoundedContext–Feature–UserStory 간 소속 관계를 영속화해야 한다.
- **FR-008**: 시스템은 각 User Story가 어떤 Aggregate의 Command를 구현하는지를 기존 온톨로지의 `IMPLEMENTS` 관계로 확인하고, 트리에서 User Story 선택 시 연결된 Command를 식별해야 한다.
- **FR-009**: 사용자가 User Story를 클릭하면, 시스템은 연결된 Command를 기점으로 하는 설계 괘적(연결된 aggregate, event, policy, 후속 command/aggregate)만 로딩하여 Requirements 탭 내부 캔버스 영역에 렌더링해야 한다.
- **FR-010**: 괘적 캔버스는 무관한 노드를 제외하고 command-aggregate-event-policy-command-aggregate 범위로 간략하게 표현해야 하며, 기존 Design 탭의 캔버스 렌더링 방식을 재사용해야 한다.
- **FR-011**: Requirements 탭은 신규 Feature와 User Story를 추가하는 기능을 제공해야 하며, 입력 방식으로 문서 업로드와 자연어 입력을 모두 지원해야 한다.
- **FR-012**: 문서 업로드 버튼은 Requirements 탭 영역 내에 배치되어야 한다.
- **FR-013**: 문서 업로드는 기존 데이터를 자동으로 삭제하지 않고 증분 upsert(병합) 방식으로 동작해야 하며, 업로드 시 기존 데이터 삭제를 묻는 동작을 제거해야 한다.
- **FR-014**: 시스템은 요구사항 데이터를 명시적으로 삭제하는 별도 버튼/액션을 제공해야 하며, 이 액션은 실행 전 사용자 확인을 받아야 한다.
- **FR-015**: 사용자는 트리에서 User Story를 다른 Feature 아래로 drag-n-drop 하여 소속을 변경할 수 있어야 하며, 변경은 영속화되어야 한다.
- **FR-016**: 사용자는 Feature 또는 User Story를 삭제할 수 있어야 하며, Feature 삭제 시 하위 User Story 처리 방식(미분류 이동 또는 함께 삭제)을 선택할 수 있어야 한다.
- **FR-017**: User Story 추가 또는 삭제, Feature 삭제 시 시스템은 영향도 분석을 자동으로 트리거해야 한다.
- **FR-018**: 영향도 분석은 기존 User Story와의 중복·충돌 여부 및 설계상의 영향을 평가해야 하며, 기존에 일부 구현된 변경 영향 분석 기능을 재사용·확장해야 한다.
- **FR-019**: 영향도 분석은 백그라운드에서 비차단으로 수행되어야 하며, 사용자는 분석 완료를 기다리지 않고 작업을 계속할 수 있어야 한다.
- **FR-020**: 영향도 분석에서 문제가 발견되면, 시스템은 영향받는 요소를 명시한 리포트를 비차단 알림(리포트 패널/배지 등)으로 제공해야 한다. 문제가 없으면 별도 경고를 표시하지 않는다.
- **FR-021**: 신규 자연어/문서 입력 시 시스템은 User Story를 BC와 Feature로 자동 분류해야 하며, 사용자는 트리에서 수동으로 분류를 조정할 수 있어야 한다.
- **FR-022**: BC 또는 Feature 자동 분류가 불확실한 User Story는 생성하되 "미분류" 상태로 두고 사용자에게 표시해야 한다.

### Key Entities *(include if feature involves data)*

- **Epic (Bounded Context)**: 요구사항 트리의 최상위 그룹. 기존 온톨로지의 Bounded Context와 동일한 실체이며, Requirements 탭에서 "Epic"으로 표현된다.
- **Feature**: BC와 User Story 사이의 새 그룹 단위. 관련 User Story 묶음을 나타내며, 하나의 BC에 속하고 여러 User Story를 포함한다. 이름과 설명을 가진다.
- **User Story**: "As a {role} I want {action} so that {benefit}" 형태의 요구사항 단위. 하나의 Feature에 소속(또는 미분류)되고, 하나의 Command를 구현한다(`IMPLEMENTS`). role/action/benefit/우선순위/상태를 가진다.
- **Acceptance Criteria (GWT)**: User Story의 인수조건. 해당 User Story가 구현하는 Command에 연결된 Given-When-Then으로 표현된다.
- **Command / Aggregate / Event / Policy**: 설계 괘적을 구성하는 기존 설계 노드. User Story 선택 시 연결된 부분 집합만 캔버스에 로딩된다.
- **Impact Report**: 요구사항 추가·삭제 시 생성되는 영향도 분석 결과. 중복 가능 User Story, 충돌, 영향받는 설계 요소 목록을 포함한다.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 기획자는 Requirements 탭을 열어 Epic→Feature→User Story→Acceptance Criteria 4단계로 임의의 요구사항을 5초 이내에 찾아 열어볼 수 있다.
- **SC-002**: 인제스트된 User Story의 95% 이상이 자동으로 BC와 Feature에 분류되어 트리에 배치된다(미분류 비율 5% 이하).
- **SC-003**: User Story 클릭 후 연결된 설계 괘적이 탭 내부 캔버스에 2초 이내에 렌더링된다.
- **SC-004**: 문서를 증분 업로드해도 기존 요구사항 데이터의 100%가 보존된다(자동 삭제로 인한 데이터 손실 0건).
- **SC-005**: 요구사항 추가·삭제 후 영향도 분석 리포트가 사용자 작업을 차단하지 않고 백그라운드 완료 후 표시되며, 중복/충돌 사례의 90% 이상을 보고한다.
- **SC-006**: 기획자는 문서 업로드, 자연어 입력 등 별도 화면 이동 없이 Requirements 탭 한 곳에서 요구사항 추가·이동·삭제 작업을 모두 완료할 수 있다.

## Assumptions

- 기존 인제스트 파이프라인은 이미 User Story를 분해하고 BC로 분류하고 있으며, Feature 그룹화 단계를 추가로 도입한다. Feature는 LLM이 자동 도출하고 사용자가 수동 조정한다.
- User Story↔Command는 기존 온톨로지의 `IMPLEMENTS` 관계로 이미 연결되어 있어 추가 연결 작업 없이 활용한다.
- 인수조건은 기존에 Command/Policy에 부착된 GWT(Given-When-Then)를 재사용하며, User Story 노드 자체에도 별도 acceptanceCriteria 속성이 있으나 트리 드릴다운의 "Acceptance Criteria"는 Command의 GWT를 기준으로 한다.
- 설계 괘적 캔버스는 기존 Design 탭의 캔버스 렌더링 컴포넌트를 재사용하되, User Story가 구현하는 Command 범위로 필터링하여 Requirements 탭 내부에 임베드한다.
- 영향도 분석은 spec 004(change-impact-planning)에서 일부 구현된 변경 영향 분석 기능을 재사용·확장한다.
- 증분 upsert는 기존 인제스트의 MERGE 기반 동작을 그대로 활용하며, 업로드 시 자동 데이터 삭제 동작만 제거한다.
- 명시적 삭제 액션은 기존 데이터 초기화 기능을 별도 버튼으로 노출한다.
- "Big picture"와 "Aggregate" 등 기존 탭 구성과 좌측 트리(NavigatorPanel)는 유지되며, Requirements 탭은 별도 모드로 동작한다.
- 한 User Story = 한 Command 가정이 유효하다.
