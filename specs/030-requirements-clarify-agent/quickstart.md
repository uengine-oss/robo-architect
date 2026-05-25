# Phase 1 Quickstart: Requirements Clarification Agent

수동 스모크 시나리오(S1~S5)와 개발 런북. 명세의 사용자 스토리·성공 기준에 대응한다.

## 사전 조건

- 백엔드: `uvicorn api.main:app --reload --host 127.0.0.1 --port 8000`
- Neo4j 기동, `.env`에 `NEO4J_*` + LLM provider(`LLM_PROVIDER`/`LLM_MODEL`/`*_API_KEY`) 설정
- 신규 의존성 설치: `uv pip install deepagents` (또는 `uv sync` — `pyproject.toml`에 추가 후)
- 요구사항 트리에 데이터 존재: 문서 인제스트로 UserStory가 추출되어 Requirements 탭 트리에 표시되는 상태

---

## S1 — 모호성 탐지 & 질문 큐 (US1 / P1)

1. Requirements 탭에서 일부러 모호한 UserStory(예: "사용자로서 빠르게 검색하고 싶다" 류 — 측정 불가 형용사·미정의 데이터 규칙)를 포함한 범위(BoundedContext 또는 Feature 노드)를 고른다.
2. "요구사항 명확화"를 실행 → 세션이 시작되고 SSE 진척이 `loading_scope → scanning → drafting_questions → questions_ready`로 흐르는지 확인.
3. **기대**: 우선순위 질문 큐(≤5)가 뜬다. 각 질문에 출처 요구사항·모호성 범주·추천 답변이 연결되어 있다(SC-001 — 벤치마크 세트에서 시드된 모호 요구사항의 ≥80% 검출).
4. 질문이 6개 이상 후보였던 큰 범위라면 `deferredNote`("일부 영역 미해소")가 표시되는지 확인(FR-004).

## S2 — 모호성 없음 경로 (US1 / Edge)

1. 이미 명확한(역할·행동·이득·수용 기준이 구체적인) UserStory만 있는 범위로 세션을 시작한다.
2. **기대**: 질문 0개, "중대한 모호성 없음" 보고 후 세션이 곧장 `completed`(FR-011). 빈 범위(UserStory 0건)면 시작 단계에서 422 `empty_scope`로 막힌다.

## S3 — 대화형 응답 & 요구사항 갱신 (US2 / P2)

1. S1의 질문 큐에서 첫 질문에 대해 — (a) 추천 답변 수락, (b) 폐쇄형 선택지 선택, (c) 단답형 자유 입력 각각을 시도한다.
2. 답변 시 `/answer`가 `RequirementEditProposal`을 반환하고 영향받는 요구사항의 **before/after diff**가 인라인으로 뜨는지 확인(그래프는 아직 미변경).
3. "적용"을 누르면 `/apply`가 편집을 반영하고, 요구사항이 갱신되며, 임팩트 리포트가 트리거되는지 확인(`impactReportIds` 비어 있지 않음).
4. 해석 불가한 답변(예: 선택지와 무관한 문장)을 넣어 `needsDisambiguation` 재질문이 뜨고, 그 재질문이 질문 상한을 소모하지 **않는지** 확인(FR-007).
5. **기대**: 각 적용 후 해당 UserStory에 `clarifications` 로그 항목이 1건 추가된다(FR-009).

## S4 — 건너뛰기 / 조기 종료 / 동시 편집 (US2 / Edge)

1. 한 질문을 "건너뛰기"(`mode=skip`) — 그 질문으로는 어떤 요구사항도 바뀌지 않고 다음 질문으로 넘어가는지 확인.
2. 세션 도중 "세션 종료"를 누른다 — 이미 적용된 답변은 유지되고 미답 질문은 미변경 상태로 종료 요약이 뜨는지 확인(FR-006).
3. 동시성: 세션이 열린 채로 다른 탭/사용자가 같은 UserStory를 편집한 뒤 `/apply`를 시도 → 409 `edit_conflict`로 최신 `updatedAt`이 반환되는지 확인(낙관적 잠금).
4. 세션 중 페이지를 이탈했다 재진입 → `GET /sessions/{id}`로 질문 큐·진척이 복원되는지 확인(FR-013).

## S5 — 종료 요약 & 되돌리기 & 로그 (US3 / P3)

1. 세션을 끝까지 진행한 뒤 종료 요약을 연다 — 세션 중 변경된 모든 요구사항이 before/after로, 범주별 커버리지 표와 함께 나오는지 확인(FR-010).
2. 요약에서 한 변경을 "되돌리기" → 해당 요구사항이 세션 직전 내용으로 복원되고 다른 변경은 유지되는지 확인.
3. 같은 범위로 명확화를 한 번 더 실행(재스캔) → 모호 요구사항 수가 첫 세션 대비 ≥70% 감소하는지 확인(SC-004).
4. `GET /clarification/log?scopeType=&scopeId=`로 종료된 세션의 Q→A 로그가 그대로 재열람되는지 확인(FR-014, US3 시나리오 3).

---

## 개발 런북

- **`deepagents` 런타임**: 딥 에이전트 코드(`ambiguity_agent.py`·`clarify_methodology.py`) 변경 후 `uvicorn --reload`로 충분히 반영된다 — 별도 프로세스 아님(인프로세스 백그라운드 태스크).
- **uvicorn `--reload`**: 신규 라우트(`routes/clarification.py`)는 `--reload` 없이 기동한 서버에서 404로 보인다 — 런북은 `--reload` 필수(원칙 IX 일반 규칙).
- **LLM provider**: 딥 에이전트와 답변 인코더는 `get_llm()`을 쓰므로 `.env`의 `LLM_PROVIDER`/`LLM_MODEL`만 바꾸면 provider 전환된다. 토큰 사용량은 요구사항 feature의 `ingestion_llm_runtime` 집계에 합류.
- **벤치마크 세트**: SC-001(검출율 ≥80%)·SC-004(재스캔 시 ≥70% 감소) 검증용으로 시드된 모호 요구사항이 든 고정 UserStory 세트를 `clarification_agent/tests/`에 픽스처로 둔다.
- **세션 수명**: 진행 중 세션은 in-memory다 — 서버 재기동 시 진행 중 세션은 유실되며 사용자는 재시작한다(impact report·인제스트 세션과 동일). 적용 완료된 답변·`UserStory.clarifications` 로그는 그래프에 영속되어 재기동에 영향받지 않는다.
- **SSE 디버깅**: 진척이 멈춰 보이면 `GET /sessions/{id}` 폴링으로 실제 상태를 확인한다 — SSE 채널 단절과 분석 실패를 구분.
