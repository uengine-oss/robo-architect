# Feature Specification: Requirement Direct-Edit with Edit History

**Feature Branch**: `033-requirement-edit-history`

**Created**: 2026-05-30

**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 요구사항 직접 편집 (Priority: P1)

분석가가 Requirements 패널에서 UserStory를 선택한 후, 편집 탭을 클릭해 역할(role)·목적(action)·혜택(benefit)·우선순위·상태 필드를 수정하고 저장한다. 저장 즉시 트리와 개요 탭에 반영된다.

**Why this priority**: AI 생성 요구사항이 부정확한 경우 사람이 직접 교정할 수 있어야 하며, 이것이 전체 기능의 핵심이다.

**Independent Test**: Requirements 탭에서 임의의 UserStory를 선택 → "편집" 탭 → 모든 필드 수정 → 저장 → 개요 탭 확인으로 단독 검증 가능.

**Acceptance Scenarios**:

1. **Given** 사용자가 UserStory를 선택한 상태에서, **When** "편집" 탭을 클릭하면, **Then** 현재 저장된 값이 폼에 채워진 편집 화면이 표시된다.
2. **Given** 사용자가 필드를 수정하고 "저장"을 클릭하면, **When** 저장이 성공하면, **Then** "저장되었습니다" 알림과 함께 자동으로 개요 탭으로 이동하고 트리도 갱신된다.
3. **Given** 사용자가 "취소"를 클릭하면, **When** 취소 처리되면, **Then** 변경 없이 개요 탭으로 돌아간다.
4. **Given** 두 사용자가 동시에 같은 UserStory를 편집하는 경우, **When** 나중에 저장하는 사용자의 요청이 충돌을 감지하면, **Then** "다른 사용자가 이미 수정했습니다" 메시지가 표시된다.

---

### User Story 2 - 편집 이력 조회 (Priority: P2)

분석가가 UserStory의 이력 탭을 열어 누가 언제 어떤 필드를 어떻게 바꿨는지 타임라인으로 확인한다.

**Why this priority**: 팀 협업 환경에서 변경 추적은 투명성과 책임 소재 파악에 필수다.

**Independent Test**: 편집을 1회 이상 수행한 UserStory의 "이력" 탭에서 편집자명·시각·변경 필드의 before/after가 표시됨을 확인.

**Acceptance Scenarios**:

1. **Given** UserStory에 편집 이력이 없는 경우, **When** 이력 탭을 열면, **Then** "편집 이력이 없습니다" 메시지가 표시된다.
2. **Given** 이력이 있는 UserStory의 이력 탭을 열면, **When** 이력이 로드되면, **Then** 최신순으로 편집자 이름·시각·변경된 필드별 이전값→이후값이 나열된다.
3. **Given** 명확화(clarification) 기능으로 변경이 적용된 경우, **When** 이력 탭을 보면, **Then** AI 또는 시스템 사용자 이름으로 이력이 기록된다.

---

### User Story 3 - 편집자 신원 자동 적용 (Priority: P3)

편집 시 별도 로그인 없이 앱이 자동으로 현재 로그인 사용자(git config 기반 identity)를 편집자로 기록한다.

**Why this priority**: Electron 환경에서 이미 신원이 확보되어 있으므로 별도 입력 없이 자동화 가능하다.

**Independent Test**: 앱 설정의 사용자 정보 확인 후 편집 → 이력 탭에서 동일한 이름/이메일이 기록됨을 확인.

**Acceptance Scenarios**:

1. **Given** 사용자가 Electron 앱에서 인증된 상태로 편집을 저장하면, **When** 이력이 생성되면, **Then** identity 설정의 이름과 이메일이 편집자로 기록된다.
2. **Given** 웹 모드(identity 헤더 없음)에서 편집하면, **When** 이력이 생성되면, **Then** "unknown" 사용자로 기록되고 기능은 정상 동작한다.

---

### Edge Cases

- 저장 중 네트워크 오류: "저장 실패" 메시지 표시, 폼 유지 (재시도 가능)
- 동시 편집 충돌 (409): 메시지 표시 후 폼 유지, 사용자가 다시 시도하거나 새로고침 선택
- 변경된 필드가 없는 상태로 저장: no-op 처리 (DB 쓰기 없음, 정상 응답)
- 이력 탭 최대 표시 건수: 최신 50건까지 표시

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 사용자는 UserStory의 역할(role), 목적(action), 혜택(benefit), 우선순위(priority), 상태(status) 필드를 편집 탭에서 직접 수정할 수 있어야 한다.
- **FR-002**: 저장 시 현재 로그인된 사용자의 이름과 이메일이 편집 이력에 자동으로 기록되어야 한다.
- **FR-003**: 편집 이력은 변경된 필드별로 이전 값과 이후 값을 포함해야 한다.
- **FR-004**: 이력 탭은 최신순으로 최대 50건의 편집 이력을 표시해야 한다.
- **FR-005**: 동시 편집 충돌이 감지되면 사용자에게 명확한 안내 메시지를 표시해야 한다.
- **FR-006**: 변경 없이 저장할 경우 불필요한 이력이 생성되지 않아야 한다.
- **FR-007**: 명확화(clarification) 기능을 통한 자동 편집도 동일한 이력 구조로 기록되어야 한다.
- **FR-008**: 인수조건(Acceptance Criteria) 필드는 직접 편집 탭에서 수정할 수 없다 (명확화 탭 전용).

### Key Entities

- **UserStory**: 편집 대상 노드. `role`, `action`, `benefit`, `priority`, `status`, `updatedAt` 속성 보유.
- **EditHistory**: 편집 이력 노드. `id`, `timestamp`, `userName`, `userEmail`, `changes` (JSON: 변경된 필드별 {before, after}) 속성 보유. `(UserStory)-[:HAS_HISTORY]->(EditHistory)` 관계로 연결.
- **Actor**: 요청자 신원 (이름, 이메일). `X-User-Name` / `X-User-Email` 헤더로 전달.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 사용자가 UserStory 편집을 완료하는 데 걸리는 시간이 30초 이내 (필드 수정 + 저장 버튼 클릭 기준).
- **SC-002**: 편집 저장 후 1초 이내에 트리와 개요 탭에 변경 내용이 반영된다.
- **SC-003**: 이력 탭 로드가 1초 이내에 완료된다 (50건 기준).
- **SC-004**: 동시 편집 충돌 발생 시 100% 감지율 (낙관적 동시성 기반).
- **SC-005**: 편집 이력의 변경 필드 기록 정확도 100% (누락·오기 없음).

## Assumptions

- Electron 앱 환경에서 `X-User-Name` / `X-User-Email` 헤더는 identity middleware에 의해 항상 설정된다고 가정한다.
- 웹 모드(브라우저 직접 접근)에서는 헤더 없이 "unknown" 사용자로 기록되며 기능은 저하 없이 동작한다.
- 인수조건(acceptanceCriteria) 필드의 직접 편집은 명확화(clarification) 탭 전용으로 유지한다.
- 편집 이력의 롤백(revert to old version) 기능은 이번 스펙의 범위 밖이다.
- Neo4j 스키마 변경 없이 새 노드 타입(:EditHistory)과 관계(:HAS_HISTORY)를 추가한다.
