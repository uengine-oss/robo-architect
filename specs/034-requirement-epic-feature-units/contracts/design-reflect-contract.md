# Contract: 요구사항 변경의 설계 자동 반영 (US7)

**Feature**: 034-requirement-epic-feature-units | **Date**: 2026-05-30

신규 노드 라벨/관계 0건. **미반영 US 판정 = `(UserStory)-[:IMPLEMENTS]->(:Command)` 부재**(design-trace 재사용). 설계 생성은 기존 change_management `plan`→`apply`(propose→apply, HITL) 재사용 — 본 기능은 **식별·프롬프트·오케스트레이션**만 추가(설계 알고리즘 신규 아님).

## A. 백엔드 엔드포인트

### A1. 미반영 US 식별 — `GET /api/requirements/user-stories/pending-design`
- **Query(옵션)**: `scopeType ∈ {project, bounded_context, feature}`, `scopeId`
- **Res 200**: `PendingDesignResponse { pending: PendingUS[] }`
  - `PendingUS { userStoryId, role, action, benefit, featureId, boundedContextId }`
- **동작**: 범위 내 US 중 **어떤 설계객체(Aggregate/Command/Event/Policy/ReadModel)에도 `IMPLEMENTS`로 연결되지 않은** US만 반환. (Command 부재만 보면, 인제스천이 Aggregate엔 배치했지만 Command는 일부만 매핑한 US까지 과대 보고됨 — 특히 조회/알림성. 따라서 Aggregate 등 어떤 설계 연결이라도 있으면 "반영됨"으로 본다.)
- **충족**: FR-030, US7-AC1/AC5

### A2. 설계 반영(제안) — `POST /api/requirements/design/reflect` (SSE)
- **Req**: `DesignReflectRequest { userStoryIds[] }` (사용자가 동의한 미반영 US)
- **Res**: `text/event-stream` — `DesignReflectProgress { userStoryId, phase, percent, changeProposal?, done }`
- **동작**: US별로 기존 `POST /api/change/plan`을 호출해 journey 추가/Aggregate 생성·변경안(`changeProposal`)을 만든다. 진행/부분결과 스트리밍, 취소 가능.
- **부분 실패**: 일부 US 실패해도 나머지 진행, 실패분 표시·재시도(Edge Case).
- **충족**: FR-032, FR-033(생성), Constitution III

### A3. 설계 반영 확정 — 기존 `POST /api/change/apply` 재사용
- **동작**: A2가 만든 `changeProposal`을 사용자 확인 후 그래프 반영(HITL). 기존 설계와의 충돌·영향 표시.
- **충족**: FR-033, US7-AC4

## A'. 설계 커버리지 검증·복구 (인제스천 사후, US7 정확도 보강)

> 핵심 로직 `api/features/ingestion/workflow/post_coverage.py`(인제스천 워크플로 종료 시 best-effort 호출 + 엔드포인트 공유). "고아 US" = Command/ReadModel/Event/Policy 어디에도 `IMPLEMENTS` 없는 US.

### A'1. 검증 리포트 — `GET /api/requirements/design-coverage`
- **Res 200**: `CoverageReport { bcs: CoverageBC[], totalOrphan }` — BC별 `{boundedContextId, name, totalUS, orphanUS, orphanSample}`.
- **용도**: 인제스천 사후 누락 검증 체크리스트. (FR-037)

### A'2. 복구 — `POST /api/requirements/design-coverage/reconcile`
- **Req**: `ReconcileRequest { boundedContextId?, dryRun }`
- **Res 200**: `ReconcileResponse { results: ReconcileResult[], totalLinked, totalUnmapped }`
- **동작**: 고아 US를 LLM이 기존 Command(액션)/ReadModel(조회)에 매핑 → `IMPLEMENTS` 링크. **새 객체 생성 없음**(중복 회피); 환각 이름·미매칭은 `unmapped`로 리포트. `kind`는 무시하고 `targetName`을 실제 객체명에 매칭(LLM kind 혼동 방어). (FR-038)
- **실검증**: MembershipManagement 고아 61 → Command 13 + ReadModel 46 링크, unmapped 4. 전체 63→4. US→ReadModel 0→46.

### A'3. 인제스천 자동 수행
- `ingestion_workflow_runner` 종료 직전 `reconcile_best_effort()` 호출(try/except로 인제스천 비차단). (FR-039)

## B. 프런트 UI 계약

### B1. 탭 진입 훅
- `App.vue`의 탭 전환(`_onSwitchTab`)에서 대상 탭이 **'Event Modeling'(`EventModelingPanel`)** 또는 **'Design'(`CanvasWorkspace`)** 이면 A1 호출.
- `pending`이 비어있지 않으면 `DesignReflectPrompt.vue` 표시: **"설계에 반영하시겠습니까?"**(대상 US 수/목록).
- `pending`이 비면 프롬프트 없이 평소대로 진입(FR-034, US7-AC5).

### B2. 프롬프트 응답
- **예** → A2(SSE) 진행 표시 → 변경안 생성 → A3로 사용자 확인 후 반영(FR-031/032/033).
- **아니오** → 변경 없이 진입. 미반영 상태는 다음 진입 시 재식별(US7-AC3).
- **반복 억제**: "이번 세션 동안 묻지 않기" 제공(FR-034, Edge Case).

## C. 비기능
- 진행 스트리밍·취소(Constitution III); correlation ID 로깅(VII).
- 산출물은 그래프에만 영속(FR-035, Constitution I); 신규 스키마 0건.
- 회귀: 기존 Event Modeling/Design 탭·change-plan/apply 동작 불변(SC-006).
