# Feature Specification: Proposal Impact Artifact Preview

**Feature Branch**: `040-proposal-impact-preview`

**Created**: 2026-06-11

**Status**: Draft

**Input**: User description: "Aggregate/UI/Journey 등의 설계결과물들을 proposal 의 impact 에서 다 열어다 볼 수 있도록 Process / Design / Data 탭에 있던 컴포넌트들을 이용하여 열어볼 수 있는 링크를 제공해주는게 좋겠어. 물론, 이 노드들은 intent 에 임시로 존재하는데, 이 임시 데이터들을 기존 UI들에서 어떻게 보여주는게 좋을까? 임시로 복제본의 neo4j 를 만드는게 좋을까 아니면 pydantic 오브젝트에 담을 수 있는 간략한 형태의 json? 등의 형식으로 만들어서 proposal id 별로 serialization을 해놓고 보여주는게 나을까?"

## Context & Problem

039 Proposal Lifecycle 에서 AI 인텐트 분해는 자연어 제안을 **Strategic Diff**(Epic / Feature / UserStory / Process 변경안)와 **Tactical Diff**(Aggregate / Command / Event / VO 변경안)로 분리하고, 각 제안이 건드리는 노드를 **Impact Map** 으로 산출한다. 이 결과는 현재 Proposal 상세 화면에서 **표·diff 텍스트** 형태로만 보인다.

문제는, 검토자(PO/설계자)가 "이 제안이 실제로 만들어 낼/바꿀 Aggregate, UI 화면, 비즈니스 프로세스(Journey)가 *기존 설계 도구에서 보면 어떤 모습인가*"를 한눈에 확인할 길이 없다는 것이다. 제품에는 이미 이 산출물들을 시각적으로 보여 주는 1급 도구가 있다:

| 탭 | 컴포넌트 | 보여 주는 산출물 |
|----|----------|------------------|
| **Data** | `AggregatePanel` | Aggregate / VO / Enum (도메인 모델) |
| **Design** | `CanvasWorkspace` | UI 화면 / 와이어프레임 / UI 플로우 |
| **Process** | `BpmnPanel` | 비즈니스 프로세스 (BPMN) |
| **Processes** | `EventModelingPanel` | 이벤트 모델링 / Journey (GWT) |

검토자는 제안의 임팩트 항목에서 **링크 한 번**으로 해당 산출물을 이 도구들로 열어, 변경이 적용된 모습을 시각적으로 확인하고 싶어 한다.

핵심 난점: 제안의 신규/변경 노드는 **아직 라이브 그래프(Neo4j)에 존재하지 않는다.** 인텐트 분해 결과로서 Proposal 노드의 `strategicDiff` / `tacticalDiff` / `impactMap` 속성에 **직렬화된 JSON 으로만** 임시 존재한다. 따라서 라이브 그래프만 읽는 기존 뷰어 컴포넌트는 이 임시 노드를 그대로 표시할 수 없다. 이 임시 데이터를 기존 뷰어에 어떻게 공급할지가 본 기능의 설계 중심이다.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 임팩트 항목에서 산출물 뷰어로 열기 (Priority: P1)

검토자가 Proposal 상세의 Impact / Diff 목록에서 임의의 항목(예: "환불 Aggregate", "부분 환불 요청 화면", "환불 처리 프로세스")의 **"열기"** 링크를 누르면, 그 항목 타입에 맞는 기존 뷰어(Data/Design/Process/Processes)가 해당 노드에 **포커스된 상태로** 열린다. 신규/변경 노드는 변경이 **반영된 미리보기 모습**으로, 변경 표시(신규/수정 배지, before/after)가 함께 보인다.

**Why this priority**: 본 기능의 본질. 이 한 가지만 동작해도 "제안이 만들 설계 결과를 시각적으로 검토한다"는 핵심 가치가 성립한다.

**Independent Test**: Aggregate 를 신규 생성하는 제안 하나로, Impact 항목의 "열기"를 눌러 Data 뷰어가 해당 (임시) Aggregate 를 신규 배지와 함께 렌더링하는지 확인.

**Acceptance Scenarios**:

1. **Given** `tacticalDiff` 에 신규 Aggregate(`changeType=CREATE`)를 포함한 Proposal 이 있고, **When** 검토자가 그 항목의 "열기" 링크를 누르면, **Then** Data 뷰어가 미리보기 모드로 열리고 해당 Aggregate 가 "신규" 배지와 함께 표시된다.
2. **Given** `tacticalDiff` 에 기존 Aggregate 수정(`changeType=MODIFY`, VO 추가)을 포함한 Proposal 이 있고, **When** 검토자가 "열기"를 누르면, **Then** 라이브 Aggregate 위에 추가될 VO 가 "추가" 표시로 함께 보인다.
3. **Given** Impact Map 항목이 변경 없는 *기존* 영향 노드(예: 충돌 가능 UserStory)일 때, **When** "열기"를 누르면, **Then** 그 노드의 라이브 모습이 읽기 전용 맥락으로 열린다.
4. **Given** 뷰어가 미리보기 모드로 열려 있을 때, **When** 검토자가 본다면, **Then** 화면에 "PRO-NNN 미리보기 — 임시 데이터, 라이브 설계 아님" 임을 명확히 알리는 표식이 보인다.

---

### User Story 2 - 미리보기가 라이브 설계를 절대 오염시키지 않음 (Priority: P1)

검토자가 제안 미리보기로 어떤 뷰어를 열어 보고 조작(노드 클릭, 확대, 패닝 등)하더라도, **라이브 그래프와 라이브 탭의 데이터는 전혀 바뀌지 않는다.** 미리보기를 닫으면 흔적이 남지 않는다.

**Why this priority**: Constitution I(Graph-as-Source-of-Truth)·039 의 "메인 무결" 원칙. 미리보기가 라이브를 오염시키면 전체 신뢰가 무너진다. P1 안전 요건.

**Independent Test**: 미리보기를 열고 닫은 전후로 라이브 Data 탭의 Aggregate 수·내용이 동일한지, Neo4j 에 임시 노드가 기록되지 않았는지 확인.

**Acceptance Scenarios**:

1. **Given** 검토자가 제안 미리보기를 열어 두고, **When** 같은 Aggregate 의 라이브 Data 탭을 함께 열면, **Then** 라이브 탭에는 제안의 임시 노드가 보이지 않는다.
2. **Given** 검토자가 미리보기를 연 뒤 닫고, **When** Neo4j 를 조회하면, **Then** 그 제안의 임시 노드/관계가 라이브 그래프에 생성되어 있지 않다.
3. **Given** 두 검토자가 서로 다른 제안의 미리보기를 동시에 보더라도, **Then** 한쪽 미리보기가 다른 쪽에 영향을 주지 않는다.

---

### User Story 3 - 여러 산출물 타입을 일관되게 열기 (Priority: P2)

검토자는 한 제안 안에서 Aggregate(Data) 뿐 아니라 UI 화면(Design), 비즈니스 프로세스(Process), Journey/이벤트모델(Processes)에 해당하는 임팩트 항목도 **같은 "열기" 제스처**로 적절한 뷰어에서 확인할 수 있다.

**Why this priority**: 사용자가 "Aggregate/UI/Journey 등"을 모두 언급. 일관된 진입이 검토 효율을 높인다. 단, 각 타입의 임시 데이터 가용성은 인텐트 분해 산출 범위에 따라 다르다(아래 Assumptions 참조).

**Independent Test**: Process 변경(strategicDiff.processes)을 가진 제안에서 그 항목의 "열기"가 Process 뷰어를 해당 프로세스에 포커스해 여는지 확인.

**Acceptance Scenarios**:

1. **Given** `strategicDiff.processes` 에 프로세스 변경을 포함한 제안에서, **When** 그 항목의 "열기"를 누르면, **Then** Process(BPMN) 뷰어가 해당 프로세스 맥락으로 열린다.
2. **Given** 임팩트 항목이 UI 화면을 가리키나 제안에 그 화면의 임시 정의가 없을 때(라이브에만 존재), **When** "열기"를 누르면, **Then** Design 뷰어가 라이브 화면을 읽기 전용 맥락으로 연다.
3. **Given** 임팩트 항목 타입에 대응하는 뷰어가 없거나 해당 산출물이 미리보기로 표현 불가할 때, **When** 검토자가 보면, **Then** "열기" 링크 대신 비활성/사유 안내가 표시된다(끊긴 링크 금지).

---

### User Story 4 - 미리보기에서 편집 → 제안 diff 계획에 반영 (Priority: P2)

검토자/모델러가 미리보기 설계 화면에서 익숙한 편집 도구(Inspector 직접 편집, Chat 자연어 "수정 요청")로 제안된 설계를 다듬으면, 그 수정이 **라이브 그래프가 아니라 해당 Proposal 의 diff 계획(tacticalDiff)에 즉시 반영**되고, 미리보기가 그 결과로 재렌더된다. 라이브 디자인 그래프는 전혀 바뀌지 않는다.

**Why this priority**: 미리보기가 단순 열람을 넘어 "제안을 익숙한 설계 도구로 다듬는" 작업대가 된다. 인텐트 분해 결과를 표/JSON 이 아니라 실제 뷰어에서 손보고 그 결과가 제안에 남으므로 검토·보정 루프가 짧아진다.

**Independent Test**: 미리보기에서 배송 Aggregate 에 속성 1개를 추가·저장 → 그 제안의 tacticalDiff 에 해당 속성이 남고, 라이브 그래프엔 그 Aggregate 가 여전히 존재하지 않음을 확인.

**Acceptance Scenarios**:

1. **Given** Data 미리보기에서 신규 Aggregate 가 열려 있을 때, **When** Inspector 에서 속성을 추가/수정/삭제하고 저장하면, **Then** 그 변경이 Proposal 의 tacticalDiff 항목에 반영되고 미리보기에 즉시 보인다.
2. **Given** 미리보기에서 Chat "수정 요청"으로 변경 초안을 승인하면, **When** 적용하면, **Then** 변경이 라이브가 아니라 **제안 diff** 에 반영되고 "라이브 설계는 변경되지 않음" 안내가 표시된다.
3. **Given** 미리보기 편집을 여러 번 수행한 뒤, **When** 라이브 그래프를 조회하면, **Then** 해당 디자인 노드(예: 신규 Aggregate)는 라이브에 생성/변경되어 있지 않다(머지 전까지 무변경).
4. **Given** 라이브에 이미 존재하는 Aggregate 를 미리보기에서 수정하면, **When** 저장하면, **Then** 제안 diff 에 그 Aggregate 에 대한 MODIFY 항목이 생성/갱신된다(라이브 원본은 불변).

---

### Edge Cases

- **임시 노드가 라이브 부모를 참조**: 신규 VO 가 기존 Aggregate 에 속하거나, 신규 UserStory 가 기존 Feature 에 속할 때 — 미리보기는 라이브 맥락 위에 임시 항목을 올려 보여야 한다.
- **미리보기 편집 대상이 라이브 Aggregate**: diff 에 아직 항목이 없는 라이브 Aggregate 를 미리보기에서 수정하면 MODIFY 항목을 새로 만든다(US4-4).
- **편집 후 즉시 재렌더**: 편집 저장 시 백엔드가 갱신된 투영을 돌려주고 뷰어가 그 결과로 교체되어야 한다(stale 화면 금지).
- **신규 노드끼리 참조**: 같은 제안 안에서 신규 Command 가 신규 Aggregate 를 가리킬 때 — 두 임시 노드가 함께 해석되어야 한다(`id=null` 항목의 임시 식별자 부여 필요).
- **이미 ACCEPTED/DESTROYED 된 제안**: 머지 후엔 라이브에 반영되었거나 폐기됨 — 미리보기는 당시 직렬화 스냅샷을 보여 주되 "이미 반영됨/폐기됨" 맥락을 표시.
- **라이브 노드가 그 사이 삭제됨**: `MODIFY` 대상이 라이브에서 사라졌을 때 — 미리보기는 충돌을 표시하고 깨지지 않아야 한다.
- **대상 노드 없음(`nodeId=null`, 신규)**: 라이브 조회 키가 없으므로 순수 임시 데이터만으로 렌더링.
- **대용량 임팩트**: 수십 개 항목의 임팩트에서 각 "열기"가 빠르게 응답해야 한다.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 시스템은 Proposal 의 Impact Map / Strategic Diff / Tactical Diff 의 각 항목에 대해, 그 항목이 시각적 뷰어로 표현 가능하면 **"열기" 진입점**을 제공해야 한다.
- **FR-002**: "열기"는 항목의 노드 타입에 따라 올바른 기존 뷰어로 라우팅해야 한다 — Aggregate/VO/Enum → Data, UI 화면/플로우 → Design, 비즈니스 프로세스 → Process, Journey/이벤트모델 → Processes.
- **FR-003**: 뷰어는 열릴 때 해당 노드에 **포커스**(선택/스크롤)되어, 검토자가 임팩트 항목과 화면 속 노드를 바로 연결할 수 있어야 한다.
- **FR-004**: 신규(`CREATE`) 또는 변경(`MODIFY`) 노드는 제안의 직렬화된 diff 를 적용한 **미리보기 형태**로 렌더링되어야 하며, 신규/변경 여부와 before/after 가 시각적으로 구분되어야 한다.
- **FR-005**: 변경 없는 기존 영향 노드(impactMap 상의 충돌 노드 등)는 라이브 모습 그대로 읽기 전용 맥락으로 열려야 한다.
- **FR-006**: 미리보기는 **라이브 그래프에 대해 읽기 전용**이며, 어떤 조작도 라이브 Neo4j 디자인 그래프(Aggregate/Command/Event 등 노드)나 라이브 탭 데이터를 변경해서는 안 된다. (단, 미리보기 화면에서의 *편집*은 라이브가 아니라 제안의 diff 계획에 반영된다 — US4 참조.)
- **FR-007**: 미리보기로 임시 데이터를 표시하는 동안, 화면에는 "이것은 특정 Proposal 의 임시 미리보기이며 라이브 설계가 아니다"라는 식별 표식이 항상 보여야 한다.
- **FR-008**: 시스템은 임시 노드가 라이브 노드를 부모/참조로 가질 때, 라이브 맥락 위에 임시 변경을 **겹쳐(overlay)** 일관된 모습으로 합성해야 한다.
- **FR-009**: 같은 제안 안의 신규 노드끼리의 참조가 미리보기 안에서 해소되도록, `id` 가 없는 신규 항목에 제안 범위의 **임시 식별자**를 부여해야 한다.
- **FR-010**: 해당 항목을 뷰어로 표현할 수 없을 때(대응 뷰어 없음/표현 불가), 깨진 링크 대신 **비활성 상태와 사유**를 보여야 한다.
- **FR-011**: 임시 미리보기 데이터의 출처는 Proposal 단위로 식별/조회 가능해야 하며(제안 ID 기준), 여러 제안의 미리보기가 서로 격리되어야 한다.
- **FR-012**: 임시 미리보기 데이터는 영구 라이브 그래프와 **분리 저장/표현**되어, 제안이 폐기되면 라이브에 잔존물이 남지 않아야 한다.
- **FR-013**: 미리보기 설계 화면에서의 편집(Inspector 직접 편집, Chat 자연어 수정)은 **라이브 디자인 그래프가 아니라 해당 Proposal 의 diff 계획(tacticalDiff)에** 반영되어야 한다.
- **FR-014**: 편집 저장 시 시스템은 갱신된 미리보기 투영을 반환하고 뷰어가 **즉시 그 결과로 재렌더**해야 한다(편집 → 반영이 한 동작으로 느껴지도록).
- **FR-015**: 라이브에 이미 존재하는 노드를 미리보기에서 편집하면, 시스템은 제안 diff 에 해당 노드의 **MODIFY 항목을 생성/갱신**하고 라이브 원본은 변경하지 않아야 한다.
- **FR-016**: 편집은 제안 단위로 격리되어, 한 제안의 미리보기 편집이 다른 제안이나 라이브 설계에 영향을 주어서는 안 된다.

### Key Entities *(include if feature involves data)*

- **Proposal Preview Projection (제안 미리보기 투영)**: 특정 Proposal ID 에 대해, 라이브 그래프의 관련 부분(영향/참조 노드)과 제안의 직렬화된 Strategic/Tactical Diff 를 합성한 **읽기 전용 가상 그래프 조각**. 라이브 그래프에 기록되지 않으며 제안 ID 로 식별된다.
- **Preview Node (미리보기 노드)**: 투영 안의 개별 설계 노드. 출처가 `live`(변경 없음) / `live+modified`(라이브 + 임시 변경) / `temporary`(신규, 라이브 미존재) 중 하나임을 나타내는 표식과, 신규 노드용 임시 식별자를 가진다.
- **Open Link (열기 진입점)**: 임팩트/diff 항목에서 대상 뷰어·대상 노드·미리보기 컨텍스트(제안 ID)로 연결되는 라우팅 정보.
- **Viewer Preview Context (뷰어 미리보기 컨텍스트)**: 기존 뷰어가 라이브 대신 특정 제안의 투영을 데이터 소스로 사용하도록 하는 진입 상태(라이브 무변경 + 미리보기 식별 표식 포함). 이 상태에서의 편집은 제안 diff 로 라우팅된다.
- **Preview Edit (미리보기 편집)**: 미리보기 화면에서 발생한 변경(Inspector 직접 편집 또는 Chat 자연어 수정). 라이브 그래프가 아니라 Proposal 의 tacticalDiff 항목으로 정규화되어 반영된다. 신규(temporary) 노드는 해당 항목을 갱신, 라이브 노드는 MODIFY 항목을 생성/갱신.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 검토자는 임팩트 항목에서 **한 번의 클릭**으로 대응 산출물 뷰어를 열 수 있다.
- **SC-002**: 신규/변경 노드가 표현 가능한 임팩트 항목의 **95% 이상**이 시각 뷰어로 열려 변경 모습을 보여 준다(나머지는 사유와 함께 비활성).
- **SC-003**: 미리보기를 열고 조작·닫은 전후로 라이브 그래프와 라이브 탭 데이터가 **100% 동일**하다(잔존물 0).
- **SC-004**: "열기" 후 뷰어가 대상 노드에 포커스되어 보이기까지 **2초 이내**.
- **SC-005**: 검토자가 별도 안내 없이도 자신이 라이브가 아닌 **제안 미리보기**를 보고 있음을 인지한다(식별 표식 인지 테스트 90% 이상).
- **SC-006**: 동일 "열기" 제스처가 **4개 뷰어**(Data/Design/Process/Processes) 모두에서 일관되게 동작한다.
- **SC-007**: 미리보기에서의 편집(Inspector·Chat)이 **100% 제안 diff 에만** 반영되고 라이브 그래프에는 0건 반영된다(편집 전후 라이브 노드/관계 동일).
- **SC-008**: 편집 저장 → 미리보기 재렌더가 **2초 이내**에 보인다.

## Assumptions

- **기존 뷰어 재사용**: 새 뷰어를 만들지 않고 `AggregatePanel`(Data)·`CanvasWorkspace`(Design)·`BpmnPanel`(Process)·`EventModelingPanel`(Processes)을 재사용한다. 이 컴포넌트들은 현재 Pinia 스토어를 통해 **라이브 그래프**에서 데이터를 적재하므로, 미리보기를 위해서는 "데이터 소스를 특정 제안의 투영으로 전환하는 읽기 전용 진입 경로"가 필요하다.
- **임시 데이터 표현 방식(✅ 확정 — 오버레이 투영)**: 별도의 **복제 Neo4j 인스턴스/DB 를 만들지 않는다.** 제안의 임시 노드는 이미 Proposal 노드의 `strategicDiff`/`tacticalDiff`/`impactMap` 속성에 직렬화 JSON 으로 존재한다. 미리보기 시점에 **백엔드가 (라이브 그래프의 관련 슬라이스) + (제안 diff 오버레이)** 를 합성한 **읽기 전용 투영(Pydantic/JSON)** 을 제안 ID 별로 만들어 뷰어에 공급한다. 복제 DB 는 동기화·정리·단일진실원천(Constitution I) 측면에서 부담이 크고, 라이브에 임시 기록 후 롤백하는 방식은 오염 위험이 있어 배제한다.
- **타입별 임시 데이터 가용성**: 인텐트 분해는 현재 **Aggregate/Command/Event/VO**(Tactical)와 **Epic/Feature/UserStory/Process**(Strategic)를 생성한다. 따라서 Data 와 Process 는 임시 신규/변경 노드를 미리보기로 풍부하게 보여 줄 수 있고, **UI 화면(Design)·이벤트모델 Journey(Processes)** 는 대개 인텐트가 신규 생성하지 않으므로 임팩트로 *참조되는 라이브 노드*를 읽기 전용으로 여는 형태가 기본이다. 두 경우(임시 합성 / 라이브 포커스) 모두 동일한 "열기" UX 로 다룬다.
- **편집 가능 미리보기(라이브엔 무변경)**: 미리보기는 라이브 그래프에 대해서는 읽기 전용이지만, 화면에서의 편집(Inspector·Chat)은 제안의 diff 계획(tacticalDiff)에 반영된다(US4/FR-013~016). 편집 결과의 원천 저장소는 여전히 Proposal 노드의 직렬화 속성이며, 별도 라이브 노드를 만들지 않는다.
- **저장 위치**: 임시 미리보기 데이터의 영속 원천은 Proposal 노드의 기존 직렬화 속성이며, 본 기능은 별도 영속 저장소를 추가하지 않는다(투영은 요청 시 합성).
- **039 의존**: 본 기능은 039 Proposal Lifecycle 의 `strategicDiff`/`tacticalDiff`/`impactMap` 산출물과 Proposal 상세 UI 를 전제로 한다.

## Dependencies

- **039 Proposal Lifecycle** — Proposal 노드의 직렬화 diff 속성, Impact Map, Proposal 상세 UI.
- 기존 뷰어 컴포넌트 — `AggregatePanel`, `CanvasWorkspace`, `BpmnPanel`, `EventModelingPanel` 및 각 Pinia 스토어.
