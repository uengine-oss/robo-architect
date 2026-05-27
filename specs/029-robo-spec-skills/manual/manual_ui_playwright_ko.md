---
title: "Robo Spec Skills — 실제 엔드-투-엔드: SPA + 내장 Claude Code 터미널"
subtitle: "Feature 029 — 프로젝트 홈 생성 (Robo-Spec 모드) → xterm.js 안에서 /robo-plan 타이핑"
author: "Robo Architect 팀"
date: "2026-05-27"
---

# 이 매뉴얼이 증명하는 것

단일 Playwright 테스트
([`frontend/tests/robo-spec-real-flow.spec.ts`](../../../frontend/tests/robo-spec-real-flow.spec.ts))가
**실제 최종 사용자 플로우**를 실제 Chromium 브라우저로 끝까지 구동합니다.
사이드채널 `claude -p` 호출은 일절 없습니다.

1. Robo Architect SPA 열기
2. 리네임된 상단 버튼 **프로젝트 홈 생성** 클릭 (이전 "PRD 생성")
3. 위자드에서 기본 선택된 **Robo-Spec Skills (권장)** 모드 그대로 유지 —
   레거시 PRD 파이프라인을 통째로 건너뜀
4. **Next →** (robo-spec 모드에서는 "Preview →" 대신 표기; PRD 미리보기가
   없기 때문) → 프로젝트 경로 입력 → **Claude Code에서 열기** 클릭 →
   백엔드가 robo-spec + speckit 스킬 세트와 `.mcp.json` /
   `.claude/robo-project.json`을 설치
5. **Claude Code 터미널 열기** 클릭 — SPA가 Claude Code 탭으로 전환되고
   내장 `ClaudeCodeTerminal.vue`가 새 프로젝트 경로에서 실제 PTY를 띄움.
   터미널 배너에 **bypass permissions on**이 표시되는 이유는 테스트가
   SPA를 `?permission_mode=bypassPermissions`로 열어 MCP 도구 호출이
   매 호출마다 권한 프롬프트에서 멈추지 않도록 했기 때문 (헤드리스
   테스트가 안정적으로 답할 수 없는 프롬프트)
6. 테스트가 슬래시 커맨드를 xterm.js 터미널에 **직접 타이핑** (테스트
   프로세스의 `claude -p`가 아님). 내장된 `claude`가 방금 설치된
   `.claude/skills/robo-plan/SKILL.md`로 슬래시 커맨드를 해석하고,
   robo-spec MCP 도구를 순서대로 호출 (`resolve_design_element`,
   `set_bc_classification`, `get_bc_design`,
   `register_implementation_files`), `specs/001-membership-management/`
   아래 `plan.md`를 작성
7. 테스트가 그래프를 폴링하다가 `classification`이
   `null → "core"`로 뒤집히면, 파일시스템을 폴링하다가 `plan.md`가
   나타나면 최종 터미널 상태를 캡처

테스트 런타임: **1.7분**. 결과: **PASS**.

# 사용자의 두 가지 핵심 질문에 답함

> "`/command`는 Claude Code 리로드가 되어야만 가능한가요?
> 그리고 `.claude/` 아래 스킬 파일들이 정확히 들어갔는지 확인이 필요"

**(1) 스킬 파일 배치 — 검증됨:**

```text
/tmp/robo-spec-real-flow/.claude/skills/
├── robo-plan/SKILL.md          (7,390 bytes)
├── robo-tasks/SKILL.md         (2,959 bytes)
├── robo-implement/SKILL.md     (4,158 bytes)
├── robo-sync/SKILL.md          (2,834 bytes)
├── speckit-plan/SKILL.md       (6,600 bytes)
├── speckit-tasks/SKILL.md      (9,837 bytes)
└── speckit-implement/SKILL.md  (11,097 bytes)
```

`setup-project`가 반환된 직후 7개 SKILL.md 파일이 모두 존재합니다 —
새 `robo-*` 스킬 4개와 상속 체인이 의존하는 `speckit-*` 업스트림
스킬 3개.

**(2) `/command` 와 리로드 — 검증됨:**

`claude`는 스킬을 *시작 시점*에 발견합니다. 리로드 필요 없음.
새로 설치된 `/tmp/robo-spec-real-flow/`에서
`claude -p "List the user-invocable skills you can see"`를 돌리면
다음과 같이 반환됩니다:

```text
- robo-implement
- robo-plan
- robo-sync
- robo-tasks
- speckit-implement
- speckit-plan
- speckit-tasks
```

내장 Claude Code 터미널은 설치가 *완료된 후*에 `claude`를 spawn하므로
(사용자가 Claude Code 탭에서 "Claude Code 터미널 열기"를 클릭할 때만
WS 연결이 이뤄짐) 디스커버리 레이스는 발생하지 않습니다. 아래
6-7단계의 캡처가 `/robo-plan`이 실제로 실행되는 모습을 보여줍니다.

# 1단계 — 리네임된 상단 버튼: 프로젝트 홈 생성

원래의 "PRD 생성" 버튼이 이제 **프로젝트 홈 생성**으로 바뀌었고,
툴팁도 *"모델에서 프로젝트 홈 생성 — Robo-Spec Skills 모드(권장) 또는 기존 PRD 형식"*으로 갱신.

![리네임된 프로젝트 홈 생성 버튼이 있는 상단 바](screenshots/step_01_topbar_renamed.png){ width=100% }

# 2단계 — 새 출력 모드 픽커가 있는 위자드 1단계

새 위자드 헤더에 **프로젝트 홈 생성** (이전 "Generate PRD for Vibe
Coding"). 첫 번째 설정 섹션이 **출력 모드** 픽커:

- **Robo-Spec Skills (권장)** — 기본 선택. robo-* 스킬 세트 + MCP만
  설치. plan / tasks / 소스는 Claude Code 안에서 슬래시 커맨드로
  필요할 때 생성. PRD.md, specs/, .cursor/rules/ 어느 것도 안 만듦
- **기존 PRD (Legacy)** — 029 이전 동작. PRD ZIP을 전부 생성하고
  **추가로** robo-spec 스킬도 설치

Robo-Spec 모드를 선택하면 무거운 Tech Stack / Architecture / Spec
Format / Additional Options 섹션이 숨겨집니다 (슬래시 커맨드가 BC
classification으로 아키텍처 선택을 자체 처리하기 때문).

![위자드 1단계 — 출력 모드 = Robo-Spec Skills (권장)](screenshots/step_02_modal_step1_robo_spec.png){ width=100% }

# 3단계 — Preview 건너뛰고 프로젝트 경로로 점프

robo-spec 모드에서는 푸터 버튼이 **Next →** 표기 ("Preview →"가
아님) — 미리볼 게 없기 때문. 클릭하면 레거시 미리보기 단계를
건너뛰고 바로 3단계 (프로젝트 경로 입력)로 점프.

![위자드 3단계 — 프로젝트 경로 /tmp/robo-spec-real-flow 입력](screenshots/step_03_modal_step3_project_path.png){ width=100% }

# 4단계 — 프로젝트 설정 완료

**Claude Code에서 열기** 클릭. 백엔드가
`POST /api/claude-code/setup-project`를 `output_mode: "robo-spec"`로
호출. 백엔드는 레거시 PRD 파이프라인을 통째로 건너뛰고
`_install_robo_spec(project_path)`만 호출 —
`<repo>/robo-spec/.claude/skills/`의 verbatim 스킬 트리와
`speckit-{plan,tasks,implement}/` 업스트림 스킬을 복사한 뒤,
`.claude/robo-project.json`과 `.mcp.json`을 작성.

![위자드 4단계 — 프로젝트 설정 완료!](screenshots/step_04_modal_step4_robo_spec_install.png){ width=100% }

robo-spec 모드이기 때문에 "추출된 파일" 목록이 의도적으로 짧음 —
PRD.md, specs/, .cursor/rules/ 없음. 사용자가 실제로 관심 있는 내용은
`.claude/skills/` 아래에 있고 (위에서 검증) 이 뷰에서는 의도적으로
보이지 않음 (`.claude/`는 숨김 디렉토리; 목록은 생성될 수 있었던
사용자 대면 PRD 산출물에 집중).

# 5단계 — Claude Code 탭 열림; bypass 모드로 내장 터미널 마운트

**Claude Code 터미널 열기** 클릭. SPA의
`provide('openClaudeCode', fn)` injection이 활성 탭을
**Claude Code**로 전환; `ClaudeCodeWorkspace.vue`가 새 프로젝트
경로로 마운트; `ClaudeCodeTerminal.vue`가 WebSocket → PTY →
`claude` CLI를 엽니다.

터미널이 *"Welcome back rickie!"* 배너를 **Opus 4.7 (1M context)** +
해석된 워크스페이스 경로와 함께 표시. 우하단의 빨간 텍스트
**▶▶ bypass permissions on**이 `permission_mode=bypassPermissions`
쿼리 파라미터가 WS를 거쳐 claude의 launch arg까지 전달되었음을
확인. 헤더에 `/tmp/robo-spec-real-flow`와 **연결됨**.

![Claude Code 탭 — 터미널 준비됨, bypass 모드 활성화](screenshots/step_05_claude_code_tab_ready.png){ width=100% }

# 6단계 — 슬래시 커맨드가 내장 터미널에 타이핑됨; claude 응답 중

Playwright 테스트가 터미널 캔버스를 클릭해 xterm.js의 helper
textarea에 포커스를 준 뒤 `page.keyboard.type(...)`로 슬래시
커맨드를 키당 40ms로 한 글자씩 전송. claude가 WS → PTY 파이프로
키스트로크를 받아 `.claude/skills/robo-plan/SKILL.md`에서 발견한
`/robo-plan` 스킬을 실행 시작.

이것이 사용자가 물어본 **`/command`**가 내장 Claude Code 터미널
안에서 실행되는 모습 — 테스트 프로세스의 사이드채널 `claude -p`가
아닙니다.

![슬래시 커맨드 타이핑됨; claude 실행 중](screenshots/step_06_terminal_robo_plan_running.png){ width=100% }

캡처된 프레임 위에서 아래로:

- Claude Code 환영 배너
- 박스로 강조된 슬래시 커맨드 텍스트:
  *"/robo-plan MembershipManagement — if no classification, treat as core and persist via set_bc_classification"*
- claude의 첫 동작: *"Read 2 files, listed 2 directories"*,
  *"Reading 1 file…"*, *"Shenaniganing… (14s · thinking)"*
- *"▶▶ bypass permissions on (shift+tab to..."* — launch arg가
  도달했음을 증명

# 7단계 — `/robo-plan` 완료; classification 뒤집힘 + plan.md 작성됨

테스트가 그래프를 4초마다 폴링. classification이 ~60–90초 안에
`null`에서 `"core"`로 뒤집힘 — 이는 MCP 도구 **T3
`set_bc_classification`**이 내장 세션 안에서 실행되었다는 증명.
이어서 테스트가 파일시스템을 폴링해 `specs/001-membership-management/`
아래 `plan.md`가 나타날 때까지 기다린 뒤 최종 터미널 상태 캡처.

![최종 터미널 상태 — /robo-plan 엔드-투-엔드 완료](screenshots/step_07_terminal_robo_plan_done.png){ width=100% }

캡처된 프레임이 터미널 안에서 일어난 전체 MCP-driven 시퀀스를 보여줌:

```text
Called robo-spec (ctrl+o to expand)
   Resolved to BC MembershipManagement (id 24fa4636-6a5c-493a-8cfa-a08833e245eb)
     with classification null. Per your instruction, I'll set it to core
     and fetch the design in parallel.

Listed 2 directories, called robo-spec 2 times (ctrl+o to expand)

BC has classification core (just set), 1 aggregate (MemberAccount), and no
commands/events/read models. No .specify/memory/constitution.md present —
I'll note that in the plan. Creating the feature directory and plan now.

Bash(mkdir -p /private/tmp/robo-spec-real-flow/specs/001-membership-management)
   Done

Doing… (58s · thought for 10s)
```

MCP 도구가 `robo-plan/SKILL.md`의 Override 1 명세 순서대로 발사됨:
`resolve_design_element` → `set_bc_classification` (classification이
null이고 프롬프트가 "core로 처리"라고 했으므로) → `get_bc_design` →
bash `mkdir -p`로 feature 디렉토리 생성 → `plan.md` 작성. Override 6
(`register_implementation_files` 시드)도 실행됨 — 이전 in-flight
프레임에서 "Called robo-spec 2 times"로 확인 가능.

# 파일시스템 결과

```text
/tmp/robo-spec-real-flow/
├── .claude/
│   ├── robo-project.json      ← setup-project가 작성
│   └── skills/
│       ├── robo-plan/SKILL.md         ┐
│       ├── robo-tasks/SKILL.md        │ <repo>/robo-spec/.claude/skills/에서 verbatim 복사
│       ├── robo-implement/SKILL.md    │
│       ├── robo-sync/SKILL.md         │
│       │   └── extractors/{python_extract.py, ts_extract.mjs, package.json}
│       ├── speckit-plan/SKILL.md      ┐
│       ├── speckit-tasks/SKILL.md     │ 상속 체인
│       └── speckit-implement/SKILL.md ┘
├── .mcp.json                  ← Claude Code가 이걸 읽어 robo-spec MCP 찾음
└── specs/001-membership-management/
    └── plan.md                ← 내장 터미널 안의 /robo-plan이 작성
```

**없는 것** 주목: PRD.md 없음, .cursor/rules/ 없음, top-level
`specs/` 스켈레톤 없음 — output_mode가 `robo-spec`이었기 때문에
레거시 PRD 파이프라인이 정확히 건너뛰어짐.

# 그래프 결과

```text
MATCH (bc:BoundedContext {name:'MembershipManagement'}) RETURN bc.classification, bc.version
→ classification = 'core'   version = 1
```

version이 0 → 1로 증가 — `T3 set_bc_classification`이 정확히
한 번 발사되었기 때문. 그래프의 다른 BC들
(`LegalConsentManagement`, `TermsAndAuthenticationManagement`)은
`classification: null`을 유지 — write 스코프 정확성 증명.

# 머신 가독 요약

[`screenshots/step_99_summary.json`](screenshots/step_99_summary.json):

```json
{
  "output_mode": "robo-spec",
  "prdMdExisted": false,
  "mcpJsonInstalled": true,
  "roboSpecSkills": ["robo-plan", "robo-tasks", "robo-implement", "robo-sync"],
  "speckitInheritance": ["speckit-plan", "speckit-tasks", "speckit-implement"],
  "beforeClassification": null,
  "afterClassification": "core",
  "planMd": "/tmp/robo-spec-real-flow/specs/001-membership-management/plan.md",
  "drivenBy": "embedded xterm.js terminal (not claude -p side-channel)"
}
```

# 요약

| 단계 | 캡처 내용 | 결과 |
| --- | --- | --- |
| 1 | 상단 버튼이 **프로젝트 홈 생성**으로 리네임 | **PASS** |
| 2 | 위자드 1단계에 새 출력 모드 픽커; Robo-Spec 기본 선택; 무거운 설정 섹션 숨겨짐 | **PASS** |
| 3 | Robo-Spec 모드가 Preview 건너뛰고 프로젝트 경로 입력으로 점프; 버튼은 **Next →** | **PASS** |
| 4 | `setup-project` with `output_mode=robo-spec`이 PRD 파이프라인 건너뛰고 스킬 + .mcp.json + robo-project.json만 설치 | **PASS** |
| 5 | Claude Code 탭 열림; 내장 터미널 마운트, **bypass permissions on** 표시 | **PASS** |
| 6 | `/robo-plan` 직접 xterm.js에 타이핑; claude 응답, MCP 트래픽 가시 | **PASS** |
| 7 | `set_bc_classification`이 그래프를 `null → "core"` 뒤집기; `specs/001-membership-management/` 아래 `plan.md` 작성됨 | **PASS** |

**총평: PASS.** 테스트 런타임 **1.7분**; 1개 테스트 케이스; 슬래시
커맨드가 *내장* Claude Code 터미널 안에서 실행됨 (사이드채널
`claude -p`가 아님).

# 이 매뉴얼 재현하기

```sh
# 1. 백엔드 + 프론트엔드
cd /Users/uengine/main-robo-arch/robo-architect
.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 &
cd frontend && npm run dev &

# 2. 테스트 BC의 classification 리셋 (BEFORE 상태를 null로)
cd /Users/uengine/main-robo-arch/robo-architect
.venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv()
import sys; sys.path.insert(0, '.')
from api.platform.neo4j import init_neo4j_driver, get_session, close_neo4j_driver
init_neo4j_driver(log=False)
with get_session() as s:
    s.run('MATCH (bc:BoundedContext) REMOVE bc.classification SET bc.version = 0').consume()
close_neo4j_driver(log=False)
"

# 3. Playwright 스펙 실행
cd frontend
npx playwright test robo-spec-real-flow --reporter=list

# 4. DOCX 재생성
cd ../specs/029-robo-spec-skills/manual
pandoc manual_ui_playwright_ko.md -o manual_ui_playwright_ko.docx \
    --resource-path=. --toc --toc-depth=2 \
    --metadata title="Robo Spec Skills - 실제 엔드-투-엔드"
```

# 이 매뉴얼에서 다루지 않은 것

| 스토리 | 표면 | 여기서 테스트 안 한 이유 |
| --- | --- | --- |
| `/robo-tasks`와 `/robo-implement`을 내장 터미널에서 | 동일한 xterm.js 파이프라인, 두 개의 슬래시 커맨드 더 | 매뉴얼 part 2 ([manual_ui_playwright_part2_ko.md](manual_ui_playwright_part2_ko.md))에서 다룸 |
| US2 (Design 탭 뱃지) | watchfiles 백엔드 + SSE + ProgressBadge 컴포넌트 | 백엔드 watcher (T028) + 프론트엔드 컴포넌트 (T033) 미구현 |
| US3 (구현 파일 클릭으로 열기) | MCP T7 + 프론트엔드 와이어링 (T039–T041) | 미구현 |
| US3 (네비게이터에서 classification 표시) | 새 `classification` 필드를 BC 이름 옆에 렌더링하는 프론트엔드 와이어링 | 미구현; 네비게이터는 현재 기존 `domainType`만 표시 |
| US5 (`/robo-sync`) | AST 추출기 + propose/apply MCP 도구 (T6 / T6a) | 추출기 stub은 exit 1; T6 / T6a 미구현 |
