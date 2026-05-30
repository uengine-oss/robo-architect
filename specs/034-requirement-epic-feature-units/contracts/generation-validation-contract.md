# Contract: 하위 US 자동 생성(US5) · DDD 적합성 검증(US6)

**Feature**: 034-requirement-epic-feature-units | **Date**: 2026-05-30

prefix `/api/requirements` (별도 표기 제외). 모든 LLM 산출물은 제안→확인(Constitution IV), 장시간 작업은 SSE 진행(Constitution III). 신규 노드 라벨/관계 0건 — 영속은 기존 UserStory 경로 재사용.

## A. 하위 User Story 자동 생성 (US5)

### A1. 생성(제안) — `POST /api/requirements/{scopeType}/{scopeId}/generate-stories` (SSE)
- `scopeType ∈ {epic, feature}`; `scopeId` = bcId | featureId
- **Req**: `GenerateChildStoriesRequest { engine? }` (engine 생략 시 Settings 기본값 사용)
- **Res**: `text/event-stream` — `GenerateChildStoriesProgress { phase, percent, partial[], done }`. 최종 이벤트에 전체 `GeneratedStory[]`.
- **engine 분기**:
  - `in-process`: spec 008 `run_user_story_planning()`를 Epic/Feature 컨텍스트로 호출.
  - `claude-ide`: A3 preflight 통과 시 로컬 `claude`로 speckit-specify/robo 스킬 실행 → MCP로 그래프 컨텍스트 사용.
- **취소**: 클라이언트 연결 종료 또는 취소 신호 → 진행 중단(FR-022).
- **폴백**: 후보 0건/실패 → 빈 결과 + 안내, 수동 추가 경로 유지(FR-023).
- **충족**: FR-018, FR-019(제안), FR-022, FR-023

### A2. 확정 — `POST /api/requirements/child-stories/confirm`
- **Req**: `ConfirmChildStoriesRequest { scopeType, scopeId, selected[] }`
- **Res 200**: `ConfirmChildStoriesResponse { created: UserStoryDTO[] }`
- **동작**: 사용자가 고른 후보만 기존 UserStory 영속 경로로 저장(미선택 시 무반영, FR-019). 저장 후 트리 갱신.
- **충족**: FR-019, US5-AC1/AC5

### A3. 로컬 도구 점검 — `GET /api/requirements/local-tooling/status`
- **Res 200**: `LocalToolingStatus { claudeInstalled, speckitInstalled, missing[], installHint }`
- **동작**: `shutil.which("claude")` + speckit/robo-spec 스킬 존재 점검(현재 미구현 → 신규). engine=`claude-ide`에서 생성 전 호출.
- **미설치 시 UI**: 생성 차단 + 설치 안내 표시(FR-021).
- **충족**: FR-021, US5-AC3

### Settings — 엔진 토글
- **프런트**: `SettingsPanel.vue`에 `requirementGenerationEngine: 'in-process' | 'claude-ide'` 노출(Pinia 저장).
- **Electron**: `DesktopSettings.requirementGenerationEngine`(`ipc-contract.ts`) 추가 + 마이그레이션 기본값 `'in-process'`.
- **충족**: FR-020, SC-008

## B. DDD 적합성·입도·spec 정합성 검증 (US6)

### B1. 검증 — `POST /api/requirements/validate`
- **Req**: `ValidateRequest { targetType, target, mode }`
- **Res 200**: `ValidateResponse { ok, findings[], source }`
  - `findings[].kind ∈ {wrong_bc, oversized_feature, spec_conflict}`, 각 `suggestion: CorrectionProposal`.
  - `ok=true` ⇔ findings 비어있음(FR-028 통과).
- **경로 분기**:
  - `in-process`: 백엔드 에이전트가 그래프(BC/Feature/US)+기존 spec으로 검증.
  - `claude-ide`/스킬: robo-spec `robo-validate` 스킬(또는 speckit-specify override)이 MCP 툴로 컨텍스트 조회 후 동일 스키마 산출.
- **비차단**: warning이어도 사용자 강행 허용. 단 정의된 BC 0건이면 BC 선행 요구(FR-028, Edge Case).
- **충족**: FR-024, FR-025, FR-026, FR-027, FR-028, SC-009

### B2. 검증 스킬 자산 (robo-spec)
- **신규**: `skills/robo-spec/robo-validate/SKILL.md` — `extends: speckit-specify`(override) 또는 독립 스킬. 입력: 추가/생성 대상 + BC 목록 + 기존 spec. 출력: `ValidationFinding[]`.
- **설치**: 기존 `_install_robo_spec()`(`claude_code/router.py:340`)가 워크스페이스 `.claude/skills/`로 복사하는 경로에 포함.
- **데이터 접근**: robo-spec MCP(`/mcp`) 툴 — `list_design_elements`(BC 목록), `get_bc_design`(BC 설계), `resolve_design_element`. 필요 시 기존 spec 컨텍스트 제공 툴 확장.
- **충족**: FR-027, US6-AC4

## C. 트리거 지점 (UI)
- Epic/Feature **확정 직후** A1 자동 호출(하위 US 제안) — `GeneratedStoriesReview.vue`로 검토→A2 확정.
- 등록/생성 **이전 또는 직후** B1 호출 — `ValidationFindings.vue`로 교정안 표시→사용자 확인.
- 비기능: correlation ID 로깅(Constitution VII); LLM 산출물은 사용자 언어 설정 준수(FR-017).
