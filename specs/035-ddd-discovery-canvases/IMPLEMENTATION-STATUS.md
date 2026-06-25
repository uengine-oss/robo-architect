# 035 구현 상태 (resumable)

**Worktree**: `/Users/uengine/main-robo-arch/robo-architect-035` · **Branch**: `035-ddd-discovery-canvases` (base `main` @518dd93)
**작성**: 2026-05-31 (세션 중단 시점)

## ✅ 완료 — 백엔드 (전부 `python3 ast` 구문 통과, import 스모크 미실행)

| 파일 | 내용 | tasks |
|---|---|---|
| `api/features/contexts/router.py` | `Classification` Literal에 `generic` 추가 + 422 가드 + docstring | T043 (US6) |
| `api/features/requirements/requirements_contracts.py` | 035 DTO 블록 전체(Wizard*/Pivotal*/BcCanvas*/AggregateCanvas*/DddExport*/GraphChangePreview) | T005,T006 |
| `routes/pivotal_events.py` | `POST /pivotal-events/toggle`, `GET /pivotal-events/subdomains/propose` | T022,T025 (US2) |
| `routes/canvas.py` | BC/Aggregate canvas `GET`+`PATCH`(If-Match 낙관버전, 속성만 SET) | T028,T029,T038,T039 (US3/US5) |
| `ddd_wizard/__init__.py,step_prompts.py,wizard_session.py,engine.py` | 단계 메타·추천·세션 상태머신·LLM/폴백 엔진 | T007,T011,T017 (US1) |
| `routes/ddd_wizard.py` | start/get/answer/stream(SSE)/confirm — confirm은 기존 경로 위임 | T012-T016 (US1) |
| `routes/ddd_export.py` | `POST /ddd-export` 그래프→.ddd 내보내기 | T047,T048 (US7) |
| `requirements/router.py` | 위 4개 라우터 include | T008 |

**설계 원칙 준수**: 신규 노드 라벨/관계 0건(속성 추가만), propose→confirm, SSE, 이원화 엔진(in-process `get_llm` / claude-ide CLI + 폴백), 진실의 원천=그래프.

## ⏳ 남은 작업

1. **import 스모크 테스트**: `cd worktree && uv run python -c "import api.features.requirements.router"` (또는 pip 환경). 런타임 import 오류 확인.
2. **프런트엔드** (T018,T019,T031-T033,T037,T041,T046,T050): 
   - `DddWizardPanel.vue`(프로파일링→단계 SSE), `BcCanvasTab.vue`, `AggregateCanvasTab.vue`
   - `EpicDetail.vue` 탭화(현재 무탭) — `UserStoryDetail.vue` 탭 패턴 참고
   - `AggregateViewerInspector.vue`에 Canvas 탭 슬롯
   - `requirements.store.js`에 액션, `RequirementsPanel.vue` 진입구 + ingestion 모달 상호링크
   - `CanvasWorkspace.vue` BC 노드 클릭 → EpicDetail 진입(현재 BC클릭 무동작 라인 수정)
3. **스키마 문서**(T002): `docs/cypher/schema/03_node_types.cypher` 주석에 Event.pivotal/hotspot, BC/Aggregate 캔버스 속성.
4. **테스트**(T021,T034,T042): pytest. neo4j 필요한 통합테스트는 기존 `clarification_agent/tests/` 패턴 확인. 최소 단위: wizard_session 상태전이, step_prompts.recommend_plan, ddd_export _slug.
5. **매뉴얼**: `/test-and-create-manual` 스킬로 한국어 manual.md+docx (앱 기동 필요 — Q1~Q15 quickstart 기반).
6. **DDD 검증 연계**(T051), 언어정책(T052), 관찰성(T053), Swagger/README(T054), 스키마 diff 회귀(T055).

## ⚠️ 주의/발견
- worktree에 `.specify/`가 gitignore라 없음 → 슬래시 커맨드 대신 tasks.md 수동 진행.
- `python` 명령 없음 → **`python3` 사용**.
- `generation/local_tooling` 모듈은 없음. 034 이원화/preflight는 `routes/child_story_generation.py`에 인라인(`_generate`,`/local-tooling/status`). 035는 동일 패턴을 ddd_wizard에 인라인 구현함.
- neo4j 헬퍼는 범용(`get_session()`로 직접 Cypher)이 코드베이스 패턴. neo4j_client는 create_bounded_context/create_user_story/link_* 보유.
- BC canvas inbound flow는 현재 빈 목록(outbound만 TRIGGERED_BY로 투영). 필요시 보강.
