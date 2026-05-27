---
title: "Robo Spec Skills — Part 2: /robo-tasks → 스코프드 /robo-implement"
subtitle: "Feature 029 — 기존 프로젝트 홈에서 이어서 내장 Claude Code 터미널 안에서"
author: "Robo Architect 팀"
date: "2026-05-27"
---

# 이 매뉴얼이 증명하는 것 (Part 1에서 이어서)

[Part 1](manual_ui_playwright_ko.md)이 SPA를 **프로젝트 홈 생성**부터
**Claude Code 터미널 열기**까지 구동했고 `/robo-plan`을 내장 xterm.js
터미널에 타이핑해 `plan.md`를 생성하고 `BoundedContext.classification`을
`null`에서 `"core"`로 뒤집었습니다.

이 part 2는 그 시점에서 이어 받아서 다음을 증명합니다:

1. 생성된 `plan.md`를 파일 트리 클릭으로 파일 에디터 페인에 열 수 있음 —
   즉, 개발자가 실제 플랜 내용을 보지, 디스크의 경로만 보는 게 아님
2. 같은 내장 터미널에 타이핑한 `/robo-tasks`가 각 체크박스에
   `<!-- @robo elementId="..." -->` 마커가 붙은 `tasks.md`를 생성함
3. `/robo-implement` — 명시적 스코프 제약(***MemberAccount 어그리거트
   엔티티만***) — 이 프로젝트를 부분적으로 스캐폴드하고 `tasks.md`에서
   매칭되는 체크박스를 부분적으로 체크함. 이게 현실적인
   "BC 전체가 아니라 어그리거트 하나부터 코딩 시작" 플로우
4. 부분 실행 후 `tasks.md`를 에디터 페인에 다시 열면 구현된 항목의
   `- [ ]`였던 체크박스만 `- [x]`로 뒤집힌 게 보임
5. 스캐폴드된 `MemberAccount.ts`를 에디터 페인에 열면 `/robo-implement`가
   실제로 무엇을 작성했는지 보임

테스트: [`frontend/tests/robo-spec-tasks-implement.spec.ts`](../../../frontend/tests/robo-spec-tasks-implement.spec.ts).

# "지금 구현되고 있는 스펙이 어떤 스펙인지를 보여주는 비주얼라이저"

사용자가 물어본 비주얼라이저는 Claude Code 탭의 파일 에디터
페인(`FileTreePane.vue`의 오른쪽 `FileEditorPane.vue`)입니다.
개발자가 파일 트리에서 `specs/<NNN>-<slug>/tasks.md`를 클릭하면,
페인이 파일 내용을 라이브로 렌더링합니다 — `@robo` 마커까지 모두 —
어떤 작업이 아직 `- [ ]`이고 어떤 게 `- [x]`인지 보여줍니다.
아래 4개 스크린샷이 각각 이걸 캡처합니다: 에디터 페인이 "지금
구현 중" 뷰입니다.

Design 탭의 더 풍부한 element 단위 진행 뱃지(US2)는 별도 관심사로
아직 보류 — 같은 체크박스 상태를 각 Aggregate/Command/Event 노드에
그래픽으로 렌더링할 예정. 지금은 에디터 페인이 단일 진실 공급원이고
이 플로우에서 완전히 작동합니다.

# 1단계 — 파일 트리로 plan.md를 에디터 페인에 열기

Part 1에서 `/robo-plan`이 완료된 후 (또는 테스트가 기존 것을 재사용),
Claude Code 탭 왼쪽 파일 트리에 다음이 보입니다:

```text
.claude/
specs/
└── 001-membership-management/
    └── plan.md
```

`specs` → `001-membership-management` → `plan.md` 클릭. 중앙 페인이
실제 플랜 내용을 로드.

![/robo-plan 후 에디터 페인에 열린 plan.md](screenshots/part2_01_plan_md_in_editor.png){ width=100% }

개발자가 `plan.md` 안에서 읽는 내용:

- *"BoundedContext id 24fa4636-… version 1"* with `classification: core`
- *"Architecture: Clean Architecture (entities / usecases / interface_adapters / frameworks_and_drivers)"* — BC가 `core`라서 선택됨
- *"Source of truth: Robo Architect graph"* — `spec.md`, `data-model.md`,
  `contracts/` 중 어느 것도 emit하지 않는다는 명시적 진술 (FR-004 + research R5)
- *"Design slice: 1 aggregate (MemberAccount), already with N implementation-file links"* — 이전 실행이 파일을 등록했다면
- "File Layout" 섹션이 `src/membership-management/entities/MemberAccount.ts` 같은 경로 예측
- *"Next: /robo-tasks 001-membership-management"*

# 2단계 — 터미널에 /robo-tasks 타이핑; claude 생성 중

테스트가 `/robo-plan`을 돌렸던 같은 내장 터미널에 `/robo-tasks`를
타이핑. claude가 `plan.md`(태스크의 진실 공급원)와 MCP
`T2 get_bc_design`로 라이브 디자인을 읽고, 각 디자인-엘리먼트-바운드
태스크에 `@robo` 마커가 붙은 `tasks.md`를 작성하기 시작.

![내장 터미널에서 실행 중인 /robo-tasks](screenshots/part2_02_robo_tasks_running.png){ width=100% }

# 3단계 — tasks.md를 에디터 페인에 열기 — INITIAL 상태

`/robo-tasks` 완료 후 파일 트리에서 `tasks.md` 클릭. 에디터 페인이
전체 태스크 목록 표시. 모든 체크박스가 `- [ ]`로 시작하고, 적어도
하나의 태스크에 MemberAccount용
`<!-- @robo elementId="..." kind="Aggregate" -->` 마커가 부착됨 (다른
setup/integration 태스크는 의도적으로 마커 없음 —
`robo-tasks/SKILL.md`의 Override 3 따름).

![/robo-implement 전 tasks.md — 모두 미체크, @robo 마커 보임](screenshots/part2_03_tasks_md_initial.png){ width=100% }

# 4단계 — 스코프 = MemberAccount 어그리거트만으로 /robo-implement

테스트가 명시적 스코프 제약 프롬프트와 함께 `/robo-implement` 타이핑:

> *"/robo-implement — ONLY scaffold the MemberAccount aggregate
> entity file (one file under entities/). Do not scaffold any
> usecases, interface_adapters, frameworks_and_drivers, or
> repository files. Skip Phase 1 setup tasks except the entities/
> directory. Stop after the aggregate entity is created and its
> @robo marker is ticked."*

현실적인 "BC 전체가 아니라 어그리거트 하나부터 코딩 시작" 패턴.
claude의 동작:

1. 어그리거트가 필요로 하는 디렉토리만 생성
2. `src/membership-management/entities/MemberAccount.ts` 스캐폴드
3. MCP `register_implementation_files(mode="merge")` 호출로 새 파일을
   MemberAccount 엘리먼트 id 대해 그래프에 기록
4. **오직** `@robo`-태그된 MemberAccount 태스크만 `tasks.md`에서
   `- [ ]` → `- [x]`로 체크. 다른 태스크는 `- [ ]` 유지

![스코프 = MemberAccount만으로 실행 중인 /robo-implement](screenshots/part2_04_robo_implement_running.png){ width=100% }

# 5단계 — tasks.md 재오픈 — 체크박스 뒤집힘

파일 트리에서 `tasks.md` 다시 클릭 (에디터 페인이 디스크에서
재로드). MemberAccount 태스크가 이제 `- [x]`; 스코프에 포함되지
않은 setup 태스크는 `- [ ]` 유지. `@robo` 마커는 정확히 보존되어
후속 `/robo-implement` 실행이 element id로 태스크를 다시 찾을 수
있음.

![스코프드 /robo-implement 후 tasks.md — MemberAccount 태스크 체크됨](screenshots/part2_05_tasks_md_checked.png){ width=100% }

이게 사용자가 물어본 비주얼라이저 동작:
**어떤 스펙/태스크가 지금 구현되고 있는지가 Claude Code 탭의 에디터
페인 안에서 바로 보입니다.** 개발자는 언제든 `tasks.md`를 다시 열어
라이브 상태를 확인할 수 있습니다.

# 6단계 — 스캐폴드된 MemberAccount.ts를 에디터 페인에 열기

마지막으로 파일 트리에서 `src/membership-management/entities/`로
이동해 `MemberAccount.ts` 클릭. 에디터 페인이 `/robo-implement`가
작성한 최소 스캐폴드 표시:

![에디터 페인에 열린 MemberAccount.ts](screenshots/part2_06_member_account_source.png){ width=100% }

R7 enforcement 확인: 이 소스 파일에 `@robo` 마커가 **없음**. 마커는
`tasks.md`에만 살아 있습니다. `grep -rIn '@robo' src/`는 빈 결과
반환 — 아래 요약의 `roboMarkersInSrc` 필드로 테스트가 확인.

# 머신 가독 요약

[`screenshots/part2_99_summary.json`](screenshots/part2_99_summary.json):

```json
{
  "workspace": "/tmp/robo-spec-real-flow",
  "planMd": ".../001-membership-management/plan.md",
  "tasksMd": ".../001-membership-management/tasks.md",
  "memberAccountTs": ".../entities/MemberAccount.ts",
  "tasksUncheckedInitial": 6,
  "tasksCheckedAfterImplement": 1,
  "constraint": "MemberAccount aggregate entity only — Phase 2 partial scaffold",
  "roboMarkersInSrc": "(none — R7 enforced)"
}
```

`tasksUncheckedInitial`은 `/robo-tasks` 직후 `- [ ]` 행 개수;
`tasksCheckedAfterImplement`는 스코프드 `/robo-implement` 직후
`- [x]` 행 개수. 델타가 스코프드 실행이 in-scope 체크박스만 뒤집었음을
증명.

# 요약

| 단계 | 캡처 내용 | 결과 |
| --- | --- | --- |
| 1 | plan.md가 에디터 페인에 보임 (파일 트리 클릭) | **PASS** |
| 2 | 내장 터미널에서 /robo-tasks 실행 중 | **PASS** |
| 3 | tasks.md 초기 상태 — 모두 `[ ]` + @robo 마커 | **PASS** |
| 4 | 스코프 = MemberAccount 어그리거트만으로 /robo-implement | **PASS** |
| 5 | 스코프드 implement 후 tasks.md — MemberAccount 태스크 `[x]`, 나머지 `[ ]` 유지 | **PASS** |
| 6 | 스캐폴드된 MemberAccount.ts가 에디터 페인에 보임 | **PASS** |

# 재현하기

```sh
# 백엔드 + 프론트엔드는 Part 1에서 이미 떠 있음.

cd /Users/uengine/main-robo-arch/robo-architect/frontend
npx playwright test robo-spec-tasks-implement --reporter=list

cd ../specs/029-robo-spec-skills/manual
pandoc manual_ui_playwright_part2_ko.md -o manual_ui_playwright_part2_ko.docx \
    --resource-path=. --toc --toc-depth=2 \
    --metadata title="Robo Spec Skills - Part 2"
```

스펙은 Part 1의 `/tmp/robo-spec-real-flow/`를 재사용 (idempotent
설치 + 기존 `plan.md`가 있으면 재사용 — 재실행이 빠름). 워스트
케이스에서 3개의 풀 claude-in-terminal 라운드트립을 커버하기 위해
테스트 예산은 12분; 일반 런타임은 **3-5분**.
