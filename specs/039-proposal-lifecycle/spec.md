# Feature Specification: Proposal Lifecycle Management

**Feature Branch**: `039-proposal-lifecycle`

**Created**: 2026-06-05

**Status**: In Progress (구현 반영 — 생애주기·구현·검증·승인 흐름 동작)

**Last updated**: 2026-06-10 — 작업 분해(robo-proposal-tasks)·tasks.md 진행 모니터링·`/robo-implement` PRO 모드·검증(robo-sync 구조 검증 + GWT)·기본 PO 정책 반영.

---

## 개요

038에서 구현한 `RequirementChange(Change)` 기반 요구사항 변경 관리 시스템을 **Proposal(제안) 기반 생애주기 관리**로 진화시킨다.

기존 Change는 요구사항 변경 레코드를 생성하고 수동으로 승인·구현하는 단순한 트래킹 도구였다. Proposal은 자연어 의도를 AI가 분해·분석하여 **격리된 Git Worktree 샌드박스에서 구현·검증하고 PO가 Accept/Destroy 결정하는 완전한 "평행 우주" 실험 단위**다. 메인 시스템은 Accept가 확정되는 순간까지 절대 건드리지 않는다.

038의 핵심 인프라(Neo4j 그래프, EFFECT 관계, SemanticDiff, SSE 스트리밍, skill_runner)는 그대로 재사용하되, Proposal 생애주기를 지원하는 상위 계층을 추가한다.

**구현된 흐름(요약)**: DRAFT(인텐트 분해) → SUBMITTED → **작업 목록 생성/재생성**(`robo-proposal-tasks`로 미리 분해, SUBMITTED 게이팅) → **구현하기**(대상 프로젝트 worktree 생성·`PROPOSAL_<id>_TASKS.md` 기록; 비-git이면 동의 후 `git init`) → **"Claude Code 셀로 이동"** 버튼으로 셀 진입 + `/robo-implement <PRO-NNN>` 자동 주입(robo-implement PRO 모드) → tasks.md 진행 모니터링(목록·상세에 진행 중/정체/완료) → 전부 완료 시 **"구현 완료 → 검증"** → **검증**('검증' 탭 진입 시 트리거: robo-sync 구조 검증 + GWT, "재검증" 가능) → PENDING_ACCEPTANCE → **Accept(기본 PO 정책 — 자기 승인 허용)/Destroy**.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Proposal 생성: 자연어 입력 → 인텐트 분해 (Priority: P1)

사용자가 Proposals 탭에 자연어 한 줄을 입력하면, AI가 전략적(Epic/Feature/UserStory 수준) 변경과 전술적(Aggregate/Command/Event/VO 수준) 변경으로 분해하여 Proposal 초안(DRAFT)을 생성한다.

**Why this priority**: Proposal 생성이 없으면 모든 후속 단계가 불가능하다. 인텐트 분해는 038 Change에는 없던 핵심 신규 기능이다.

**Independent Test**: Proposals 탭에서 자연어 문장을 입력하면 전략적 변경 항목(수정될 Epic·Feature·UserStory 목록)과 전술적 변경 항목(수정될 Aggregate·Command·Event·VO 목록)이 구분 표시된 Proposal 초안이 생성된다.

**Acceptance Scenarios**:

1. **Given** 사용자가 Proposals 탭에서 자연어를 입력하고 제출했을 때, **When** AI가 인텐트 분해를 완료하면, **Then** 전략적 변경 항목(신규/수정 Epic·User Story·Feature)과 전술적 변경 항목(Aggregate·Command·Event·VO)이 구분 표시된 Proposal 초안(DRAFT 상태)이 생성된다.
2. **Given** AI가 Impact Map을 생성할 때, **When** 그래프 DB에서 영향받는 노드가 탐색되면, **Then** 관련 UserStory·Feature·BoundedContext 목록과 각 노드의 충돌 가능성(HIGH|MEDIUM|LOW)이 함께 표시된다.
3. **Given** 요구사항이 모호할 때, **When** AI가 최대 5개의 명확화 질문이 필요하다고 판단하면, **Then** 순차적으로 선택형 질문이 제시되고 답변 후 Proposal 초안이 확정된다. 사용자가 중단하면 현재까지의 정보로 DRAFT 저장된다.
4. **Given** Proposal이 생성될 때, **Then** 생성자(사용자 ID)·생성 시각·원본 자연어 입력이 Proposal에 기록된다.
5. **Given** Impact Map 생성이 30초를 초과할 때, **Then** 이미 탐색된 부분 결과가 SSE를 통해 점진적으로 표시된다.

---

### User Story 2 — Proposal 검토: Strategic·Tactical Diff 확인 및 수정 (Priority: P1)

생성된 Proposal의 Strategic Diff(User Story·Feature·Epic 변경안)와 Tactical Diff(Aggregate·VO·Command·Event 변경안)를 상세 화면에서 검토하고, 필요 시 개별 항목을 수정·삭제·추가할 수 있다.

**Why this priority**: PO와 아키텍트가 AI 제안을 검토·보정하는 단계가 없으면 Proposal을 신뢰할 수 없다.

**Independent Test**: Proposal 상세 화면에서 Strategic Diff 섹션에 변경될 User Story 목록이 Before/After 형태로, Tactical Diff 섹션에 변경될 Aggregate 필드가 SemanticDiff 형태로 표시되면 완료.

**Acceptance Scenarios**:

1. **Given** Proposal이 DRAFT 상태일 때, **When** 상세 화면을 열면, **Then** Strategic Diff 섹션(Epic/Feature/UserStory 변경안)과 Tactical Diff 섹션(Aggregate·Command·Event·VO 변경안)이 Before/After 형태로 표시된다.
2. **Given** Proposal 상세 화면에서, **When** 사용자가 특정 Diff 항목을 편집하면, **Then** 해당 변경안이 업데이트되고 영향받는 연관 항목의 충돌 경고가 재계산된다.
3. **Given** Strategic Diff에서 특정 User Story 변경안을 제거하면, **Then** 해당 항목과 연결된 Tactical Diff 항목들도 자동으로 제거 제안이 표시된다.
4. **Given** Proposal이 DRAFT 상태일 때, **When** 사용자가 인텐트 분해 결과가 의도를 잘못 반영했다고 판단해 자연어 피드백(예: "부분 환불이 아니라 전액 취소다")을 입력하고 "재생성"을 누르면, **Then** 그 피드백과 직전 분해 결과가 함께 스킬에 전달되어 분해가 다시 수행되고, 보정 narration이 실시간 스트리밍된 뒤 새 Strategic·Tactical Diff가 화면에 갱신된다. 피드백이 지적하지 않은 부분은 유지된다. (피드백은 여러 번 누적 가능)
5. **Given** Proposal이 DRAFT 상태일 때, **When** 사용자가 분해 결과가 정확하다고 판단해 그대로 "Proposal 제출(SUBMIT)"을 누르면, **Then** 상태가 SUBMITTED로 전환되고 샌드박스 구현 단계가 활성화된다.

---

### User Story 3 — 샌드박스 구현: Git Worktree 격리 환경에서 자동 코드 생성 (Priority: P2)

SUBMITTED 상태의 Proposal에서 (작업 목록 생성 후) "구현하기"를 누르면, **Claude Code 탭에 설정된 대상 프로젝트**(robo-architect 자기 자신이 아니라 사용자가 설계·구현 중인 프로젝트)를 원천으로 격리된 Git Worktree(`proposal/<PRO-NNN>` 브랜치)가 생성되고 작업 목록(`PROPOSAL_<id>_TASKS.md`)이 기록된다. **자동으로 Code 탭으로 넘어가지 않고**, "Claude Code 셀로 이동" 버튼을 눌러야 **Code 탭의 살아있는 Claude Code 셀(PTY 터미널)**이 그 Worktree로 전환되며 셀에 `/robo-implement <PRO-NNN>`(robo-implement PRO 모드)이 자동 입력되어 인터랙티브하게 구현을 진행한다. 사용자는 같은 셀에서 진행 로그를 실시간으로 보고, 중지(Ctrl+C/Esc)하거나 중간 피드백을 입력할 수 있다.

**Why this priority**: 샌드박스 격리야말로 "실패에 대한 두려움" 문제를 해결하는 핵심 메커니즘이다.

**Independent Test**: SUBMITTED Proposal에서 작업 목록 생성 후 "구현하기"를 누르면 대상 프로젝트의 Git repo에 `proposal/<PRO-NNN>` 브랜치/Worktree와 `PROPOSAL_<id>_TASKS.md`가 생성되고, "Claude Code 셀로 이동"을 누르면 Code 탭의 셀이 그 Worktree에서 `/robo-implement`로 구현을 시작한다.

**Acceptance Scenarios**:

1. **Given** Proposal이 SUBMITTED 상태이고 작업 목록이 생성되어 있을 때, **When** 사용자가 "구현하기"를 누르면, **Then** 대상 프로젝트의 Git repo에서 `proposal/<PRO-NNN>` 격리 브랜치/Worktree와 `PROPOSAL_<id>_TASKS.md`가 생성되며(자동 이동 없음), 이어 "Claude Code 셀로 이동"을 누르면 Code 탭의 셀이 그 Worktree로 전환되어 `/robo-implement <PRO-NNN>`으로 구현을 시작한다.
1a. **Given** 대상 프로젝트 경로가 아직 Git 저장소가 아닐 때, **When** 사용자가 "구현 시작"을 누르면, **Then** "Git 저장소를 생성하고 계속할까요?" 확인 다이얼로그가 표시되고, 동의하면 백엔드가 `git init` + 초기 커밋을 수행한 뒤 Worktree 생성·구현이 이어지며, 거부하면 상태 변경 없이(SUBMITTED 유지) 중단된다.
2. **Given** 샌드박스 구현이 진행 중일 때, **Then** 진행 로그가 Code 탭의 Claude Code 셀(터미널)에 실시간으로 표시되고, 사용자는 그 셀에서 중지(Ctrl+C/Esc)하거나 추가 지시(피드백)를 입력할 수 있다.
3. **Given** Proposal이 IMPLEMENTING 상태이고 작업이 완료(tasks.md 전부 체크)됐을 때, **When** Proposal 상세 화면에서 "구현 완료 → 검증"을 누르면, **Then** Proposal 상태가 IMPLEMENTING → TESTING으로 전환되고 '검증' 탭으로 자동 이동하여 검증이 시작된다. (부분 완료면 "미구현부분 완료하기"로 동일 전환.)
3a. **Given** Proposal이 SUBMITTED 상태일 때, **When** 사용자가 "작업 목록 생성"을 누르면, **Then** proposal 쪽 헤드리스 서브프로세스가 Strategic·Tactical Diff로부터 작업 목록을 분해해 분석 서술이 실시간 스트리밍되고 Phase별 작업 목록이 표시되며, 그 뒤에야 "구현 시작" 버튼이 노출된다. "구현 시작" 시 이 목록이 워크트리에 `PROPOSAL_<id>_TASKS.md`로 미리 기록되어 셀이 그대로 따라 구현한다.
3b. **Given** Proposal이 IMPLEMENTING/TESTING 상태일 때, **When** 셀이 워크트리의 `PROPOSAL_<id>_TASKS.md` 작업을 `- [x]`로 체크해 나가면, **Then** 구현 탭에 진행률 바·Phase별 체크리스트·상태 배지가 주기적으로 갱신 표시되고, 일정 시간 체크리스트 갱신이 없으면 "정체(멈춤 가능)"로 표시된다.
4. **Given** 사용자가 다른 탭으로 이동했다가 돌아와도, **When** Proposal 상세의 "Claude Code 셀로 이동" 버튼을 누르면, **Then** 셀(PTY 세션)이 끊기지 않은 채로 Code 탭으로 전환되어 진행 중인 구현 세션을 그대로 이어볼 수 있다.
5. **Given** 여러 Proposal이 각자의 Worktree에서 동시에 구현 중일 때, **Then** Code 탭 상단의 세션 탭 바에 worktree별 독립 Claude Code 셀이 동시에 표시되고(프로세스·UI 중복 없음), 탭을 클릭하면 해당 세션으로 전환되며 좌측 파일 트리/에디터도 그 worktree를 따라간다.
6. **Given** 구현 세션이 진행 중일 때, **When** 브라우저를 새로고침하면, **Then** 세션 탭이 복원되고 같은 `session_id`로 재연결되어 살아있는 claude 세션에 재어태치(스크롤백 재생)된다. 세션 탭의 × 를 눌러야만 해당 PTY가 실제로 종료된다.
7. **Given** Proposal이 이미 IMPLEMENTING이거나 그 이후 상태(TESTING/PENDING_ACCEPTANCE/MERGE_FAILED)일 때, **When** 사용자가 "다시 구현하기"를 누르면, **Then** 확인 후 기존 Worktree·셀 세션이 초기화되고 새 Worktree·셀로 처음부터 다시 구현이 시작된다. (ACCEPTED·DESTROYED 상태에서는 버튼이 비활성/미노출.)
8. **Given** Proposal이 Destroy 처리되면, **Then** 대상 프로젝트의 해당 Git Worktree와 브랜치가 자동으로 정리(삭제)된다.

---

### User Story 4 — 자동 검증 및 PO 승인 (Accept/Destroy) (Priority: P2)

구현이 완료된 Proposal에 대해 **검증**(① UserStory GWT 인수 조건 LLM-judge + ② robo-sync 구조 검증: Tactical Diff ↔ 구현체)이 실행되고, 결과를 확인한 PO가 최종 Accept 또는 Destroy를 결정한다.

**Why this priority**: 사람이 수동으로 테스트 코드를 작성하지 않아도, 인수 조건뿐 아니라 **설계(Aggregate/VO/Command)와 실제 구현체의 일치**까지 자동 검증되는 구조가 Proposal 패러다임의 핵심 가치다.

**Independent Test**: 구현 완료된 Proposal의 "검증" 탭을 열면 검증이 실행되고(구조/인수조건별 통과/실패), 통과 후 "Accept" 또는 "Destroy" 버튼이 활성화되면 완료.

**Acceptance Scenarios**:

1. **Given** Proposal이 TESTING 상태일 때, **When** 사용자가 "검증" 탭을 열면, **Then** 검증이 트리거되어 "검증 중" 표시 후, robo-sync 구조 검증(구조)과 GWT 인수 조건(인수조건) 결과가 `category` 배지와 함께 표시되고 TESTING→PENDING_ACCEPTANCE로 전환된다.
2. **Given** 테스트 결과가 표시된 상태에서, **When** PO가 "Accept"를 누르면, **Then** 샌드박스 브랜치가 메인 브랜치에 머지되고 그래프 DB에 Strategic·Tactical Diff가 반영되는 Dual Merge가 단일 트랜잭션으로 실행된다.
3. **Given** Dual Merge가 완료되면, **Then** Proposal 상태가 ACCEPTED로 전환되고 변경된 UserStory·Aggregate·Feature 노드들이 그래프 DB에 업데이트된다.
4. **Given** PO가 "Destroy"를 누르면, **Then** Proposal 상태가 DESTROYED로 전환되고 샌드박스 브랜치·Worktree가 정리되며, Proposal의 Diff 내용은 이력으로 보관된다.
5. **Given** 검증 일부가 실패(FAIL)했을 때, **When** PO가 실패를 무시하고 Accept를 시도하면, **Then** 실패 항목 수와 리스크 경고가 표시되며 PO가 "실패 항목 인지" 체크 후에야 Accept가 진행된다.
6. **Given** 기본 PO 정책이 적용될 때, **When** Proposal 작성자 본인이 Accept를 누르면, **Then** 자기 승인이 허용되어 Accept가 진행된다(역할 시스템 도입 시 비-PO는 거부). (FR-014)
7. **Given** 구현이 완료(TESTING)된 Proposal에서, **When** 사용자가 '샌드박스 구현' 탭의 "검증하기"를 누르거나 '검증' 탭의 "재검증"을 누르면, **Then** 검증이 runner(스트리밍)로 실행되어 실행 로그가 실시간 표시되고 완료 시 갱신된 결과가 나타난다(완료 후 언제든 추가 검증 가능). (FR-007g)
7b. **Given** 검증이 진행 중일 때, **When** 사용자가 "중지"를 누르면, **Then** 검증 스트림이 닫히고 서버의 claude 서브프로세스가 정리되며 상태는 TESTING으로 남아 언제든 재검증할 수 있다. (FR-007g)
8. **Given** 구현이 완료(TESTING)되었으나 검증을 아직 통과·완료하지 않았을 때, **When** PO가 'Accept / Destroy' 탭으로 이동하면, **Then** 탭이 노출되고(검증 미완료 안내와 함께) 검증 없이도 Accept/Destroy를 결정할 수 있다. (FR-009b)

---

### User Story 5 — Proposal 목록 조회 및 관리 (Priority: P2)

팀 멤버는 Proposals 탭에서 모든 Proposal을 상태별로 필터링하여 조회하고, 각 Proposal의 진행 상태·작성자·생성일·영향 범위를 한눈에 파악할 수 있다.

**Why this priority**: 여러 Proposal이 동시에 진행될 수 있으므로 목록 관리가 필수다.

**Independent Test**: Proposals 탭에서 상태 필터(DRAFT/SUBMITTED/IMPLEMENTING/TESTING/ACCEPTED/DESTROYED)를 선택하면 해당 Proposal 목록이 표시된다.

**Acceptance Scenarios**:

1. **Given** Proposals 탭이 열릴 때, **When** Proposal 목록이 로딩되면, **Then** PRO-NNN ID·제목·상태·작성자·생성일·영향 노드 수가 목록에 표시된다.
2. **Given** 상태 필터를 선택하면, **Then** 해당 상태의 Proposal만 목록에 표시된다.
3. **Given** Proposal이 IMPLEMENTING 또는 TESTING 상태일 때, **Then** 목록 항목에 실시간 진행 상태(진행률 %)가 함께 표시된다.
4. **Given** DESTROYED 상태의 Proposal을 클릭하면, **Then** 폐기된 Diff 이력이 조회 전용으로 표시된다(복구 옵션은 별도 제공).

---

### User Story 6 — Dual Merge 상세: 코드 + 그래프 DB 단일 트랜잭션 동기화 (Priority: P3)

Accept 시점에 Git 코드 머지와 Neo4j 그래프 DB 업데이트가 단일 트랜잭션으로 처리되어, 코드와 스펙이 항상 일치하는 Single Source of Truth 상태가 유지된다.

**Why this priority**: Spec Drift 문제를 원천 해결하는 메커니즘이나, 기반 기능(Accept)이 먼저 완성되어야 한다.

**Independent Test**: Accept 후 메인 브랜치를 확인했을 때 샌드박스 코드가 머지되어 있고, 그래프 DB에서 해당 UserStory·Aggregate 노드의 내용이 Proposal의 After 상태로 업데이트되어 있으면 완료.

**Acceptance Scenarios**:

1. **Given** PO가 Accept를 확정했을 때, **When** Dual Merge가 완료되면, **Then** Git 메인 브랜치에 샌드박스 구현 코드가 반영되어 있고, Neo4j 그래프 DB의 관련 노드 속성이 Strategic·Tactical Diff의 After 값으로 업데이트되어 있다.
2. **Given** Dual Merge 도중 코드 머지에 성공했지만 그래프 DB 업데이트가 실패하면, **Then** 코드 머지가 롤백되고 Proposal은 MERGE_FAILED 상태로 전환되어 재시도 옵션이 제공된다.
3. **Given** Dual Merge가 완료되면, **Then** PRD·DDD 스펙 문서(도메인 용어집, 컨텍스트 맵 마크다운)가 Proposal의 Diff를 기반으로 자동 갱신된다.

---

### Edge Cases

- 동일한 UserStory/Aggregate를 수정하는 두 Proposal이 동시에 IMPLEMENTING 상태일 때 충돌 감지 및 경고.
- Proposal의 Strategic Diff에 새 UserStory 생성이 포함될 때, 샌드박스에서 해당 UserStory의 Aggregate 구현도 자동 생성.
- 샌드박스 Git Worktree 생성 시 디스크 공간이 부족하면 오류 메시지와 함께 Proposal 상태를 DRAFT로 복귀.
- 대상 경로가 아직 Git 저장소가 아니면(로컬 repo 미생성) 오류 대신 git init 확인 다이얼로그를 띄운다. 동의 시 `git init` + 초기 커밋 후 Worktree를 생성하고, 거부 시 상태 변경 없이(SUBMITTED 유지) 중단한다. (FR-006)
- 샌드박스 Worktree(`<projectRoot>/.sandbox/`)와 컨텍스트 파일(`PROPOSAL_*.md`)은 대상 프로젝트의 `.git/info/exclude`에 등록되어 사용자 프로젝트의 `git status`·머지를 오염시키지 않는다.
- Impact Map 분석에서 그래프 DB 연결이 없는 요구사항(고아 노드)은 "관련 노드 없음" 표시 후 수동 매핑 옵션 제공.
- Clarification 세션 중 사용자가 5분 이상 응답하지 않으면 세션 만료 처리, 현재 상태로 DRAFT 저장.
- ACCEPTED Proposal의 Diff는 영구 보관(삭제 불가)하여 언제든 이력 조회 가능.
- Accept 권한은 PO 역할 기준. 기본 정책상 모든 사용자가 PO 역할을 가지므로 **자기 승인(작성자 본인 Accept)이 허용**된다. 실제 역할 시스템 도입 시 비-PO는 거부.
- 동시 Claude Code 셀 세션 수가 백엔드 상한(기본 16)을 초과하면 새 세션 생성을 거부하고 "사용하지 않는 셀을 닫아달라"는 안내를 표시한다. 사용자가 ×로 닫지 않고 떠난 세션은 일정 시간(TTL, 기본 30분) 분리 상태로 유지된 뒤 자동 회수된다.
- "다시 구현하기"는 기존 Worktree와 셀 세션을 초기화(종료)하고 새로 시작하므로, 실행 전 확인을 받는다. 재구현 시 셀 세션은 새 식별자(`session_id`의 epoch 증가)로 다시 띄워 종료-재연결 경합을 방지한다.
- 과거 데이터(예: `impactMap` 항목의 누락/널 필드)는 응답 직렬화 시 항목 단위로 보정·스킵하여, 한 건의 스키마 위반이 목록 조회 전체를 실패시키지 않는다.
- Worktree 원천(projectRoot)은 **현재 Code 탭에 설정된 프로젝트 루트**를 우선하고, 저장된 `proposal.projectRoot`는 폴백으로만 쓴다(과거 오염 저장된 값이 우선되지 않도록). 어떤 경로든 `.../.sandbox/proposal/<id>` 안쪽을 가리키면(다른 Proposal의 worktree 경로 등) 프런트·백엔드 양쪽에서 실제 루트로 끌어올려(de-nest) **샌드박스 안에 worktree를 중첩 생성하지 않는다.** 백엔드는 저장 시 정규화된 루트로 덮어써 자가 치유하고, 재구현 시 같은 브랜치를 체크아웃 중인 잔존 worktree까지 정리한 뒤 재생성한다. (FR-006)

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 시스템은 `Proposal` 노드를 생성·조회·목록화할 수 있어야 하며, 각 Proposal은 전역 고유 ID(`PRO-NNN`)를 가져야 한다.
- **FR-002**: Proposal 생성 시 AI가 자연어 입력을 인텐트 분해하여 Strategic Diff(Epic/Feature/UserStory 변경안)와 Tactical Diff(Aggregate/Command/Event/VO 변경안)를 각각 구분하여 생성해야 한다.
- **FR-003**: 시스템은 그래프 DB에서 Proposal 영향 범위(Impact Map)를 탐색하여 영향받는 노드 목록과 충돌 가능성(HIGH/MEDIUM/LOW)을 생성해야 한다. 038의 `EFFECT` 관계·`effect_analyzer.py`를 재사용한다.
- **FR-004**: 요구사항이 모호할 때 AI가 최대 5개의 명확화 질문을 순차 제시하고, 사용자 답변을 Proposal에 반영해야 한다.
- **FR-002a**: DRAFT 상태의 Proposal에서 사용자는 인텐트 분해 결과를 **그대로 제출**하거나, 결과가 의도를 잘못 반영한 경우 **자연어 피드백을 입력해 재생성**할 수 있어야 한다. 재생성은 (1) 피드백을 Proposal의 `intentFeedbackLog`(JSON List<{feedback,at}>)에 누적 저장하고, (2) 인텐트 분해 스킬(`robo-proposal-intent`)을 **직전 분해 결과(strategicDiff/tacticalDiff) + 누적 피드백**을 프롬프트에 실어 다시 호출하며(인텐트 SSE 재구독), (3) 보정 narration을 실시간 스트리밍한 뒤 새 Strategic·Tactical Diff로 갱신한다. 스킬은 피드백을 최우선 반영하되 지적되지 않은 부분은 유지하고, 재생성 시에는 가능한 한 추가 명확화 질문 없이 `done`을 반환한다. 재생성은 DRAFT에서만 허용된다(SUBMITTED 이후 409). FR-004의 선택형 명확화 질문과 달리 자유 서술형 보정이라는 점에서 상호 보완적이다.
- **FR-005**: Proposal 상태 기계는 `DRAFT → SUBMITTED → IMPLEMENTING → TESTING → PENDING_ACCEPTANCE → ACCEPTED / DESTROYED` 흐름을 따르며, Dual Merge 실패 시 `MERGE_FAILED`(재시도 가능)를 가진다. "다시 구현하기"는 IMPLEMENTING/TESTING/PENDING_ACCEPTANCE/MERGE_FAILED에서 SUBMITTED로 되돌린 뒤 IMPLEMENTING으로 재진입하는 루프를 허용한다(ACCEPTED·DESTROYED 제외). 각 전이 시 이력(상태·시각·처리자)이 누적 저장되어야 한다.
- **FR-006**: "구현 시작" 시 Git Worktree의 원천은 **robo-architect(설계 도구 자신)가 아니라 Claude Code 탭에 설정된 대상 프로젝트 경로(`projectRoot`)**여야 한다. 시스템은 그 대상 프로젝트의 Git repo에서 `proposal/<PRO-NNN>` 브랜치와 `<projectRoot>/.sandbox/proposal/<PRO-NNN>` Worktree를 생성하고, `projectRoot`를 Proposal에 저장하여 이후 머지·정리에 사용한다. 대상 경로가 미설정이면 명확한 오류를 반환한다. **대상 경로가 아직 Git 저장소가 아니면(로컬 repo 없음) 즉시 실패하지 않고, 사용자에게 다이얼로그로 "Git 저장소를 생성(git init)하고 계속할까요?"를 묻는다. 사용자가 동의하면 백엔드가 대상 경로에 `git init` + 초기 커밋(`--allow-empty`)을 수행한 뒤 Worktree 생성을 이어가고, 거부하면 Proposal 상태를 그대로 둔 채(SUBMITTED) 진행을 중단한다.** 이 흐름은 백엔드가 `409 NOT_A_GIT_REPO`(머신 판독 코드 + projectRoot)를 반환하고 프런트엔드가 동의 시 `initGit=true`로 1회 재요청하는 방식으로 구현한다.
- **FR-007**: 구현은 헤드리스 배치가 아니라 **Code 탭의 살아있는 Claude Code 셀(PTY 터미널)을 재사용**하여 인터랙티브하게 실행되어야 한다. "구현하기"는 Worktree 생성·tasks.md 기록까지만 **준비**하고 **자동으로 Code 탭으로 이동하지 않는다.** 안내 멘트("구현은 Code 탭의 Claude Code 셀에서 진행됩니다…")에 연결된 **"Claude Code 셀로 이동" 버튼을 눌렀을 때만** 그 셀로 진입하며, 최초 진입 시 셀에 **`/robo-implement <PRO-NNN>` 명령을 자동 입력**해 구현을 시작한다(robo-implement 스킬의 PRO 모드가 워크트리의 `PROPOSAL_<id>.md`·`PROPOSAL_<id>_TASKS.md`를 읽어 미체크 작업을 구현·체크). 사용자는 같은 셀에서 진행 로그를 보고, 중지(Ctrl+C/Esc)하거나 중간 피드백을 입력할 수 있어야 한다. 셀은 `<KeepAlive>`로 탭 전환에도 유지되며, 이미 세션이 있으면 "Claude Code 셀로 이동"은 명령 주입 없이 그 셀로만 전환한다(이어보기).
- **FR-007a**: IMPLEMENTING → TESTING 전환은 사용자 트리거다(헤드리스 구현 완료 신호 없음). primary 버튼 라벨은 tasks.md 진행에 따라 "미구현부분 완료하기"(부분 완료) 또는 "구현 완료 → 검증"(전부 완료)로 표시되며(FR-007d), 전환 직후 검증은 '검증' 탭에서 실행된다(FR-007g).
- **FR-007e**: 구현 작업 목록은 **Claude Code 셀이 아니라 proposal 쪽에서 미리** 분해해야 한다(인텐트 분해와 동일하게 헤드리스 서브프로세스 = `robo-proposal-tasks` 스킬을 SSE로 호출). SUBMITTED 상태에서 사용자가 "작업 목록 생성"을 누르면, 시스템은 Strategic·Tactical Diff로부터 speckit 형식 작업 목록(`{id, phase, text, files, parallel}`)을 분해해 분석 서술(narration)을 실시간 스트리밍하고 결과를 Proposal(`tasksJson`)에 저장한다. **작업 목록이 생성된 뒤에야 "구현하기" 버튼이 노출된다.** 또한 "구현하기"는 클릭 시 작업 목록 존재 여부를 확인해, **있으면 곧바로 Code 탭으로 이동**하고 **없으면(레거시/미생성) 작업 분해를 먼저 수행해 결과를 보여준 뒤** 진행한다(작업 목록이 만들어지기 전에는 Code 탭으로 넘어가지 않는다). "구현하기" 시 implement_runner는 저장된 작업 목록을 speckit tasks 마크다운으로 렌더해 워크트리에 `PROPOSAL_<id>_TASKS.md`로 **미리 기록**하고, 셀에는 "이미 있는 체크리스트를 따라 구현하며 완료 항목을 `- [x]`로 바꾸고 단계마다 commit" 하도록 지시한다(작업 목록이 없으면 셸이 직접 생성하는 폴백). 작업 목록이 이미 생성된 상태에서는 **"작업 목록 재생성"** 버튼으로 기존 목록을 버리고(확인 후) Diff로부터 다시 분해할 수 있다(구현 시작 전 검토·보정용).
- **FR-007f**: 구현 진행 상황을 **워크트리의 tasks 체크리스트(`PROPOSAL_<id>_TASKS.md`, speckit tasks 형식)** 모니터링으로 표시해야 한다. 백엔드는 `GET /api/proposals/{id}/progress`로 이 파일을 파싱해 `{total, done, percent, sections[], items[], updatedAt, secondsSinceUpdate}`를 반환하고, 구현 탭은 구현 시작 이후 상태에서 이를 주기 폴링(~4초)하여 진행률 바·Phase별 체크리스트·상태 배지(진행 중 / 완료 / **정체(임계 90초 미갱신 = 멈춤 가능, 스피너 숨김)** / 준비 중)를 표시한다. **Proposals 목록**에서도 활성(IMPLEMENTING/TESTING) 항목의 진행을 가볍게 폴링(~8초)해 항목별로 **진행 중(스피너) / 정체(스피너 없음) / 완료**를 표시한다. `PROPOSAL_*.md`는 대상 repo의 `.git/info/exclude`에 등록되어 머지·`git status`를 오염시키지 않는다. (헤드리스 완료 신호가 없는 인터랙티브 셀 구현에서 파일 기반 추적이 진행 상태 신호다. v1 범위에서 Code 탭 셀을 구현 탭에 임베드해 동시 표시하는 것은 제외 — 진행 표시는 tasks.md 모니터링으로 한정.)
- **FR-007b**: 여러 Proposal이 동시에 각자의 worktree에서 독립적인 Claude Code 셀 세션으로 구현될 수 있어야 한다. Code 탭은 worktree별 세션을 **동시에 상주**시키고(프로세스·UI 중복 없음) **상단 세션 탭 바**로 전환할 수 있어야 한다(main 프로젝트 세션 + proposal 세션들 + 수동 셸). 좌측 파일 트리/에디터는 활성 세션의 worktree를 따라간다.
- **FR-007c**: Claude Code 셀 세션은 단일 WebSocket 수명과 분리되어, 브라우저 새로고침·탭 전환·일시적 연결 끊김에도 백엔드 PTY가 살아남아야 한다. 같은 `session_id`로 재연결하면 스크롤백이 재생(replay)되며 동일 claude 세션에 재어태치된다. 세션을 명시적으로 닫을(×) 때만 PTY가 종료되며, 오래 분리된 세션은 TTL로 회수된다.
- **FR-007d**: 샌드박스 구현 탭의 **기본(primary) 버튼은 워크트리 `PROPOSAL_<id>_TASKS.md`의 진행 상태로 결정**된다(ACCEPTED·DESTROYED 제외):
  - **tasks.md 없음(=구현 시작 전)** → **"구현하기"**. 단, SUBMITTED에서 작업 목록(`tasksJson`)이 아직 없으면 먼저 "작업 목록 생성"만 노출(게이팅).
  - **일부만 체크(부분 완료, IMPLEMENTING)** → **"미구현부분 완료하기"** (IMPLEMENTING → TESTING).
  - **전부 체크(완료, IMPLEMENTING)** → **"구현 완료 → 검증"** (IMPLEMENTING → TESTING). 두 경우 모두 검증(자동 테스트) 단계로 진행하며, **"다시 구현하기"는 보조 버튼**으로 함께 제공된다.
  재구현은 SUBMITTED 첫 구현뿐 아니라 IMPLEMENTING/TESTING/PENDING_ACCEPTANCE/MERGE_FAILED에서도 가능하다. (버튼 상태 판단을 위해 구현 시작 이후에는 모든 상태에서 진행률을 폴링한다.)
- **FR-007g**: 구현 완료(IMPLEMENTING→TESTING) 시 **검증 단계**가 활성화되어야 한다. 검증(`robo-proposal-test`)은 두 축으로 수행한다: **① 인수 조건(GWT)** — UserStory의 Given-When-Then을 LLM-as-judge로 샌드박스 구현에 대해 판정(`category: acceptance`). **② 구조 검증** — Proposal의 Tactical Diff(Aggregate/Command/Event/VO 의도된 변경)가 실제 구현체에 반영됐는지 **robo-sync 추출기**(`ts_extract.mjs`/`python_extract.py`)로 코드 구조를 추출해 비교(`category: structural`, 실제 스펙 ↔ 구현체 일치 검증). 결과 item은 `category`를 가지며 **"검증"** 탭에서 "인수조건"/"구조" 배지로 구분 표시된다. 검증은 헤드리스 일회 실행이 아니라 **runner(스트리밍)** 로 실행되어(작업 분해·인텐트 분해와 동일 방식, `GET /stream/{id}/validate` SSE), robo-sync 추출기·LLM-judge의 **실행 로그(narration·tool 사용)가 실시간**으로 '검증' 탭에 표시된다. 검증은 **검증 탭이 열릴 때(또는 '샌드박스 구현' 탭의 "검증하기")** 트리거되며, **"중지"** 버튼으로 진행 중 언제든 멈출 수 있다(SSE 연결을 닫으면 서버의 claude 서브프로세스가 정리되고 상태는 TESTING으로 남아 재검증 가능 — 고아 서브프로세스 누수 방지). 스트림은 탭을 전환해도(컴포넌트 언마운트) store 싱글톤에서 유지되어 검증이 끊기지 않는다. **"재검증"** 버튼으로 언제든 다시 실행할 수 있다(재검증 시 PENDING_ACCEPTANCE/MERGE_FAILED→TESTING으로 되돌리고 이전 결과를 비운 뒤 재실행). 검증 완료 시 TESTING→PENDING_ACCEPTANCE로 전환된다. (비스트리밍 폴백 `POST /{id}/validate` + `test-results` 폴링도 유지.) (단계 이름은 "테스트"가 아니라 **"검증"** — robo-sync 싱크 맞춤 검증.) **구현 완료(TESTING) 이후에는 검증 통과·완료 여부와 무관하게 "검증"·"Accept / Destroy" 탭이 모두 노출된다.** '샌드박스 구현' 탭에도 구현 완료 시 **"검증하기"** 버튼이 다시 표시되어(다시 구현하기와 별개), 검증을 언제든 추가로 재실행할 수 있다. "구현 완료 → 검증"을 누르면 자동으로 검증 탭으로 전환된다.
- **FR-008**: 구현 완료 후 **검증**은 두 축으로 실행된다(상세 FR-007g): ① 그래프 DB의 UserStory GWT 인수 조건 LLM-judge, ② robo-sync 추출기를 통한 구조 검증(Tactical Diff ↔ 구현체). (이전의 "자동 테스트"는 "검증"으로 일원화.)
- **FR-009**: PO가 Accept를 확정하면 코드 머지(샌드박스 브랜치 → 메인)와 그래프 DB 업데이트(Strategic·Tactical Diff 반영)가 단일 트랜잭션(All-or-Nothing)으로 처리되어야 한다.
- **FR-009b**: Accept/Destroy는 **검증 완료(PENDING_ACCEPTANCE)** 뿐 아니라 **구현 완료(TESTING)** 상태에서도 가능해야 한다. 즉 검증을 통과·완료하지 않았더라도 구현이 완료되었으면 PO가 Accept/Destroy 탭으로 이동해 결정을 내릴 수 있다(탭에 "검증 미완료" 안내 표시). 백엔드 Accept는 `TESTING` 또는 `PENDING_ACCEPTANCE`에서 허용한다. 검증 실패 항목이 있는 경우의 강제 Accept 게이팅(FR-005식 "실패 항목 인지")은 그대로 적용된다.
- **FR-010**: Dual Merge 실패 시 이미 완료된 쪽을 롤백하고 Proposal을 MERGE_FAILED 상태로 전환하며 재시도 옵션을 제공해야 한다.
- **FR-011**: PO가 Destroy를 선택하면 Proposal 상태가 DESTROYED로 전환되고 대상 프로젝트(`projectRoot`)의 Git Worktree·브랜치가 자동으로 정리되어야 한다.
- **FR-012**: DESTROYED 포함 모든 Proposal의 Diff 이력이 영구 보관되어 이력 조회 전용으로 접근 가능해야 한다.
- **FR-013**: 동일한 그래프 노드를 수정하는 두 Proposal이 동시에 IMPLEMENTING 상태로 진입하려 할 때 충돌 경고를 표시해야 한다.
- **FR-014**: Accept는 **PO 역할**을 가진 사용자만 수행할 수 있다. 인증·역할 시스템이 도입되기 전 기본 정책으로 **모든 사용자에게 PO 역할을 부여**하며, 이 경우 **자기 승인이 허용된다**(작성자 본인도 Accept 가능). 추후 실제 역할이 주입되면 비-PO는 `403`으로 거부된다. (038의 자기 승인 방지 정책은 기본-PO 정책으로 대체)
- **FR-015**: 038의 `RequirementChange(CHG-NNN)` 노드는 `Proposal(PRO-NNN)` 노드로 마이그레이션 없이 초기화한다.

### Key Entities

- **Proposal**: Proposal 생애주기 단위. 속성: `id(PRO-NNN)`, `title`, `originalPrompt`, `author`, `createdAt`, `status`, `statusHistory[]`, `clarificationLog[]`, `strategicDiff(JSON)`, `tacticalDiff(JSON)`, `impactMap(JSON)`, `tasksJson(작업 목록 JSON)`, `testResults(검증 결과 JSON)`, 그리고 샌드박스 속성(`projectRoot`, `sandboxBranch`, `sandboxWorktreePath`, `sandboxStatus`).
- **StrategicDiff**: Proposal에 포함되는 전략적 변경안. Epic·Feature·UserStory 수준의 추가/수정 명세. Proposal 노드에 JSON 속성으로 저장.
- **TacticalDiff**: Proposal에 포함되는 전술적 변경안. 038의 `SemanticDiff`(DiffOp 목록) 구조 재사용. Proposal → Target 노드 EFFECT 관계에 저장.
- **Tasks(작업 목록)**: 구현 작업 분해 결과. proposal 쪽에서 `robo-proposal-tasks` 스킬로 미리 분해(`{id, phase, text, files, parallel}[]`)해 `tasksJson`에 저장하고, 구현 시작 시 speckit tasks 마크다운으로 렌더해 워크트리의 `PROPOSAL_<id>_TASKS.md`로 기록한다(셀이 `- [x]` 체크 → 진행 추적의 원천).
- **ImpactMap**: 그래프 탐색 결과. 영향 노드 목록(`nodeId`, `nodeLabel`, `conflictLevel`). Proposal 노드에 JSON 속성으로 저장.
- **TestRunResult(검증 결과)**: 검증(robo-proposal-test) 산출물. `{totalScenarios, passed, failed, skipped, items[]}`. 각 item은 `category`("acceptance" GWT 인수 조건 | "structural" robo-sync 구조 검증), `result`(PASS|FAIL|SKIPPED), `reason`을 가진다. `testResults`에 JSON으로 저장.
- **Sandbox**: Git 격리 환경 메타데이터. 속성: `projectRoot`(대상 프로젝트 Git repo 경로 = Claude Code 탭 경로), `branchName`, `worktreePath`(`<projectRoot>/.sandbox/proposal/<PRO-NNN>`), `createdAt`, `status`. Proposal 노드의 속성(`projectRoot`, `sandboxBranch`, `sandboxWorktreePath`, `sandboxStatus`)으로 저장. 대상 경로가 Git repo가 아니면 사용자 동의 후 `git init`(FR-006). 오염된 경로(다른 Proposal의 worktree 등)는 de-nest하여 중첩 생성을 방지한다.
- **TerminalSession**: Claude Code 셀(PTY) 세션. Neo4j가 아니라 런타임/클라이언트 상태다. 프런트엔드는 `{id, label, workdir, kind('main'|'proposal'|'shell'), proposalId, epoch}`를 localStorage에 보관한다. proposal 세션은 **경로가 아니라 proposalId로 키잉**(`id = 'proposal:<PRO-NNN>'`)되어 worktree 경로가 바뀌어도 중복 탭이 생기지 않는다(같은 proposalId의 중복 세션은 더 얕은 경로로 dedupe). 백엔드는 `session_id = <id>#<epoch>`를 키로 PTY를 보관(스크롤백 링버퍼·attach된 WebSocket·detach 시각)하며, 같은 `session_id` 재연결 시 재어태치(replay)된다.
- **EFFECT**: Proposal → UserStory·Feature·Aggregate 관계. 038의 EFFECT 관계 재사용. 속성: `reason`, `impactLevel`, `diff(SemanticDiff JSON)`.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 자연어 입력 후 인텐트 분해(Strategic·Tactical Diff 초안 생성)까지 60초 이내에 완료된다.
- **SC-002**: Impact Map 탐색 결과가 30초 이내에 SSE를 통해 표시된다(그래프 노드 500개 기준).
- **SC-003**: "구현 시작"부터 Worktree 생성 + Code 탭 셀이 그 Worktree에서 구현을 시작하기까지 10초 이내에 처리된다.
- **SC-004**: Proposals 탭에서 Proposal 목록 로딩이 2초 이내에 완료된다(Proposal 50건 기준).
- **SC-005**: Accept 후 Dual Merge(코드 머지 + 그래프 DB 업데이트)가 30초 이내에 완료된다.
- **SC-006**: 메인 브랜치를 건드리지 않고 동시에 실험 가능한 Proposal 수가 제한 없다(Worktree 디스크 용량 내).
- **SC-007**: Accept 완료 후 그래프 DB의 해당 노드 속성이 Proposal의 After 값과 100% 일치한다(Spec Drift 0%).
- **SC-008**: Destroy 처리된 Proposal의 Diff 이력이 영구 보관되어 언제든 조회 가능하다(0건 소실).
- **SC-009**: 여러 Proposal이 각자 worktree에서 동시에 구현될 때, Code 탭의 세션 탭으로 프로세스·UI 중복 없이 전환할 수 있다(동시 세션 상한 내).
- **SC-010**: 구현 세션 진행 중 브라우저를 새로고침해도 같은 `session_id`로 재어태치되어 스크롤백이 재생되고 claude 세션이 유지된다(세션 손실 0건, ×로 닫은 경우 제외).

---

## Assumptions

- 038 브랜치의 `RequirementChange` 관련 Neo4j 노드·EFFECT 관계·SemanticDiff 구조는 그대로 재사용하되, Proposal ID 체계(`PRO-NNN`)로 전환한다.
- Git Worktree 생성·삭제는 서버 사이드(Python 백엔드)에서 `git worktree add/remove` 명령으로 처리하되, 명령의 `cwd`와 원천 repo는 robo-architect가 아니라 Claude Code 탭의 대상 프로젝트(`projectRoot`)이다. `projectRoot`는 프런트엔드가 `localStorage['claude_code_workspace_root']`(Claude Code 탭 경로)에서 읽어 `/implement` 요청에 전달한다. 대상 경로가 아직 Git 저장소가 아니면 백엔드는 `409 NOT_A_GIT_REPO`를 반환하고, 프런트엔드가 사용자 동의를 받아 `initGit=true`로 재요청하면 백엔드가 `git init` + 초기 커밋(`--allow-empty`, fallback git identity 주입) 후 Worktree를 생성한다. `git worktree add ... HEAD`는 HEAD가 커밋을 가리켜야 하므로 초기 커밋이 필수다.
- 검증(`robo-proposal-test`)은 두 축이다: ① UserStory GWT 인수 조건 LLM-judge, ② Tactical Diff ↔ 구현체 **구조 검증**(robo-sync 추출기 `ts_extract.mjs`/`python_extract.py`로 샌드박스 코드 구조를 추출해 의도된 변경과 비교). 별도 테스트 코드 파일은 작성하지 않는다. 검증은 **'검증' 탭이 열릴 때 `POST /{id}/validate`로 트리거**되며(fire-and-forget 유실 방지), 백그라운드 실행 + 프런트엔드 `test-results` 폴링으로 결과를 받는다. "재검증" 버튼으로 재실행 가능.
- Dual Merge의 원자성(Atomicity)은 코드 머지 성공 여부를 확인한 뒤 그래프 DB를 업데이트하고, 그래프 DB 실패 시 Git 커밋을 되돌리는 보상 트랜잭션(compensating transaction) 방식으로 구현한다.
- 구현 실행은 헤드리스 `skill_runner.py`/SSE가 아니라 029의 Claude Code 셀(PTY 터미널, `/api/claude-code/terminal` + `App.vue`의 `openClaudeCode`/`<KeepAlive>`) 인프라를 재사용한다. 백엔드는 Worktree 생성·컨텍스트 파일(`PROPOSAL_<id>.md`)·작업 목록(`PROPOSAL_<id>_TASKS.md`) 작성 후 셀에 보낼 **구현 시작 명령 `/robo-implement <PRO-NNN>`**(robo-implement 스킬의 **PRO 모드**: `PROPOSAL_<id>.md`+`PROPOSAL_<id>_TASKS.md`를 읽어 미체크 작업을 구현·체크)을 반환한다. "구현하기"는 **자동으로 Code 탭으로 이동하지 않고**, "Claude Code 셀로 이동" 버튼을 눌렀을 때 그 명령을 셀에 주입한다(최초 진입 시 1회). robo-implement PRO 모드는 대상 프로젝트의 `.claude/skills/robo-implement`에 있어야 하며(없으면 추가·커밋 → worktree가 HEAD 체크아웃으로 상속), 인텐트 분해·작업 분해(`robo-proposal-tasks`)·검증(`robo-proposal-test`)은 기존 SSE/skill_runner로 수행한다.
- Claude Code 셀의 PTY는 단일 WebSocket 수명과 분리된 **세션 레지스트리**(백엔드 메모리)로 관리한다. 세션은 `session_id`(worktree 경로 등 + epoch)로 식별되고, 출력 스크롤백 링버퍼(기본 256KB)·동시 세션 상한(기본 16)·분리 TTL(기본 30분)을 가진다. ws 끊김은 detach(유지), 명시적 종료(`{type:'close'}` 메시지 또는 `DELETE /api/claude-code/terminal/session`)만 PTY를 죽인다. 프런트엔드는 세션 목록(id/label/workdir/kind/epoch)을 `localStorage`에 보관해 새로고침 시 복원·재어태치한다.
- 인텐트 분해(Strategic/Tactical 분류)는 LangChain 기반 AI 에이전트가 수행하며, 그래프 DB의 기존 노드 구조를 컨텍스트로 주입한다.
- 생성자/Accept 처리자 정보는 현재 세션 actor에서 가져온다. Accept는 PO 역할이 필요하나, 역할 미들웨어가 역할을 싣지 않으면 **기본 PO**로 간주한다(기본 PO 정책 → 자기 자신이 작성한 Proposal도 Accept 가능; FR-014).
- 038의 `ChangeStatus` 열거형은 Proposal 전용 `ProposalStatus` 열거형으로 교체하며, 기존 CHG 노드는 초기화한다.
- PRD·DDD 스펙 마크다운 자동 갱신(Dual Merge 후속 처리)은 v1에서는 `specs/` 디렉토리의 특정 파일을 업데이트하는 수준으로 구현한다.
