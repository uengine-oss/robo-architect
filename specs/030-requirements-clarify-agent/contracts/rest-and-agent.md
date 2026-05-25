# Phase 1 Contracts: Requirements Clarification Agent

신규 라우트는 기존 `requirements_router`(prefix `/api/requirements`) 아래 `routes/clarification.py`로 추가된다 — 모든 경로는 `/api/requirements/clarification/...`. `requirements_router`는 `api/main.py`에 이미 등록되어 있어 등록 변경 불필요. 모든 요청/응답 본문은 `clarification_contracts.py`의 Pydantic 모델(→ `data-model.md`).

규약: 5xx는 분석 실패가 아닌 인프라 오류에만. 분석 자체의 실패는 세션 `status=failed`로 200 본문에 담아 탭을 비파괴(FR-013). LLM 생성 편집은 `/answer`에서 제안만, `/apply`에서만 그래프 반영(원칙 IV).

---

## REST 엔드포인트 (9개)

### 1. `POST /api/requirements/clarification/sessions` — 세션 시작
- **Body**: `StartSessionRequest` `{ scopeType, scopeId }`
- **200**: `ClarificationSessionDTO` (`status=analyzing`, `questions=[]`)
- **동작**: 범위 검증 → in-memory 세션 생성 → 딥 에이전트 모호성 스캔을 FastAPI 백그라운드 태스크로 기동 → 즉시 반환. 진척은 (2)의 SSE로.
- **409 `scope_session_exists`**: 같은 범위에 활성 세션 존재(FR-016) — 본문에 기존 `sessionId`.
- **404 `scope_not_found`**: 범위 ID가 트리에 없음.
- **422 `empty_scope`**: 범위 내 UserStory 0건 — "명확화할 요구사항 없음"(edge case).

### 2. `GET /api/requirements/clarification/sessions/{sessionId}/stream` — 진척 SSE
- **응답**: `StreamingResponse`, `media_type=text/event-stream`. `data: {ClarificationProgressEvent JSON}\n\n` 반복.
- **종료**: `phase` ∈ `{questions_ready, completed, error}` 도달 또는 상한 틱. 분석 페이즈(`loading_scope→scanning→drafting_questions→questions_ready`)와 답변별 인코딩 페이즈(`encoding→edit_ready`)를 한 채널로.
- `impact_report.py`의 스트림 제너레이터 패턴 재사용.

### 3. `GET /api/requirements/clarification/sessions/{sessionId}` — 세션 스냅샷(폴링/재접속)
- **200**: `ClarificationSessionDTO` 전체(질문 큐·진척·상태). SSE 재접속 폴백(FR-013).
- **404 `session_not_found`**.

### 4. `POST /api/requirements/clarification/sessions/{sessionId}/answer` — 답변 제출(제안)
- **Body**: `AnswerRequest` `{ questionId, mode, optionKey?, text? }`
- **200**: `RequirementEditProposal` — 영향받는 요구사항별 `before`/`after`. **그래프 뮤테이션 0건.**
- `mode=skip`: 질문 `status=skipped`, 빈 `edits`로 응답, 다음 질문 전진.
- 답변 해석 불가: `needsDisambiguation=true` + `disambiguationPrompt`(질문 상한 미소진 — FR-007).
- 인코딩 진척은 (2) SSE의 `encoding→edit_ready`로도 노출.
- **409 `question_not_current`**: 큐 순서를 벗어난 질문.

### 5. `POST /api/requirements/clarification/sessions/{sessionId}/apply` — 편집 적용(반영)
- **Body**: `ApplyRequest` `{ questionId }`
- **동작**: 해당 질문의 제안 편집을 `user_story_edit_service.apply_user_story_edit()`로 적용 → 낙관적 잠금·no-op 감지·임팩트 분석 트리거 승계 → `UserStory.clarifications`에 로그 항목 append → 질문 `status=applied`, 다음 질문 전진.
- **200**: `ApplyResponse` `{ appliedRequirementIds, impactReportIds, conflict?, noOp }`
- **409 `edit_conflict`**: 세션 중 외부 변경 — 본문에 최신 `updatedAt`. UI는 재인코딩 후 재적용.

### 6. `POST /api/requirements/clarification/sessions/{sessionId}/end` — 조기 종료
- **200**: `ClarificationSummaryDTO`. 이미 `applied`된 답변은 유지, 미답 질문은 미변경(FR-006). 세션 `status=completed`.

### 7. `GET /api/requirements/clarification/sessions/{sessionId}/summary` — 종료 요약
- **200**: `ClarificationSummaryDTO` — `changedRequirements`(before/after) + 범주별 `coverage` 표(FR-010).
- **404 `session_not_found`**.

### 8. `POST /api/requirements/clarification/sessions/{sessionId}/revert` — 개별 변경 되돌리기
- **Body**: `RevertRequest` `{ requirementId }`
- **동작**: 해당 UserStory를 세션 직전 스냅샷으로 복원(`apply_user_story_edit()` 재사용) + `clarifications` 로그 항목 표시.
- **200**: 갱신된 `ClarificationSummaryDTO`.
- **409 `edit_conflict`**: 복원 대상이 세션 후 외부 변경됨.

### 9. `GET /api/requirements/clarification/log` — 명확화 로그 조회
- **Query**: `scopeType`, `scopeId`
- **200**: `ClarificationLogResponse` — 범위 내 모든 `UserStory.clarifications`를 시간순 집계(FR-014). 종료된 세션의 로그 재열람(US3 시나리오 3).

---

## SSE 이벤트 스키마

`ClarificationProgressEvent` (→ `data-model.md` §3.10). 페이즈별 `data`:

| `phase` | `data` 페이로드 |
|---------|-----------------|
| `loading_scope` | `{ requirementCount }` |
| `scanning` | `{ category, status }` — 분류 체계 진행 |
| `drafting_questions` | `{ drafted }` — 지금까지 작성된 후보 수 |
| `questions_ready` | `{ questions: ClarificationQuestionDTO[], noAmbiguities, deferredNote }` |
| `encoding` | `{ questionId }` |
| `edit_ready` | `{ proposal: RequirementEditProposal }` |
| `completed` | `{ summary: ClarificationSummaryDTO }` |
| `error` | `{ code, message }` — 세션 `status=failed`, 적용된 답변 보존 |

---

## 딥 에이전트 계약 (`ambiguity_agent.py`)

`run_ambiguity_scan(requirements: list[RequirementForScan], *, on_progress) -> QuestionQueue`

- **런타임**: LangChain `deepagents` 딥 에이전트. 모델은 `get_llm()` 주입(provider-agnostic).
- **지시문**: `clarify_methodology.py`의 8범주 분류 체계 + Clear/Partial/Missing 표기 + 세션당 ≤5 + Impact×Uncertainty 우선순위.
- **도구**:
  - `list_requirements()` → 범위 내 요구사항(프롬프트에 동봉 가능 — 작은 범위면 도구 불필요).
  - `submit_clarification_questions(questions, noAmbiguities, deferredNote, coverage)` → 종료 도구. 인자 스키마 = `QuestionQueue`. 호출 시 에이전트 종료.
- **출력**: `QuestionQueue` `{ questions(≤5), noAmbiguities, deferredNote, coverage }`.
- **불변식**: `len(questions) ≤ 5`; 폐쇄형 질문은 `options` 2~5개; 각 질문 `referencedRequirementIds`는 입력 범위 내 id; 모호성 없으면 `noAmbiguities=true`·`questions=[]`.

`answer_encoder.encode_answer(question, final_answer, requirements) -> RequirementEditProposal`

- **런타임**: `get_llm().with_structured_output(RequirementEditProposal)` 단발 호출.
- **불변식**: `edits[*].after`는 모호 표현을 치환(중복 추가 금지 — FR-008); 해석 불가 시 `needsDisambiguation=true`.

---

## 오류 코드 요약

| 코드 | HTTP | 의미 |
|------|------|------|
| `scope_not_found` | 404 | 범위 ID가 요구사항 트리에 없음 |
| `empty_scope` | 422 | 범위 내 UserStory 0건 |
| `scope_session_exists` | 409 | 같은 범위에 활성 세션 존재(FR-016) |
| `session_not_found` | 404 | 세션 ID 없음 |
| `question_not_current` | 409 | 큐 순서를 벗어난 질문 |
| `edit_conflict` | 409 | 세션 중 요구사항 외부 변경(낙관적 잠금) |

분석/인코딩 LLM 실패는 5xx가 아니라 세션 `status=failed` + SSE `error` 이벤트로 처리 — Requirements 탭 비파괴(FR-013).
