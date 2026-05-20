# Implementation Plan: Requirements Tab

**Branch**: `026-requirements-tab` | **Date**: 2026-05-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/026-requirements-tab/spec.md`

## Summary

기획자 전용 "Requirements" 탭을 기존 탭 목록 맨 앞에 추가한다. 좌측 트리는 Epic(BoundedContext) → Feature → User Story → Acceptance Criteria(GWT) 4단계 드릴다운을 제공하고, User Story 선택 시 본문과 인수조건을 표시하며 연결된 Command의 설계 괘적을 탭 내부 캔버스에 임베드 렌더링한다. 신규 요구사항은 문서 업로드(증분 upsert) 또는 자연어 입력으로 추가하며, 자연어 입력은 LLM 분해 결과를 검토 후 확정한다. User Story drag-n-drop 재배치, Feature/User Story 삭제, 추가·삭제 시 백그라운드 비차단 영향도 분석을 지원한다.

기술 접근: 온톨로지에 `Feature` 노드 타입과 `HAS_FEATURE`/`HAS_USER_STORY` 관계를 신규 도입하고, 인제스트 워크플로에 BC 분류 직후 동작하는 `feature_grouping` 페이즈를 추가한다. 백엔드는 `api/features/requirements/` 신규 feature 모듈(라우터 prefix `/api/requirements`)로, 프런트는 `frontend/src/features/requirements/`로 구성한다. 영향도 분석은 기존 `api/features/change_management`(spec 004)의 impact 엔진을 재사용·확장한다. 캔버스 괘적은 기존 Design 탭의 Vue Flow 렌더링 컴포넌트를 재사용한다.

## Technical Context

**Language/Version**: Python 3.11+ (backend), JavaScript / Vue 3 (frontend)
**Primary Dependencies**: FastAPI, LangChain + LangGraph, Neo4j 공식 드라이버; Vue 3 + Vite, Vue Flow, EventSource(SSE)
**Storage**: Neo4j (단일 진실 원천 — `api/platform/neo4j.py` 경유)
**Testing**: pytest (backend), Playwright (frontend `frontend/tests/`)
**Target Platform**: Linux/macOS 서버 + 브라우저 SPA
**Project Type**: Web application (frontend + backend, 미러 구조)
**Performance Goals**: User Story 클릭 → 괘적 캔버스 렌더 2초 이내(SC-003); 트리 드릴다운 탐색 5초 이내(SC-001)
**Constraints**: 증분 upsert로 기존 데이터 100% 보존(SC-004); 영향도 분석은 사용자 작업을 차단하지 않는 백그라운드 실행(FR-019)
**Scale/Scope**: 신규 탭 1개, 신규 백엔드 feature 1개(~6 엔드포인트), 신규 인제스트 페이즈 1개, 신규 노드 타입 1개 + 관계 2개, 프런트 신규 feature 폴더 1개

## Constitution Check

*GATE: Phase 0 이전 통과 필수, Phase 1 이후 재확인.*

| 원칙 | 평가 | 결과 |
|------|------|------|
| I. Graph-as-Source-of-Truth | `Feature`·소속 관계 모두 Neo4j에 영속; 병렬 저장소 없음. Requirements 탭은 그래프의 투영. | ✅ Pass |
| II. Event Storming 어휘 | "Epic/Feature/User Story"는 Agile 어휘이나, 온톨로지에 이미 `Requirement`·`UserStory`(Agile 계층)가 존재. `Feature`는 그 계층의 그룹 단위로 일관됨. 설계 노드(Command/Event/Policy)는 기존 어휘 유지. | ✅ Pass (note) |
| III. Streaming-First UX | 인제스트(feature_grouping 포함)는 기존 SSE 페이즈 스트림으로 진행률 노출. 영향도 분석은 백그라운드 작업으로 비동기 실행 + 결과 폴링/푸시. | ✅ Pass |
| IV. Human-in-the-Loop on Mutations | 자연어 입력은 LLM이 User Story를 분해 → **propose(초안) → 사용자 확정 → persist**. 수동 입력(역할/행동/효과 직접 작성)은 직접 저장. 데이터 명시 삭제는 별도 버튼 + 확인 절차. | ✅ Pass |
| V. Feature-Modular Architecture | 백엔드 `api/features/requirements/`, 프런트 `frontend/src/features/requirements/` 미러. 교차 의존은 platform·Neo4j·change_management 라우터 경유. | ✅ Pass |
| VI. Provider-Agnostic LLM | feature_grouping·자연어 분해 모두 기존 `ingestion_llm_runtime` 추상화 사용; 프로바이더 하드코딩 없음. | ✅ Pass |
| VII. Observable by Default | 신규 로그 카테고리 `requirements.*`, 페이즈 경계 로깅, correlation ID 부착. | ✅ Pass |
| VIII. Figma SceneGraph Pipeline | 해당 없음(SerializedSceneGraph 생성 없음). | ✅ N/A |
| IX. Plugin ↔ Backend Dev-Loop | 해당 없음(Figma 플러그인 비관여). | ✅ N/A |

**개발 워크플로 게이트**: 신규 노드/관계는 `docs/cypher/schema/03_node_types.cypher`·`04_relationships.cypher`에 코드 이전 반영(Phase 1 data-model.md에서 정의, 구현 시 동시 반영). 신규 엔드포인트는 Swagger `/docs`에 노출. 프런트/백엔드 미러 폴더 동일 PR 생성.

위반 없음 — Phase 0 진행 가능.

## Project Structure

### Documentation (this feature)

```text
specs/026-requirements-tab/
├── plan.md              # 이 파일
├── research.md          # Phase 0 산출물
├── data-model.md        # Phase 1 산출물
├── quickstart.md        # Phase 1 산출물
├── contracts/           # Phase 1 산출물
│   └── rest-api.md
├── checklists/
│   └── requirements.md  # /speckit-specify 산출물
└── tasks.md             # /speckit-tasks 산출물 (이 명령에서 생성 안 함)
```

### Source Code (repository root)

```text
api/
├── features/
│   ├── requirements/                      # 신규 feature 모듈
│   │   ├── __init__.py
│   │   ├── router.py                      # prefix /api/requirements
│   │   ├── routes/
│   │   │   ├── requirements_tree.py        # Epic→Feature→US 트리 조회
│   │   │   ├── feature_crud.py             # Feature 생성/삭제
│   │   │   ├── user_story_crud.py          # US 생성(수동/NL propose·confirm)/삭제/재배치
│   │   │   └── design_trace.py             # US→Command 설계 괘적 서브그래프
│   │   ├── requirements_contracts.py       # Pydantic DTO
│   │   ├── tree_service.py                 # 트리 집계 Cypher
│   │   ├── feature_grouping_llm.py         # 자연어 입력 분해 + Feature 분류
│   │   └── impact_hook.py                  # change_management 영향도 분석 트리거(백그라운드)
│   ├── ingestion/
│   │   ├── workflow/phases/
│   │   │   └── feature_grouping.py          # 신규 페이즈 — BC 분류 직후 Feature 묶음
│   │   └── event_storming/neo4j_ops/
│   │       └── features.py                  # Feature 노드 + HAS_FEATURE/HAS_USER_STORY upsert
│   └── change_management/                  # 기존 — impact 엔진 재사용·확장
│
docs/cypher/schema/
├── 03_node_types.cypher                    # Feature 노드 정의 추가
├── 04_relationships.cypher                 # HAS_FEATURE / HAS_USER_STORY 추가
├── 01_constraints.cypher                   # Feature.id / Feature.key 제약 추가
└── 02_indexes.cypher                       # Feature 인덱스 추가

frontend/
├── src/
│   ├── App.vue                             # tabComponents 에 Requirements 추가
│   ├── app/layout/TopBar.vue               # tabs 배열 맨 앞 Requirements
│   └── features/
│       ├── requirements/                    # 신규 feature 폴더
│       │   ├── ui/
│       │   │   ├── RequirementsPanel.vue     # 탭 루트 (트리 + 상세 + 임베드 캔버스)
│       │   │   ├── RequirementsTree.vue      # Epic→Feature→US→AC 드릴다운 + drag-n-drop
│       │   │   ├── UserStoryDetail.vue       # "As a..I want..so that.." + 인수조건
│       │   │   ├── DesignTraceCanvas.vue     # Design 캔버스 컴포넌트 재사용 래퍼
│       │   │   ├── AddRequirementDialog.vue  # 문서/자연어 추가 + NL propose 검토
│       │   │   └── ImpactReportPanel.vue     # 비차단 영향도 리포트
│       │   └── requirements.store.js
│       └── requirementsIngestion/
│           └── ui/RequirementsIngestionModal.vue  # 자동 삭제 로직 제거(증분 upsert)
└── tests/
    └── requirements-tab.spec.ts             # Playwright 시나리오
```

**Structure Decision**: 기존 `api/features/<feature>/` + `frontend/src/features/<feature>/` 미러 구조(원칙 V)를 따라 `requirements` feature를 양쪽에 신설한다. 인제스트 페이즈·neo4j_ops는 기존 `ingestion` feature 안에 추가하고, 영향도 분석은 기존 `change_management` feature를 재사용한다. 캔버스 괘적은 Design 탭의 Vue Flow 컴포넌트를 재사용 래핑한다.

## Complexity Tracking

> Constitution Check 위반 없음 — 작성 불필요.
