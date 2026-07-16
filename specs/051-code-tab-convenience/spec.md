# Feature Specification: Code 탭 무인 실행 편의성 (Code Tab Convenience & Unattended Runs)

**Feature Branch**: `051-code-tab-convenience` (미생성 — 사용자 WIP 보존, 착수 승인 시 분기)

**Created**: 2026-07-15

**Status**: Draft

**Input**: 사용자 지시 — "생성 엔진(프론트 설계·생성 품질·실행/자가수정 루프·스텁→풀코드·완주 재구동)은 건들지 말고, **Code 탭까지 가서 무인으로 돌리는 편의성**만 고쳐라." + Playwright/직접 프로브로 라이브 확정된 결함들.

## 배경 (Why)

Code 탭까지 도달해 구현을 무인으로 돌리는 **경험 자체가 막혀** 있다. 라이브로 확정된 것:

- **오토모드가 실제로 안 됨**: 터미널이 `--permission-mode` 없이 `claude`를 띄워([pty_backend.py:52-57](project/robo-architect/api/features/claude_code/pty_backend.py#L52-L57)) Edit/Write/Bash마다 승인 프롬프트 → 자는 동안 스톨. (사용자 최대 통증)
- **세션 매니저 500**: `GET /api/claude-code/terminal/sessions` → HTTP 500 `AttributeError`([router.py:876](project/robo-architect/api/features/claude_code/router.py#L876) `sess.pid`, 실제는 `sess.proc.pid`) → 상주 claude 세션을 정리할 수 없음.
- **Code 탭 강제 모달**: 프로젝트 루트 없으면 "프로젝트 홈 생성" 마법사가 터미널을 덮고 ×로만 닫힘 → 진입 흐름 끊김.
- **폴더피커 드라이브 감옥**: 인앱 피커가 `~`에서 시작, 드라이브 루트의 parent가 자기 자신([router.py browse-directory](project/robo-architect/api/features/claude_code/router.py#L63-L95)) → D: 도달 불가.
- **Ctrl+C 미작동(Windows)**: ConPTY에 raw `\x03`만 기록([pty_backend.py:290-291](project/robo-architect/api/features/claude_code/pty_backend.py#L290-L291)), 커스텀 키핸들러 없음.
- **오버레이 우발적 닫힘**: 폴더피커/세션매니저 `@click.self`([ClaudeCodeTerminal.vue:468](project/robo-architect/frontend/src/features/claudeCode/ui/ClaudeCodeTerminal.vue#L468)) → 바깥 클릭/커서 이탈로 닫힘.
- **로그 불편**: 스트리밍 로그가 원시 `[tool] Read D:\…경로`로 노출, 자동 스크롤은 `ProposalCreate`에만.

## 범위 경계 (Scope)

**포함 = Code 탭까지의 편의성 + 무인 실행.** 아래 4묶음.

**제외(이번 스펙 아님, 명시적):**

- 생성 엔진: 프론트엔드 생성 설계·품질, 실행/빌드/자가수정 루프, 스텁→풀코드, 완주 자동 재구동 루프.
- 다른 탭(Proposals/Stories/Process/Design/Data)의 표면 재설계(→ 050 및 후속).
- Legacy(Analyzer) 영역.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 무인 실행 (상시 오토모드) (Priority: P1)

사용자는 구현을 시작하고 자리를 비운다. Claude Code 셀이 파일 편집·명령 실행을 **승인 없이** 진행해, 돌아왔을 때 작업이 멈춰 있지 않고 진척돼 있다.

**Why this priority**: 최대 통증. 승인 스톨이 무인 완주를 원천 차단한다.

**Independent Test**: 오토모드로 셀을 띄우고 파일 편집을 유발하는 작업을 시켰을 때 권한 프롬프트 없이 진행되는지 확인.

**Acceptance Scenarios**:

1. **Given** 오토모드가 기본 켜진 상태, **When** 셀에서 Edit/Write/Bash가 필요한 작업이 실행되면, **Then** 승인 프롬프트 없이 자동 진행된다.
2. **Given** 사용자가 화면을 떠나 있어도, **When** 구현이 진행되면, **Then** 승인 대기로 멈추지 않는다.
3. **Given** 오토모드 상태를 사용자가 인지해야 하므로, **When** 셀을 보면, **Then** "오토 모드"임이 헤더 등에서 명확히 보인다.

---

### User Story 2 - 매끄러운 진입·경로 설정 (Priority: P1)

사용자는 프로젝트 폴더를 **한 번에** 고르고(원하는 드라이브 어디든, D: 포함) 곧바로 Code 탭에서 작업을 시작한다. 정체불명 모달을 ×로 닫는 일이 없다.

**Why this priority**: 진입 흐름 끊김(#4)이 "완주 전에 지침"을 만든다.

**Independent Test**: 프로젝트 루트 미설정 상태로 Code 탭에 들어가, 네이티브 폴더 선택으로 D: 경로를 고르고 터미널이 그 경로에서 뜨는지 확인. 강제 모달이 뜨지 않는지 확인.

**Acceptance Scenarios**:

1. **Given** 프로젝트 루트 미설정, **When** Code 탭에 진입하면, **Then** 강제 "프로젝트 홈 생성" 모달이 뜨지 않고, 경로를 설정하라는 명확한 인라인 안내가 보인다.
2. **Given** 경로 선택 UI, **When** 사용자가 폴더를 고르면, **Then** OS 네이티브 다이얼로그로 **임의 드라이브(D: 포함)** 를 자유롭게 탐색·선택할 수 있다.
3. **Given** 경로가 선택되면, **When** 확정하면, **Then** 터미널이 그 경로에서 시작된다(다른 탭·모달을 거치지 않음).

---

### User Story 3 - 신뢰할 수 있는 터미널 조작 (Priority: P2)

사용자는 실행 중인 작업을 **Ctrl+C로 중단**하고, 실수로 창을 닫지 않으며, 진행 로그를 **손 스크롤 없이** 읽는다.

**Why this priority**: 일상 조작의 불편이 반복 좌절을 만든다.

**Independent Test**: 실행 중 셀에서 Ctrl+C로 현재 작업이 인터럽트되는지(Windows 포함), 오버레이가 바깥클릭/커서이탈로 안 닫히는지, 로그가 자동으로 최신까지 내려가고 tool 활동이 사람이 읽는 형태인지 확인.

**Acceptance Scenarios**:

1. **Given** 셀에서 claude가 실행 중, **When** 사용자가 Ctrl+C를 누르면, **Then** 현재 작업이 인터럽트된다(Windows ConPTY 포함).
2. **Given** 폴더피커/세션매니저 등 오버레이가 열림, **When** 마우스가 바깥으로 나가거나 바깥을 클릭하면, **Then** 닫히지 않고 ×/취소/Esc로만 닫힌다.
3. **Given** 스트리밍 로그가 진행 중, **When** 새 줄이 도착하면, **Then** 하단으로 자동 스크롤되고(사용자가 위로 올린 경우 존중), tool 활동은 원시 `[tool] …경로`가 아니라 아이콘+라벨+대상 형태로 표시된다.

---

### User Story 4 - 세션 정리 (Priority: P2)

사용자는 상주하는 claude 세션(좀비 포함)을 **목록으로 보고 정리**한다.

**Why this priority**: 세션이 쌓여도 정리 창이 500이라 손댈 수 없다(리소스 누적).

**Independent Test**: ⚙ 세션을 열어 목록이 오류 없이 뜨고, 한 세션을 종료하면 실제로 그 프로세스가 사라지는지 확인.

**Acceptance Scenarios**:

1. **Given** 백엔드에 살아있는 세션이 있음, **When** 세션 매니저를 열면, **Then** 200으로 목록(PID·경로·분리시간)이 표시된다(500 없음).
2. **Given** 세션 목록, **When** 한 세션을 "종료"하면, **Then** 해당 claude 프로세스가 종료되고 목록에서 사라진다.
3. **Given** 분리된 세션들, **When** "분리된 세션 정리"를 누르면, **Then** 화면에 붙지 않은 세션만 정리된다(붙어있는 셀은 보존).

### Edge Cases

- 오토모드에서도 사용자가 원할 때 **수동 개입(입력·중지)** 은 여전히 가능해야 한다(무인 ≠ 조작 불가).
- 네이티브 다이얼로그가 없는 환경(순수 웹 배포)에서는 경로 입력 대체 수단(경로 직접 입력/드라이브 목록)이 있어야 한다.
- Ctrl+C가 xterm의 "선택 영역 복사"와 충돌하지 않아야 한다(선택 없을 때 인터럽트, 선택 있을 때의 동작은 명시적으로 정의).
- 세션 종료가 화면에 붙어있는 활성 셀을 실수로 죽이지 않아야 한다.
- 존재하지 않는/권한 없는 경로 선택 시 명확한 오류(조용한 폴백 금지 — 원칙 IV).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 시스템은 Code 탭 터미널을 **기본으로 오토(무프롬프트) 권한 모드**로 실행해야 한다(사용자 결정: 상시 오토모드). e2e 전용 URL 경로가 아니라 정식 UI 배선으로 적용한다.
- **FR-002**: 셀 헤더 등에서 현재 **오토 모드임을 명시**해야 한다.
- **FR-003**: 사용자는 프로젝트 루트를 **OS 네이티브 폴더 선택**으로 지정할 수 있어야 하며, **임의 드라이브(D: 포함)** 를 탐색·선택할 수 있어야 한다.
- **FR-004**: Code 탭 진입 시 **강제 "프로젝트 홈 생성" 모달을 띄우지 않는다.** 프로젝트 준비는 사용자가 필요할 때 선택적으로 여는 진입점으로 제공한다.
- **FR-005**: 터미널에서 **Ctrl+C가 실행 중 프로세스를 인터럽트**해야 한다(Windows ConPTY 포함). xterm 선택-복사와의 충돌은 명시적으로 처리한다.
- **FR-006**: Code 탭의 오버레이(폴더피커·세션매니저 등)는 **× / 취소 / Esc로만 닫히며**, 마우스 이탈·우발적 바깥 클릭으로 닫히지 않아야 한다.
- **FR-007**: 스트리밍 로그는 **하단 자동 스크롤**(사용자 상단 스크롤 존중)과 **사람 친화 tool 표기**(아이콘+라벨+대상, 원시 `[tool] …경로` 미노출)를 제공해야 한다.
- **FR-008**: **세션 매니저 목록 API가 정상(200) 동작**해야 하며(현 `sess.pid` 500 수정), 세션 나열·개별 종료·분리 세션 일괄 정리가 동작해야 한다.
- **FR-009**: 오토모드에서도 **수동 입력·중지 개입**이 가능해야 한다.
- **FR-010**: 경로/세션 관련 실패는 **조용히 삼키지 않고** 사용자에게 명확히 표면화해야 한다(터미널 cwd 존재검증 실패의 침묵 폴백 포함, [router.py:964-969](project/robo-architect/api/features/claude_code/router.py#L964-L969)). *(원칙 IV)*
- **FR-011**: 위 변경은 **생성 엔진(구현 산출물 품질·프론트 생성·실행 루프)을 바꾸지 않는다.** 구현 명령·스킬·산출물 계약은 불변.

### Key Entities

- **PTY 세션**: 백엔드가 유지하는 살아있는 `claude` 프로세스(id·pid·cwd·attached·분리시간). 세션 매니저의 표시 단위.
- **권한 모드**: 셀 실행 시 `claude`에 전달되는 permission 정책(기본 = 오토).
- **워크스페이스 루트**: Code 탭·구현의 기준 프로젝트 경로.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 오토모드 기본 셀에서 무인 작업 시 **승인 프롬프트 = 0**.
- **SC-002**: 폴더 선택으로 **D: 등 임의 드라이브 경로 선택 가능**(현재 불가 → 가능).
- **SC-003**: Code 탭 진입 시 **강제 모달 = 0**.
- **SC-004**: 실행 중 셀에서 **Ctrl+C로 인터럽트 성공(Windows 포함)**.
- **SC-005**: 세션 매니저 목록 API **200**(현 500 → 정상), 세션 종료/정리 동작.
- **SC-006**: 오버레이의 마우스이탈·우발적 바깥클릭 닫힘 = **0**.
- **SC-007**: 스트리밍 로그 자동 스크롤 동작 + 원시 `[tool] …경로` 노출 = **0**.
- **SC-008**: 구현 산출물(생성 코드) 계약·동작 **불변**(엔진 무회귀).

## Assumptions

- "상시 오토모드"는 사용자가 선택했다. 위험 명령도 무확인 실행되나 구현은 격리 worktree라 범위가 제한된다. (필요 시 후속에 예외 목록/토글 추가 여지)
- 데스크톱(Electron) 환경을 1차 대상으로 한다(네이티브 다이얼로그). 순수 웹 배포는 경로 직접입력 대체 수단으로 커버.
- 생성 엔진·다른 탭 표면·Legacy는 범위 밖(위 제외 참조).
- 현재 main 작업 트리에 사용자 WIP(`ClaudeCodeTerminal.vue`·`skill_runner.py`·`workspace.api.js` 등)가 있으므로, 코드 착수 전 분기·WIP 처리를 사용자와 먼저 합의한다.
