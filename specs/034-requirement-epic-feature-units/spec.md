# Feature Specification: Epic / Feature 단위 요구사항 등록·뷰·편집, 하위 US 자동 생성, DDD 적합성 검증

**Feature Branch**: `034-requirement-epic-feature-units`

**Created**: 2026-05-30

**Status**: Draft

**Input**: User description(누적):
- "Requirement 에서 + 해서 추가할때는 User story 단위로 추가하는 것도 지원하지만, Epic / Feature 단위의 등록도 가능하며, 각 Epic 과 Feature 들도 자신의 뷰 페이지와 편집 페이지가 제공됨. 거기에 따라서 clarification radar 가 필터링 되어 보이기도 해야 함."
- "Epic 과 Feature 가 추가되면, 이에 대한 하위 US 들을 자동으로 생성하는 기능이 동작해야 함. … 사용자는 설정에서 in-process LLM 에이전트나 claude ide 둘 중 하나를 선택할 수 있다. 생성된 하위 US는 제안 후 사용자 확인. 사용자 로컬에 클로드와 speckit 설치 없으면 설치하도록 유도."
- "epic 이 추가되거나 feature 가 추가될 때 해당 feature 의 위치가 부적절하다고 판단될 수 있음. 즉, DDD 에 의거하여 해당 feature 가 해당 epic(BC) 영역 내에 들어가는 것이 옳지 않거나 feature 가 너무 큰 범위로 정의될 수도 있어 검증해줘야 함. 어떤 요구사항이든 그 굵기와 무관하게 우리가 정의한 BC 내에 feature 와 us 수준으로 적절히 나뉘어 추가되어야 함. 기존 spec 과의 충돌/align 은 speckit 스킬로 검증되어야 하며, 없다면 robo-spec skill 에서 speckit-specify 를 override 하거나 신규 스킬로 추가."

## Overview

오늘 Requirements 화면의 "+" 버튼은 **User Story 한 단계**만 추가할 수 있다. Epic(= 최상위 그룹, 현재 BoundedContext에 해당)과 Feature(중간 그룹)는 시스템이 자동 분류하거나 인제스천을 통해서만 생기고, 사용자가 직접 의도적으로 등록할 수단이 없다. 또한 Epic·Feature를 선택해도 전용 보기/편집 화면이 없어, 트리 노드 클릭 시 User Story만 상세가 뜬다. clarification radar(명확도 레이더) 역시 데이터상 Project/Epic/Feature 범위를 지원하지만, 트리에서 Epic·Feature를 선택했을 때 그 범위로 자동 필터링되어 보이지는 않는다. 그리고 Epic/Feature를 추가해도 그 하위 User Story가 자동으로 채워지지 않으며, 추가되는 Feature가 올바른 BC(Epic)에 적정 입도로 들어가는지에 대한 검증이 없다.

이 기능은 (1) "+" 추가 흐름을 **Epic / Feature / User Story 세 단계 granularity**로 확장하고, (2) **Epic과 Feature에 각각 전용 뷰 페이지와 편집 페이지**를 제공하며, (3) **선택된 Epic·Feature 범위에 따라 clarification radar가 필터링되어** 표시되고, (4) **Epic·Feature 추가 시 그 하위 User Story를 자동 생성**(제안 후 사용자 확인; 생성 엔진은 설정에서 in-process LLM 또는 로컬 Claude IDE+speckit 중 선택)하며, (5) 추가·생성되는 모든 요구사항이 **DDD 관점에서 올바른 BC에 적정 입도(Feature/US)로 분해·배치되는지, 기존 spec과 충돌/align되는지 검증**되도록 한다.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Epic / Feature / User Story 단위로 골라서 등록 (Priority: P1)

요구사항 작성자는 Requirements 화면의 "+" 버튼을 눌렀을 때, 추가하려는 단위(Epic / Feature / User Story)를 먼저 선택할 수 있다. 단위를 고르면 그에 맞는 등록 폼이 나타나며, 각 폼은 **자연어로 설명하면 AI가 후보를 제안**하는 방식과 **필드를 직접 채워 넣는 수동 입력** 방식을 모두 지원한다. Feature를 추가할 때는 소속 Epic을, User Story를 추가할 때는 소속 Epic/Feature를 지정한다. 등록을 확정하면 트리에 즉시 반영된다.

**Why this priority**: 기능의 핵심. 이것만 구현해도 "Epic/Feature를 사용자가 직접 등록한다"는 가장 중요한 가치가 단독으로 전달된다. 뷰/편집 페이지와 레이더 필터링은 이 위에 얹히는 후속 가치다.

**Independent Test**: "+"를 눌러 Epic을 하나 등록하고, 그 Epic 아래에 Feature를 하나, 다시 그 Feature 아래에 User Story를 하나 등록한 뒤 트리에 3단계가 모두 나타나는지로 단독 검증 가능하다.

**Acceptance Scenarios**:

1. **Given** Requirements 화면이 열려 있고, **When** "+" 버튼을 누르면, **Then** 추가 단위로 Epic / Feature / User Story 중 하나를 선택할 수 있는 진입점이 보인다.
2. **Given** 추가 단위로 Epic을 선택하고 이름·설명을 수동 입력해 확정하면, **Then** 트리 최상위에 새 Epic이 추가되고 선택 가능 상태가 된다.
3. **Given** 추가 단위로 Feature를 선택하고 소속 Epic을 지정한 뒤 확정하면, **Then** 해당 Epic 하위에 새 Feature가 추가된다.
4. **Given** 추가 단위로 Feature 또는 User Story를 선택하고 자연어 설명을 입력해 "제안"을 요청하면, **Then** AI가 후보(들)를 제시하고 사용자가 검토 후 확정/수정/취소할 수 있다.
5. **Given** User Story를 추가할 때 소속 Epic·Feature를 지정하지 않은 경우, **Then** 시스템이 기존의 자동 분류 흐름으로 적절한 Feature에 배치하거나 사용자가 직접 배치하도록 안내한다.

---

### User Story 2 - Epic·Feature 전용 뷰 페이지 (Priority: P2)

사용자가 트리에서 Epic 또는 Feature 노드를 선택하면, 그 단위에 특화된 **뷰(읽기) 페이지**가 표시된다. 뷰 페이지는 해당 Epic/Feature의 이름·설명·출처(자동/수동)와 하위 구성(Epic→하위 Feature 목록·요약, Feature→하위 User Story 목록·요약), 그리고 명확도 요약을 보여 준다. User Story를 선택했을 때는 기존의 상세 화면이 그대로 유지된다.

**Why this priority**: 등록한 Epic/Feature를 의미 있게 확인할 수단. P1으로 만든 데이터에 가독성을 부여한다. 편집(US3)과 레이더 필터링(US4)의 기반이 된다.

**Independent Test**: 기존 Epic·Feature를 트리에서 선택했을 때 해당 단위의 요약·하위 목록이 담긴 전용 뷰가 뜨는지로 단독 검증 가능하다(편집 기능 없이도).

**Acceptance Scenarios**:

1. **Given** 트리에 Epic·Feature·User Story가 있고, **When** Epic 노드를 선택하면, **Then** Epic 전용 뷰 페이지가 열리고 이름·설명·하위 Feature 목록과 각 항목 요약이 보인다.
2. **Given** Feature 노드를 선택하면, **Then** Feature 전용 뷰 페이지가 열리고 이름·설명·하위 User Story 목록이 보인다.
3. **Given** User Story 노드를 선택하면, **Then** 기존 User Story 상세 화면이 그대로 표시된다(회귀 없음).
4. **Given** 비어 있는(하위가 없는) Epic 또는 Feature를 선택하면, **Then** 빈 상태 안내와 함께 하위 항목을 추가하라는 행동 유도가 보인다.

---

### User Story 3 - Epic·Feature 편집 페이지 (Priority: P2)

사용자는 Epic 또는 Feature의 뷰 페이지에서 "편집"으로 전환하여 이름·설명 등 메타데이터를 수정하고 저장할 수 있다. 저장하면 트리와 뷰 페이지에 즉시 반영된다. 편집을 취소하면 변경이 폐기된다.

**Why this priority**: 등록·조회 후 자연스러운 유지보수 행위. P1·US2 위에서 가치를 완성하지만, 읽기 전용으로도 MVP는 성립하므로 P2.

**Independent Test**: 기존 Feature의 이름을 편집 페이지에서 바꿔 저장한 뒤 트리·뷰에 새 이름이 반영되는지로 단독 검증 가능하다.

**Acceptance Scenarios**:

1. **Given** Epic 뷰 페이지에서, **When** "편집"을 눌러 이름·설명을 바꾸고 저장하면, **Then** 변경 내용이 영구 저장되고 트리·뷰에 즉시 반영된다.
2. **Given** Feature 편집 중 필수 항목(예: 이름)을 비우고 저장을 시도하면, **Then** 검증 오류가 표시되고 저장이 막힌다.
3. **Given** 편집 도중 "취소"를 누르면, **Then** 변경이 폐기되고 직전 저장 상태로 돌아간다.

---

### User Story 4 - 선택 범위에 따른 clarification radar 필터링 (Priority: P3)

사용자가 트리 또는 뷰 페이지에서 특정 Epic 또는 Feature를 선택하면, clarification radar(명확도 레이더)가 그 범위에 속한 요구사항만 집계해 표시된다. 선택을 Project(전체) / Epic / Feature 사이에서 바꾸면 레이더가 해당 범위로 다시 필터링되어 갱신된다.

**Why this priority**: 명확도 진단을 계층 단위로 좁혀 보는 부가 가치. 핵심 등록 흐름과 독립적이므로 P3.

**Independent Test**: 서로 다른 Feature를 차례로 선택했을 때 레이더의 카테고리 점수가 각 범위에 맞게 달라지는지로 단독 검증 가능하다.

**Acceptance Scenarios**:

1. **Given** 트리에서 한 Feature를 선택하면, **Then** 레이더가 그 Feature 하위 요구사항만 집계해 10개 카테고리 점수를 표시한다.
2. **Given** 한 Epic을 선택하면, **Then** 레이더가 그 Epic에 속한 모든 Feature·User Story를 합산해 표시한다.
3. **Given** 선택을 전체(Project)로 바꾸면, **Then** 레이더가 프로젝트 전체 범위로 갱신된다.
4. **Given** 선택한 Epic/Feature에 집계할 요구사항이 없으면, **Then** 레이더가 빈/중립 상태임을 명확히 나타낸다(오류가 아니라 정보).

---

### User Story 5 - Epic·Feature 추가 시 하위 User Story 자동 생성 (Priority: P1)

사용자가 Epic 또는 Feature를 등록하면, 시스템은 그 단위에 어울리는 **하위 User Story들을 자동으로 생성해 제안**한다. 사용자는 제안된 User Story 목록을 검토·수정·취사선택한 뒤 **확정**하며, 확정한 항목만 트리에 영구 반영된다. 생성 엔진은 **설정(Settings)에서 두 가지 중 선택**한다 — (a) 백엔드 **in-process LLM 에이전트**, 또는 (b) 사용자 PC에 설치된 **Claude IDE + speckit-specify 스킬**. (b)를 선택했는데 로컬에 Claude/speckit이 없으면 시스템이 **설치를 안내**한다.

**Why this priority**: "Epic/Feature를 등록하면 하위가 자동으로 채워진다"는 핵심 가치. P1 등록 흐름과 직접 묶이며, 빈 Epic/Feature를 손으로 채우는 수고를 없앤다.

**Independent Test**: 새 Feature를 하나 등록했을 때 하위 User Story 후보가 제안되고, 사용자가 일부를 확정하면 그 항목들이 해당 Feature 아래 트리에 나타나는지로 단독 검증 가능하다.

**Acceptance Scenarios**:

1. **Given** Settings에서 생성 엔진이 "in-process LLM"이고 Epic/Feature를 등록하면, **Then** 하위 User Story 후보 목록이 제안되고, 사용자가 검토·수정·선택해 확정하면 확정 항목만 트리에 반영된다.
2. **Given** Settings에서 생성 엔진이 "Claude IDE"이고 로컬에 Claude/speckit이 설치되어 있으면, **Then** speckit-specify 스킬을 통해 하위 User Story가 생성되어 동일한 제안→확인 흐름으로 반영된다.
3. **Given** 생성 엔진이 "Claude IDE"인데 로컬에 Claude 또는 speckit이 없으면, **Then** 생성을 진행하지 않고 설치 안내(설치 방법/링크 또는 설치 트리거)를 표시한다.
4. **Given** 생성된 후보가 0건이거나 엔진이 실패하면, **Then** 사용자에게 알리고 수동으로 User Story를 추가할 수 있는 경로로 폴백한다.
5. **Given** 제안된 후보를 사용자가 모두 취소(미확정)하면, **Then** 트리에 아무 User Story도 추가되지 않는다.

---

### User Story 6 - DDD 적합성·입도·스펙 정합성 검증 (Priority: P2)

요구사항(Epic/Feature/User Story)이 추가되거나 자동 생성될 때, 시스템은 그것이 **DDD 관점에서 올바른 BC(Epic)에 속하는지**, **Feature 입도가 과도하게 크지 않은지**, 그리고 **기존 spec과 충돌하거나 정합(align)되는지**를 검증한다. 입력의 굵기와 무관하게 결과물은 **우리가 정의한 BC 안에서 Feature/User Story 수준으로 적절히 분해·배치**되어야 한다. 부적합(잘못된 BC, 과대 Feature, 기존 spec과 충돌)이 발견되면 시스템은 **경고와 함께 교정안(올바른 BC로 재배치, 적정 크기로 분할)을 제안**하고, 사용자가 확인 후 적용한다. 이 검증은 **speckit의 스킬을 통해** 수행하며, 적합한 스킬이 없으면 **robo-spec 스킬에서 speckit-specify를 override하거나 신규 검증 스킬을 추가**해 제공한다.

**Why this priority**: 자동 생성·자유 입력이 들어오면 모델 일관성이 깨질 위험이 커진다. DDD 적합성·스펙 정합성 검증은 그래프-단일-진실원(Constitution)을 지키는 안전장치다. 단, 등록·자동생성(P1) 위에 얹히는 품질 게이트이므로 P2.

**Independent Test**: 의도적으로 엉뚱한 BC에 큰 범위의 Feature를 추가했을 때, 시스템이 "이 Feature는 BC X가 더 적절/너무 큼"을 경고하고 재배치·분할 교정안을 제안하는지로 단독 검증 가능하다.

**Acceptance Scenarios**:

1. **Given** 어떤 Epic에 Feature를 추가하는데 그 Feature가 DDD상 다른 BC에 더 적합하면, **Then** 시스템이 부적합을 경고하고 올바른 BC로의 재배치를 제안한다.
2. **Given** 추가/생성된 Feature가 한 Feature로 보기엔 범위가 지나치게 크면, **Then** 시스템이 이를 표시하고 더 작은 Feature/User Story 단위로의 분할안을 제안한다.
3. **Given** 새 요구사항이 기존 spec과 충돌(중복·모순)하면, **Then** 시스템이 충돌 지점을 알리고 정합 방향(병합/대체/구분)을 제안한다.
4. **Given** 검증을 수행할 적합한 speckit 스킬이 없으면, **Then** robo-spec 스킬 세트가 speckit-specify를 override하거나 신규 스킬로 검증 기능을 제공해 동작이 끊기지 않는다.
5. **Given** 검증 결과가 모두 적합하면, **Then** 경고 없이 통과되어 등록/생성 흐름이 그대로 진행된다.

---

### User Story 7 - 요구사항 변경의 설계 자동 반영 (Event Modeling / Design 연동) (Priority: P3)

Epic·Feature·User Story가 추가·변경된 뒤 사용자가 Requirements 탭에서 **"Event Modeling" 또는 "Design" 탭으로 이동**하면, 시스템은 **설계에 아직 반영되지 않은 User Story가 있는지 자동으로 식별**한다. 그런 US가 있으면 **"이에 따라 설계에 반영하시겠습니까?"** 라고 묻고, 사용자가 동의하면 **설계 생성이 자동으로 진행**된다. 그 결과로 Event Modeling에 **새 사용자 journey가 추가**되거나 **Aggregate가 생성·변경**될 수 있다. 생성된 설계 변경은 (HITL 원칙에 따라) 사용자 확인 후 그래프에 반영된다.

**Why this priority**: 요구사항→설계의 추적성/일관성을 자동으로 메우는 가치. 다만 등록·생성·검증(P1·P2)이 선행되어야 의미가 있으므로 P3.

**Independent Test**: 설계가 없는 US를 하나 만든 뒤 Design 탭으로 이동했을 때 "반영하시겠습니까?" 프롬프트가 뜨고, 동의하면 해당 US에 대한 journey/aggregate 설계가 생성되어 나타나는지로 단독 검증 가능하다.

**Acceptance Scenarios**:

1. **Given** 설계가 반영되지 않은 US가 존재하고, **When** 사용자가 Requirements에서 Event Modeling 또는 Design 탭으로 이동하면, **Then** 시스템이 미반영 US를 식별해 "설계에 반영하시겠습니까?"를 묻는다.
2. **Given** 사용자가 "예"로 동의하면, **Then** 설계 생성이 자동 진행되고, 필요한 경우 새 사용자 journey가 Event Modeling에 추가되거나 Aggregate가 생성·변경된다.
3. **Given** 사용자가 "아니오"로 거절하면, **Then** 설계 변경 없이 탭으로 진입하며, 미반영 상태는 다음 진입 시 다시 식별될 수 있다.
4. **Given** 설계 생성으로 만들어진 변경안이 있으면, **Then** 그 변경은 사용자 확인을 거쳐 그래프에 반영된다(자동 무단 반영 아님).
5. **Given** 미반영 US가 하나도 없으면, **Then** 탭 이동 시 프롬프트 없이 평소처럼 진입한다.

---

### Edge Cases

- 동일 Epic 안에서 이름이 중복되는 Feature(또는 동일 부모에서 중복 Epic)를 등록하려 하면 어떻게 처리되는가? → 중복 안내 또는 구분 가능한 식별을 제공한다.
- 하위 항목(Feature·User Story)이 있는 Epic/Feature의 이름을 변경하면 하위 항목과의 연결이 끊기지 않고 유지되어야 한다.
- AI 제안 흐름에서 후보가 0건이거나 응답이 지연/실패하면, 수동 입력으로 폴백할 수 있어야 한다.
- 자동 분류로 생성된 Feature와 사용자가 수동 등록한 Feature가 섞일 때, 수동 등록·수동 배치가 이후 자동 재분류에 의해 임의로 덮어써지지 않아야 한다.
- 뷰/편집 페이지를 보던 중 같은 항목이 외부에서 변경·삭제된 경우의 표시.
- "+" 추가 단위 선택 후 아무것도 입력하지 않고 닫으면 아무 변경도 생기지 않아야 한다.
- 자동 생성 엔진이 "Claude IDE"인데 Claude는 있고 speckit 스킬만 없거나 버전이 낮은 경우 → 부분 설치 안내.
- 자동 생성이 오래 걸리는 경우(LLM/스킬 호출) 진행 상태가 사용자에게 보여야 하며, 도중 취소가 가능해야 한다.
- DDD 검증이 동시에 여러 부적합(잘못된 BC + 과대 입도 + 기존 spec 충돌)을 보고하는 경우의 표시·우선순위.
- 정의된 BC가 하나도 없는 빈 프로젝트에서 Feature/US를 추가·생성하려는 경우(배치할 BC 없음) → BC(Epic) 먼저 만들도록 유도.
- DDD 교정안(재배치/분할)을 사용자가 거부하고 원안을 강행하는 경우의 허용 여부(경고는 남기되 차단하지 않음).
- 설계 자동 반영(US7) 도중 Aggregate 변경이 기존 설계와 충돌하거나 기존 설계 요소를 덮어쓸 위험이 있는 경우 → 변경 영향 표시 후 확인.
- 미반영 US가 매우 많아 설계 생성이 오래 걸리는 경우 → 진행 상태·부분 결과 표시, 취소 가능.
- 탭 이동마다 프롬프트가 반복되어 성가신 경우 → "이번 세션 동안 묻지 않기" 등 과도한 반복 억제(허위 프롬프트 최소화).
- US7 설계 생성 중 일부 US만 성공하고 일부는 실패하는 부분 실패의 표시·재시도.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Requirements 화면의 "+" 추가 진입점은 사용자가 추가할 단위를 **Epic / Feature / User Story 중에서 선택**할 수 있도록 제공해야 한다.
- **FR-002**: 시스템은 **Epic 단위 등록**을 지원해야 하며, 등록된 Epic은 트리 최상위 그룹으로 나타나야 한다. (Epic은 기존 최상위 그룹 개념과 동일한 실체로 취급한다 — Assumptions 참조.)
- **FR-003**: 시스템은 **Feature 단위 등록**을 지원해야 하며, 등록 시 소속 Epic을 지정하고 해당 Epic 하위에 배치해야 한다.
- **FR-004**: 시스템은 기존의 **User Story 단위 등록**을 계속 지원해야 하며(회귀 없음), 소속 Epic·Feature 배치 흐름을 유지해야 한다.
- **FR-005**: Epic·Feature·User Story 각 등록 폼은 **AI 제안(자연어 설명→후보 제시→검토·확정) 방식과 수동 직접 입력 방식을 모두** 제공해야 한다.
- **FR-006**: AI 제안 흐름은 후보를 사용자가 **확정 전에 검토·수정·취소**할 수 있어야 하며, 후보가 없거나 실패해도 수동 입력으로 폴백할 수 있어야 한다.
- **FR-007**: 사용자가 트리에서 **Epic 노드를 선택**하면 시스템은 Epic 전용 **뷰 페이지**를 표시하고, 이름·설명·출처와 하위 Feature 목록 및 요약을 보여 줘야 한다.
- **FR-008**: 사용자가 트리에서 **Feature 노드를 선택**하면 시스템은 Feature 전용 **뷰 페이지**를 표시하고, 이름·설명·출처와 하위 User Story 목록 및 요약을 보여 줘야 한다.
- **FR-009**: 사용자가 **User Story 노드를 선택**하면 기존 User Story 상세 화면이 그대로 표시되어야 한다(회귀 없음).
- **FR-010**: 시스템은 Epic과 Feature 각각에 대해 이름·설명 등 메타데이터를 수정·저장할 수 있는 **편집 페이지**를 제공해야 하며, 저장 시 트리·뷰에 즉시 반영해야 한다.
- **FR-011**: 편집 시 필수 항목 누락 등 유효하지 않은 입력은 **검증 오류로 막고**, "취소" 시 변경을 폐기해야 한다.
- **FR-012**: Epic/Feature의 이름·설명 변경은 **하위 항목과의 연결을 보존**해야 한다(하위 Feature·User Story가 분리되지 않음).
- **FR-013**: 사용자가 Epic 또는 Feature를 선택하면 clarification radar는 **그 범위에 속한 요구사항만 집계**해 표시해야 한다.
- **FR-014**: 선택 범위가 Project(전체) / Epic / Feature 사이에서 바뀌면 radar는 **해당 범위로 다시 필터링되어 갱신**되어야 한다.
- **FR-015**: 선택 범위에 집계할 요구사항이 없으면 radar는 **빈/중립 상태를 정보로 명확히** 나타내야 하며 오류로 처리하지 않아야 한다.
- **FR-016**: 사용자가 수동으로 등록·배치한 Epic·Feature·User Story는 이후 **자동(재)분류에 의해 임의로 덮어써지지 않아야** 한다.
- **FR-017**: 모든 신규 등록·편집 화면의 LLM 생성 산출물(예: AI 제안 텍스트)은 사용자의 언어 설정(기어 아이콘, 기본=브라우저 로캘)을 따라야 한다. (프로젝트 생성 언어 정책 준수.)

**하위 User Story 자동 생성 (US5)**

- **FR-018**: Epic 또는 Feature가 등록되면 시스템은 그 단위에 어울리는 **하위 User Story 후보를 자동 생성**해야 한다.
- **FR-019**: 자동 생성된 User Story는 **제안 상태로 먼저 제시**되어야 하며, 사용자가 **검토·수정·취사선택 후 확정**한 항목만 그래프에 영구 반영되어야 한다(Human-in-the-Loop).
- **FR-020**: 시스템은 생성 엔진을 **Settings에서 (a) in-process LLM 에이전트와 (b) 로컬 Claude IDE + speckit-specify 스킬 중 하나로 선택**할 수 있도록 제공해야 하며, 선택된 엔진으로 생성을 수행해야 한다.
- **FR-021**: 생성 엔진이 "Claude IDE"로 설정된 상태에서 로컬에 **Claude 또는 speckit이 설치되어 있지 않으면**, 시스템은 생성을 진행하지 않고 **설치를 안내(설치 방법·링크 또는 설치 트리거)**해야 한다.
- **FR-022**: 자동 생성이 오래 걸릴 수 있으므로 시스템은 **진행 상태를 사용자에게 표시**하고, 진행 중 **취소**할 수 있어야 한다.
- **FR-023**: 자동 생성 결과가 0건이거나 엔진이 실패하면 시스템은 이를 알리고 **수동 추가 경로로 폴백**할 수 있어야 한다.

**DDD 적합성·입도·스펙 정합성 검증 (US6)**

- **FR-024**: 요구사항(Epic/Feature/User Story)이 추가·자동생성될 때, 시스템은 그것이 **DDD 관점에서 올바른 BC(Epic)에 속하는지** 검증하고, 부적합 시 **올바른 BC로의 재배치를 제안**해야 한다.
- **FR-025**: 시스템은 Feature의 **입도가 과도하게 큰지 검증**하고, 그럴 경우 **더 작은 Feature/User Story 단위로의 분할안을 제안**해야 한다. 입력의 굵기와 무관하게 결과물은 **정의된 BC 내에서 Feature/US 수준으로 적절히 분해·배치**되어야 한다.
- **FR-026**: 시스템은 새 요구사항이 **기존 spec과 충돌·중복·모순되는지 검증**하고, 충돌 시 **정합 방향(병합/대체/구분)을 제안**해야 한다.
- **FR-027**: 위 DDD·정합성 검증은 **speckit의 스킬을 통해 수행**되어야 하며, 적합한 스킬이 없으면 **robo-spec 스킬 세트가 speckit-specify를 override하거나 신규 검증 스킬을 추가**해 기능이 끊기지 않도록 해야 한다.
- **FR-028**: 검증으로 제시된 교정안(재배치/분할/정합)은 **사용자 확인 후 적용**되며, 사용자가 교정안을 거부하고 원안을 강행하면 **경고는 남기되 차단하지 않는다**(단, 배치할 BC가 전혀 없는 경우는 BC 생성 선행을 요구).
- **FR-029**: 자동 생성·검증 흐름은 그 산출물을 **그래프(단일 진실원)에만 영속**해야 하며, 별도 병렬 저장소를 두지 않는다.

**요구사항 변경의 설계 자동 반영 (US7)**

- **FR-030**: 사용자가 Requirements에서 **Event Modeling 또는 Design 탭으로 이동**할 때, 시스템은 **설계에 아직 반영되지 않은 User Story를 자동으로 식별**해야 한다.
- **FR-031**: 미반영 US가 식별되면 시스템은 **"설계에 반영하시겠습니까?"** 형태로 사용자에게 진행 여부를 물어야 한다(자동 무단 진행 금지).
- **FR-032**: 사용자가 동의하면 시스템은 **설계 생성을 자동 수행**하여, 필요 시 **Event Modeling에 새 사용자 journey를 추가**하거나 **Aggregate를 생성·변경**해야 한다.
- **FR-033**: 설계 생성으로 만들어진 변경은 **사용자 확인을 거쳐 그래프에 반영**되어야 하며(Human-in-the-Loop), 기존 설계와의 충돌·영향은 사용자에게 표시되어야 한다.
- **FR-034**: 미반영 US가 없으면 탭 이동 시 **프롬프트 없이** 평소처럼 진입해야 하며, 시스템은 불필요한 반복 프롬프트를 억제하는 수단(예: 세션 내 다시 묻지 않기)을 제공해야 한다.
- **FR-035**: 설계 자동 반영도 그 산출물을 **그래프에만 영속**하며, 신규 노드 라벨/관계를 도입하지 않고 기존 Event Modeling·Aggregate·설계-추적 구조를 재사용해야 한다.

### Key Entities *(include if feature involves data)*

- **Epic**: 요구사항 트리의 최상위 그룹. 이름·설명·출처(자동/수동)를 가지며, 다수의 Feature를 포함한다. (현재 시스템에서 최상위 그룹 역할을 하는 기존 개념과 동일 실체로 취급 — Assumptions 참조.)
- **Feature**: Epic에 속하는 중간 그룹. 이름·설명·출처를 가지며, 다수의 User Story를 포함한다. Epic과의 소속 관계를 가진다.
- **User Story**: Feature(및 Epic)에 속하는 최소 요구사항 단위. 역할·행동·이익·인수 조건 등 기존 속성을 유지한다.
- **Clarity Scope(명확도 범위)**: radar 집계의 기준이 되는 선택 단위(Project / Epic / Feature). 선택된 범위에 속한 User Story 집합으로부터 카테고리별 명확도 점수가 계산된다.
- **AI 제안 후보(Proposal)**: 자연어 입력 또는 자동 생성에 대한 AI의 임시 제안 항목으로, 확정 전까지는 트리에 반영되지 않는 미확정 상태다. Epic/Feature 후보, 자동 생성된 하위 User Story 후보, DDD 교정안(재배치/분할/정합)을 모두 포함한다.
- **생성 엔진 설정(Generation Engine Setting)**: 하위 US 자동 생성에 사용할 엔진 선택값 — `in-process LLM` 또는 `Claude IDE(+speckit)`. Settings에 저장된다.
- **DDD 검증 결과(Validation Finding)**: 추가/생성 대상에 대한 검증 산출물 — 부적합 유형(잘못된 BC 배치 / 과대 입도 / 기존 spec 충돌), 영향 대상, 제안 교정안으로 구성된다.
- **로컬 도구 가용성(Local Tooling Availability)**: 로컬 Claude IDE 및 speckit 스킬의 설치·버전 상태. "Claude IDE" 엔진 선택 시 사전 점검되어 설치 안내 여부를 결정한다.
- **미반영 US(Design-Pending User Story)**: 그래프상 설계(journey/Aggregate/설계-추적)와 연결되지 않은 User Story. Event Modeling/Design 탭 진입 시 자동 식별되어 설계 반영 프롬프트의 대상이 된다.
- **설계 변경안(Design Change Proposal)**: 미반영 US로부터 생성된 설계 산출물 — 새 사용자 journey, 신규/변경 Aggregate 등. 확정 전까지 미반영 상태이며 사용자 확인 후 그래프에 반영된다.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 사용자는 "+"에서 단위를 골라 Epic / Feature / User Story 각각을 **3단계 모두 한 흐름에서** 새로 등록할 수 있다(세 단위 모두 등록 성공률 100%).
- **SC-002**: 빈 상태에서 시작해 Epic 1개 → Feature 1개 → User Story 1개로 이어지는 첫 계층 구성을 **3분 이내**에 끝낼 수 있다.
- **SC-003**: 트리에서 Epic 또는 Feature를 선택하면 **2초 이내**에 해당 전용 뷰 페이지가 표시된다.
- **SC-004**: Epic 또는 Feature를 편집·저장한 변경은 **새로고침 없이** 트리와 뷰에 반영된다.
- **SC-005**: 서로 다른 Epic·Feature·Project 범위를 선택했을 때 radar 집계 결과가 **각 범위에 맞게 달라지며**, 잘못된 범위 혼입이 0건이다.
- **SC-006**: 기존 User Story 추가·상세·명확화 흐름이 **회귀 없이** 동일하게 동작한다(기존 시나리오 통과율 100%).
- **SC-007**: Epic 또는 Feature 등록 후 **별도 수동 입력 없이** 하위 User Story 후보가 자동 제안되며, 사용자는 제안 중 일부를 골라 확정해 트리에 반영할 수 있다(자동 제안 발생률 100%, 확정 항목만 반영).
- **SC-008**: 생성 엔진을 Settings에서 두 방식(in-process LLM / Claude IDE) 간 전환할 수 있고, "Claude IDE" 선택 시 로컬 미설치 환경에서는 **생성 대신 설치 안내가 100% 표시**된다(잘못된 생성 시도 0건).
- **SC-009**: 잘못된 BC 배치·과대 입도·기존 spec 충돌을 의도적으로 만든 케이스에서 시스템이 **부적합을 감지하고 교정안을 제안**한다(의도된 부적합 케이스 감지율 100%), 적합한 케이스에서는 불필요한 경고가 발생하지 않는다(허위 경고 최소화).
- **SC-010**: 자동 생성·검증을 포함한 모든 산출물은 **그래프에만 영속**되며, `docs/cypher/schema/` 변경 없이(신규 노드 라벨/관계 0건) 동작한다.
- **SC-011**: 설계가 반영되지 않은 US가 있을 때 Event Modeling/Design 탭 진입 시 **반영 프롬프트가 표시**되고(미반영 케이스 100% 식별), 동의 시 해당 US에 대한 journey/Aggregate 설계가 생성되어 확인 후 반영된다. 미반영 US가 없으면 프롬프트가 뜨지 않는다(허위 프롬프트 0건).

## Assumptions

- **Epic = 기존 최상위 그룹(BoundedContext) 실체**: 사용자 확인에 따라 "Epic"은 새 노드 타입을 신설하지 않고, 현재 트리 최상위 그룹으로 동작하는 기존 개념과 동일 실체로 취급한다. 따라서 데이터 모델/스키마 변경은 없음을 전제한다.
- **AI 제안 + 수동 입력 병행**: 사용자 확인에 따라 Epic·Feature 추가는 User Story와 마찬가지로 AI 제안 흐름과 수동 입력을 모두 제공한다.
- **"뷰 페이지/편집 페이지"의 형태**: 현재 앱은 탭 기반 SPA로 별도 URL 라우팅이 없으므로, "페이지"는 Requirements 화면 내 전용 보기/편집 영역(상세 패널·폼)으로 구현됨을 전제한다. 별도 브라우저 라우트/딥링크는 범위 밖이다.
- **radar 범위 백엔드 지원 재사용**: 명확도 집계는 이미 Project / Epic(BoundedContext) / Feature 범위를 지원하므로, 이번 작업의 신규 가치는 주로 선택→필터링 연동과 등록/뷰/편집 화면에 있다.
- **단일 사용자 로컬 도구 신뢰 모델**: 데스크톱/로컬 단일 사용자 환경을 전제하며, 동시 편집 충돌은 단순 안내 수준으로 처리한다(엄격한 락/머지는 범위 밖).
- **삭제·이동(드래그)** 등 기존 트리 조작은 본 기능의 직접 범위가 아니며, 기존 동작을 회귀 없이 유지하는 것만 전제한다.
- **생성 엔진 이원화**: 사용자 확인에 따라 하위 US 자동 생성은 백엔드 in-process LLM과 로컬 Claude IDE(+speckit) 두 엔진을 모두 지원하며 Settings로 선택한다. "Claude IDE" 엔진은 로컬에 Claude/speckit 설치를 전제하고, 미설치 시 설치 안내로 폴백한다. (in-process 엔진은 설치 불필요.)
- **clarification은 로컬 speckit이 아님**: 현 clarification은 in-process LLM(LangChain deepagents)으로 동작한다. 따라서 "clarification처럼 로컬 speckit 사용"이라는 표현은 실제로는 새 메커니즘(로컬 Claude+speckit 헤드리스 호출)을 도입하는 것이며, in-process 옵션과 양립한다.
- **DDD/정합성 검증 스킬 부재 가능성**: 현재 speckit 스킬군에는 BC 배치·입도·spec 충돌을 검증하는 전용 스킬이 없을 수 있다(speckit-analyze는 spec-kit 산출물 일관성용). 이 경우 robo-spec 스킬 세트에서 speckit-specify를 override하거나 신규 검증 스킬을 추가해 충족한다. 검증에 필요한 그래프(BC/Feature/US)·기존 spec 컨텍스트는 기존 robo-spec MCP 경로로 제공 가능함을 전제한다.
- **교정안 비차단 원칙**: DDD 교정안은 제안·경고하되, 사용자가 거부하고 원안을 강행하는 것을 차단하지 않는다(배치할 BC가 전혀 없는 경우만 BC 생성 선행 요구).
- **설계 자동 반영은 기존 설계 파이프라인 재사용**: US7의 journey/Aggregate 생성은 기존 Event Modeling·설계 생성·변경영향(change-impact) 메커니즘을 재사용하며, 신규 설계 알고리즘이나 노드 라벨을 도입하지 않음을 전제한다. "미반영 US" 식별은 기존 설계-추적(US↔Command/Aggregate) 연결의 부재로 판정함을 전제한다.

## Out of Scope

- 별도 브라우저 라우트/딥링크(예: `/requirements/epic/:id`) 도입.
- 새로운 Epic 노드 타입 신설 또는 Neo4j 스키마 변경.
- Epic/Feature에 대한 명확화(clarify) 세션 자체의 신규 로직 — radar 표시 범위 필터링만 다룬다.
- 권한/감사 등 다중 사용자 협업 기능.
- 설계 생성 알고리즘 자체의 신규 구현 — US7은 기존 Event Modeling/Aggregate 설계 생성을 **트리거·오케스트레이션**할 뿐, 설계 엔진을 새로 만들지 않는다.
- BPMN/PRD/문서 export 등 설계 하류 산출물의 자동 재생성(별도 기능).
