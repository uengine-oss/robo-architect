# Implementation Plan: Code 탭 무인 실행 편의성 (051)

**Spec**: [spec.md](./spec.md) · **Created**: 2026-07-15 · **Status**: Draft

## 목표 흐름 vs 현재 흐름

현재: 경로 설정이 인앱 피커(드라이브 감옥)·강제 모달을 거치고, 셀은 승인 프롬프트로 스톨, Ctrl+C 무반응, 세션 정리창은 500. → 무인 완주 불가.

목표: 경로를 네이티브로 한 번에 → Code 탭 즉시 진입(강제 모달 없음) → **오토모드로 무인 실행** → Ctrl+C·×/Esc·자동스크롤로 매끄럽게 관찰 → 세션 매니저로 정리.

## Constitution Check

- **III 단일 진실**: 권한 모드 기본값은 한 곳에서 정의(분산 금지). 도메인/상태 색과 무관.
- **IV silent fail 금지**: 터미널 cwd 존재검증 실패의 침묵 폴백을 표면화(FR-010).
- I·II·V·VI·VII(LLM/스키마/전략분기/KV캐시/submit): **해당 없음** — LLM·스키마·Neo4j 라벨/관계 변경 0. 생성 엔진 불변(FR-011).
- 결과: PASS (신규 그래프 계약·LLM 0).

## WIP 조율 (사용자 미커밋 변경 보존)

동일 working tree에 사용자 WIP 존재(웹모드 연결 + skill_runner stdin). 051은 아래 **비겹침 영역/파일**만 수정:
- `ClaudeCodeTerminal.vue`: 사용자=`resolveBackendCoords`(L~90). 051=`getWsUrl`(권한모드)·`onData`/키핸들러(Ctrl+C)·폴더피커 오버레이(L~468)·헤더 배지. → 영역 분리, 보존.
- `skill_runner.py`·`workspace.api.js`·`vite.config.js`: 051 **미수정**.

## 항목별 설계 (US → 변경 → 파일 → 검증)

### US1 — 상시 오토모드 (P1)
- **원인**: `terminal_ws(permission_mode="")` → `build_claude_argv`가 무플래그. 프론트는 e2e URL로만 전달.
- **변경**:
  - 프론트 `getWsUrl`이 **기본 권한모드를 항상 전달**. 세션 종류로 분기 — proposal worktree 세션 = `bypassPermissions`(격리, 헤드리스와 동일 수준), main/shell 세션 = `acceptEdits`(사용자 실제 저장소라 파괴적 명령은 남겨두는 안전선). URL `?permission_mode=` 은 그대로 override 유지(테스트 호환).
  - 헤더에 "오토 모드"(+모드명) 배지 노출.
- **파일**: `ClaudeCodeTerminal.vue`(getWsUrl·template), 세션 kind 전달 위해 `ClaudeCodeWorkspace.vue` prop 1개. 백엔드(`pty_backend`·`router`)는 이미 지원 → 변경 최소.
- **검증**: proposal 셀에서 Edit/Bash 유발 작업 → 프롬프트 0. main 셀 = acceptEdits 동작. 배지 표시.
- **결정 필요**: main/shell도 완전 무프롬프트(bypass) 원하시면 그렇게. 기본안=worktree bypass / main acceptEdits.

### US2 — 네이티브 경로 + 강제 모달 제거 (P1)
- **원인**: 인앱 `browse-directory` 피커(드라이브 루트 parent==self) + Code 탭 진입 시 setup-project 마법사 강제 오픈.
- **변경**:
  - Electron: 워크디렉터리 버튼 → **네이티브 폴더 다이얼로그**(런처의 `desktop.projectRoot.choose` 재사용/동형 preload API). 웹: 인앱 피커에 **드라이브 목록/경로 직접입력** 추가(백엔드 browse-directory가 드라이브 루트에서 드라이브 열거 제공, parent==self 대신 드라이브 선택 반환).
  - 강제 모달: 진입 트리거를 찾아 **자동 오픈 제거** → 필요 시 여는 버튼/빈상태 인라인 안내로 대체.
- **파일**: `ClaudeCodeTerminal.vue`(피커), `api/features/claude_code/router.py`(browse-directory 드라이브 열거), 강제 모달 트리거 컴포넌트(구현 시 위치 확정 — setup-project/PRD 마법사), preload(Electron 다이얼로그 채널 필요 시).
- **검증**: 루트 미설정 진입 → 강제 모달 0 + 인라인 안내. D: 선택 → 터미널 그 경로에서 기동.

### US3 — Ctrl+C · 오버레이 닫힘 · 로그 (P2)
- **Ctrl+C(Windows)**: `_WindowsPtyProcess`가 raw `\x03`만 기록 → ConPTY 인터럽트 미전달. **pywinpty 인터럽트 경로**(`GenerateConsoleCtrlEvent`/pywinpty sendintr 확인) 추가. 프론트 `attachCustomKeyEventHandler`로 **선택 없을 때 Ctrl+C=\x03**(선택 있으면 복사 유지).
- **오버레이**: 폴더피커·세션매니저 `@click.self` 제거 + Esc 핸들러(×/취소/Esc만).
- **로그**: 스트리밍 로그 자동스크롤 + 사람친화 tool 표기는 **공용 StreamLog(050 디자인시스템)로 구현·재사용** — 이 항목은 050과 공유. Code 탭 xterm은 이미 스크롤됨.
- **파일**: `pty_backend.py`(Windows 인터럽트), `ClaudeCodeTerminal.vue`(키핸들러·피커 오버레이), `SessionManagerPopover.vue`(오버레이). StreamLog는 050.
- **검증**: 실행 중 Ctrl+C 인터럽트(Win). 바깥클릭/커서이탈로 안 닫힘. Esc로 닫힘.

### US4 — 세션 매니저 500 (P2)
- **원인**: `router.py:876` `sess.pid`(부재) — 실제 `sess.proc.pid`.
- **변경**: `sess.pid` → `sess.proc.pid` (`_PtySession`에 pid 프로퍼티 추가도 대안).
- **파일**: `api/features/claude_code/router.py`.
- **검증**: `GET /api/claude-code/terminal/sessions` → 200. ⚙세션 목록 표시·개별 종료·분리 정리 동작.

## 회귀 기준 (엔진·기존 시나리오 보존)

- 생성 산출물·구현 명령·스킬 계약 불변(FR-011). skill_runner 미변경.
- 기존: 세션 재어태치(새로고침), 멀티 세션 전환, 재구현(epoch), URL `permission_mode` override — 회귀 확인.
- 사용자 WIP(웹모드 연결·stdin) 동작 보존.

## 구현 순서 (독립 배포 가능 슬라이스)

1. **US4 세션-500**(한 줄, 백엔드) — 즉시 검증(curl 200). 가장 저위험.
2. **US1 오토모드** — 최대 가치. 실측(무인 진행) 검증.
3. **US3 오버레이 닫힘 + Ctrl+C**.
4. **US2 네이티브 경로 + 강제 모달 제거** — 트리거 위치 확정 필요, 범위 큼.

각 슬라이스는 Playwright/실물 + 회귀로 검증 후 다음으로.

## 미해결/확인

- US1 main/shell 권한 기본값(acceptEdits vs bypass) — 사용자 확인.
- 8501 백엔드가 `--reload`인지(내 백엔드 수정이 재시작 유발 여부) — 착수 시 확인, 사용자 사용 방해 최소화.
- 강제 "프로젝트 홈 생성" 모달의 정확한 트리거 컴포넌트 — 구현 착수 시 grep으로 확정.
