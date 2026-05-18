# Phase 1 Contracts: Requirements Tab REST API

신규 라우터: `api/features/requirements/router.py`, prefix `/api/requirements`, tag `requirements`.
모든 엔드포인트는 Swagger `/docs`에 노출되며 Pydantic 모델은 [data-model.md](../data-model.md) §2 참조.

## §1. 트리 조회

### `GET /api/requirements/tree`

Epic(BC) → Feature → UserStory → AcceptanceCriteria 4단계 트리를 단일 응답으로 반환.

- 쿼리 파라미터: 없음 (필요 시 향후 `bc_id` 단위 lazy 확장)
- 200 → `RequirementsTreeDTO`
- Feature 없는 US는 각 Epic의 `unassignedFeature` 버킷, BC도 없는 US는 최상위 `unassigned` 배열.
- AcceptanceCriteria는 `UserStory-[:IMPLEMENTS]->Command-[:HAS_GIVEN|HAS_WHEN|HAS_THEN]->*` 에서 도출. Command 미연결 시 빈 배열.

## §2. Feature CRUD

### `POST /api/requirements/feature`
- body: `FeatureCreateRequest`
- 201 → `FeatureCreateResponse`. `Feature` 노드 + `HAS_FEATURE`(`source='manual'`) 생성.
- 404 → `boundedContextId` 미존재.

### `DELETE /api/requirements/feature`
- body: `FeatureDeleteRequest` (`userStoryDisposition`: `unassign`|`delete`)
- 200 → `FeatureDeleteResponse`. `disposition='unassign'`이면 하위 `HAS_USER_STORY`만 detach(US 잔존), `'delete'`면 하위 US까지 삭제.
- 삭제 후 영향도 분석을 백그라운드 트리거 → `impactReportId` 반환(§6).
- 404 → `featureId` 미존재.

## §3. User Story 추가 — propose / confirm (Human-in-the-Loop)

### `POST /api/requirements/user-story/propose`
- body: `UserStoryProposeRequest` (자연어 `text`)
- 200 → `UserStoryProposeResponse`. **그래프 미변경** — LLM이 분해한 초안 + BC/Feature 제안 + `warnings`.
- 모호 입력 시 `proposals[].unclear=true`, `warnings`에 `requirement_unclear` 등.

### `POST /api/requirements/user-story/confirm`
- body: `UserStoryConfirmRequest` (propose 결과를 사용자가 검토·수정한 값, 또는 수동 직접 입력값)
- 201 → `UserStoryConfirmResponse`. `UserStory` 생성 + `IMPLEMENTS`(BC) + `HAS_USER_STORY`(Feature, `source='manual'`) 연결.
- `boundedContextId`/`featureId`가 null이면 미분류 상태로 생성.
- 생성 후 영향도 분석(중복·충돌 포함) 백그라운드 트리거 → `impactReportId` 반환(§6).

> 수동 입력(역할/행동/효과 직접 작성)은 propose를 건너뛰고 confirm만 호출한다. 자연어 입력은 propose → confirm 2단계 필수(Constitution IV).

## §4. User Story 재배치 / 삭제

### `PATCH /api/requirements/user-story/move`
- body: `UserStoryMoveRequest` (drag-n-drop)
- 200 → `UserStoryMoveResponse`. 기존 `HAS_USER_STORY` detach 후 대상 Feature로 MERGE(`source='manual'`).
- 대상 Feature가 다른 BC 소속이면 US의 `IMPLEMENTS`(BC)도 갱신, `boundedContextChanged=true` + 영향도 분석 트리거.
- 404 → `userStoryId` 또는 `targetFeatureId` 미존재.

### `DELETE /api/requirements/user-story`
- body: `UserStoryDeleteRequest`
- 200 → `UserStoryDeleteResponse`. 삭제 후 영향도 분석 백그라운드 트리거 → `impactReportId`.
- 404 → 미존재.

## §5. 설계 괘적

### `GET /api/requirements/user-story/{id}/design-trace`
- path: User Story id
- 200 → `DesignTraceResponse`. `UserStory-[:IMPLEMENTS]->Command` 기점에서 `HAS_COMMAND`/`EMITS`/`TRIGGERS`/`INVOKES` 체인을 제한 깊이(쿼리 `depth`, 기본 2) BFS 순회한 부분 그래프.
- `nodes`/`relationships`는 Design 탭 캔버스(`/api/graph/expand-with-bc`)와 동일 포맷 → 프런트 Vue Flow 재사용.
- 연결 Command 없음 → `empty=true`, `nodes=[]`.
- 404 → `id` 미존재.

## §6. 영향도 리포트 (비차단)

영향도 분석은 §2~§4의 mutation 응답을 차단하지 않고 백그라운드에서 실행된다. mutation 응답은 `impactReportId`만 즉시 반환하고, 프런트는 아래로 결과를 비차단 수신한다.

### `GET /api/requirements/impact-report/{report_id}`
- 200 → `ImpactReportDTO`. `status`: `running`|`done`|`failed`.
- 프런트는 폴링 또는 SSE 구독(`GET /api/requirements/impact-report/{report_id}/stream`)으로 완료 시 리포트 패널/배지 갱신.
- 분석은 기존 `change_management` 엔진(impact_analysis 4-path traversal, impact_propagation_engine, related_search 중복 탐지)을 재사용.
- `findings` 비어 있으면 프런트는 경고 미표시(FR-020).

## §7. 인제스트 / 삭제 (기존 엔드포인트 재사용 — 신규 아님)

| 엔드포인트 | 변경 |
|-----------|------|
| `POST /api/ingest/upload` | 변경 없음 — 이미 MERGE 기반 증분 upsert. Requirements 탭의 업로드 버튼이 이 엔드포인트 호출 |
| `DELETE /api/ingest/clear-all` | 변경 없음 — Requirements 탭의 별도 "데이터 삭제" 버튼이 호출, 사용자 확인 후 |
| 인제스트 SSE 스트림 | `GROUPING_FEATURES` 페이즈 이벤트 추가(Feature 묶음 진행률 + 카운트) |

**프런트 변경**: `RequirementsIngestionModal.vue`의 업로드 전 기존 데이터 삭제 확인 다이얼로그·`/api/graph/clear` 호출 제거(증분 upsert가 기본). `analyzer` 모드와 동일 흐름.

## §8. 검증 규칙 요약

- `source`: 수동 경로(feature 생성, US move, 수동 confirm)는 항상 `manual`; 인제스트 LLM 경로는 `llm`.
- `HAS_USER_STORY`는 US당 최대 1개 — move/confirm 시 기존 관계 detach 선행.
- propose는 그래프 미변경(읽기/LLM 전용); confirm만 mutation.
- 재인제스트는 `source='manual'` Feature·`HAS_USER_STORY`를 덮어쓰지 않음.

## §9. 인증 / 로깅

- 인증: 기존 프로젝트 세션 정책을 그대로 따름(별도 추가 없음).
- 로깅 카테고리: `requirements.tree.*`, `requirements.feature.*`, `requirements.user_story.*`, `requirements.design_trace.*`, `requirements.impact.*`, `agent.requirements.feature_grouping.*`. 모든 요청에 correlation ID 부착, 페이즈 경계(start/decision/error) 로깅(Constitution VII).
