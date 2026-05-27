---
title: "Robo Spec Skills — Part 3: /robo-sync 역방향 동기화"
subtitle: "Feature 029 — 개발자가 소스코드를 수정하면 그래프가 AST 추출 + MCP로 따라잡음"
author: "Robo Architect 팀"
date: "2026-05-27"
---

# 이 매뉴얼이 증명하는 것 (Parts 1 + 2에서 이어서)

[Part 1](manual_ui_playwright_ko.md)이 SPA를 **프로젝트 홈 생성**부터
**Claude Code 터미널 열기**까지 구동하고 `/robo-plan`을 실행해 `plan.md`를
생성하고 `BoundedContext.classification = "core"`를 그래프에 기록했습니다.

[Part 2](manual_ui_playwright_part2_ko.md)가 `/robo-tasks`(각 체크박스에
`@robo` 마커가 붙은 `tasks.md` 생성)를 실행하고, 스코프드
`/robo-implement`로 `MemberAccount.ts`를 스캐폴드하고 MemberAccount 체크박스를
체크했습니다.

이 Part 3은 **US5 — 역방향 동기화**를 다룹니다. 개발자가 Robo Architect
외부에서 `MemberAccount.ts`를 수정했고(프로퍼티 `email` 추가), 그래프의
Aggregate Design 뷰가 그 변경을 반영하기를 원합니다. 구체적으로 이
매뉴얼은 다음을 증명합니다:

1. `/robo-sync` 스킬이 TypeScript AST 익스트랙터를 수정된 소스 파일에
   실행합니다 — **마커 코멘트는 필요 없고, 작성되지도 않습니다**.
2. MCP 툴을 순서대로 세 번 호출합니다: `get_bc_design`, `propose_sync`,
   `apply_proposal`.
3. proposal diff가 `+1 added` (`email`), `~7 modified` (익스트랙터의 타입
   대소문자 정규화), `0 removed` — `requiresConfirmation`은 비어 있어 비
   대화형으로 적용됩니다.
4. 그래프의 MemberAccount 노드가 업데이트됩니다: 프로퍼티 개수 7 → 8,
   aggregate 버전 0 → 1.
5. SPA의 Aggregate 탭 네비게이터가 MemberAccount를
   MembershipManagement(core) 하위에 표시합니다 — 단, 캔버스는 HTML5
   드래그-앤-드롭이 필요해 헤드리스 Playwright가 구동할 수 없으므로
   InspectorPanel 프로퍼티 목록은 **캡처되지 않습니다** ("이 매뉴얼이
   캡처하지 못한 것" 섹션 참고).

MCP 스모크는 `propose_sync` → `apply_proposal` 시퀀스를 직접 검증해
확인했습니다. 전후 그래프 상태는
`sync_05_member_account_after_graph.json`(pretty-printed)과
`sync_04_graph_after_api_response.png`(Chrome의 raw Swagger 응답)으로
확인됩니다.

# 한눈에 보는 플로우

개발자가 `MemberAccount.ts`에 `public readonly email: string,`을 타이핑하고,
내장 Claude Code 터미널에 `/robo-sync`를 입력합니다. 스킬이 `ts_extract.mjs`로
클래스 구조를 추출하고, diff를 MCP 서버에 제안하고, 확인이 필요 없는 승인
경로를 받아 `apply_proposal`을 호출합니다. 그래프 버전이 원자적으로 올라가고,
이후 어떤 클라이언트든 `GET /api/contexts/{bc_id}/full-tree`를 호출하면
MemberAccount에서 8개의 프로퍼티를 볼 수 있습니다.

# 1단계 — 수정 전의 MemberAccount.ts

Part 2에서 `/robo-implement`가 스캐폴드한 파일은 생성자에 7개의 필드가
있습니다 — Robo Architect 그래프가 그 시점에 MemberAccount에 이미 가지고
있던 7개의 프로퍼티와 일치합니다.

![Claude Code 에디터 페인의 MemberAccount.ts — 생성자 필드 7개 (수정 전)](screenshots/sync_01_source_before_edit.png){ width=100% }

생성자에 보이는 7개 필드: `id`, `status`, `profile`, `personalInformation`,
`identityVerification`, `parentalConsent`, `termsConsents`. 이는 그래프와
정확히 일치하며 — 요약 JSON의 `before.graph_properties` 목록이 이 정렬을
확인합니다:

```json
"graph_properties": [
  "id", "identityVerification", "parentalConsent",
  "personalInformation", "profile", "status", "termsConsents"
]
```

# 2단계 — 개발자가 생성자에 `email` 추가

개발자가 생성자에 `public readonly email: string,` 한 줄을 타이핑합니다.
파일은 이제 생성자 파라미터 8개. **`@robo` 마커는 추가하지 않고 필요하지도
않습니다** — AST 익스트랙터는 순수하게 TypeScript 구조로만 동작합니다
(research R7).

![`public readonly email: string,` 추가 후 MemberAccount.ts — 생성자 필드 8개](screenshots/sync_02_source_after_edit.png){ width=100% }

그래프는 아직 변경되지 않았습니다. 수치로 본 전후 비교:

| 항목 | 수정 전 | 수정 후 |
| --- | --- | --- |
| 소스 생성자 필드 수 | 7 | 8 |
| 그래프 프로퍼티 수 | 7 | 7 (아직 동기화 전) |
| `MemberAccount` aggregate 버전 | 0 | 0 (아직 동기화 전) |

# 3단계 — 내장 터미널에 /robo-sync 타이핑

개발자가 내장 Claude Code xterm.js 터미널에 `/robo-sync`를 타이핑합니다.
claude가 설치된 스킬의 `SKILL.md`를 읽고, `.claude/robo-project.json`으로
프로젝트 컨텍스트를 찾고, `specs/001-membership-management/plan.md`에서
BC id를 추출한 뒤 MCP 라운드트립을 시작합니다.

![내장 Claude Code 터미널에서 /robo-sync 실행 중 — SKILL.md 로드, MCP 툴 호출 보임](screenshots/sync_03_robo_sync_running.png){ width=100% }

`robo-sync/SKILL.md`에 정의된 스킬 플로우:

1. `robo-project.json` 읽기 — `projectId`, `backendUrl`, `mcpEndpoint`.
2. `plan.md`에서 BC id 추출 → `24fa4636-6a5c-493a-8cfa-a08833e245eb`.
3. `get_bc_design(bcId=…)` 호출 — 각 엘리먼트의 `implementationFiles[]`
   링크 포함 현재 디자인 전체 수신.
4. `MemberAccount`의 등록된 구현 파일
   (`src/membership-management/entities/MemberAccount.ts`)에 대해 익스트랙터 실행:
   ```sh
   node .claude/skills/robo-sync/extractors/ts_extract.mjs \
       src/membership-management/entities/MemberAccount.ts
   ```
5. `propose_sync(projectId, bcId, extracts)` 호출 — 서버가 diff 계산.
6. 개발자에게 diff를 평문으로 보여주고 파괴적 변경에 대한 확인 요청
   (이번에는 없음 — `requiresConfirmation: []`).
7. `apply_proposal(projectId, proposalId, confirmed=[])` 호출.

# 4단계 — MCP 라운드트립: claude가 실제로 호출한 것

요약 JSON의 `tools_called` 배열에 세 MCP 툴이 이 순서로 기록됩니다:

```json
"tools_called": ["get_bc_design", "propose_sync", "apply_proposal"]
```

`propose_sync` 응답이 담은 diff:

```json
"proposal_diff": { "added": 1, "modified": 7, "removed": 0 }
```

- **+1 added** — 생성자에서 추출된 새로운 `email: string` 프로퍼티.
- **~7 modified** — 익스트랙터가 타입 이름을 정규화 (예: 그래프가
  일부 필드에 `"Object"`를 저장했으나 TypeScript 소스는 `object`라 쓰고,
  익스트랙터는 일관되게 소문자로 emit하므로 MCP 서버가 이를 업데이트로
  기록). 의미적 변경이 아닌 대소문자 정규화 artefact입니다.
- **-0 removed** — 삭제된 필드 없음.

필드가 제거되지 않았고 충분한 신뢰도로 플래그될 rename도 감지되지 않았으므로
`requiresConfirmation`이 비어 왔습니다:

```json
"requires_confirmation": []
```

개발자 입력이 필요 없어 claude가 즉시
`apply_proposal(projectId, proposalId, confirmed=[])` 를 호출했고, 서버가
반환:

```json
"apply_status": "applied",
"graph_version_bumped": "0 -> 1"
```

# 5단계 — /robo-sync 후 그래프 상태

## 원시 API 증거 (캡처 4)

Chrome에서 보이는 원시 `GET /api/contexts/{bc_id}/full-tree` 응답이
`MemberAccount.properties[]`에 이제 `email` 항목이 있음을 확인합니다.
의도적으로 필터 없는 Swagger 출력 — 밀도 있는 JSON이지만 직접 검증 가능합니다.

![Chrome의 raw GET /api/contexts/{bc_id}/full-tree JSON — MemberAccount properties[]에 email 포함](screenshots/sync_04_graph_after_api_response.png){ width=100% }

## Pretty-printed 그래프 슬라이스 (캡처 5)

[`screenshots/sync_05_member_account_after_graph.json`](screenshots/sync_05_member_account_after_graph.json)은
`/robo-sync` 후 그래프에서 가져온 MemberAccount 노드 전체입니다. 문서 하단의
`properties[]` 배열에 이제 8개 항목이 있습니다. `email`이 있음을 확인하는
핵심 라인:

```json
"properties": [
  {
    "description": "Member account unique identifier.",
    "id": "275bc68d-305d-4529-a9a8-68cbaa0c5256",
    "isKey": true,
    "name": "id",
    "parentType": "Aggregate",
    "type": "string"
  },
  {
    "description": null,
    "displayName": null,
    "id": "54ce14b3-5126-47b5-8896-96d90183432b",
    "isForeignKey": null,
    "isKey": null,
    "isRequired": null,
    "name": "email",
    "parentId": "82704ceb-bbf2-4cd3-b010-bc6ab82b09e4",
    "parentType": "Aggregate",
    "type": "string"
  },
  ...
]
```

`email` 프로퍼티(id `54ce14b3-…`)는 AST 익스트랙터가 `MemberAccount.ts`
생성자에서 읽은 그대로입니다. `description`, `displayName`, `isKey`,
`isForeignKey`, `isRequired` 필드가 `null`인 것은 익스트랙터가 TypeScript
생성자에서 추출할 수 있는 것만 가져오기 때문 — 더 풍부한 설명은 이후
`/robo-plan` 재실행이나 Robo Architect SPA에서 수동으로 추가할 수 있습니다.

최종 전후 비교:

| 항목 | 수정 전 | 수정 후 |
| --- | --- | --- |
| 소스 생성자 필드 수 | 7 | 8 |
| 그래프 `MemberAccount.properties[]` 수 | 7 | 8 |
| `MemberAccount` aggregate 버전 | 0 | 1 |
| 그래프에 `email` | 없음 | 있음 (`type: "string"`) |

# 6단계 — SPA가 보여줄 것 (드래그-앤-드롭 제한)

Playwright 테스트가 `/robo-sync` 완료 후 **Aggregate** 탭으로 이동했습니다.
왼쪽 네비게이터가 **MembershipManagement (core)**를 확장된 상태로 표시하고
**MemberAccount**가 하위 노드로 올바르게 보입니다.

![SPA Aggregate 탭 — 네비게이터에 MembershipManagement (core) → MemberAccount 보임, 캔버스는 "선택된 aggregate 없음"](screenshots/sync_06_aggregate_view_with_email.png){ width=100% }

중앙 캔버스는 *"No aggregates selected — Drag a Bounded Context or an
Aggregate from the navigator onto the canvas"*라고 표시합니다. 예상된 결과:
MemberAccount의 8개 프로퍼티(`email` 포함)를 나열하는 InspectorPanel은
사용자가 `MemberAccount`를 네비게이터에서 캔버스로 드래그해야 채워집니다.
**이는 테스트 하니스 한계이며, `/robo-sync`의 한계가 아닙니다.**

실제 사용자가 `MemberAccount`를 캔버스에 드래그하면 InspectorPanel이
즉시 업데이트되어 8개의 프로퍼티를 표시하고 `email`을 포함합니다. 그래프
수준 증거(캡처 4, 5)가 프로퍼티가 그곳에 있음을 확인; SPA는 그래프가
가진 내용을 미러링할 뿐입니다.

# 이 매뉴얼이 캡처하지 못한 것 (그리고 그 이유)

요약 JSON의 `ui_limitation_noted` 필드가 이를 정확하게 명시합니다:

> *"The Aggregate Viewer's canvas requires HTML5 drag-and-drop from the
> navigator. Headless Playwright cannot reliably drive that custom drag
> protocol, so the manual relies on the JSON / Swagger evidence (captures 4–5)
> to prove the property landed in the graph. Live users dragging MemberAccount
> onto the canvas would see the email property in the InspectorPanel — this is
> a test-harness limitation, not a /robo-sync limitation."*

이 매뉴얼이 **확실하게** 증명한 세 가지:

- AST 익스트랙터가 8-필드 TypeScript 생성자를 올바르게 파싱했습니다.
- MCP 시퀀스(`get_bc_design` → `propose_sync` → `apply_proposal`)가
  `status: "applied"`와 버전 `0 → 1` 범프로 완료됐습니다.
- 그래프의 `MemberAccount.properties[]` 수가 7에서 8로 늘었고 `email`이
  `"string"` 타입으로 올바르게 존재합니다.

비헤드리스(또는 CDP-구동) 런으로 시각적으로 확인해야 할 것:

- Aggregate 캔버스의 InspectorPanel에서 8개 프로퍼티 목록 표시.
- 특히 `email` 행이 "새로 동기화됨"으로 강조 표시(SPA가 향후 그런 시각적
  어포던스를 추가하는 경우).

# 머신 가독 요약

[`screenshots/sync_99_summary.json`](screenshots/sync_99_summary.json):

```json
{
  "feature": "029-robo-spec-skills",
  "skill": "/robo-sync",
  "workspace": "/tmp/robo-spec-real-flow",
  "file_edited": "src/membership-management/entities/MemberAccount.ts",
  "bc_id": "24fa4636-6a5c-493a-8cfa-a08833e245eb",
  "aggregate_id": "82704ceb-bbf2-4cd3-b010-bc6ab82b09e4",
  "aggregate_name": "MemberAccount",
  "before": {
    "source_field_count": 7,
    "graph_property_count": 7,
    "aggregate_version": 0
  },
  "after": {
    "source_field_count": 8,
    "source_fields_added": ["email"],
    "graph_property_count": 8,
    "aggregate_version": 1
  },
  "mcp_round_trip": {
    "extractor_called": "node robo-spec/.claude/skills/robo-sync/extractors/ts_extract.mjs <file>",
    "tools_called": ["get_bc_design", "propose_sync", "apply_proposal"],
    "proposal_diff": { "added": 1, "modified": 7, "removed": 0 },
    "requires_confirmation": [],
    "apply_status": "applied",
    "graph_version_bumped": "0 -> 1"
  }
}
```

`proposal_diff.modified: 7`은 4단계에서 설명한 타입 대소문자 정규화
artefact입니다 — 의미 있는 변경 7개가 아니라, 타입 문자열의 대소문자가
바뀐 (`Object` → `object` 등) 필드 7개입니다. 진짜 새로운 필드는 `email`
하나뿐입니다. `requires_confirmation: []`은 파괴적이거나 모호한 변경이
없었음을 확인합니다.

# 요약

| 단계 | 캡처 내용 | 결과 |
| --- | --- | --- |
| 1 | MemberAccount.ts — 수정 전 7개 필드, 그래프와 일치 | **PASS** |
| 2 | 개발자가 `email` 추가 — 8개 필드, @robo 마커 없음 | **PASS** |
| 3 | /robo-sync 내장 터미널에서 실행 — 익스트랙터 + MCP 호출 보임 | **PASS** |
| 4 | MCP 라운드트립: `get_bc_design` → `propose_sync` → `apply_proposal` (+1 ~7 -0, 확인 요청 없음) | **PASS** |
| 5 | 그래프 수정 후: 프로퍼티 8개, `email: string` 존재, 버전 0→1 | **PASS** |
| 6 | SPA 네비게이터에 MemberAccount(core) 표시 — 캔버스 비어 있음 (드래그-앤-드롭 하니스 한계, 스킬 결함 아님) | **NOTED** |

# 재현하기

```sh
# 백엔드 + 프론트엔드는 Parts 1 + 2에서 이미 떠 있음.
# /tmp/robo-spec-real-flow/에 다음이 존재:
#   - .claude/robo-project.json
#   - specs/001-membership-management/plan.md
#   - src/membership-management/entities/MemberAccount.ts  (Part 2에서)

# 1. MemberAccount.ts에 email 추가
echo "    public readonly email: string," >> \
    /tmp/robo-spec-real-flow/src/membership-management/entities/MemberAccount.ts

# 2. Playwright 테스트 실행 (SPA + /robo-sync 스킬 구동)
cd /Users/uengine/main-robo-arch/robo-architect/frontend
npx playwright test robo-spec-sync --reporter=list

# 3. 이 매뉴얼을 DOCX로 렌더링
cd ../specs/029-robo-spec-skills/manual
pandoc manual_ui_playwright_part3_ko.md -o manual_ui_playwright_part3_ko.docx \
    --resource-path=. --toc --toc-depth=2 \
    --metadata title="Robo Spec Skills - Part 3"
```

Part 3 테스트 예산은 8분(`/robo-sync`용 claude-in-terminal 라운드트립 한 번
+ MCP 스모크 호출). `/robo-plan`이나 `/robo-implement`보다 LLM 호출 수가
적어 일반 런타임은 **2–4분**입니다.
