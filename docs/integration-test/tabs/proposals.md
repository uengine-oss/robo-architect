# Proposals 탭 — 통합 검증

- **activeTab 값**: `Proposals`
- **패널 컴포넌트**: [`ProposalsPanel.vue`](../../../frontend/src/features/proposals/ui/ProposalsPanel.vue) → [`ProposalDetail.vue`](../../../frontend/src/features/proposals/ui/ProposalDetail.vue)
- **프런트 store**: [`proposals.store.js`](../../../frontend/src/features/proposals/proposals.store.js)
- **백엔드**: [`api/features/proposal_lifecycle/`](../../../api/features/proposal_lifecycle/)
- **주요 라우트**:
  - CRUD/상세: `POST /api/proposals/`, `GET /api/proposals/`, `GET /api/proposals/{id}`
  - Detailed DDD: `/mode`, `/stream/scope`, `/stage-plan/confirm`, `/stream/stage/{stage}`, `/stage/{stage}/draft`, `/stage/{stage}/confirm`, `/staged/consolidate`
  - Plan/구현/검증/승인: `/stream/plan`, `/plan/confirm`, `/tasks`, `/implement`, `/implement/complete`, `/stream/{id}/validate`, `/accept`
- **상태**: 🟢 Detailed DDD 주요 회귀 수정 완료, AC 리뷰 통과

## 1. 탭의 의도/목표

Proposals 탭은 기존 라이브 모델을 직접 수정하기 전에 변경 제안을 별도 Proposal로 만들고, 검토 가능한 단계들을 거쳐 코드 구현과 Neo4j 라이브 반영까지 연결하는 변경 라이프사이클 탭이다.

현행 라이프사이클은 다음 흐름이다.

1. **Intent**: 요구사항 입력 및 전략적 의도 분해
2. **Detailed DDD**: Scope → Discover → Decompose → Strategize → Connect → Define → Tactical
3. **Plan**: DDD 산출물을 표준 strategic/tactical diff로 수렴하고 Constitution 기반 구현 계획 생성
4. **Sandbox 구현**: 대상 프로젝트 worktree 생성, Claude Code `/robo-implement <PRO-ID>`로 구현
5. **Validation**: 구조/GWT 검증
6. **Accept / Destroy**: dual merge 및 Neo4j 라이브 데이터 반영 또는 폐기

## 2. 주요 구현 구조

| 영역 | 프런트 | 백엔드 | 비고 |
|---|---|---|---|
| Proposal 목록/상세 | `ProposalsPanel.vue`, `ProposalDetail.vue` | `routes/proposals_crud.py` | 상태 필터, 상세 탭 |
| Detailed DDD 전략 단계 | `StrategicStages.vue`, `StageRunner.vue` | `routes/proposals_staged.py`, `services/stage_runners/*` | Discover/Decompose/Strategize |
| Detailed DDD 전술 단계 | `PlanStages.vue`, `DefineViz.vue`, `TacticalViz.vue` | `services/staged_runner.py` | Connect/Define/Tactical |
| DDD 수렴 | `PlanStages.vue` | `services/staged_consolidate.py` | stageArtifacts → 표준 diff |
| Plan/Impact | `PlanView.vue`, `ImpactMapView.vue` | `routes/proposals_plan.py`, `services/plan_runner.py` | Constitution 필요 시 인터뷰 |
| 구현 | `SandboxProgressView.vue` | `routes/proposals_sandbox.py`, `services/implement_runner.py` | Code 탭 handoff |
| 승인/반영 | `DualMergeView.vue` | `routes/proposals_acceptance.py`, `services/dual_merge.py`, `services/proposal_apply.py` | Git merge + Neo4j 적용 |

## 3. Detailed DDD 검증 시나리오

### S0. 새 Proposal 생성

- Proposals 탭에서 `+ 새 Proposal`.
- 요구사항 입력 후 `상세 DDD` 선택.
- `AI 분석 시작`으로 Proposal 생성.
- 기대:
  - `decompositionMode = DETAILED_DDD`
  - 상태는 `DRAFT`/Intent
  - Scope 분석 후 stage plan 표시

### S1. Scope/Stage Plan

- Scope 분석 결과에서 적용/생략 단계를 확인한다.
- 6단계 전체 검증이 필요하면 `DECOMPOSE`, `CONNECT`도 적용으로 바꾸고 `플랜 확정`.
- 기대:
  - `stagePlan.stages`가 Neo4j에 저장된다.
  - `currentStage`가 첫 활성 stage로 설정된다.

### S2. Discover draft 저장/복원

- Discover 결과가 생성되면 Confirm 전에 새로고침한다.
- 기대:
  - `/stage/{stage}/draft`로 `stageDraftArtifacts.DISCOVER`가 저장된다.
  - 재진입 시 Discover SSE가 재실행되지 않고 draft가 복원된다.
  - Confirm 시 `stageDraftArtifacts.DISCOVER`가 제거되고 `stageArtifacts.DISCOVER`로 승격된다.

### S3. Define UI

- Define stage는 Bounded Context Canvas를 BC별 탭으로 렌더링한다.
- 기대:
  - `장바구니`, `주문` 같은 BC 탭이 표시된다.
  - 한 번에 하나의 BCC만 펼쳐져 스크롤 압박이 줄어든다.

### S4. Tactical UI

- Tactical stage는 Aggregate를 BC별 그룹으로 렌더링한다.
- 기대:
  - `장바구니` 그룹 아래 `Cart`
  - `주문` 그룹 아래 `Order`
  - Aggregate 카드에도 BC 배지가 표시된다.

### S5. DDD 수렴

- Tactical까지 완료 후 `수렴 → Plan 으로`.
- 기대:
  - `strategicDiff`에 BoundedContext뿐 아니라 Feature/UserStory/Process가 생성된다.
  - `tacticalDiff`는 `nodeLabel`, `nodeTitle`, `changeType`, `semanticDiff`를 갖는 표준 schema로 저장된다.
  - 저장 전 tactical 필수 필드 검증이 수행된다.

### S6. Plan Impact Open

- Plan Impact에서 live node id가 없는 신규 diff 항목은 기존 viewer no-op 대신 `Diff 미리보기` modal로 열어야 한다.
- 기대:
  - live id가 있으면 기존 viewer로 이동
  - temp/non-live id 또는 id 없음이면 diff preview modal 표시
- 정적 검증:
  - `ImpactMapView.vue`에서 `Diff 미리보기` 버튼 및 modal 구현
  - `frontend` build 통과

### S7. Sandbox 구현

- Plan 확정 후 `샌드박스 구현`.
- 작업 목록 생성 → `구현하기` → `Claude Code 셀로 이동`.
- 기대:
  - 대상 프로젝트 root가 Code 탭에서 저장되어 있어야 구현 버튼이 활성화된다.
  - worktree가 생성되고 Proposal은 `IMPLEMENTING`으로 전환된다.
  - Code 탭 proposal session에 `/robo-implement <PRO-ID>`가 주입되고 실행된다.
- Code 탭 세부 검증은 [code.md](code.md)의 S7 참고.

### S8. 검증/Accept/라이브 반영

- 구현 checklist 완료 후 `구현 완료 → 검증`.
- 검증 통과 후 `Accept`.
- 기대:
  - Proposal 상태가 `ACCEPTED`.
  - Requirements tree에 BoundedContext/Feature/UserStory가 표시된다.
  - Design/Data에 Aggregate가 BC와 연결되어 표시된다.
  - Accept 전 적용 결과가 비어 있으면 `ACCEPTED`로 전환하지 않는다.

## 4. 수정된 주요 이슈

| # | 심각도 | 이슈 | 조치 | 검증 |
|---|---|---|---|---|
| P1 | ERROR | Discover 확정 전 새로고침 시 재실행 | `stageDraftArtifacts` 저장 + Confirm 승격 | `draftSaved=true`, `confirmPromoted=true` |
| P2 | INFO | Define 단일 긴 폼 | BC별 탭 렌더링 | `장바구니`/`주문` 탭 증거 |
| P3 | INFO | Tactical Aggregate BC 구분 어려움 | BC별 그룹 렌더링 + BC 배지 | `장바구니`/`주문` 그룹 증거 |
| P4 | CRITICAL | DDD 수렴 schema 불일치 | 표준 diff 생성 + validation | Feature/UserStory/Process 및 `tacticalStandard=true` |
| P5 | ERROR | Plan Impact Open no-op | non-live item diff preview modal | build 통과 및 코드 확인 |
| P6 | CRITICAL | Accept 후 라이브 반영 불완전 | 수렴 schema 개선 + Accept 적용 검증 | Accept proof live data |

## 5. 남은 관찰/주의

- 요구사항 밖 도메인 확장(예: 결제)은 이번 수정에서 보류했다. 사용자가 stage feedback으로 조정 가능하다.
- `open-pencil` submodule 상태 변경은 이번 검증 범위 밖이다.
- 브라우저 자동화에서 일반 click이 일부 버튼 이벤트에 닿지 않는 경우가 있어, 검증 중 DOM click을 보조로 사용했다. 사용자 UI에서는 실제 마우스 클릭을 기준으로 재확인 필요.

## 6. 결론

Detailed DDD 경로는 기존의 가장 큰 문제였던 “stage 결과 유실”, “표준 diff 불일치”, “Accept 후 라이브 반영 불완전”을 중심으로 수정됐다. 최종 서브에이전트 리뷰에서는 관련 AC가 모두 만족된 것으로 판정됐다.
