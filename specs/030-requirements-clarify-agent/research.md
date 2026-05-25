# Phase 0 Research: Requirements Clarification Agent

기능 명세의 미해결 결정점과 기술 선택을 해소한다. 각 항목은 Decision / Rationale / Alternatives 형식.

---

## R1. 딥 에이전트 런타임 — `deepagents` 패키지 vs raw LangGraph `StateGraph`

**Decision**: 모호성 스캔(분석 단계)은 LangChain **`deepagents`** 패키지의 딥 에이전트로 구동한다. `pyproject.toml`에 `deepagents` 의존성을 추가한다.

**Rationale**:
- 사용자가 명시적으로 "랭체인 딥 에이전트"를 요청했다 — `deepagents`는 그 개념의 LangChain 공식 구현체(계획용 todo 도구 + 서브에이전트 + 가상 파일시스템 + 상세 시스템 프롬프트를 LangGraph 위에 패키징)다.
- 모호성 스캔은 "분류 체계 8범주를 훑고 → 후보 질문을 모으고 → Impact×Uncertainty로 상위 5개를 골라낸다"는 개방형 다단계 작업이다. 딥 에이전트의 내장 계획(todo) 능력이 이 페이즈 구조에 자연히 대응한다.
- `deepagents`는 LangGraph 위에 빌드되어 이미 있는 `langgraph>=0.2.0`·`langgraph-checkpoint>=2.0.0`와 호환되고, LangChain chat model을 주입받으므로 `get_llm()`을 그대로 넘겨 provider-agnostic(원칙 VI)을 유지한다.

**Alternatives considered**:
- *raw LangGraph `StateGraph`* (`change_management/planning_agent/` 선례): 신규 의존성 0건이라는 장점은 있으나, 노드·엣지·라우팅·상태 모델을 직접 작성해야 해 코드량이 크고, "딥 에이전트"라는 사용자 요청과 어휘가 어긋난다. → `deepagents`가 사용 불가/불안정으로 판명될 경우의 **폴백**으로만 남긴다(동일 결과, 더 많은 코드). 폴백 시 `clarification_agent/`의 외부 인터페이스(`run_ambiguity_scan(requirements) -> QuestionQueue`)는 동일하게 유지해 라우트·세션 계층은 무영향.
- *단발 거대 프롬프트 LLM 호출*: 계획·반복 없이 한 번에 질문을 뽑는 방식. 구현은 가장 단순하나, 큰 범위에서 분류 체계 커버리지가 들쭉날쭉하고 "딥 에이전트"가 아니다. 기각.

---

## R2. SpecKit `clarify` 방법론을 에이전트 지시문으로 인코딩

**Decision**: `clarify_methodology.py`에 `.claude/skills/speckit-clarify/SKILL.md`의 핵심을 딥 에이전트 시스템 지시문으로 상수화한다 — (1) 8개 모호성 분류 체계(Functional Scope & Behavior / Domain & Data Model / Interaction & UX Flow / Non-Functional Quality / Integration & Dependencies / Edge Cases & Failure Handling / Terminology Consistency / Completion Signals), (2) 후보별 Clear·Partial·Missing 상태 표기, (3) 세션당 질문 ≤5 + Impact×Uncertainty 우선순위 휴리스틱, (4) 폐쇄형 질문은 2~5개 상호배타 선택지 + 추천 답변, 단답형은 추천값 제시. 에이전트는 마지막에 `submit_clarification_questions` 도구를 호출해 구조화된 질문 큐를 반환한다.

**Rationale**: SKILL.md의 방법론은 *대화형 명령*용 절차이지만, 그 분석 부분(분류 체계 스캔 → 우선순위 큐)은 그대로 에이전트 지시문으로 옮길 수 있다. 대화형 Q&A 루프(한 번에 하나·답변 인코딩)는 본 기능에서 REST 계층이 담당하므로(R3) 에이전트 책임에서 분리한다. 도구 기반 종료(`submit_*` 도구)는 에이전트 최종 메시지를 파싱하는 것보다 스키마 강제가 확실하다.

**Alternatives considered**:
- `/speckit-clarify` 슬래시 커맨드를 그대로 호출: 이 기능은 *제품 런타임 안의* 명확화이지 spec 파일 편집이 아니다. 스킬은 `.specify/` spec 파일을 전제로 하므로 부적합. 방법론(분류 체계·우선순위 규칙)만 차용한다.
- 분류 체계를 코드 enum이 아닌 자유 프롬프트로: 커버리지 측정(SC-001/SC-004)과 질문 범주 표기가 어려워짐. enum으로 고정.

---

## R3. 대화형 Q&A 아키텍처 — 에이전트 내부 `interrupt()` vs REST 구동 루프

**Decision**: 딥 에이전트는 **분석 단계 한 번만** 자율 실행해 질문 큐를 산출한다(FR-015). 한 번에 하나씩 묻고 답을 받는 대화형 루프는 **REST 계층 + in-memory 세션**이 구동한다 — 질문은 `GET /sessions/{id}`/SSE로 노출, 답변은 `POST /answer`, 적용은 `POST /apply`. 답변별 인코딩은 별도의 좁은 LLM 호출(R4)이며 에이전트를 재기동하지 않는다.

**Rationale**:
- LangGraph `interrupt()`로 에이전트를 사람 입력에서 멈출 수도 있으나, 그러면 에이전트 그래프 실행이 사용자 답변(분 단위로 늦을 수 있음)까지 살아 있어야 하고 HTTP 무상태 모델과 충돌한다.
- 분석을 한 번에 끝내 큐를 만들면 세션은 가벼운 상태 머신이 된다 — 재접속(FR-013)·진척 표기(FR-012)·조기 종료(FR-006)가 단순한 CRUD가 된다.
- 인코딩을 에이전트에서 떼면 답변당 비용·지연이 예측 가능하다(R4).

**Alternatives considered**:
- *에이전트 내 `interrupt()` 기반 단일 장기 실행*: 재접속·서버 재기동·동시성 처리가 모두 어려워짐. 기각.

---

## R4. 답변 인코딩 — 딥 에이전트 서브태스크 vs 집중형 structured-output LLM 호출

**Decision**: 답변 → 요구사항 편집안 변환은 `answer_encoder.py`의 **집중형 `get_llm().with_structured_output(RequirementEditProposal)` 호출**로 구현한다. 입력은 (질문, 최종 답변, 영향받는 UserStory 현재 내용), 출력은 영향받는 각 요구사항의 before/after(role/action/benefit/acceptanceCriteria)다. 답변을 해석할 수 없으면(FR-007) 편집안 대신 `needsDisambiguation=true` + 재질문 프롬프트를 반환한다.

**Rationale**: "이 Q&A를 반영해 이 요구사항을 다시 써라"는 단일 단계·좁은 범위 작업이다 — 계획·반복이 필요 없으므로 딥 에이전트는 과하다. structured-output은 스키마를 강제하고 빠르며(성능 목표 10초 이내) 결정적에 가깝다. 딥 에이전트는 개방형 스캔용으로만 남긴다.

**Alternatives considered**:
- 인코딩도 딥 에이전트로: 답변당 에이전트 1회 = 비용·지연 폭증, 이득 없음. 기각.
- 규칙 기반 텍스트 치환: 자연어 답변을 요구사항 문장에 매끄럽게 녹이지 못함. 기각.

---

## R5. 세션·로그 영속성 — in-memory 세션 + `UserStory.clarifications` 속성

**Decision**: **2계층**으로 나눈다.
- *진행 중 세션*(질문 큐·현재 인덱스·답변·딥 에이전트 체크포인트): `clarification_session.py`의 in-memory 딕셔너리(`sessionId` 키) + 딥 에이전트용 LangGraph `MemorySaver`. 프로세스 수명 범위.
- *영구 명확화 로그*: 적용된 답변마다 `{sessionId, questionId, question, answer, category, before, after, at}` 항목을 영향받는 `UserStory` 노드의 신규 속성 `clarifications`(JSON 인코딩 배열)에 append. 신규 노드 라벨 0건.

**Rationale**:
- 진행 중 세션은 무거운 일시적 프로세스 상태다 — impact report `_REPORTS` 딕셔너리, 인제스트 세션, change-planning `MemorySaver`가 모두 같은 패턴을 쓴다. FR-013이 명시한 트리거("중단·에이전트 실패·사용자 이탈")는 모두 프로세스 내 사건이며, in-memory 세션 + `GET /sessions/{id}` 재접속으로 충족된다. 서버 재기동 시 진행 중 세션은 유실되며 사용자는 재시작한다 — impact report·인제스트 세션과 동일한 수용된 한계(quickstart 런북에 명시).
- 영구 로그를 `UserStory` 속성에 두면 FR-014("영향받는 요구사항에서 추적 가능")를 문자 그대로 충족한다 — 로그가 요구사항의 속성이다. US3 시나리오 3("이전에 끝난 세션의 로그 재열람")은 범위 내 UserStory들의 `clarifications` 속성을 집계해 만족한다.
- 신규 노드 라벨을 만들지 않아 `04_relationships.cypher` 변경·관계 마이그레이션을 피한다(원칙 I — 그래프 안에 사는 추적 데이터, CRUD 노드 증식 회피).

**Alternatives considered**:
- *`ClarificationSession`/`ClarificationQuestion` Neo4j 노드*: 질의 가능하고 추적 스토리에 부합하나, 신규 라벨·관계·스키마 마이그레이션을 동반하고 일시적 세션 상태까지 그래프에 넣게 됨. 본 기능 범위에는 과함. 기각(향후 spec 012 timeline-traceability와 통합 시 재고).
- *전부 in-memory*: 서버 재기동 시 로그 영구 소실 → FR-014 위반. 기각.
- *별도 파일 스토어*(`.robo/` 등, spec 029 선례): 명확화 로그는 대상 프로젝트 산출물이 아니라 요구사항 자체의 메타데이터다 — 그래프 속성이 더 적합. 기각.

---

## R6. 원칙 IV 정합 — propose(`/answer`) / apply(`/apply`) 분리

**Decision**: 답변 1건 = 그래프 변경 1건이며, LLM 생성이므로 propose/apply를 분리한다.
- `POST /answer` — 답변을 인코딩해 `RequirementEditProposal`(영향받는 요구사항별 before/after)을 **반환만** 한다. 그래프 뮤테이션 0건. 질문 상태 `pending → answered`.
- `POST /apply` — 아키텍트가 diff를 검토한 뒤 호출하면 인코딩된 편집을 그래프에 적용한다. 질문 상태 `answered → applied`, 다음 질문으로 전진.

`/api/change/plan`(propose) + `/api/change/apply`(apply) 선례와 동형이다. UI는 두 단계를 한 화면에 붙여(답변 시 diff가 바로 뜨고 "적용" 버튼이 옆에) 명세의 "수락 시 인코딩, 별도 일괄 승인 게이트 없음"(spec Assumption) 의도를 해치지 않으면서 원칙 IV("LLM 변경은 제안 후 명시 확인으로만 적용")를 충족한다.

**Rationale**: spec Assumption은 "별도 *일괄* 승인 게이트"를 배제했을 뿐, 답변 시점의 인라인 diff 확인은 게이트가 아니라 같은 흐름의 일부다. 원칙 IV는 NON-NEGOTIABLE은 아니나 정면 위반은 거버넌스상 명시 해소가 필요하다 — 인라인 propose/apply가 양쪽을 모두 만족시키는 해법이다.

**Alternatives considered**:
- *답변 수락 즉시 자동 적용*: 원칙 IV 정면 위반. 종료 요약의 되돌리기만으로는 "적용 전 검토"를 대체 못 함. 기각.
- *세션 종료 시 일괄 적용 게이트*: spec Assumption이 명시 배제. 기각.

---

## R7. 스트리밍 — 분석·인코딩 진척 SSE 채널

**Decision**: 세션당 SSE 채널 1개 — `GET /api/requirements/clarification/sessions/{id}/stream`. Starlette `StreamingResponse`(`media_type="text/event-stream"`)로 `ClarificationProgressEvent`를 흘린다. 요구사항 feature의 `routes/impact_report.py` 스트림 선례를 그대로 따른다. 이벤트는 분석 페이즈(범위 로드 → 분류 체계 스캔 → 질문 큐 작성 → 준비 완료)와 답변별 인코딩 페이즈(인코딩 중 → 편집안 준비) 양쪽을 커버. 재접속 시 `GET /sessions/{id}` 폴링이 동등한 스냅샷을 제공(FR-013).

**Rationale**: 딥 에이전트 스캔은 수 초~수십 초 — 원칙 III상 스트리밍 필수. 인제스트는 `EventSourceResponse`(sse-starlette)를, impact report는 `StreamingResponse`를 쓴다 — 후자가 같은 feature 안 선례이고 신규 의존성이 없어 채택. 분석·인코딩을 한 채널로 합치면 프런트 구독이 단순해진다.

**Alternatives considered**:
- *폴링 전용*: 원칙 III("수 초 초과 작업은 스트리밍 필수")에 미달. 폴링은 재접속 폴백으로만.
- *WebSocket*: 단방향 진척에는 과함. 기각.

---

## R8. 범위 해소 & 요구사항 읽기

**Decision**: 세션 범위는 `{scopeType: project|bounded_context|feature, scopeId}`. 범위 내 `UserStory` 열거는 기존 `tree_service`의 트리 조회(`BoundedContext-[:HAS_FEATURE]->Feature-[:HAS_USER_STORY]->UserStory`, `UserStory-[:IMPLEMENTS]->BoundedContext`)를 재사용해 해당 서브트리의 UserStory만 필터링한다. `project` 범위는 트리 전체 + `unassigned` 버킷 포함. 딥 에이전트에는 각 UserStory의 `id`·`role`·`action`·`benefit`·`acceptanceCriteria`·`priority`·`status`를 전달한다.

**Rationale**: `tree_service.build_requirements_tree()`가 이미 정확히 이 계층을 조립한다 — 재사용이 자명. 범위 ID는 트리 노드 ID와 1:1.

**Alternatives considered**:
- 명확화 전용 Cypher 신규 작성: `tree_service`와 중복. 기각.

---

## R9. 인코딩된 편집의 그래프 반영

**Decision**: `/apply`는 `RequirementEditProposal`의 각 편집을 `UserStoryUpdateRequest`로 변환해 기존 `user_story_edit_service.apply_user_story_edit()`를 호출한다. 이로써 (1) `baseUpdatedAt` 낙관적 잠금 — 세션 중 외부 변경 시 HTTP 409로 정확히 드러남(edge case "동시 편집"), (2) no-op 감지 — 답변이 실질 변경을 안 만들면 쓰기·임팩트 분석 생략, (3) 임팩트 분석 자동 트리거(`trigger="edit"`)를 모두 승계한다. 적용 후 `clarification_log.py`가 `UserStory.clarifications`에 로그 항목을 append한다.

**Rationale**: 명확화 편집도 결국 UserStory 편집이다 — US7 직접 편집 경로를 재사용하면 동시성·임팩트 처리를 공짜로 얻고 일관성이 보장된다. 별도 쓰기 경로는 두 번째 편집 의미론을 만들 위험이 있다.

**Alternatives considered**:
- 명확화 전용 Cypher 직접 쓰기: 낙관적 잠금·임팩트 트리거를 재구현해야 함. 기각.

---

## 미해결 항목

없음 — Technical Context의 모든 항목이 결정되었다. Phase 1 진행 가능.
