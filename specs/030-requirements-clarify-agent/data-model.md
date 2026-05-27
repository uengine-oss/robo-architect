# Phase 1 Data Model: Requirements Clarification Agent

신규 Neo4j 노드 라벨/관계 **0건**. 기존 `UserStory` 노드에 속성 1개 추가, 나머지는 in-memory 세션 상태를 표현하는 Pydantic DTO다.

---

## 1. Neo4j 변경

### 1.1 `UserStory` — 신규 속성 `clarifications`

| 속성 | 타입 | 설명 |
|------|------|------|
| `clarifications` | `String` (JSON 인코딩 `List<ClarificationLogEntry>`) | 이 요구사항에 적용된 명확화 로그. 신규 노드 라벨이 아닌 속성. 비어 있으면 부재/`"[]"`. |

`docs/cypher/schema/03_node_types.cypher`의 `UserStory` 정의에 위 속성을 문서화한다. 기존 `criteriaUserEdited`·`criteriaEditedAt` 등 provenance 속성과 동급. 신규 관계 타입 없음 → `04_relationships.cypher` 무변경.

`ClarificationLogEntry` (JSON 항목 구조):

| 필드 | 타입 | 설명 |
|------|------|------|
| `sessionId` | string | 이 항목을 만든 명확화 세션 |
| `questionId` | string | 출처 질문 |
| `question` | string | 질문 텍스트 |
| `answer` | string | 최종 답변(선택지 라벨 또는 자유 입력) |
| `category` | string | 모호성 분류 체계 범주(아래 enum) |
| `before` | object | 적용 전 요구사항 스냅샷(`role`/`action`/`benefit`/`acceptanceCriteria`) |
| `after` | object | 적용 후 스냅샷 |
| `at` | string (ISO-8601) | 적용 시각 |

---

## 2. 열거형

### 2.1 `AmbiguityCategory` (모호성 분류 체계 — speckit-clarify 차용)

`functional_scope` · `domain_data_model` · `interaction_flow` · `non_functional` · `integration_dependencies` · `edge_cases` · `terminology` · `completion_signals`

### 2.2 `ScopeType`

`project` · `bounded_context` · `feature`

### 2.3 `SessionStatus`

`analyzing` (딥 에이전트 스캔 중) · `awaiting_answers` (질문 큐 준비, 응답 대기) · `encoding` (답변 인코딩 중) · `completed` (정상 종료) · `discarded` (사용자 폐기) · `failed` (분석 실패 — 이미 적용된 답변은 보존)

### 2.4 `QuestionStatus`

`pending` · `answered` (인코딩됨, 적용 대기) · `applied` (그래프 반영) · `skipped`

### 2.5 `QuestionType`

`closed` (2~5개 상호배타 선택지) · `short_answer` (≤5단어 자유 입력)

### 2.6 `CoverageStatus` (종료 요약의 범주별 상태)

`resolved` · `deferred` (질문 상한 초과로 보류) · `clear` (이미 충분) · `outstanding` (미해소·저영향)

---

## 3. DTO (Pydantic — `clarification_contracts.py`)

### 3.1 `ClarificationScope`
| 필드 | 타입 | 설명 |
|------|------|------|
| `scopeType` | `ScopeType` | 범위 종류 |
| `scopeId` | string | 트리 노드 ID(`project`면 `"*"` 또는 프로젝트 ID) |
| `scopeName` | string | 표시용 이름 |

### 3.2 `ClarificationQuestionDTO`
| 필드 | 타입 | 설명 |
|------|------|------|
| `questionId` | string | UUID |
| `order` | int | 큐 내 1-기반 순서 |
| `category` | `AmbiguityCategory` | 해소 대상 범주 |
| `priority` | int | Impact×Uncertainty 우선순위(1=최고) |
| `questionType` | `QuestionType` | 폐쇄형/단답형 |
| `questionText` | string | 질문 |
| `referencedRequirementIds` | string[] | 이 질문이 다루는 UserStory id(들) |
| `recommendedAnswer` | string | 추천/제안 답변 |
| `options` | `QuestionOption[]` | 폐쇄형일 때 2~5개, 단답형이면 빈 배열 |
| `status` | `QuestionStatus` | 상태 |

`QuestionOption`: `{ key: string, label: string }`

### 3.3 `ClarificationSessionDTO`
| 필드 | 타입 | 설명 |
|------|------|------|
| `sessionId` | string | UUID |
| `scope` | `ClarificationScope` | 범위 |
| `status` | `SessionStatus` | 세션 상태 |
| `progress` | `SessionProgress` | 진척 |
| `questions` | `ClarificationQuestionDTO[]` | 질문 큐(분석 완료 후 채워짐) |
| `noAmbiguities` | bool | 모호성 미발견 시 true(FR-011) |
| `deferredNote` | string \| null | 질문 상한 초과로 미해소된 영역 안내(FR-004) |
| `createdAt` / `endedAt` | string \| null | 타임스탬프 |

`SessionProgress`: `{ phase: string, message: string, questionsTotal: int, questionsAnswered: int, currentQuestionIndex: int }`

### 3.4 `StartSessionRequest`
`{ scopeType: ScopeType, scopeId: string }`

### 3.5 `AnswerRequest`
| 필드 | 타입 | 설명 |
|------|------|------|
| `questionId` | string | 대상 질문 |
| `mode` | `option` \| `recommended` \| `free_text` \| `skip` | 답변 방식 |
| `optionKey` | string \| null | `mode=option`일 때 선택지 키 |
| `text` | string \| null | `mode=free_text`일 때 ≤5단어 입력 |

### 3.6 `RequirementEdit` / `RequirementEditProposal`
`RequirementEdit`:
| 필드 | 타입 | 설명 |
|------|------|------|
| `requirementId` | string | 영향받는 UserStory id |
| `baseUpdatedAt` | string | 인코딩 시점 `updatedAt`(낙관적 잠금용) |
| `before` | `UserStorySnapshot` | 현재 내용 |
| `after` | `UserStorySnapshot` | 제안 내용 |
| `fieldsSummary` | string | 변경 필드 한 줄 요약 |

`RequirementEditProposal` (`/answer` 응답):
| 필드 | 타입 | 설명 |
|------|------|------|
| `questionId` | string | 출처 질문 |
| `finalAnswer` | string | 정규화된 최종 답변 |
| `edits` | `RequirementEdit[]` | 영향받는 요구사항별 편집안(뮤테이션 0건 — 제안만) |
| `needsDisambiguation` | bool | 답변 해석 불가 시 true(FR-007) |
| `disambiguationPrompt` | string \| null | 재질문 텍스트(질문 상한 미소진) |

`UserStorySnapshot`: `{ role, action, benefit, priority, status, acceptanceCriteria: string[] }`

### 3.7 `ApplyRequest` / `ApplyResponse`
`ApplyRequest`: `{ questionId: string }`
`ApplyResponse`:
| 필드 | 타입 | 설명 |
|------|------|------|
| `appliedRequirementIds` | string[] | 그래프에 반영된 UserStory id |
| `impactReportIds` | string[] | 적용으로 트리거된 임팩트 리포트 id |
| `conflict` | `EditConflict` \| null | 세션 중 외부 변경 시 — 영향받는 요구사항의 최신 `updatedAt`(HTTP 409 동반) |
| `noOp` | bool | 실질 변경 없어 쓰기 생략됨 |

### 3.8 `ClarificationSummaryDTO` (`/summary`)
| 필드 | 타입 | 설명 |
|------|------|------|
| `sessionId` | string | 세션 |
| `changedRequirements` | `ChangedRequirement[]` | 세션 중 변경된 요구사항 |
| `coverage` | `CoverageRow[]` | 범주별 상태 |
| `questionsAsked` / `questionsApplied` / `questionsSkipped` | int | 집계 |

`ChangedRequirement`: `{ requirementId, requirementLabel, questionId, before: UserStorySnapshot, after: UserStorySnapshot }`
`CoverageRow`: `{ category: AmbiguityCategory, status: CoverageStatus }`

### 3.9 `RevertRequest`
`{ requirementId: string }` — 해당 요구사항을 세션 직전 스냅샷으로 복원하고 `clarifications` 로그에서 관련 항목을 표시(FR-010).

### 3.10 `ClarificationProgressEvent` (SSE 페이로드)
| 필드 | 타입 | 설명 |
|------|------|------|
| `phase` | string | `loading_scope` \| `scanning` \| `drafting_questions` \| `questions_ready` \| `encoding` \| `edit_ready` \| `completed` \| `error` |
| `message` | string | 사람용 메시지 |
| `progress` | float | 0.0~1.0 |
| `data` | object \| null | 페이즈별 페이로드(예: 준비된 질문 큐, 인코딩 결과) |

### 3.11 `ClarificationLogResponse` (`GET /log`)
`{ scope: ClarificationScope, entries: ClarificationLogEntry[] }` — 범위 내 모든 `UserStory.clarifications`를 시간순 집계(FR-014, US3 시나리오 3).

---

## 4. 딥 에이전트 I/O 계약

`ambiguity_agent.run_ambiguity_scan(requirements, *, on_progress) -> QuestionQueue`

- **입력** `requirements`: `RequirementForScan[]` — `{ id, role, action, benefit, acceptanceCriteria: string[], priority, status }`
- **출력** `QuestionQueue`: `{ questions: ClarificationQuestionDTO[]  (≤5), noAmbiguities: bool, deferredNote: string|null, coverage: CoverageRow[] }`
- 에이전트는 `clarify_methodology.py`의 분류 체계·우선순위 지시문으로 구동되며, 종료 시 `submit_clarification_questions` 도구를 호출해 위 구조를 반환한다.
- `on_progress` 콜백으로 `ClarificationProgressEvent`를 SSE 채널에 전달.

`answer_encoder.encode_answer(question, final_answer, requirements) -> RequirementEditProposal`

- structured-output LLM 호출. 답변 해석 불가 시 `needsDisambiguation=true`.

---

## 5. 세션 상태 머신

```
                start (POST /sessions)
                       │
                       ▼
                 ┌───────────┐   분석 실패
                 │ analyzing │ ───────────────► failed
                 └─────┬─────┘  (적용된 답변 보존)
                       │ 질문 큐 준비 / 또는 noAmbiguities
                       ▼
              ┌─────────────────┐
              │ awaiting_answers│◄──────────┐
              └───┬────────┬────┘           │
        answer    │        │ skip / 다음 질문 │
       (인코딩)    ▼        └─────────────────┘
              ┌──────────┐  apply (그래프 반영) → 다음 질문
              │ encoding │ ──────────────────────────┘
              └──────────┘
                       │ 마지막 질문 처리 / end (조기 종료)
                       ▼
                 ┌───────────┐
                 │ completed │   (POST /sessions/{id} discard → discarded)
                 └───────────┘
```

- 범위당 활성 세션 1개만 허용(FR-016) — 같은 `scopeId`에 `analyzing`/`awaiting_answers`/`encoding` 세션이 있으면 신규 시작은 409로 거부하고 기존 `sessionId`를 안내.
- `analyzing → failed` 전이는 이미 `applied`된 질문을 그대로 둔다(FR-013).
- `noAmbiguities=true`면 `analyzing → completed`로 곧장 전이, 질문 0개(FR-011).

---

## 6. 검증 규칙 (명세 요구사항 매핑)

| 규칙 | 출처 |
|------|------|
| 질문 큐 길이 ≤ 5 | FR-004 |
| 폐쇄형 질문 선택지 2~5개·상호배타 | FR-005 |
| 답변 모드는 option/recommended/free_text/skip 중 하나, free_text는 ≤5단어 | FR-005·FR-006 |
| `/answer`는 그래프 뮤테이션 0건, `/apply`만 반영 | FR-008·원칙 IV |
| `after`는 무효화된 텍스트를 치환(중복 추가 금지) | FR-008 |
| `baseUpdatedAt` 불일치 시 409 conflict | edge case "동시 편집"·R9 |
| `revert`는 세션 직전 스냅샷으로만 복원 | FR-010 |
| 범위당 활성 세션 1개 | FR-016 |
| 적용된 답변마다 `UserStory.clarifications` 항목 1건 | FR-009·FR-014 |
