# Feature Specification: 레거시 참조 프로버넌스 — "어떤 노드가 인용됐나"를 일급 데이터로

**Feature Branch**: `052-legacy-reference-provenance` · **Created**: 2026-07-16 · **Status**: Draft
**Input**: 사용자 요구 "실제 어떤 노드가 참조되었나 보여주는 UI/UX가 있어야 — 잘 녹여서, 크게는 말고".

## 동기 (현재 사실 — 2026-07-16 검증 세션)

AI 스테이지(Intent/Plan)가 `mcp__robo-cluster__cluster_retrieve` 로 레거시 그래프를 실제 검색·인용함은
검증됐다(응답에 함수별 rules/examples/tables 포함 — analyzer spec 056). 그러나 그 증거가 UI 에는
**우연적 흔적**으로만 남는다:

- ① 진행 스트림의 원시 `[tool] mcp__…cluster_retrieve` / `[레거시 참조] …` 라인 — 흘러가면 끝.
  게다가 051 이 tool 라인을 사람친화화하면 이 흔적은 사라진다.
- ② BC 분해 뷰의 설명 문단 속 `(레거시 근거: product_stock.avail_qty…)` — LLM 재량 산문이라
  런마다 있을 수도 없을 수도 있고, 클릭·추적 불가.

→ "무엇을 참조해 이 설계가 나왔나"가 재현 불가능한 상태. 프로버넌스를 산문이 아닌 **구조화
데이터로 저장**하고 UI 에 작게 노출한다.

## User Scenarios

### US1 — 참조 기록 캡처·저장 (P1)

스킬 실행 스트림에는 tool_use/tool_result 이벤트가 이미 흐른다(skill_runner 가 중계 — [tool] 라인의
원천). 여기서 `cluster_retrieve` 호출·응답을 파싱해 proposal 산출물에 저장한다:

```
proposal.legacyReferences: [{
  stage: "INTENT" | "PLAN" | <ddd-stage>,
  query: "<검색어>",
  nodes: [{ id, name, label, relevance, rulesCount }],   # 응답 clusters[].nodes 요약
  at: <timestamp>
}]
```

- LLM 재량 아님 — **호출이 있었으면 무조건 기록**(결정론). 호출 0회면 빈 배열(그것도 정보).
- 저장 위치는 proposal state(기존 stageArtifacts 와 동렬). Accept 시 그래프의 Proposal 노드에도 요약 보존.

### US2 — 여정 전체에 스며드는 노출 (P1, "잘 녹여서 + 연결됐음을 계속 강조")

사용자 결정(2026-07-16): 한 군데가 아니라 **제안의 여정 내내** "레거시와 연결돼 있음"이 보여야
한다 — 많을수록 좋되, 표식은 작고 **모든 자리에서 동일**해야 한다(같은 의미=같은 표식).

**공용 컴포넌트 1개** `LegacyRefChip` — `⛓ 레거시 근거 N` 칩 + 클릭 팝오버(스테이지별 검색어,
참조 함수 목록: 이름·한줄요약·rules 수, 행마다 "그래프에서 보기" 딥링크 — 기존 Analyzer 노드
포커스 라우팅 재사용). 이 한 컴포넌트를 아래 표면에 **전부** 배치한다(사본 금지):

| # | 표면 | 배치 | 비고 |
|---|---|---|---|
| 1 | Intent/스테이지 **진행 스트림** | `[tool] cluster_retrieve` 원시 라인을 `🔍 레거시 그래프 검색: "<query>" → 함수 N·규칙 M 참조` 한 줄로 대체 | 051 사람친화화와 단일 진실 공유 |
| 2 | **BC 분해/Intent 결과 뷰** 헤더 우측 | 칩 | 영상 "다리" 장면의 상시 증거 |
| 3 | BC 분해 뷰 **스토리 섹션 하단** | 소형 각주형: "이 분해는 레거시 함수 N개를 참조해 생성됨" + 칩 | |
| 4 | **Plan(구현계획) 뷰** 헤더 | 칩 (PLAN 스테이지 기록) | |
| 5 | **Proposal 목록 행** | 초소형 `⛓N` 아이콘 배지 | 목록에서도 "근거 기반 제안"임이 보임 |
| 6 | **Proposal 상세 메타 영역** | "레거시 참조" 접이식 섹션(스테이지별 전체 기록) | 팝오버의 풀버전 |
| 7 | Accept 후 **Design 탭 BC/Aggregate 상세** | 칩 (Proposal 노드에 보존된 요약 역참조) | 설계 요소가 살아있는 한 출처가 따라감 |

- 참조 0건이면 어느 표면에서도 렌더하지 않는다(빈 배지 노이즈 금지).
- 거대 패널·새 탭 신설 금지. 050 표면 토큰(색·타이포) 준수 — 칩은 보조 톤, 본문과 경쟁하지 않게.

### US3 — 데모/감사 활용 (P2)

칩·팝오버가 있으면 "그래프 데이터가 실제 쓰였다"의 스크린샷 증거가 항상 재현 가능해진다
(영상 데모 §VIDEO-SESSION-BRIEF 의 강조 컷이 우연 의존에서 벗어남).

## Requirements

- **FR-001**: skill_runner 스트림 소비부에서 `mcp__robo-cluster__cluster_retrieve` tool_use(입력 query)와
  대응 tool_result(clusters payload)를 짝지어 US1 스키마로 축약 저장. 파싱 실패는 경고 로그 + 스킵
  (스테이지 진행은 불변 — 프로버넌스는 부가 데이터, 본류 차단 금지).
- **FR-002**: proposal 조회 API 응답에 `legacyReferences` 포함(additive). 기존 소비자 회귀 0.
- **FR-003**: 프론트 칩+팝오버 — Intent 결과/BC 분해 뷰. 참조 0건이면 렌더 자체를 안 함.
- **FR-004**: tool 라인 사람친화화(051 과 공유 영역)는 본 spec 의 검색 요약 한 줄 포맷을 단일 진실로.
- **FR-005**: 노드 행 딥링크는 기존 Analyzer 그래프 포커스 경로 재사용(중복 라우팅 신설 금지).

## Success Criteria

- SC-001: 간소화 DDD 1회 실행 후 proposal API 에 legacyReferences ≥1 스테이지 기록(쿼리·노드 목록 실측 일치 —
  analyzer 검색 로그와 대조).
- SC-002: UI 칩 클릭 → 참조 함수 이름들이 그 런의 cluster_retrieve 응답과 정확히 일치(스크린샷 증거).
- SC-003: 참조 0회 런에서 칩 미표시·API 빈 배열(조용한 실패 아님 — 명시적 0).
- SC-004: 기존 proposal 조회·스테이지 진행 회귀 0.

## Non-Goals / 주의

- strategicDiff 항목별 세밀 귀속(`이 Feature 는 이 함수에서`)은 LLM 재량 영역이라 이번 범위 밖
  (프롬프트로 groundedIn 강제하는 후속 spec 후보로만 기록).
- 사용자 WIP 충돌 주의: skill_runner·ClaudeCodeTerminal 는 051/사용자 WIP 공유 영역 — hunk 분리 원칙.
