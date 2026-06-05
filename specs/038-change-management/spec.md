# Feature Specification: Requirement Change Management

**Feature Branch**: `038-change-management`

**Created**: 2026-06-02

**Status**: Draft

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Change 목록 관리 및 조회 (Priority: P1)

팀 멤버는 Requirements 탭의 **Changes** 메뉴에서 모든 Change 레코드를 시간 순서로 조회하고, 각 Change가 어떤 요구사항/설계 요소에 영향을 주는지 한눈에 파악할 수 있다.

**Why this priority**: Change 관리의 진입점이자 핵심 뷰. 이것 없이는 이후 모든 워크플로우가 불가능하다.

**Independent Test**: Changes 탭을 열어 Change 목록이 시간 역순으로 표시되고, 각 항목에 ID(CHG-NNN), 상태, 작성자, 영향 받는 항목 수가 보이면 완료.

**Acceptance Scenarios**:

1. **Given** 시스템에 Change 레코드가 존재할 때, **When** 사용자가 Changes 탭을 열면, **Then** Change 목록이 생성일시 역순으로 나열되고 CHG-NNN ID·상태·작성자·요약·영향 항목 수가 표시된다.
2. **Given** Changes 탭이 열려 있을 때, **When** 특정 Change를 클릭하면, **Then** 해당 Change의 상세 화면(원본 프롬프트, 영향받는 UserStory/Feature/Aggregate 목록, 하위 Change 목록, 상태 이력)이 표시된다.
3. **Given** Change 목록이 있을 때, **When** 사용자가 Change를 삭제하면, **Then** 해당 Change는 목록에서 제거되고 연결된 EFFECT 관계도 함께 삭제된다.

---

### User Story 2 - Change 생성 (여러 진입점) (Priority: P1)

사용자는 세 가지 방법으로 Change를 생성할 수 있다: ① Changes 탭의 "추가 Change" 버튼, ② 자연어 프롬프트 입력창에 요구사항 변경 문장 입력, ③ UserStory/Feature/Design 탭에서 항목을 직접 수정.

**Why this priority**: Change 생성이 없으면 관리 자체가 불가능하다. 여러 진입점 지원은 현실적인 팀 워크플로우를 반영한다.

**Independent Test**: 세 가지 방법 각각으로 Change를 생성하고 CHG-NNN ID가 부여된 레코드가 Changes 탭에 나타나면 완료.

**Acceptance Scenarios**:

1. **Given** Changes 탭에서, **When** "추가 Change" 버튼을 누르고 변경 내용을 입력하면, **Then** 새 Change 레코드(CHG-NNN)가 생성되고 입력한 텍스트가 원본 프롬프트로 저장된다.
2. **Given** 요구사항 변경 프롬프트를 입력창에 입력했을 때, **When** 시스템이 분석을 완료하면, **Then** 변경 의도에 해당하는 Change 레코드가 자동 생성되고 영향받는 UserStory·Feature·Aggregate에 EFFECT 관계가 연결된다.
3. **Given** UserStory 탭에서 사용자가 특정 스토리의 내용을 직접 수정했을 때, **When** 저장하면, **Then** 해당 수정 내용을 반영하는 Change 레코드가 생성되어 수정된 스토리와 EFFECT로 연결된다.
4. **Given** Change가 생성될 때, **Then** 생성자(사용자 ID/이메일), 생성 시각, 원본 프롬프트(또는 수정 내용 요약), 상태(`DRAFT`)가 기록된다.

---

### User Story 3 - Change 영향도 분석 (EFFECT 관계 그래프) (Priority: P2)

Change가 생성되면 시스템이 자동으로 연관 UserStory·Feature·Aggregate를 분석하여 EFFECT 관계를 그래프에 연결하고, 사용자는 상세 화면에서 어떤 설계 요소가 영향을 받는지 시각적으로 확인할 수 있다.

**Why this priority**: 영향도가 보이지 않으면 Change를 반영할지 판단하기 어렵다.

**Independent Test**: Change 생성 후 상세 화면에서 "영향받는 항목" 섹션에 UserStory·Aggregate 목록과 각 관계 이유가 표시되면 완료.

**Acceptance Scenarios**:

1. **Given** Change가 생성되었을 때, **When** 시스템이 영향도 분석을 완료하면, **Then** 해당 Change 노드에서 영향받는 UserStory·Feature·Aggregate 노드로 EFFECT 관계가 생성된다.
2. **Given** Change 상세 화면에서, **When** 영향받는 Aggregate를 클릭하면, **Then** 해당 Aggregate의 설계 화면으로 이동하거나 상세 정보가 사이드패널에 표시된다.
3. **Given** EFFECT 관계가 연결된 UserStory가 있을 때, **Then** 해당 UserStory의 기존 IMPLEMENTS→Command 연결을 통해 설계 요소(Aggregate·Event·Command)까지 전파 경로가 표시된다.

---

### User Story 4 - Change 번들 (Change Set) 관리 (Priority: P2)

관련된 여러 Change를 하나의 **Change Set(묶음)**으로 그룹화하여 함께 검토·승인·반영할 수 있다.

**Why this priority**: 관련된 변경들을 원자적으로 다루어야 설계 충돌을 예방할 수 있다.

**Independent Test**: 두 개 이상의 Change를 선택해 하나의 Change Set으로 묶고, Change Set 단위 승인·반영이 작동하면 완료.

**Acceptance Scenarios**:

1. **Given** 여러 Change 레코드가 있을 때, **When** 사용자가 복수의 Change를 선택하고 "Change Set 생성"을 누르면, **Then** 하나의 Change Set 레코드가 만들어지고 선택한 Change들이 그 아래로 그룹화된다.
2. **Given** Change Set이 존재할 때, **When** Change Set을 승인/반영하면, **Then** 포함된 모든 Change가 함께 처리된다.
3. **Given** Change Set에 속한 특정 Change를 제거하면, **Then** 해당 Change는 Change Set에서 분리되고 독립 Change로 복귀한다.

---

### User Story 5 - Change 승인 워크플로우 (Priority: P2)

Change 또는 Change Set을 팀원이 제출(SUBMITTED)하면, 다른 권한 있는 팀원이 승인(APPROVED) 또는 반려(REJECTED)할 수 있다. 승인된 Change만 구현 단계로 진행할 수 있다.

**Why this priority**: 의사결정 거버넌스가 없으면 변경이 무분별하게 반영될 위험이 있다.

**Independent Test**: 한 사용자가 Change를 제출하고 다른 사용자가 승인하면 Change 상태가 APPROVED로 바뀌고 "구현 시작" 버튼이 활성화되면 완료.

**Acceptance Scenarios**:

1. **Given** Change가 `DRAFT` 상태일 때, **When** 작성자가 "제출"을 누르면, **Then** 상태가 `SUBMITTED`로 변경되고 승인자에게 알림이 표시된다.
2. **Given** Change가 `SUBMITTED` 상태일 때, **When** 승인자가 "승인"을 누르면, **Then** 상태가 `APPROVED`로 변경되고 "구현 시작" 버튼이 활성화된다.
3. **Given** Change가 `SUBMITTED` 상태일 때, **When** 승인자가 "반려"를 누르면, **Then** 상태가 `REJECTED`로 변경되고 반려 사유가 기록된다.
4. **Given** Change에 상태 전이가 발생할 때마다, **Then** 상태 이력(상태값·시각·처리자)이 시간 순으로 누적 저장된다.

---

### User Story 6 - Change 구현 워크플로우 (태스크 생성 → 진행 추적) (Priority: P3)

승인된 Change를 "구현 시작"하면 구현 스킬이 Change ID를 인수로 호출되어 태스크 목록이 생성되고, 구현 진행 상태가 Change 상세 화면에서 실시간으로 확인된다.

**Why this priority**: 최종 가치 전달 단계이지만 승인 워크플로우 이후에 위치한다.

**Independent Test**: APPROVED 상태의 Change에서 "구현 시작"을 누르면 태스크 목록이 생성되고 진행 상태가 표시되면 완료.

**Acceptance Scenarios**:

1. **Given** Change가 `APPROVED` 상태일 때, **When** 사용자가 "구현 시작"을 누르면, **Then** 구현 스킬이 Change ID(CHG-NNN)를 인수로 호출되어 구현 태스크 목록이 생성된다.
2. **Given** 구현이 진행 중일 때, **Then** Change 상세 화면에 태스크별 진행 상태(대기/진행중/완료)가 실시간으로 출력된다.
3. **Given** 구현을 시작하기 전 미반영된 선행 Change가 있을 때, **When** 구현 시작을 시도하면, **Then** 시스템이 선행 Change 목록을 보여주며 함께 반영할지 여부를 선택하게 한다.
4. **Given** 구현이 완료되면, **Then** Change 상태가 `IMPLEMENTED`로 전환되고 연결된 문서·테스트가 자동 갱신된다.

---

### User Story 7 - 회귀 테스트 영향도 산출 (Priority: P3)

Change 적용 시 영향받는 테스트(단위·계약·E2E)를 자동으로 목록화하여 회귀 테스트 대상을 사용자에게 제시한다.

**Why this priority**: 품질 보증의 마지막 단계로, 구현 완료 후 필요하다.

**Independent Test**: Change 구현 완료 후 "영향받는 테스트 목록"에 관련 UserStory·Aggregate·UI에 연결된 테스트들이 열거되면 완료.

**Acceptance Scenarios**:

1. **Given** Change에 의해 UserStory·Aggregate가 변경되었을 때, **Then** 해당 노드에 연결된 테스트 노드(그래프 상)가 회귀 테스트 대상 목록에 포함된다.
2. **Given** 변경이 마이크로서비스 간 계약에 영향을 줄 때, **Then** 계약 테스트(Contract Test) 항목이 회귀 목록에 추가된다.
3. **Given** 변경이 UI 흐름을 포함할 때, **Then** E2E 테스트 항목이 회귀 목록에 추가된다.

---

### Edge Cases

- 동일한 UserStory/Aggregate에 EFFECT를 가진 Change가 동시에 여러 개 존재할 때 충돌 감지 및 경고.
- 이미 `IMPLEMENTED` 상태인 Change를 다시 반영 시도하면 경고 표시.
- Change Set 내 일부 Change만 승인 가능한지, 전체 묶음 단위로만 승인 가능한지 선택 정책.
- 승인자가 자신이 제출한 Change를 승인하려는 경우 경고(자기 승인 방지).
- 그래프에서 연결 노드를 찾을 수 없는 경우 EFFECT 분석 부분 실패 처리(나머지는 정상 저장).

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 시스템은 `Change` 노드를 생성·조회·삭제할 수 있어야 하며, 각 Change는 전역 고유 ID(`CHG-NNN`)를 가져야 한다.
- **FR-002**: Change 노드는 원본 프롬프트(또는 수정 요약), 생성자, 생성 시각, 현재 상태를 저장해야 한다.
- **FR-003**: Change 생성 시 시스템은 영향받는 UserStory·Feature·Aggregate를 분석하여 `EFFECT` 관계를 자동으로 생성해야 한다.
- **FR-004**: Change는 세 가지 진입점(Changes 탭 직접 입력, 자연어 프롬프트, 탭 내 직접 수정)을 통해 생성될 수 있어야 한다.
- **FR-005**: 복수의 Change를 하나의 Change Set으로 묶을 수 있어야 하며, Change Set 단위로 승인·반영이 가능해야 한다.
- **FR-006**: Change 상태는 `DRAFT → SUBMITTED → APPROVED / REJECTED → IMPLEMENTED` 순서를 따르며, 각 전이 시 이력(상태·시각·처리자)이 누적 저장되어야 한다.
- **FR-007**: 제출자와 승인자는 다른 사용자여야 하며(자기 승인 방지), 시스템은 이를 검증해야 한다.
- **FR-008**: `APPROVED` 상태의 Change에서 "구현 시작"을 실행하면 구현 스킬이 `CHG-NNN`을 인수로 호출되어 태스크 목록을 생성해야 한다.
- **FR-009**: 구현 진행 상태(태스크별 대기/진행/완료)가 Change 상세 화면에 실시간으로 반영되어야 한다.
- **FR-010**: 구현 시작 전 미반영 선행 Change 목록을 사용자에게 제시하고 함께 반영 여부를 선택하게 해야 한다.
- **FR-011**: 구현 완료 시 관련 문서가 자동으로 갱신되어야 한다.
- **FR-012**: Change 적용 후 영향받는 테스트(단위·계약·E2E) 목록이 회귀 테스트 대상으로 자동 산출되어야 한다.
- **FR-013**: 기존 Change 데이터(구 스키마)는 마이그레이션 없이 삭제(초기화)한다.
- **FR-014**: Changes 탭에서 Change를 삭제할 수 있으며, 삭제 시 연결된 EFFECT 관계도 함께 제거되어야 한다.

### Key Entities

- **Change**: 요구사항 변경 단위. 속성: `id(CHG-NNN)`, `title`, `originalPrompt`, `author`, `createdAt`, `status`, `statusHistory[]`, `sourceType(PROMPT|DIRECT_EDIT|MANUAL)`.
- **ChangeSet**: 복수 Change의 묶음. 속성: `id`, `title`, `createdAt`, `author`, `status`.
- **EFFECT**: Change → UserStory·Feature·Aggregate 관계. 속성: `reason`, `impactLevel(HIGH|MEDIUM|LOW)`.
- **CONTAINS**: ChangeSet → Change 관계.
- **StatusHistory**: Change 상태 전이 이력. 속성: `fromStatus`, `toStatus`, `timestamp`, `actor`, `comment`.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 사용자가 Change를 생성한 후 30초 이내에 EFFECT 관계 분석 결과를 확인할 수 있다.
- **SC-002**: Changes 탭에서 Change 목록 로딩이 2초 이내에 완료된다(Change 100건 기준).
- **SC-003**: Change → 구현 태스크 생성까지의 클릭 수가 3회 이하이다.
- **SC-004**: 구현 완료 후 회귀 테스트 대상 목록이 자동으로 제시되어 수동 분석 시간이 70% 이상 단축된다.
- **SC-005**: 승인 없이 구현이 시작되는 경우가 0건이다(승인 필수 검증).
- **SC-006**: 팀 내 변경 이력 추적 가능성: 모든 Change에 작성자·시각·원본 프롬프트가 100% 기록된다.

---

## Assumptions

- 사용자 인증 시스템이 이미 존재하며, 생성자/승인자 정보는 현재 세션의 사용자 정보에서 가져온다.
- 그래프 DB(Neo4j)에 UserStory·Feature·Aggregate·Command·Event 노드가 이미 존재한다.
- EFFECT 관계 분석은 기존 graph traversal 로직 또는 AI 스킬(robo-changes)을 재사용한다.
- 구현 스킬은 `robo-changes/robo-change-tasks`를 호출하며, Change ID를 인수로 받아 태스크 목록을 반환한다.
- 태스크 실행 진행 상태는 SSE(Server-Sent Events)로 프런트엔드에 전달된다(Constitution III 준수).
- 자기 승인 방지 정책은 동일 사용자 ID 비교로 구현한다(Role-Based 권한은 v1 범위 밖).
- 기존 037 브랜치의 Change 관련 데이터 모델은 이번 스펙으로 교체되므로 마이그레이션 없이 초기화한다.
- 테스트 노드가 그래프에 존재할 경우에만 회귀 테스트 목록 산출이 작동한다(없으면 "연결된 테스트 없음" 표시).
- Change Set 승인 정책은 전체 묶음 단위 승인으로 기본 설정한다(개별 승인은 v2).
