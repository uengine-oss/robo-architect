# Implementation Plan: Requirements Clarification Agent — 추출된 요구사항을 딥 에이전트로 명확화

**Branch**: `030-requirements-clarify-agent` | **Date**: 2026-05-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/030-requirements-clarify-agent/spec.md`

## Summary

문서 인제스트가 요구사항을 추출해 Requirements 탭의 요구사항 트리(BoundedContext → Feature → UserStory)에 채운 뒤에도, 추출된 UserStory는 모호하거나 미명세인 경우가 잦다 — 그 공백은 설계·구현 단계에서 비싸게 드러난다. 본 기능은 SpecKit `clarify` 스킬의 방법론(모호성 분류 체계 스캔 → 우선순위 질문 큐 → 답변의 증분 인코딩)을 **LangChain 딥 에이전트**로 자동화해, 추출 직후 요구사항을 대화형으로 명확화한다.

흐름: 아키텍트가 Requirements 탭에서 범위(프로젝트 / BoundedContext / Feature)를 선택해 "요구사항 명확화"를 실행하면 — (US1) 딥 에이전트가 범위 내 모든 UserStory를 자율 다단계로 스캔해 분류 체계별 모호성을 찾고, 영향받는 요구사항·범주·추천 답변이 연결된 우선순위 질문 큐(최대 5개)를 만든다. (US2) 질문은 한 번에 하나씩, 추천 답변·선택지와 함께 제시되고, 아키텍트가 답하면 에이전트가 그 답을 영향받는 UserStory의 구체적 편집안으로 인코딩한다 — 편집안은 *제안*만 되고(`/answer`), 아키텍트가 before/after를 검토 후 *적용*을 명시적으로 누를 때만(`/apply`) 그래프에 반영된다. (US3) 세션 종료 시 변경된 요구사항을 before/after로 보여주는 요약과, 개별 변경 되돌리기, 그리고 범위에 영구 부착되는 명확화 로그를 제공한다.

기술 접근: 신규 코드는 기존 `api/features/requirements/` feature 안의 sub-package `clarification_agent/`와 라우트 파일 `routes/clarification.py`로 들어간다 (`change_management/planning_agent/` 선례와 동형). 모호성 스캔은 LangChain **`deepagents`** 런타임으로 구동하는 자율 딥 에이전트가 담당하고, 답변 인코딩은 좁은 범위의 structured-output LLM 호출이 담당한다 — 두 경로 모두 모델을 `get_llm()`에서 받아 provider-agnostic(원칙 VI). 진행 중 세션은 in-memory 스토어에 두고(impact report `_REPORTS`·인제스트 세션·change-planning `MemorySaver` 선례), 영구 명확화 로그는 신규 Neo4j 노드 라벨 없이 `UserStory.clarifications` 속성에 저장한다. 인코딩된 편집의 그래프 반영은 기존 `user_story_edit_service.apply_user_story_edit()`를 재사용해 낙관적 잠금·no-op 감지·임팩트 분석 트리거를 자동 승계한다. 장시간 스캔은 SSE로 진척을 스트리밍한다(요구사항 feature의 `impact_report.py` 스트림 선례 재사용).

## Technical Context

**Language/Version**: Python 3.11+ (backend, 딥 에이전트), JavaScript / Vue 3 (frontend)
**Primary Dependencies**: FastAPI, Neo4j 공식 드라이버, LangChain + LangGraph (기존); **신규** `deepagents` (LangChain 딥 에이전트 런타임 — LangGraph 위에 계획·서브에이전트·가상 파일시스템을 얹은 패키지); SSE는 Starlette `StreamingResponse`(`text/event-stream`); Vue 3 + Vite + Pinia
**Storage**: Neo4j (도메인 모델 — 단일 진실 원천, `api/platform/neo4j.py` 경유). 요구사항은 기존 `UserStory` 노드에서 제자리 편집된다. 영구 명확화 로그는 신규 노드 라벨 없이 `UserStory.clarifications`(JSON 인코딩 배열) 속성에 저장. 진행 중 세션 상태는 in-memory(프로세스 수명 범위 — impact report·인제스트 세션 선례)
**Testing**: pytest (backend — 딥 에이전트 모호성 스캔, 답변 인코더, 세션 수명주기, 벤치마크 요구사항 세트 기반 모호성 탐지율), Playwright (`frontend/tests/`)
**Target Platform**: Linux/macOS 서버 + 브라우저 SPA
**Project Type**: Web application (frontend + backend 미러 — 둘 다 기존 `requirements` feature 폴더 확장)
**Performance Goals**: 분석 단계 첫 진척 SSE 이벤트 2초 이내; UserStory ≤25개 범위의 전체 명확화 세션(시작→요약)이 SC-002 10분 예산 내; 답변당 인코딩 제안 10초 이내; 세션당 질문 상한 5개(FR-004)
**Constraints**: 세션당 질문 ≤5(FR-004); LLM 생성 편집은 답변별 사용자 명시 확인 없이 그래프에 반영 금지(원칙 IV / FR-008 — `/answer` 제안 → `/apply` 적용 분리); 신규 Neo4j 노드 라벨/관계 0건; 모든 실패 경로에서 이미 적용된 답변 보존(FR-013); 인코딩된 답변은 무효화된 요구사항 텍스트를 *치환*하고 중복 생성 금지(FR-008); 모호성 없음 경로는 질문 0개로 깨끗이 종료(FR-011)
**Scale/Scope**: 기존 `api/features/requirements/` 내 신규 sub-package 1개(딥 에이전트 분석 + 답변 인코더 + in-memory 세션 스토어 + 로그 액세서), 신규 REST 엔드포인트 ~9개(`/api/requirements/clarification/*`, SSE 1개 포함), `UserStory` 신규 속성 1개(`clarifications`), 프런트 신규 컴포넌트 2개 + 트리/패널/스토어 확장. 신규 Python 의존성 1개(`deepagents`). 신규 Neo4j 노드/관계 0건.

## Constitution Check

*GATE: Phase 0 이전 통과 필수, Phase 1 이후 재확인.*

| 원칙 | 평가 | 결과 |
|------|------|------|
| I. Graph-as-Source-of-Truth (NON-NEGOTIABLE) | 명확화는 `UserStory`를 Neo4j에서 읽고, 인코딩된 편집을 기존 `user_story_edit_service.apply_user_story_edit()` 경로로 다시 Neo4j에 쓴다 — 그래프가 단일 진실 원천으로 유지된다. 영구 명확화 로그는 `UserStory.clarifications` 속성으로 그래프 *안*에 산다. 진행 중 세션 상태(질문 큐·현재 인덱스·딥 에이전트 체크포인트)는 *모델 상태*가 아닌 일시적 프로세스 상태이며, impact report `_REPORTS`·인제스트 세션·change-planning `MemorySaver`와 동일하게 in-memory에 둔다 — 그래프에 병렬 복제하지 않으므로 두 번째 진실 원천을 만들지 않는다. | ✅ Pass (note) |
| II. Event Storming 어휘 | 범위 종류는 `bounded_context`·`feature`·`project`로 기존 온톨로지 라벨과 일치하고, 명확화 대상은 `UserStory`다. 신규 용어("clarification"·"ambiguity")는 도메인 엔티티가 아니라 *프로세스*를 가리키므로 CRUD 명명 회피 원칙과 충돌하지 않는다. | ✅ Pass |
| III. Streaming-First UX | 분석 단계(딥 에이전트의 다단계 LLM 스캔)는 수 초~수십 초가 걸리므로 SSE로 스트리밍한다 — `GET /sessions/{id}/stream`, 요구사항 feature의 `impact_report.py` `StreamingResponse text/event-stream` 선례 재사용. 답변당 인코딩 진척도 같은 SSE 채널로 노출. 질문 응답 루프 자체(`/answer`·`/apply`)는 즉시 완료되는 그래프 질의/뮤테이션이므로 요청/응답 적합. | ✅ Pass |
| IV. Human-in-the-Loop on Mutations | 명확화 편집은 LLM이 생성하므로 propose/apply 분리: `POST /answer`는 인코딩된 편집안을 *제안*만 하고(그래프 뮤테이션 0건), `POST /apply`는 아키텍트가 before/after diff를 검토한 뒤 명시적으로 호출할 때만 적용한다 — `/api/change/plan`+`/api/change/apply` 선례와 동형. 세션 종료 요약 + 변경별 되돌리기(FR-010)가 추가 안전망. 모호성 스캔 자체는 그래프에 대해 읽기 전용. | ✅ Pass (note) |
| V. Feature-Modular Architecture | 백엔드는 신규 feature가 아니라 기존 `api/features/requirements/` 안의 sub-package `clarification_agent/` + `routes/clarification.py`로 들어간다(`change_management`가 `planning_agent/`를 품는 선례와 동형) — 명확화는 요구사항 feature의 한 능력이지 별도 도메인이 아니다. 프런트도 기존 `frontend/src/features/requirements/`를 확장한다. 교차 feature 의존은 platform(`get_llm`·`neo4j`)과 동일 feature 내 서비스 재사용뿐. | ✅ Pass |
| VI. Provider-Agnostic LLM | 딥 에이전트와 답변 인코더 모두 모델을 `get_llm()`(요구사항 feature가 이미 쓰는 `ingestion_llm_runtime.get_llm()` 경유 — 토큰 집계 승계)에서 받는다. provider/model 하드코딩 없음. `deepagents`는 LangChain chat model을 주입받으므로 추상화를 깨지 않는다. | ✅ Pass |
| VII. Observable by Default | 신규 로그 카테고리 `requirements.clarification.*`(분석 시작·질문 큐 준비·답변 인코딩·적용·되돌리기·오류), correlation ID 부착, 페이즈 경계 로깅. | ✅ Pass |
| VIII. Figma SceneGraph Pipeline (NON-NEGOTIABLE) | 해당 없음 — `SerializedSceneGraph` 생성 없음. | ✅ N/A |
| IX. Plugin ↔ Backend Dev-Loop | 해당 없음 — Figma 플러그인 비관여. `deepagents` 설치·Claude Code 재기동 등 개발 환경 절차는 quickstart 런북에 별도 명시. | ✅ N/A |

**개발 워크플로 게이트**: 신규 Neo4j 노드 라벨/관계 타입 **없음** — 명확화 로그는 기존 `UserStory` 노드의 신규 *속성* `clarifications`로만 저장된다. 새 라벨이 아니라 속성 추가이므로 `04_relationships.cypher`는 변경 불필요하고, `docs/cypher/schema/03_node_types.cypher`의 `UserStory` 정의에 `clarifications` 속성을 문서화한다(워크플로 규칙 준수). 신규 REST 엔드포인트 ~9개는 Swagger `/docs`에 노출, README API 요약의 `/api/requirements` 항목에 명확화 하위 경로를 추가한다. 신규 Python 의존성 `deepagents`는 `pyproject.toml`에 추가한다(저장소에 `requirements.txt`는 없음 — `uv` 단일 툴체인). 프런트 UI는 기존 Requirements 탭 확장이므로 미러 규칙 충족.

위반 없음 — Phase 0 진행 가능. (Phase 1 설계 후 재확인: 아래 "Post-Design Constitution Re-Check" 참조.)

## Project Structure

### Documentation (this feature)

```text
specs/030-requirements-clarify-agent/
├── plan.md              # 이 파일
├── research.md          # Phase 0 산출물 (R1~R9)
├── data-model.md        # Phase 1 산출물
├── quickstart.md        # Phase 1 산출물
├── contracts/           # Phase 1 산출물
│   └── rest-and-agent.md
├── checklists/
│   └── requirements.md  # /speckit-specify 산출물
└── tasks.md             # /speckit-tasks 산출물 (이 명령에서 생성 안 함)
```

### Source Code (repository root)

```text
api/
└── features/
    └── requirements/                       # 기존 feature — 확장
        ├── router.py                       # 수정 — clarification_router include
        ├── requirements_contracts.py       # 기존
        ├── clarification_contracts.py      # 신규 — Pydantic DTO (Session/Question/Answer/Proposal/Summary/SSE 이벤트)
        ├── tree_service.py                 # 기존 — 범위 내 UserStory 열거에 재사용
        ├── user_story_edit_service.py      # 기존 — 인코딩된 편집 적용에 재사용 (낙관적 잠금·임팩트 트리거 승계)
        ├── impact_hook.py                  # 기존 — apply 경로가 자동으로 임팩트 분석 등록
        ├── routes/
        │   ├── ... (기존 5개 라우트)
        │   └── clarification.py            # 신규 — /api/requirements/clarification/* + SSE
        └── clarification_agent/            # 신규 sub-package — 딥 에이전트
            ├── __init__.py
            ├── clarification_session.py    # in-memory 세션 스토어 + 진척/상태 머신
            ├── ambiguity_agent.py          # LangChain 딥 에이전트(deepagents) — 모호성 스캔 → 질문 큐
            ├── clarify_methodology.py      # speckit-clarify 분류 체계 + 우선순위 휴리스틱(에이전트 지시문)
            ├── answer_encoder.py           # 답변 → 요구사항 편집안 인코딩 (structured-output LLM)
            ├── clarification_log.py        # UserStory.clarifications 속성 읽기/쓰기 + 범위별 로그 집계
            └── tests/
                ├── test_ambiguity_agent.py
                ├── test_answer_encoder.py
                ├── test_clarification_session.py
                └── test_clarification_log.py
api/main.py                                 # 변경 없음 — requirements_router는 이미 등록됨

frontend/src/features/requirements/          # UI는 Requirements 탭의 일부 — 기존 폴더 확장
├── ui/
│   ├── ClarificationPanel.vue              # 신규 — 명확화 세션 패널(질문 1개씩·추천 답변·선택지·진척·인코딩 diff)
│   ├── ClarificationSummary.vue            # 신규 — 종료 요약(before/after diff + 변경별 되돌리기 + 커버리지 표)
│   ├── RequirementsPanel.vue               # 수정 — "요구사항 명확화" 진입점
│   └── RequirementsTree.vue                # 수정 — 범위 노드에서 명확화 세션 시작
└── requirements.store.js                    # 수정 — 명확화 액션(start/answer/apply/skip/end/revert) + SSE 구독

docs/cypher/schema/03_node_types.cypher       # 수정 — UserStory.clarifications 속성 문서화
pyproject.toml                                # 수정 — deepagents 의존성 추가
README.md                                     # 수정 — /api/requirements 명확화 하위 경로 API 요약 추가
```

**Structure Decision**: Web application(미러 구조). 명확화는 별도 도메인이 아니라 요구사항 feature의 한 능력이므로, `change_management`가 `planning_agent/` 서브패키지를 품는 선례와 동형으로 기존 `api/features/requirements/` 안에 `clarification_agent/` 서브패키지와 `routes/clarification.py`를 둔다 — 신규 feature 모듈이 아니다. 따라서 라우터 prefix도 기존 `/api/requirements`를 그대로 쓰고 명확화 경로는 `/api/requirements/clarification/*` 하위에 모은다(`requirements_router`는 `api/main.py`에 이미 등록되어 있어 `main.py` 변경 불필요). 딥 에이전트(`ambiguity_agent.py`)는 별도 프로세스가 아니라 FastAPI 백그라운드 태스크로 인프로세스 실행되며, 진척은 SSE로, 진행 중 상태는 in-memory 세션 스토어로 노출한다. 프런트 UI는 별도 탭이 아닌 Requirements 탭의 추가 동작이므로 `frontend/src/features/requirements/`를 확장한다.

## Complexity Tracking

> Constitution Check 위반 없음 — 비어 있음.

## Post-Design Constitution Re-Check

Phase 1(data-model·contracts·quickstart) 작성 후 재확인:

- **원칙 IV**: contracts의 `/answer`(제안, 뮤테이션 0건) → `/apply`(검토 후 적용) 분리가 설계에 반영됨. `/answer` 응답 `RequirementEditProposal`은 before/after를 모두 담아 UI가 적용 전 diff를 렌더할 수 있다. 모호성 재스캔(SC-004)도 읽기 전용. ✅ 유지.
- **원칙 I**: data-model에서 신규 Neo4j 노드/관계 0건 확정 — `UserStory.clarifications` 속성 1개만 추가. in-memory 세션은 DTO로만 표현. ✅ 유지.
- **원칙 III**: contracts의 SSE 이벤트 스키마(`ClarificationProgressEvent`)가 분석·인코딩 양쪽 페이즈를 커버. ✅ 유지.
- **원칙 V/VI/VII**: 설계가 sub-package 경계·`get_llm()` 주입·`requirements.clarification.*` 로그 카테고리를 유지. ✅ 유지.

설계 후에도 위반 없음 — `/speckit-tasks` 진행 가능.
