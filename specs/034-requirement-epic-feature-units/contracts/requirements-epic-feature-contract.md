# Contract: Epic / Feature 등록·편집·레이더 필터링

**Feature**: 034-requirement-epic-feature-units | **Date**: 2026-05-30

모든 경로는 기존 requirements 라우터 prefix `/api/requirements` 하위. 모든 신규 엔드포인트는 `/docs` Swagger에 정확한 Pydantic 모델로 노출되어야 한다(개발 워크플로 게이트). 어휘는 Event Storming을 보존 — UI의 "Epic"은 경로상 `bounded-context`로 표현(Constitution II).

## A. 신규 백엔드 엔드포인트

### A1. Feature 편집 — `PATCH /api/requirements/feature`
- **Req**: `FeatureUpdateRequest { featureId, name?, description? }`
- **Res 200**: `FeatureUpdateResponse { feature: FeatureDTO }`
- **동작**: `update_feature()`로 노드 속성만 `SET`. `HAS_FEATURE`/`HAS_USER_STORY` 보존(FR-012).
- **오류**: `404` featureId 미존재 · `422` name 공백(FR-011)
- **충족**: FR-010, FR-011, FR-012

### A2. Epic 생성 — `POST /api/requirements/bounded-context`
- **Req**: `BoundedContextCreateRequest { name, description? }`
- **Res 201**: `BoundedContextCreateResponse { boundedContext: BoundedContextDTO }`
- **동작**: `create_bounded_context()` 래핑(MERGE on key). `key`/`displayName` 서버 도출.
- **오류**: `422` name 공백
- **충족**: FR-002

### A3. Epic 편집 — `PATCH /api/requirements/bounded-context`
- **Req**: `BoundedContextUpdateRequest { boundedContextId, name?, description? }`
- **Res 200**: `BoundedContextUpdateResponse { boundedContext: BoundedContextDTO }`
- **동작**: `update_bounded_context()`로 속성만 `SET`. `HAS_FEATURE` 보존.
- **오류**: `404` 미존재 · `422` name 공백
- **충족**: FR-010, FR-011, FR-012

### A4. Epic AI 제안 — `POST /api/requirements/epic/propose`
- **Req**: `EpicProposeRequest { text }`
- **Res 200**: `EpicProposeResponse { proposals: EpicProposal[] }` (미확정, 그래프 미반영)
- **확정**: 사용자가 후보 선택 → A2(`POST /bounded-context`) 호출
- **폴백**: `proposals` 빈 배열 허용(LLM 실패/0건) → 수동 폼(FR-006)
- **충족**: FR-005, FR-006 / Constitution IV·VI

### A5. Feature AI 제안 — `POST /api/requirements/feature/propose`
- **Req**: `FeatureProposeRequest { text, boundedContextId? }`
- **Res 200**: `FeatureProposeResponse { proposals: FeatureProposal[] }`
- **확정**: 후보 선택 → 기존 `POST /api/requirements/feature`
- **폴백**: 빈 배열 → 수동 폼
- **충족**: FR-005, FR-006

## B. 재사용(변경 없음) 엔드포인트 — 계약 고정

| 엔드포인트 | 용도 | 본 기능 사용처 | 회귀 요건 |
|-----------|------|----------------|-----------|
| `GET /api/requirements/tree` | Epic→Feature→US 트리 | 등록/편집 후 갱신 | 응답 형태 불변 |
| `POST /api/requirements/user-story/propose` `…/confirm` | US 등록 | "+"의 US 단위 | **회귀 0건**(FR-004) |
| `POST /api/requirements/feature` | Feature 생성 | Feature 수동/제안-확정 | 기존 형태 유지 |
| `GET /api/requirements/clarification/clarity?scopeType=&scopeId=` | radar 집계 | Epic/Feature 선택 시 호출 | `scopeType ∈ {project, bounded_context, feature}` 그대로 |

## C. 프런트엔드 UI 계약

### C1. "+" 단위 선택 (`AddRequirementDialog.vue`)
- 진입 시 **Epic / Feature / User Story** 단위 선택 노출(FR-001).
- 각 단위: **AI 제안 탭**(자연어→propose→후보 검토→확정) + **수동 탭**(필드 직접 입력)(FR-005).
- Feature 폼은 소속 Epic 선택, US 폼은 소속 Epic/Feature 선택. US 미지정 시 기존 자동 분류 안내(FR-003, FR-004).
- 닫기/취소 시 그래프 변경 없음(Edge Case).

### C2. 뷰 패널 분기 (`RequirementsPanel.vue` + Detail 컴포넌트)
- `selectedNode.type` 기준 분기: `epic→EpicDetail`, `feature→FeatureDetail`, `userStory→UserStoryDetail`(기존, FR-009).
- `EpicDetail`: 이름·설명·출처 + 하위 Feature 목록/요약 + 명확도 요약(FR-007).
- `FeatureDetail`: 이름·설명·출처 + 하위 User Story 목록/요약(FR-008).
- 빈 하위: 빈 상태 + 하위 추가 CTA(US2-AC4).

### C3. 편집 폼 (`EpicEditForm.vue` / `FeatureEditForm.vue`)
- Detail에서 "편집" 토글. 저장 → A1/A3 호출 → 트리·뷰 즉시 반영, 새로고침 없음(FR-010, SC-004).
- 필수 누락 검증 차단, 취소 시 변경 폐기(FR-011).

### C4. radar 범위 필터링 (`requirements.store.js` + `ClarityRadar.vue`)
- 노드 선택 시 `selectNode(type,id)`가 scope를 도출해 `fetchClarityScores(scopeType, scopeId)` 호출(FR-013, FR-014):
  - epic → `('bounded_context', bc.id)` · feature → `('feature', feature.id)` · 해제/전체 → `('project','*')`.
- 대상 0건이면 radar는 빈/중립 상태(정보), 오류 아님(FR-015).

## D. 비기능/언어
- 신규 라우트는 correlation ID + 단계 로깅(start/decision/error) emit(Constitution VII).
- AI 제안 텍스트 등 LLM 산출물은 사용자 언어 설정(기어 아이콘, 기본=브라우저 로캘)을 따른다(FR-017, 프로젝트 생성 언어 정책).
- 신뢰 모델: 로컬 단일 사용자. 편집 충돌은 정보성 안내(D7).
