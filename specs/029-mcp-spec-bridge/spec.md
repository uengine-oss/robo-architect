# Feature Specification: MCP Spec Bridge — 동적 스펙 전달과 구현 진척 동기화

**Feature Branch**: `029-mcp-spec-bridge`
**Created**: 2026-05-19
**Status**: Draft
**Input**: User description: "MCP를 만들어 기존의 'PRD 생성 → Claude Code가 BC별 DDD 마크다운 스펙 파일 생성' 방식(파일이 불필요하게 쌓이고 갱신되지 않는 문제)을 대체한다. Claude Code 쪽에 슬래시 커맨드를 하나 만들어 주고, 그 커맨드의 파라미터로 스펙(피처/BC/어그리거트)의 ID가 전달되면, MCP가 Robo Architect의 API를 호출해 해당 범위의 PRD·구현 스펙을 동적으로 받아와 전달한다. 구현 중 갱신되는 태스크 파일(스펙킷 스킬 참고, 체크박스 진척)을 만들고, 그 진척 상태를 Robo Architect가 폴링 등 가벼운 방식으로 받아 어떤 피처가 어떤 코드에 어떻게 반영되었는지 표시한다. Requirements 탭에서 구현된 피처/어그리거트를 클릭하면 실제 소스코드로 점프할 수 있게 한다."

## Clarifications

### Session 2026-05-19

- Q: 슬래시 커맨드를 어떤 형태로 생성할까요? → A: 범용 커맨드 1개 + 인자 — `.claude/commands/`에 범용 구현 커맨드를 한 번만 설치하고, 범위 종류·범위 ID는 호출 인자로 전달한다(커맨드 파일이 범위마다 누적되지 않음).
- Q: 태스크 파일을 프로젝트 어디에 둘까요? → A: `.robo/tasks/` 전용 디렉터리 — `.robo/tasks/<범위종류>-<범위ID>.md` 경로에 범위별 태스크 파일을 둔다.
- Q: MCP 서버를 대상 프로젝트에 어떻게 연결할까요? → A: "구현 커맨드 생성" 동작이 슬래시 커맨드 설치와 동시에 프로젝트의 `.mcp.json`에 MCP 서버를 등록한다.
- Q: Feature/Aggregate의 미착수·진행중·구현완료 상태를 무엇으로 판정할까요? → A: 태스크 파일 체크박스 비율로 도출 — 체크 0개=미착수, 일부=진행 중, 전부=구현 완료.

## User Scenarios & Testing *(mandatory)*

<!--
  각 User Story는 독립적으로 테스트 가능하며, 하나만 구현해도 가치를 전달하는 MVP 슬라이스다.
-->

### User Story 1 - 선택한 피처/BC/어그리거트로 Claude Code용 구현 커맨드 생성 (Priority: P1)

아키텍트가 Requirements 탭(또는 Aggregate 탭)에서 특정 Feature, Bounded Context, 또는 Aggregate를 선택하고 "Claude Code 구현 커맨드 생성"을 실행한다. Robo Architect는 대상 프로젝트의 Claude Code 커맨드 위치(`.claude/commands/`)에 범용 구현 슬래시 커맨드를 한 번만 설치하고, 같은 동작에서 프로젝트의 `.mcp.json`에 MCP 서버를 등록하며, 선택한 범위에 대한 정확한 호출 문자열(범위 종류와 범위 ID를 인자로 담은)을 아키텍트에게 제공한다. 아키텍트는 Claude Code에서 그 슬래시 커맨드 한 줄만 입력하면 해당 범위의 구현을 시작할 수 있다.

**Why this priority**: 동적 스펙 전달 흐름의 진입점이다. 커맨드를 생성·설치하는 능력이 없으면 이후의 모든 단계(동적 전달·태스크·진척·코드 점프)가 시작될 수 없다. 이 스토리만으로도 "선택한 범위를 Claude Code로 넘기는" 최소 가치가 성립한다.

**Independent Test**: Requirements 탭에서 Feature 하나를 선택해 커맨드 생성을 실행하고, 범용 구현 커맨드가 대상 프로젝트의 `.claude/commands/`에 설치되어 Claude Code 슬래시 커맨드 목록에 나타나며, 제공된 호출 문자열에 그 Feature의 ID와 범위 종류가 인자로 포함되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** Requirements 탭에 Feature·BC·User Story가 표시되어 있음, **When** 아키텍트가 Feature 노드를 선택하고 "구현 커맨드 생성"을 실행한다, **Then** 범용 구현 커맨드가 설치되고(아직 없으면), 그 Feature의 ID와 범위 종류 `feature`를 인자로 담은 호출 문자열이 아키텍트에게 제공된다.
2. **Given** 아키텍트가 Aggregate 탭에서 Aggregate를 선택함, **When** "구현 커맨드 생성"을 실행한다, **Then** 범위 종류 `aggregate`와 해당 Aggregate ID를 인자로 담은 호출 문자열이 제공된다.
3. **Given** 대상 프로젝트 홈 경로가 지정되어 있음, **When** 커맨드 생성을 완료한다, **Then** 범용 슬래시 커맨드가 그 프로젝트의 `.claude/commands/`에 설치되고 MCP 서버가 `.mcp.json`에 등록되어 Claude Code에서 즉시 호출 가능하다.
4. **Given** 대상 프로젝트 홈이 아직 지정되지 않음, **When** 커맨드 생성을 시도한다, **Then** 시스템은 프로젝트 홈을 먼저 지정하도록 안내하고, 지정 후 설치를 이어서 수행한다.

---

### User Story 2 - MCP가 PRD·구현 스펙을 동적으로 전달 (Priority: P1)

아키텍트가 Claude Code에서 생성된 슬래시 커맨드를 실행하면, 그 커맨드는 MCP 서버의 도구를 호출하고 MCP는 인자로 받은 범위 ID로 Robo Architect의 API를 호출한다. MCP는 해당 Feature/BC/Aggregate의 PRD와 구현 스펙(DDD 아티팩트에 해당하는 도메인 용어·BC 캔버스·어그리거트 설계·요구사항·인수조건 등)을 Robo Architect의 현재 모델 상태 그대로 동적으로 받아 Claude Code에 컨텍스트로 전달한다. 정적 마크다운 스펙 파일은 디스크에 생성되지 않으며, Claude Code는 전달받은 스펙을 근거로 구현을 진행한다.

**Why this priority**: 이 기능의 핵심 가치다. 기존 파일 생성 방식은 산출물이 쌓이고 모델이 바뀌어도 갱신되지 않는다. MCP를 통해 호출 시점의 최신 스펙을 동적으로 받으면 항상 신선한 스펙으로 구현할 수 있다.

**Independent Test**: 알려진 Feature ID로 MCP 도구를 직접 호출하여, Robo Architect 모델에 현재 존재하는 그 Feature의 PRD·User Story·인수조건·관련 어그리거트 설계가 응답으로 반환되고, 호출 직전 Robo Architect에서 스펙을 수정하면 그 수정이 응답에 반영되는지 확인한다.

**Acceptance Scenarios**:

1. **Given** Robo Architect에 모델링된 Feature가 존재, **When** Claude Code에서 그 Feature ID 인자로 슬래시 커맨드를 실행한다, **Then** MCP가 Robo Architect API를 호출해 그 Feature 범위의 PRD와 구현 스펙을 반환하고, 어떤 정적 스펙 마크다운 파일도 프로젝트에 기록되지 않는다.
2. **Given** 슬래시 커맨드가 한 번 생성된 뒤 Robo Architect에서 해당 범위의 모델이 수정됨, **When** 같은 슬래시 커맨드를 다시 실행한다, **Then** MCP는 수정된 최신 스펙을 반환한다(생성 시점에 고정되지 않음).
3. **Given** 범위 종류가 `bounded_context`인 커맨드, **When** 실행한다, **Then** 그 BC에 속한 Feature·User Story·Aggregate 설계가 모두 포함된 스펙 묶음이 반환된다.
4. **Given** 인자로 전달된 ID가 Robo Architect에 더 이상 존재하지 않음, **When** 슬래시 커맨드를 실행한다, **Then** MCP는 "해당 범위를 찾을 수 없음"을 명확히 알리고 빈 스펙이나 오래된 스펙을 반환하지 않는다.
5. **Given** Robo Architect API에 접근할 수 없음, **When** 슬래시 커맨드를 실행한다, **Then** MCP는 연결 실패를 명확한 메시지로 보고하고 구현을 추측으로 진행하지 않는다.

---

### User Story 3 - 구현 중 갱신되는 태스크 파일 (Priority: P2)

슬래시 커맨드가 동적 스펙을 받으면, Claude Code는 그 범위의 구현 작업을 SpecKit 스킬의 `tasks.md` 형식(체크박스 목록)에 맞춰 태스크 파일로 펼친다. 태스크 파일은 대상 프로젝트의 `.robo/tasks/<범위종류>-<범위ID>.md` 경로에 생성되며, 각 태스크는 구현이 진행됨에 따라 미완료(`- [ ]`)에서 완료(`- [x]`)로 체크된다. 태스크 파일은 어느 범위(피처/BC/어그리거트 ID)에 대한 것인지와 각 태스크가 어떤 산출물·코드 영역에 해당하는지를 식별할 수 있게 한다.

**Why this priority**: 진척을 추적할 단일 출처가 있어야 Robo Architect가 구현 상태를 반영할 수 있다. US1·US2만으로도 구현은 가능하지만, 태스크 파일이 있어야 진척 가시화(US4)가 의미를 갖는다.

**Independent Test**: 슬래시 커맨드를 실행해 구현을 시작하면 `.robo/tasks/` 아래에 범위 ID가 식별되는 태스크 파일이 생기고, 구현이 진행되면서 체크박스가 미완료→완료로 바뀌는지 파일 내용으로 확인한다.

**Acceptance Scenarios**:

1. **Given** 슬래시 커맨드가 동적 스펙을 전달받음, **When** Claude Code가 구현을 시작한다, **Then** SpecKit `tasks.md` 형식의 태스크 파일이 `.robo/tasks/<범위종류>-<범위ID>.md`에 생성되고 범위 ID가 경로와 파일 내용 모두로 식별 가능하다.
2. **Given** 태스크 파일에 미완료 태스크가 있음, **When** 그 태스크의 구현이 끝난다, **Then** 해당 항목이 완료 체크 상태로 갱신된다.
3. **Given** 태스크 항목이 코드 산출물과 연결됨, **When** 구현이 끝난다, **Then** 그 항목은 어떤 소스 파일·심볼이 만들어졌거나 수정되었는지 식별할 수 있는 정보를 담는다.

---

### User Story 4 - Robo Architect가 구현 진척을 가시화 (Priority: P2)

Robo Architect는 대상 프로젝트 홈의 위치를 이미 알고 있으므로, 그 프로젝트의 `.robo/tasks/` 디렉터리를 가벼운 방식(폴링)으로 읽어 구현 진척을 받아온다. Requirements 탭에서 각 Feature·User Story·Aggregate는 태스크 체크박스 비율(체크 0개=미착수, 일부=진행 중, 전부=구현 완료)에 따라 미착수·진행 중·구현 완료 상태로 표시되고, 태스크별 체크 진척이 보인다. 구현이 완료된 항목에는 어떤 코드 영역에 반영되었는지가 함께 표시된다.

**Why this priority**: 동적 스펙으로 구현한 결과가 Robo Architect로 되돌아와야 요구사항-구현의 폐회로가 완성된다. P1 흐름이 동작한 뒤 추가되는 가치다.

**Independent Test**: 태스크 파일의 체크박스를 미완료→완료로 바꾼 뒤, Requirements 탭에서 해당 Feature/User Story의 상태가 진행 중→구현 완료로 갱신되어 보이는지 확인한다.

**Acceptance Scenarios**:

1. **Given** `.robo/tasks/`에 범위 ID가 식별된 태스크 파일이 존재, **When** Robo Architect가 진척을 갱신한다, **Then** 그 범위의 Feature·User Story·Aggregate가 태스크 체크박스 비율(체크 0개=미착수, 일부=진행 중, 전부=구현 완료)에 따라 Requirements 탭에 표시된다.
2. **Given** 태스크 파일의 체크 상태가 변경됨, **When** Robo Architect가 다시 읽는다, **Then** Requirements 탭의 진척 표시가 변경 후 상태로 갱신된다.
3. **Given** 태스크 파일이 아직 없거나 읽을 수 없음, **When** Robo Architect가 진척을 갱신한다, **Then** 해당 범위는 "미착수" 또는 "진척 정보 없음"으로 표시되고 오류로 탭이 깨지지 않는다.
4. **Given** 태스크 파일이 손상되었거나 형식이 어긋남, **When** Robo Architect가 파싱한다, **Then** 시스템은 부분적으로 읽을 수 있는 만큼만 반영하고 전체 갱신을 중단하지 않는다.

---

### User Story 5 - 요구사항·어그리거트에서 구현 코드로 점프 (Priority: P3)

Requirements 탭에서 어떤 Feature 또는 Aggregate가 구현 완료로 표시되면, 아키텍트는 그 노드를 클릭해 실제 구현된 소스코드로 바로 이동할 수 있다. 코드 영역은 기존 Claude Code IDE 워크스페이스의 편집기에 열려 표시된다.

**Why this priority**: 요구사항에서 코드로의 추적성을 완성하는 마지막 슬라이스다. 진척 가시화(US4)가 있어야 어떤 노드가 코드와 연결됐는지 알 수 있으므로 그 뒤에 온다.

**Independent Test**: 구현 완료로 표시된 Aggregate를 Requirements 탭에서 클릭하여, 그 어그리거트를 구현한 소스 파일이 편집기에 열리는지 확인한다.

**Acceptance Scenarios**:

1. **Given** 구현 완료로 표시된 Aggregate, **When** 아키텍트가 그 노드를 클릭한다, **Then** 그 어그리거트를 구현한 소스 파일이 코드 편집기에 열린다.
2. **Given** 구현 완료로 표시된 Feature, **When** 아키텍트가 코드 점프를 실행한다, **Then** 그 Feature와 연결된 하나 이상의 소스 위치가 제시되고 선택해 열 수 있다.
3. **Given** 태스크 파일이 가리키던 소스 파일이 이후 이동·삭제됨, **When** 아키텍트가 코드 점프를 실행한다, **Then** 시스템은 대상 코드를 찾을 수 없음을 안내하고 탭을 깨뜨리지 않는다.

---

### Edge Cases

- 슬래시 커맨드 생성 후 그 범위가 Robo Architect에서 삭제된 경우 — 실행 시 MCP는 "범위 없음"을 알린다(US2-4).
- 슬래시 커맨드 실행 시 Robo Architect API가 다운/접근 불가 — MCP는 명확한 실패를 보고하고 추측 구현을 막는다(US2-5).
- 구현 커맨드 생성을 여러 번 실행한 경우 — 범용 슬래시 커맨드와 `.mcp.json` 등록은 멱등하게 처리되어 중복 누적되지 않는다.
- 한 프로젝트에서 여러 범위의 태스크 파일이 동시에 존재 — Robo Architect는 범위 ID로 각 파일을 올바른 노드에 매핑한다.
- 태스크 파일이 손상되거나 부분만 작성됨 — 부분 파싱만 반영하고 전체 갱신은 계속된다(US4-4).
- 동적 스펙 전달 도중 모델이 바뀌는 동시 편집 — 호출이 시작된 시점의 일관된 스냅샷이 전달된다.
- 기존 파일 생성 방식으로 만든 정적 스펙 파일이 이미 프로젝트에 있는 경우 — 동적 방식과 충돌 없이 공존한다(정적 파일을 자동 삭제하지 않음).

## Requirements *(mandatory)*

### Functional Requirements

**범위 선택 및 커맨드 생성**

- **FR-001**: 시스템 MUST Requirements 탭과 Aggregate 탭에서 Feature, Bounded Context, Aggregate 중 하나를 구현 범위로 선택하게 한다.
- **FR-002**: 시스템 MUST 범위 종류(`feature`/`bounded_context`/`aggregate`)와 범위 ID를 인자로 받는 단일 범용 슬래시 커맨드를 제공하며, 범위마다 별도 커맨드 파일을 만들지 않는다. "구현 커맨드 생성"은 선택한 범위에 대한 정확한 호출 문자열을 아키텍트에게 제시한다.
- **FR-003**: 시스템 MUST 범용 슬래시 커맨드를 대상 프로젝트의 Claude Code 커맨드 위치(`.claude/commands/`)에 설치하고, 같은 동작에서 MCP 서버를 프로젝트의 `.mcp.json`에 등록한다.
- **FR-004**: 시스템 MUST 대상 프로젝트 홈 경로가 지정되지 않았을 때 커맨드 생성 전에 프로젝트 홈 지정을 요구한다.
- **FR-005**: 시스템 MUST 범용 슬래시 커맨드 설치와 `.mcp.json` MCP 등록을 멱등하게 수행한다 — 이미 설치/등록되어 있으면 중복 커맨드 파일이나 중복 `.mcp.json` 항목을 누적하지 않는다.

**MCP 동적 스펙 전달**

- **FR-006**: 시스템 MUST 슬래시 커맨드가 호출하는 MCP 서버를 제공하며, MCP는 범위 ID를 받아 Robo Architect의 API로 그 범위의 PRD와 구현 스펙을 조회한다.
- **FR-007**: MCP가 전달하는 스펙 MUST 호출 시점의 Robo Architect 모델 상태를 반영하며, 슬래시 커맨드 생성 시점에 고정되지 않는다.
- **FR-008**: 동적 스펙 전달 경로에서 시스템 MUST 정적 스펙 마크다운 파일을 프로젝트 디스크에 생성하지 않는다.
- **FR-009**: 범위가 `bounded_context`이면 MCP가 반환하는 스펙 MUST 그 BC에 속한 Feature·User Story·인수조건·Aggregate 설계를 포함한다. 범위가 `feature`/`aggregate`이면 해당 범위에 한정된 스펙을 반환한다.
- **FR-010**: 인자로 전달된 범위 ID가 Robo Architect에 존재하지 않으면 MCP MUST 명확한 "범위 없음" 응답을 반환하고 빈/오래된 스펙을 반환하지 않는다.
- **FR-011**: Robo Architect API에 접근할 수 없으면 MCP MUST 명확한 실패를 보고하여 Claude Code가 추측으로 구현하지 않게 한다.
- **FR-012**: 시스템 MUST 기존 PRD 파일 생성 방식(BC별 DDD 마크다운 산출물)을 계속 지원하며, 동적 방식이 기존 방식이나 이미 존재하는 정적 산출물을 자동으로 삭제하지 않는다.

**태스크 파일**

- **FR-013**: 슬래시 커맨드 실행 시 시스템 MUST 전달받은 스펙을 SpecKit `tasks.md` 형식(체크박스 목록)의 태스크 파일로 `.robo/tasks/<범위종류>-<범위ID>.md` 경로에 펼친다.
- **FR-014**: 태스크 파일 MUST 어느 범위(범위 종류·범위 ID)에 대한 것인지 파일 경로와 파일 내 메타데이터 모두로 식별할 수 있어야 한다.
- **FR-015**: 시스템 MUST 구현이 진행됨에 따라 태스크 항목의 체크 상태를 미완료에서 완료로 갱신한다.
- **FR-016**: 완료된 태스크 항목 MUST 어떤 소스 파일/심볼이 생성·수정되었는지 식별할 수 있는 정보를 담는다.

**진척 가시화**

- **FR-017**: Robo Architect MUST 대상 프로젝트 홈의 `.robo/tasks/` 디렉터리를 가벼운 방식(폴링)으로 읽어 구현 진척을 받아온다.
- **FR-018**: Requirements 탭 MUST 각 Feature·User Story·Aggregate를 태스크 항목 체크박스 비율에 따라 미착수(체크 0개)·진행 중(일부 체크)·구현 완료(전부 체크) 상태로 표시한다.
- **FR-019**: 태스크 파일의 체크 상태가 바뀌면 Robo Architect MUST 다음 갱신 시 Requirements 탭의 진척 표시를 갱신한다.
- **FR-020**: 태스크 파일이 없거나 읽을 수 없으면 시스템 MUST 해당 범위를 미착수/진척 정보 없음으로 표시하고 탭을 깨뜨리지 않는다.
- **FR-021**: 태스크 파일이 손상되었거나 형식이 어긋나면 시스템 MUST 부분적으로 읽을 수 있는 만큼만 반영하고 전체 갱신을 중단하지 않는다.
- **FR-022**: 시스템 MUST 구현 완료 항목에 대해 어떤 코드 영역에 반영되었는지를 Requirements 탭에서 함께 보여준다.

**코드 점프**

- **FR-023**: 구현 완료로 표시된 Feature·Aggregate에 대해 시스템 MUST 클릭으로 실제 구현 소스 위치로 이동하는 동작을 제공한다.
- **FR-024**: 코드 점프 MUST 대상 소스를 기존 Claude Code IDE 워크스페이스 편집기에 연다.
- **FR-025**: 가리키던 소스 위치가 이동·삭제되어 더 이상 존재하지 않으면 시스템 MUST 대상을 찾을 수 없음을 안내하고 탭을 깨뜨리지 않는다.

### Key Entities

- **구현 범위(Implementation Scope)**: 구현 대상 단위. 종류는 Feature, Bounded Context, Aggregate 중 하나이며 Robo Architect 모델의 ID로 식별된다.
- **구현 커맨드(Implementation Command)**: 범위 종류와 범위 ID를 인자로 받는 단일 범용 Claude Code 슬래시 커맨드. 범위마다 별도 파일을 만들지 않으며 프로젝트당 한 번 설치된다.
- **MCP 스펙 브리지(MCP Spec Bridge)**: 슬래시 커맨드가 호출하는 MCP 서버. 범위 ID로 Robo Architect API를 조회해 스펙을 동적으로 전달한다.
- **라이브 스펙 묶음(Live Spec Bundle)**: MCP가 반환하는, 호출 시점 모델 상태의 PRD·구현 스펙(도메인 용어·BC 캔버스·어그리거트 설계·요구사항·인수조건 등).
- **태스크 파일(Task File)**: 구현 작업을 담은 SpecKit `tasks.md` 형식 파일. `.robo/tasks/<범위종류>-<범위ID>.md`에 위치하며 체크박스로 진척을 표현한다.
- **태스크 항목(Task Item)**: 태스크 파일의 한 항목. 완료 여부와 연결된 소스 파일/심볼 정보를 가진다.
- **구현 매핑(Implementation Mapping)**: Feature/Aggregate ↔ 실제 소스 코드 위치의 연결. 진척 표시와 코드 점프의 근거.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 아키텍트가 범위를 선택해 Claude Code에서 호출 가능한 구현 커맨드를 갖추기까지 1분 이내에 끝낼 수 있다.
- **SC-002**: 동적 경로로 구현을 시작할 때 프로젝트에 새로 생성되는 정적 스펙 마크다운 파일이 0건이다.
- **SC-003**: 슬래시 커맨드가 전달하는 스펙은 항상 호출 시점의 Robo Architect 모델과 일치한다 — 호출 직전 모델을 수정한 100건의 시나리오 모두에서 수정이 반영된다(오래된 스펙 0건).
- **SC-004**: 태스크 파일의 체크 상태가 바뀐 뒤 Requirements 탭의 진척 표시가 30초 이내에 일치한다.
- **SC-005**: 구현 완료로 표시된 Feature·Aggregate에서 실제 구현 소스 파일을 1회 클릭으로 연다.
- **SC-006**: 범위 없음·API 접근 불가·태스크 파일 손상 등 모든 실패 경로에서 시스템이 추측 스펙을 전달하거나 탭이 깨지지 않고 명확한 안내를 제공한다.

## Assumptions

- 기존 PRD 생성/파일 산출(spec 007·022)과 임베디드 Claude Code 워크스페이스(spec 015·021)는 그대로 존재하며, 본 기능은 이를 대체하지 않고 동적 대안으로 추가된다.
- Robo Architect는 대상 프로젝트의 홈 경로를 이미 알고 있다(Claude Code 워크스페이스의 작업 디렉터리 선택을 통해). 진척 폴링과 태스크 파일 위치 탐색은 이 경로를 기준으로 한다.
- 진척 동기화는 MCP가 Robo Architect로 푸시하는 방식 대신, Robo Architect가 태스크 파일을 폴링하는 방식을 채택한다. 폴링은 더 단순하고, 구현 주체(Claude Code/MCP)에 진척 보고 책임을 지우지 않으며, 태스크 파일이 단일 진실 출처가 된다.
- Robo Architect와 MCP 서버는 동일 로컬 환경에서 동작하는 단일 사용자 시나리오를 전제로 한다. MCP→Robo Architect API 호출은 로컬 API를 사용하며 별도 다중 사용자 인증은 v1 범위 밖이다.
- 태스크 파일 형식은 로컬 `.claude` 아래 SpecKit 스킬의 `tasks.md` 체크박스 규약을 따른다.
- 구현 범위의 ID는 Requirements 탭/Aggregate 탭이 사용하는 기존 Robo Architect 모델 식별자를 그대로 쓴다.
- 동적 스펙의 내용 구성(도메인 용어·BC 캔버스·어그리거트 설계·요구사항·인수조건)은 기존 DDD 아티팩트 생성(spec 022)이 만들던 산출물과 동등한 정보를, 파일 대신 응답으로 전달한다.
