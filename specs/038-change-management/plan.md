# Implementation Plan: Requirement Change Management

**Branch**: `038-change-management` | **Date**: 2026-06-02 | **Spec**: [spec.md](spec.md)

## Summary

RequirementChange(CHG-NNN) Neo4j 노드와 EFFECT 관계를 도입하여 요구사항 변경 이력을 그래프로 추적하고, DRAFT→SUBMITTED→APPROVED→IMPLEMENTED 승인 워크플로우를 거쳐 `robo-change-tasks` 스킬 PTY 호출로 구현 태스크를 생성·추적한다. `api/features/requirement_changes/` 백엔드 + `ChangesPanel.vue` 프런트엔드 + SSE 스트리밍 + 회귀 테스트 영향도 분석.

## Technical Context

**Language/Version**: Python 3.11 (backend), Vue 3 + Vite (frontend)

**Primary Dependencies**: FastAPI, Neo4j driver, sse_starlette, Pydantic v2 (backend) / Vue 3, Pinia, EventSource API (frontend)

**Storage**: Neo4j 4.4+/5.x — `RequirementChange`, `ChangeSet` 신규 노드; `EFFECT`, `CONTAINS` 신규 관계

**Testing**: pytest (backend), Playwright (e2e frontend)

**Target Platform**: Linux server + Vue 3 SPA (browser)

**Project Type**: Web application (FastAPI backend + Vue 3 frontend)

**Performance Goals**: Change 목록 로딩 2초 이내(100건 기준), EFFECT 분석 결과 30초 이내

**Constraints**: SSE 필수(Constitution III), 자기 승인 방지, 기존 `/api/change/*` 엔드포인트 회귀 없음

**Scale/Scope**: Change 레코드 수백~수천 건, 팀 규모 10명 이내

## Constitution Check

| 원칙 | 상태 | 비고 |
|------|------|------|
| I — Graph SOT | ✅ PASS | 모든 Change·ChangeSet·EFFECT·이력이 Neo4j 저장 |
| II — DDD 어휘 | ✅ PASS | BoundedContext·Aggregate·UserStory·EFFECT 용어 사용 |
| III — Streaming-First | ✅ PASS | impact-analyze·implement 모두 SSE (sse_starlette) |
| IV — Human-in-Loop | ✅ PASS | APPROVED 전 구현 불가. 삭제 시 IMPLEMENTED 상태 차단 |
| V — Feature-Modular | ✅ PASS | `api/features/requirement_changes/` 독립 모듈 |
| VI — Provider-Agnostic LLM | ✅ PASS | 직접 LLM 호출 없음; 스킬(robo-change-*)이 담당 |
| VII — Observable | ✅ PASS | SmartLogger + correlation ID 각 상태 전이 |
| X — Skill-First | ✅ PASS | robo-change-specify·tasks 스킬 PTY 호출; LangChain/LangGraph 신규 코드 없음 |

## Project Structure

### Documentation (this feature)

```text
specs/038-change-management/
├── plan.md              # 이 파일
├── research.md          # Phase 0: D1–D12 결정
├── data-model.md        # Phase 1: Neo4j 노드·관계 + Pydantic 스키마
├── quickstart.md        # Phase 1: Q1–Q10 검증 시나리오
├── contracts/
│   ├── changes-api-contract.md    # REST API 계약
│   ├── frontend-contract.vue-contract.md  # 컴포넌트·스토어
│   └── skills-contract.md         # Skill 인터페이스
└── tasks.md             # Phase 2: /speckit-tasks 생성 (미생성)
```

### Source Code

```text
# Backend
api/features/requirement_changes/
├── __init__.py
├── router.py                          # /api/requirement-changes prefix
├── requirement_changes_contracts.py   # Pydantic 모델
├── routes/
│   ├── __init__.py
│   ├── changes_crud.py           # POST/GET/DELETE Change
│   ├── changes_approval.py       # submit/approve/reject
│   ├── changes_impact.py         # GET impact, POST analyze-impact (SSE)
│   ├── changes_tasks.py          # GET preflight, POST implement (SSE)
│   └── changes_changeset.py      # ChangeSet CRUD·승인
└── services/
    ├── __init__.py
    ├── change_id_generator.py    # CHG-NNN 자동 증가
    ├── effect_analyzer.py        # EFFECT 관계 생성 (직접/AI 분기)
    ├── skill_runner.py           # PTY 스킬 실행 + SSE 프록시
    └── regression_analyzer.py   # 회귀 테스트 그래프 트래버설

# Skills (SKILL.md 파일)
skills/robo-changes/
├── robo-change-specify/SKILL.md  # extends: speckit-specify
├── robo-change-plan/SKILL.md     # extends: speckit-plan
└── robo-change-tasks/SKILL.md    # extends: speckit-tasks

# Neo4j Schema
docs/cypher/schema/
├── 03_node_types.cypher          # RequirementChange, ChangeSet 노드 추가
└── 04_relationships.cypher       # EFFECT, CONTAINS 관계 추가

# Frontend
frontend/src/features/requirements/ui/
├── ChangesPanel.vue              # 신규: Changes 탭 메인 패널
├── ChangeDetail.vue              # 신규: Change 상세·승인 버튼
├── ChangeImpactView.vue          # 신규: EFFECT 시각화
├── ChangeTasksView.vue           # 신규: SSE 구현 진행 표시
├── ChangeUSProposals.vue         # 신규: 영향받는 US 목록
├── ChangeDesignPlan.vue          # 신규: 설계 변경 계획 표시
├── RequirementsPanel.vue         # 수정: Changes 탭 추가
├── UserStoryDetail.vue           # 수정: 저장 시 DIRECT_EDIT Change 생성
└── EpicDetail.vue                # 수정: 저장 시 DIRECT_EDIT Change 생성

frontend/src/features/requirements/
└── requirements.store.js          # 수정: 신규 Change 관련 액션 추가

# API 등록
api/main.py                        # 수정: requirement_changes 라우터 등록
```

## Phase Progress

- Phase 0 Research ✅ — D1(기존 코드 공존), D2(CHG-NNN ID), D3(EFFECT 방향), D4(상태 전이), D5(자기 승인 방지), D6(ChangeSet), D7(스킬 호출), D8(EFFECT 분석 전략), D9(회귀 테스트 트래버설), D10(데이터 초기화), D11(Frontend 탭), D12(선행 Change 처리) 결정 완료.
- Phase 1 Design ✅ — data-model.md, 3 contracts(API/Frontend/Skills), quickstart.md 작성 완료.
- Phase 2 Tasks ⏸ — `/speckit-tasks` 대기.

## Complexity Tracking

| 항목 | 비고 |
|------|------|
| 신규 Neo4j 노드 2개 | RequirementChange(교체), ChangeSet(신규) — Constitution I 준수 |
| 신규 관계 2개 | EFFECT, CONTAINS — Constitution I 준수 |
| 기존 코드 공존 | `change_management/`(OLD) 유지 + `requirement_changes/`(NEW) 병렬 |
| SSE 2곳 | impact-analyze, implement — Constitution III 준수 |
