# Contract: DDD 마법사 & 검증 (US1/US2/US4/US6)

Base: `/api/requirements` (신규 `routes/ddd_wizard.py`, `routes/pivotal_events.py`). SSE는 `EventSourceResponse`(child_story_generation 패턴).

## 마법사 — US1/US4

### `POST /ddd-wizard/start`
프로파일링 답변으로 추천 단계 조합 산출.
- Req: `WizardStartRequest{scope, epicId?, profile, engine?}`
- Res: `WizardStartResponse{sessionId, recommendedPlan}`
- 409 `local_tooling_unavailable` (engine=claude-ide 미설치).

### `GET /ddd-wizard/{sessionId}/step/{stepKey}/stream` (SSE)
한 단계 실행 — 질문 제시 + 추론 스트림 + 산출물 초안 + 그래프 변경안.
- 이벤트: `reasoning`, `step_started`, `artifact`(markdown), `proposal`(GraphChangePreview[]), `done`, `error`.

### `POST /ddd-wizard/{sessionId}/answer`
사용자 답변 또는 붙여넣은 문서 제출 → 다음 추론 입력.
- Req: `WizardAnswerRequest`

### `POST /ddd-wizard/{sessionId}/step/{stepKey}/confirm`
단계 산출물의 그래프 반영(propose→confirm).
- Req: `WizardConfirmRequest{acceptedChangeIds[]}` → Res: `WizardConfirmResponse`
- 빈 목록 → 무변경(FR-016).

### `GET /ddd-wizard/{sessionId}`
세션 상태/완료 단계/산출물 조회(재개용, FR-020).

### `GET /local-tooling/status`
재사용(spec 034) — claude/speckit/ddd-starter preflight.

## 피보탈 이벤트 — US2

### `POST /pivotal-events/toggle`
- Req: `PivotalToggleRequest{eventId, pivotal?, hotspot?}` → Res: `PivotalToggleResponse`

### `POST /ddd-wizard/{sessionId}/subdomains/propose`
피보탈 경계로 서브도메인(BC 후보) 산출.
- Res: `SubdomainProposal[]` (확정은 기존 `POST /bounded-context`).

## DDD 검증 — US6 (재사용)
- `POST /validate` (spec 034 `ddd_validation`) — 마법사 단계 게이트에서 비차단 호출.

## 재사용(신규 아님)
- `GET /tree`, `POST /bounded-context`(BC 후보 확정), `POST /user-story/propose|confirm`, `POST /change/plan`·`/change/apply`.

## UI 배선
- `DddWizardPanel.vue`: "맨땅 시작"(요구사항 비어있을 때) + 에픽 추가 다이얼로그에서 진입. `AskUserQuestion` 식 프로파일링 4문항 → 단계 체크리스트 → EventSource로 단계 진행.
