# Code 탭 — 통합 검증

> 진행 방식은 [changes.md](changes.md)·[stories.md](stories.md) 참고(스펙+코드 인벤토리 → store↔라우트 확정 → 라이브 검증 → 실데이터 교차검증 → 이슈 기록).

- **activeTab 값**: `Code`
- **패널 컴포넌트**: [`ClaudeCodeWorkspace.vue`](../../../frontend/src/features/claudeCode/ui/ClaudeCodeWorkspace.vue) (3-pane 오케스트레이터) → [`FileTreePane.vue`](../../../frontend/src/features/claudeCode/ui/FileTreePane.vue) · [`FileEditorPane.vue`](../../../frontend/src/features/claudeCode/ui/FileEditorPane.vue) · [`ClaudeCodeTerminal.vue`](../../../frontend/src/features/claudeCode/ui/ClaudeCodeTerminal.vue) (xterm + WS)
- **프런트 store**: 전용 store 없음 — 세션 상태는 컴포넌트 + `localStorage`(`claude_code_workspace_sessions`·`claude_code_workspace_root`)
- **백엔드**: [`api/features/claude_code/`](../../../api/features/claude_code/) — `router.py`(FS+터미널 WS+글로벌스킬), `pty_backend.py`(fork+openpty+execvpe), `workspace_fs.py`
- **MCP/스킬**: [`api/features/robo_spec/`](../../../api/features/robo_spec/) (mcp_server.py), `skills/robo-spec/`(`/robo-plan`·`/robo-tasks`·`/robo-implement`·`/robo-sync`)
- **관련 스펙**: 015(터미널), 021(3-pane IDE 워크스페이스), 029(mcp-spec-bridge + robo-spec-skills). 029 셀은 038/039(Changes/Proposals 구현)에서 재사용.
- **상태**: 🟡 초안 (인벤토리 작성, 라이브 검증 대기)

## 1. 탭의 의도/목표 (스펙 요약)

RoboArchitect 안에 **임베디드 Claude Code IDE**. (015) 백엔드가 PTY를 fork→대상 디렉터리로 chdir→`claude` CLI를 execvpe(없으면 `$SHELL`)로 띄우고, 브라우저 키 입력을 WebSocket JSON(`{type:input}`)으로 전달, PTY 출력을 ~50Hz 배치 raw 프레임으로 스트리밍, 리사이즈는 `{type:resize}`→TIOCSWINSZ+SIGWINCH. (021) 터미널-only가 아니라 **3-pane VS Code 레이아웃**(좌: 파일트리, 중: 에디터, 우: claude 터미널). (029) **MCP 서버 + 슬래시 커맨드**(`/robo-plan`·`/robo-tasks`·`/robo-implement`·`/robo-sync`)로 speckit 유사 흐름 — 스펙 ID를 인자로 PRD/구현스펙 동적 전달, 태스크 진척(체크박스) 동기화, 소스코드 점프, 개발자 수정 역반영(robo-sync). 멀티 세션(메인 + proposal worktree 독립 PTY), 새로고침 재어태치.

## 2. 보유 기능 목록 (코드 대조 초안)

| # | 기능 | 출처 | 핵심 컴포넌트 | 엔드포인트 |
|---|---|---|---|---|
| 1 | 워크디렉터리 선택(폴더 피커) | 015/021 | `ClaudeCodeWorkspace`/`FileTreePane` | `GET /api/claude-code/browse-directory` |
| 2 | 파일 트리 조회 | 021 | `FileTreePane` | `GET /tree?root=` |
| 3 | 파일 열기/편집/저장 | 021 | `FileEditorPane` | `GET /file`, `PUT /file` |
| 4 | 파일 삭제/이동 | 021 | `FileTreePane` | `DELETE /file`, `POST /move` |
| 5 | 파일시스템 변경 감지(라이브) | 021 | `FileTreePane` | `GET /fs-events`(SSE) |
| 6 | 프로젝트 셋업 | 029 | (PRD/프로젝트 홈) | `POST /setup-project` |
| 7 | 터미널 PTY 세션(claude CLI) | 015 | `ClaudeCodeTerminal`(xterm) | `WS /terminal` |
| 8 | 터미널 세션 종료 | 015 | `ClaudeCodeWorkspace` | `DELETE /terminal/session` |
| 9 | 멀티 세션(메인 + proposal worktree) | 039 | `ClaudeCodeWorkspace` | (WS 세션 id별) |
| 10 | 새로고침 재어태치(스크롤백 replay) | 029/039 | `ClaudeCodeWorkspace`/`ClaudeCodeTerminal` | WS 재연결 |
| 11 | 글로벌 스킬 설치/상태 | 029 | `ClaudeCodeWorkspace` | `GET /global-skills/status`, `POST /global-skills/install` |
| 12 | 슬래시 커맨드(/robo-plan·tasks·implement·sync) | 029 | (claude 셀 내부) | MCP `robo_spec/mcp_server.py` |
| 13 | 외부 호출 핸드오프(`openClaudeCode`) | 038/039 | `App.vue`→이벤트 | `claude-terminal-open` 이벤트 |

> store↔라우트 1:1, WS 프로토콜(input/resize/output), 세션 수명주기, MCP 슬래시 동작은 라이브에서 확정.

## 3. 검증 시나리오 (설계)

> 전제: 백엔드/프런트 기동. Code 탭 진입. (첫 진입 시 PRD 생성 모달이 뜰 수 있음 — `claude_code_workspace_root` 미설정 시.)

### S0. Code 탭 진입 + 워크디렉터리 선택 — ✅
- robo-architect를 root로 선택 → 3-pane 렌더. 폴더 펼침·하위 파일 표시 정상.

### S1. 파일 트리/에디터 — ✅ (rename/move만 미검증)
- 트리 조회·파일 열기 ✅. 임시파일(`_scratch_code_verify.txt`)로: 외부생성→**fs-events 라이브 등장** ✅, 편집→저장(`PUT /file`) 디스크 반영 ✅, 삭제(`DELETE /file`) 디스크 제거+GET 404 ✅. rename/move(`POST /move`)만 미검증(경미).

### S2. 터미널 PTY(claude CLI) — ✅
- robo-architect root에서 claude 터미널 부팅, 메시지 전송("say hi")→정상 응답("hi"). **C11 정정: 인터랙티브는 로컬 로그인 사용으로 무해**(헤드리스만 env키 영향).

### S3. 멀티 세션 + 재어태치 — 🟡 재어태치✅ / 멀티세션 보류
- 새로고침 후 세션 복원 + "Welcome back" + 이전 대화 스크롤백 replay + "연결됨" ✅. 멀티세션(메인+proposal)은 Proposals 검증 때. **관찰: 터미널 배너 cwd(`~/Desktop/non-git-test`)와 UI 폴더칩/트리(`/Users/seongwon/Desktop/robo`) 불일치 가능 → S6/I16에서 `pwd`로 확정.**

### S4. 슬래시 커맨드 / MCP — ✅ (end-to-end, D7 P0 수정)
- 글로벌 스킬 11개 verified ✅. **robo-spec 프로젝트 홈 생성**(`POST /setup-project` → `/Users/seongwon/projects/my-project`): `.claude/skills/`(robo-*+speckit 3종)·`.mcp.json`(robo-spec MCP `http://localhost:8000/mcp/`)·`robo-project.json`(projectId) 모두 정상 ✅. **MCP 엔드포인트 라이브**(POST initialize→200, main.py:342 마운트) ✅. **브릿지 실동작 검증완료** ✅: `/robo-plan`(인자 없음)→스킬이 MCP `list_design_elements` 호출→그래프의 자동납부 BC 4개(AccountVerification·AutoDebit·IdentityVerification·PaymentMethod, ID 일치) 반환→"BC 택1" 프롬프트. 제가 MCP 직접 호출로 교차검증. **단 `get_bc_design`이 빈 설계 반환하는 P0 버그 발견·수정(D7)** → 수정 후 cmd/evt/rm 정상. **실제 스킬 흐름 완주**(사용자): resolve_design_element→get_bc_design(1 agg/3 cmd/7 evt/3 rm)→set_bc_classification(core 영속, get_bc_design 재확인)→**plan.md 생성**(Clean Architecture, 설계 슬라이스 라이브)→register_implementation_files(14요소 impl-링크 시딩, full-tree 반영). 읽기+쓰기 MCP 도구 전부 동작, 그래프=단일진실(spec/data-model 미생성). caveat=D8.

### S5. 외부 핸드오프 — ⬜
- Changes/Proposals "구현 시작"→`openClaudeCode`→Code 탭 명령 주입. **(C6) 콜드스타트 시 명령 자동실행 안 됨** 확인.

### S6. 세션 수명주기 — ⬜
- proposal ACCEPTED/DESTROYED 후 worktree 삭제 시 **(I14) 죽은 세션 잔존**(tree 400 반복) 확인. **(I16) 폴더피커=활성세션** 동작.

## 4. 발견 이슈

| # | 심각도 | 증상 | 원인(추정) | 후속 |
|---|---|---|---|---|
| C11 | ✅ **정정(무해)** | ~~터미널 claude가 무효 ANTHROPIC_API_KEY 상속 → 인증 실패~~ → **라이브 검증 결과 정상**. 터미널 claude에 메시지 전송 시 정상 응답("hi"). [pty_backend.py:139](../../../api/features/claude_code/pty_backend.py#L139)가 키를 상속해도 **인터랙티브 claude는 로컬 claude.ai 로그인을 사용**하므로 무해. **헤드리스 `claude -p`만** 키를 우선 사용해 실패(C1/C2, headless 전용). | 비대칭 확정: 인터랙티브=로그인 / 헤드리스=env키. pty_backend 수정 불필요. S5 구현(인터랙티브)·외부핸드오프 인증 정상. |
| D1 | 🟡 **(수정)** | **에디터 헤더 긴 파일경로가 저장/삭제/새로고침 버튼을 가림**(터미널 pane 넓힐 때). 사용자 지적 | [FileEditorPane.vue](../../../frontend/src/features/claudeCode/ui/FileEditorPane.vue) `.editor-tab`이 `white-space:nowrap`인데 `min-width:0`·overflow·축소설정 없음 → 경로가 안 잘리고 `.editor-actions`(margin-left:auto)를 밀어냄. actions에 flex-shrink도 없음 | **수정함**: `.editor-tab` flex:1 1 auto+min-width:0+overflow:hidden, `.editor-tab-path` ellipsis, `.editor-actions` flex-shrink:0. 경로는 `…`로 잘리고 버튼 항상 유지. |
| (이월) C6 | 🟡 | 외부 핸드오프 명령 자동실행 안 됨(콜드스타트) | [ClaudeCodeWorkspace.vue:357](../../../frontend/src/features/claudeCode/ui/ClaudeCodeWorkspace.vue#L357) | S5 |
| C7/I16 | 🟢 **수정·검증완료** | **터미널 실제 cwd가 폴더 피커를 안 따라감 → 칩이 거짓말**. 폴더칩·트리=`/Users/seongwon/Desktop/robo`인데 터미널 `pwd`=`/Users/seongwon/Desktop/non-git-test`(옛 빈 폴더). 결과: 터미널 명령(`/robo-implement` 핸드오프 포함)이 **표시와 다른 옛 폴더에서 조용히 실행** = S5 구현이 빈 폴더에서 돈 원인. | ① [onTerminalWorkdirPicked(ClaudeCodeWorkspace.vue:543)](../../../frontend/src/features/claudeCode/ui/ClaudeCodeWorkspace.vue#L543)가 **`s.workdir`/라벨만 갱신, PTY 재생성 안 함**(칩·트리는 s.workdir 읽어 새 경로 표시) ② 백엔드 PTY 레지스트리(router.py:718+)가 `session_id`로 키잉돼 새로고침/재연결에도 **옛 cwd PTY에 reattach**(workdir 무시) ③ PTY가 셸 아닌 `claude` 직접 execvpe라 셸 `cd` 불가. | **수정함(확인 후 respawn)**: [onTerminalWorkdirPicked](../../../frontend/src/features/claudeCode/ui/ClaudeCodeWorkspace.vue#L543)가 폴더 변경 시 `window.confirm`("새 폴더로 다시 시작? 현재 세션 종료") → OK면 `closeTerminalSession(backendId)`로 기존 PTY kill + `epoch++` + workdir 갱신. 터미널 호스트 `:key`를 `id#epoch`로 바꿔 **epoch bump 시 ClaudeCodeTerminal remount → 새 cwd로 fresh PTY**. 취소 시 무변경(칩도 안 바뀜). |
| D2 | 🟠 **(UX 갭)** | **모델→PRD 프로젝트 생성(`PRDGeneratorModal`)의 영구 진입점 없음**. 사용자가 "모델 기반 PRD 생성 경로가 어디 갔지?" 질문. | 진입점이 [TopBar.vue:52](../../../frontend/src/app/layout/TopBar.vue#L52) **Code 탭 첫 클릭 + `claude_code_workspace_root` 미설정** 한 곳뿐. 프로젝트 홈이 한번 설정되면(폴더 피커 변경 포함) `hasProjectHome()=true`라 영구히 자동 스킵 → 모델로 **새 프로젝트를 다시 생성할 UI 버튼이 없음**. | **후속**: "모델로 새 프로젝트 생성"을 Code 탭/메뉴에 **명시 버튼**으로 노출(현재는 localStorage `claude_code_workspace_root` 비워야만 재노출). PRD 모달=모델→프로젝트홈(robo-spec/legacy)의 유일 경로라 발견성 중요. |
| D3 | 🟡 **(수정)** | **PRD 모달 출력모드 카드: ① 설명이 전문용어만 길고 의미 불명 ② Legacy 카피가 "Cursor"만 언급(실제론 Cursor/Claude 선택 가능) ③ 두 카드 높이 불균형**(설명 길이 차) (사용자 지적). | [PRDGeneratorModal.vue:388~410](../../../frontend/src/features/prdGeneration/ui/PRDGeneratorModal.vue#L388) radio-desc 잡고 카피 + `.radio-cards` grid에서 `.radio-card-content`가 내용 높이만큼만 커짐(height 미설정). | **수정함**: ① 굵은 한 줄 요약(robo-spec="그때그때 생성·항상 최신" / legacy="지금 파일로 추출·한 번에") + 간결 평행 본문 ② 하단 `.radio-note` 꼬리표("Claude Code 전용" / "Cursor / Claude Code 선택")로 대상 도구 명시 ③ `.radio-card{display:flex}`+`.radio-card-content{height:100%}`로 **높이 균등화**, note는 `margin-top:auto`로 하단 정렬 ④ **카드가 모달 절반 폭만 쓰던 문제**: 출력모드 섹션이 2열 `.form-grid`>`.form-group` 안에 들어가 1열(½폭)만 차지 → 래퍼 제거해 `.radio-cards`가 **전체 폭** 사용(카드 각 ½폭, 줄바꿈 자연스러움). |
| D4 | 🟠 **(UX 혼란)** | **PRD 모달 Step 3에서 footer "Done"이 아무것도 안 함**. 사용자가 "Done"을 눌렀더니 프로젝트 생성 없이 모달만 닫힘(또는 무반응) → 진짜 생성 버튼을 못 찾음. | Step 3(프로젝트 경로 폼)의 실제 액션은 **내용 안 `btn-claude` "Claude Code에서 열기"**([PRDGeneratorModal.vue:745](../../../frontend/src/features/prdGeneration/ui/PRDGeneratorModal.vue#L745) `setupAndOpenClaudeCode`→`POST /setup-project`)인데, **footer엔 `closeModal`만 하는 "Done"**([line 825](../../../frontend/src/features/prdGeneration/ui/PRDGeneratorModal.vue#L825))이 주버튼 자리에 있음 → 사용자는 footer 주버튼을 누르는 게 자연스러워 혼란. | **후속**: Step 3 footer를 실제 액션("프로젝트 생성")으로 바꾸거나, in-content 버튼만 남기고 footer Done 제거. (수정 보류 — 사용자 생성 진행 우선) |
| D5 | 🟢 **(수정)** | **robo-spec 프로젝트 생성 후 "이제 뭘 하나" 안내 0**. 사용자: "/robo-plan으로 시작하는 건 맞는데 일반 사용자는 모를 것". | ① [openInClaudeCode](../../../frontend/src/features/prdGeneration/ui/PRDGeneratorModal.vue#L298)가 **명령 없이** 터미널을 열어 빈 프롬프트만 보임 ② 모달 next-steps([line 757](../../../frontend/src/features/prdGeneration/ui/PRDGeneratorModal.vue#L757))가 **레거시 PRD 전용 내용**(ZIP·Cursor·PRD.md·CLAUDE.md·.claude/agents)이라 robo-spec(그 파일들 없음)에 부적합 + `/robo-plan`·`/robo-tasks`·`/robo-implement` 언급 전무. | **수정함**: (a) [openInClaudeCode](../../../frontend/src/features/prdGeneration/ui/PRDGeneratorModal.vue#L298)가 robo-spec이면 `/robo-plan ` pre-fill (b) 완료 화면(step 4)을 robo-spec 분기 — "robo-* 스킬·MCP 설치됨" + **다음 단계 안내**(`/robo-plan <BC>`→`/robo-tasks`→`/robo-implement`) + pre-fill 힌트. `.robo-next-steps` 스타일 추가. **육안 확인은 다음 robo-spec 생성 시.** |
| D7 | 🔴 **P0(수정·검증)** | **robo-spec MCP `get_bc_design`이 모든 BC에서 commands/events/readmodels를 빈 배열로 반환** → `/robo-plan`·`/robo-tasks`가 **빈 설계**를 받아 계획·구현이 망가짐(설계는 그래프에 멀쩡: full-tree는 6 commands 반환). | [mcp_server.py:192](../../../api/features/robo_spec/mcp_server.py#L192) 기본 쿼리가 **`apoc.coll.toSet`(APOC 의존)** 사용 → 이 Neo4j에 **APOC 미설치**라 쿼리 throw → except 폴백(L202-222)이 **commands/events/readmodels=[]로 명시 반환**(무성한 degrade). | **수정함**: `collect(DISTINCT)`가 이미 중복제거하므로 `apoc.coll.toSet` 제거(APOC 의존 삭제). 재검증: get_bc_design(IdentityVerification)→cmd=6·evt=6·rm=5 정상(JudgeIdentityVerificationResult 등 모델 일치). **백엔드 픽스 — C1/C2/C8과 함께 커밋 대상.** |
| D8 | 🟡 **(경미)** | robo-spec 프로젝트 홈에 **`.specify/` 디렉터리·speckit 버전 마커 없음** → 스킬의 `requires-speckit ">=0.8.13,<0.9.0"` 호환성 검증 불가(스킬이 직접 flag). robo-plan 오버라이드가 setup-plan.sh를 우회해 진행은 됨. | `setup-project`/`_install_robo_spec`이 speckit-plan/tasks/implement SKILL.md는 복사하나 **`.specify/` 스캐폴딩·버전 마커는 미설치**. | **후속**: setup-project가 .specify 버전 마커도 깔거나, robo 스킬 frontmatter의 requires-speckit 핀을 현실화. 기능 영향 없음(오버라이드 우회). |
| D9 | 🟢 **(수정)** | **터미널 출력이 길어지면 스크롤 버벅임**(사용자 지적). | [ClaudeCodeTerminal.vue](../../../frontend/src/features/claudeCode/ui/ClaudeCodeTerminal.vue) xterm이 **렌더러 addon 없이 기본 DOM 렌더러** 사용 + `scrollback:5000`. DOM 렌더러는 대량 출력/긴 스크롤백에서 느림. | **수정함**: `@xterm/addon-webgl@0.19.0` 설치 + **`terminal.open()` 직후** `WebglAddon` 로드(GPU 렌더). `onContextLoss`→dispose 폴백 + try/catch(WebGL 미지원 시 기본 렌더러 유지). |
| D6 | 🟡 **(중복)** | **슬래시 커맨드 `/robo-plan`(외 robo-*)이 자동완성에 2개씩 뜸**. 사용자 지적. | robo 스킬이 **두 스코프에 이중 설치**: ① 글로벌 `~/.claude/skills/robo-plan`(Code 탭 global-skills install) ② 프로젝트 `<proj>/.claude/skills/robo-plan`(`setup-project`/`_install_robo_spec`). Claude Code가 user+project 스킬을 합쳐 보여줘 중복. 기능 무해(동일 스킬). | **후속**: 정책 정리 — robo 프로젝트는 항상 로컬 설치되므로 (a) `setup-project`가 글로벌 존재 시 로컬 스킬 복사 생략 or (b) robo 프로젝트에선 글로벌 robo 스킬 미설치/숨김. 설계 결정 필요(글로벌은 비-robo-project 워크디렉터리용). |
| (이월) I14 | 🟡 | 종료된 proposal Code 세션 잔존(tree 400 반복) | 세션 prune 없음 | S6 |

## 5. 결론

- (초안) S0(진입+워크디렉터리) → S1~S6 라이브 검증. **핵심 회귀 위험**: ① pty_backend env(C11)로 터미널 claude 인증 ② 멀티세션/재어태치 정합 ③ FS 안전(경로 탈출·삭제) ④ MCP 슬래시 동작 ⑤ 세션 수명주기(I14/I16).
- 교차: 외부 핸드오프는 **Changes(038)·Proposals(039)** 와, MCP 스킬은 **robo_spec** 과, 진척 동기화는 **Stories/Design 탭(소스 점프)** 과 관계.
