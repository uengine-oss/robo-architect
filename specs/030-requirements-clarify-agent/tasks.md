---
description: "Task list for Requirements Clarification Agent implementation"
---

# Tasks: Requirements Clarification Agent — 추출된 요구사항을 딥 에이전트로 명확화

**Input**: Design documents from `/specs/030-requirements-clarify-agent/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/rest-and-agent.md, quickstart.md

**Tests**: Test tasks ARE included — `plan.md`'s Project Structure explicitly specifies `clarification_agent/tests/` with four test files. They are placed at the end of each story phase as verification (strict test-first TDD was not requested).

**Organization**: Tasks are grouped by user story (US1/US2/US3 from spec.md) for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 (Setup, Foundational, Polish carry no story label)
- All paths are repository-relative.

## Path Conventions

Web app, both sides extend the **existing** `requirements` feature:
- Backend: `api/features/requirements/` (new sub-package `clarification_agent/`, new `routes/clarification.py`)
- Frontend: `frontend/src/features/requirements/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependency and package scaffolding.

- [X] T001 [P] Add `deepagents` to `[project.dependencies]` in `pyproject.toml` (LangChain deep-agent runtime; alongside existing `langgraph`), then run `uv sync`
- [X] T002 [P] Create the `clarification_agent` sub-package: `api/features/requirements/clarification_agent/__init__.py` and `api/features/requirements/clarification_agent/tests/__init__.py`
- [X] T003 [P] Document the new `clarifications` property (JSON-encoded `List<ClarificationLogEntry>`) on the `UserStory` node in `docs/cypher/schema/03_node_types.cypher`, next to the existing `criteriaUserEdited` provenance properties

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared DTOs, the in-memory session store, and the route skeleton — every user story depends on these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Define all Pydantic DTOs and enums in `api/features/requirements/clarification_contracts.py` per data-model.md §2–3: enums (`AmbiguityCategory`, `ScopeType`, `SessionStatus`, `QuestionStatus`, `QuestionType`, `CoverageStatus`) and models (`ClarificationScope`, `QuestionOption`, `ClarificationQuestionDTO`, `SessionProgress`, `ClarificationSessionDTO`, `StartSessionRequest`, `AnswerRequest`, `UserStorySnapshot`, `RequirementEdit`, `RequirementEditProposal`, `ApplyRequest`, `EditConflict`, `ApplyResponse`, `ChangedRequirement`, `CoverageRow`, `ClarificationSummaryDTO`, `RevertRequest`, `ClarificationProgressEvent`, `ClarificationLogEntry`, `ClarificationLogResponse`)
- [X] T005 Implement the in-memory session store + state machine in `api/features/requirements/clarification_agent/clarification_session.py`: `_SESSIONS` dict keyed by `sessionId`, create/get/update helpers, the `analyzing→awaiting_answers→encoding→completed/discarded/failed` transitions (data-model.md §5), single-active-session-per-scope guard (FR-016), and a per-session progress-event buffer for SSE replay
- [X] T006 Create `api/features/requirements/routes/clarification.py` with an `APIRouter` (no extra prefix — paths under `/clarification/...`), and register it in `api/features/requirements/router.py` via `router.include_router(clarification_router)`

**Checkpoint**: Contracts, session store, and routing exist — user story implementation can begin.

---

## Phase 3: User Story 1 - Surface ambiguities in newly extracted requirements (Priority: P1) 🎯 MVP

**Goal**: An autonomous deep agent scans a chosen scope of extracted requirements and produces a prioritized clarification-question queue (≤5), streamed to the UI.

**Independent Test**: Pick a scope containing deliberately vague user stories, start a session, and confirm a prioritized question list appears — each question linked to a specific requirement and an ambiguity category; a fully-clear scope yields "no ambiguities" with zero questions.

### Implementation for User Story 1

- [X] T007 [P] [US1] Encode the SpecKit `clarify` methodology in `api/features/requirements/clarification_agent/clarify_methodology.py`: the 8 `AmbiguityCategory` taxonomy definitions, Clear/Partial/Missing scan rubric, the ≤5-question cap, the Impact×Uncertainty prioritization heuristic, and the deep-agent system instructions string
- [X] T008 [US1] Implement the deep agent in `api/features/requirements/clarification_agent/ambiguity_agent.py`: `run_ambiguity_scan(requirements, *, on_progress) -> QuestionQueue` using the `deepagents` runtime with the model from `get_llm()` (provider-agnostic, via `ingestion_llm_runtime`), the `clarify_methodology` instructions, and a `submit_clarification_questions` terminal tool whose schema is `QuestionQueue`; enforce ≤5 questions and in-scope `referencedRequirementIds` (depends on T004, T007)
- [X] T009 [US1] Implement `POST /clarification/sessions` in `api/features/requirements/routes/clarification.py`: resolve the scope by reusing `tree_service.build_requirements_tree()` to enumerate in-scope `UserStory` snapshots, create the session, kick a FastAPI background task that calls `run_ambiguity_scan` and feeds `ClarificationProgressEvent`s to the session buffer (set `status=failed` on agent error, preserving the tab); return 404 `scope_not_found`, 409 `scope_session_exists`, 422 `empty_scope` per contracts (depends on T005, T006, T008)
- [X] T010 [US1] Implement `GET /clarification/sessions/{sessionId}/stream` in `api/features/requirements/routes/clarification.py` as a `StreamingResponse` (`text/event-stream`) replaying then tailing the session progress buffer, following the `routes/impact_report.py` SSE generator pattern (depends on T009)
- [X] T011 [US1] Implement `GET /clarification/sessions/{sessionId}` poll endpoint in `api/features/requirements/routes/clarification.py` returning the full `ClarificationSessionDTO` snapshot (SSE reconnect fallback, FR-013); 404 `session_not_found` (depends on T009)
- [X] T012 [P] [US1] Add the clarification start + SSE-subscription actions to `frontend/src/features/requirements/requirements.store.js`: `startClarification(scopeType, scopeId)`, an `EventSource` subscription to the stream endpoint, and session/question/progress state refs
- [X] T013 [P] [US1] Create `frontend/src/features/requirements/ui/ClarificationPanel.vue` rendering analysis progress, the prioritized question queue (question text, category, referenced requirements, recommended answer), and the no-ambiguities / deferred-areas states
- [X] T014 [US1] Wire the "요구사항 명확화" entry point in `frontend/src/features/requirements/ui/RequirementsTree.vue` (start a session from a scope node) and `frontend/src/features/requirements/ui/RequirementsPanel.vue` (host `ClarificationPanel.vue`), calling the store actions from T012 (depends on T012, T013)
- [X] T015 [P] [US1] Create a benchmark fixture of seeded-ambiguity `UserStory` records in `api/features/requirements/clarification_agent/tests/fixtures/benchmark_requirements.py` for SC-001/SC-004 measurement
- [X] T016 [P] [US1] Write `api/features/requirements/clarification_agent/tests/test_ambiguity_agent.py`: ≤5-question cap, no-ambiguity path yields zero questions, and ≥80% seeded-ambiguity detection on the T015 fixture (SC-001)
- [X] T017 [P] [US1] Write `api/features/requirements/clarification_agent/tests/test_clarification_session.py`: state-machine transitions, progress-buffer behavior, and the single-active-session-per-scope guard (FR-016)

**Checkpoint**: A user can start a clarification session and see a prioritized question queue — MVP delivers value standalone.

---

## Phase 4: User Story 2 - Answer clarification questions and update the requirements (Priority: P2)

**Goal**: The user answers questions one at a time; each accepted answer is encoded into a proposed requirement edit and, on explicit confirmation, applied to the graph.

**Independent Test**: With a generated question queue, answer questions (accepting recommendations, choosing options, free-form text), confirm each `/answer` returns a before/after proposal with no mutation, `/apply` updates the requirement and triggers impact analysis, skip/end-early behave correctly, and an uninterpretable answer triggers a disambiguation re-prompt without consuming the cap.

### Implementation for User Story 2

- [X] T018 [P] [US2] Implement `answer_encoder.encode_answer(question, final_answer, requirements) -> RequirementEditProposal` in `api/features/requirements/clarification_agent/answer_encoder.py` as a `get_llm().with_structured_output(RequirementEditProposal)` call; produce before/after per affected requirement, replace (not duplicate) invalidated text, and return `needsDisambiguation=true` + prompt when the answer is uninterpretable (FR-007, FR-008) (depends on T004)
- [X] T019 [P] [US2] Implement clarification-log writing in `api/features/requirements/clarification_agent/clarification_log.py`: `append_log_entry(user_story_id, entry)` that reads/decodes the `UserStory.clarifications` JSON array, appends a `ClarificationLogEntry`, and writes it back via `api/platform/neo4j.py` (depends on T004)
- [X] T020 [US2] Implement `POST /clarification/sessions/{sessionId}/answer` in `api/features/requirements/routes/clarification.py`: normalize the `AnswerRequest` (option/recommended/free_text/skip), call `encode_answer`, emit `encoding`/`edit_ready` progress events, return the `RequirementEditProposal` with zero graph mutation; handle skip (advance, empty edits) and 409 `question_not_current` (depends on T005, T018)
- [X] T021 [US2] Implement `POST /clarification/sessions/{sessionId}/apply` in `api/features/requirements/routes/clarification.py`: convert each proposed `RequirementEdit` to a `UserStoryUpdateRequest` and apply via the existing `user_story_edit_service.apply_user_story_edit()` (inherits optimistic lock, no-op detection, impact-analysis trigger), append the log entry via T019, advance the question to `applied`; return `ApplyResponse` with `impactReportIds`, and 409 `edit_conflict` on stale `baseUpdatedAt` (depends on T019, T020)
- [X] T022 [P] [US2] Extend `frontend/src/features/requirements/ui/ClarificationPanel.vue`: per-question answer controls (option buttons, accept-recommendation, free-text ≤5 words, skip), inline before/after diff of the returned proposal, an "적용" button, and the disambiguation re-prompt state
- [X] T023 [P] [US2] Extend `frontend/src/features/requirements/requirements.store.js` with `answerQuestion`, `applyEdit`, `skipQuestion`, and `endSession` actions calling the answer/apply endpoints
- [X] T024 [P] [US2] Write `api/features/requirements/clarification_agent/tests/test_answer_encoder.py`: encoding produces a valid before/after proposal, invalidated text is replaced not duplicated (FR-008), and uninterpretable answers yield `needsDisambiguation`

**Checkpoint**: Users can answer questions and apply the resulting requirement edits — US1 + US2 both work.

---

## Phase 5: User Story 3 - Review clarification results and keep a traceable history (Priority: P3)

**Goal**: An end-of-session summary lists every changed requirement with before/after and a coverage table; individual changes can be reverted; the clarification log persists for later traceability.

**Independent Test**: Complete a session, open the summary (every changed requirement shown before/after), revert one change (it returns to pre-session content while others remain), and reopen the clarification log for the scope later to confirm it persists.

### Implementation for User Story 3

- [X] T025 [P] [US3] Extend `api/features/requirements/clarification_agent/clarification_log.py` with `read_scope_log(scope) -> list[ClarificationLogEntry]` that aggregates `UserStory.clarifications` across all in-scope user stories in chronological order (FR-014)
- [X] T026 [US3] Implement `POST /clarification/sessions/{sessionId}/end` in `api/features/requirements/routes/clarification.py`: finalize the session (`status=completed`, keep applied answers, leave unanswered questions untouched) and build the `ClarificationSummaryDTO` (`changedRequirements` before/after, `coverage` rows, counts) (depends on T005)
- [X] T027 [US3] Implement `GET /clarification/sessions/{sessionId}/summary` in `api/features/requirements/routes/clarification.py` returning the `ClarificationSummaryDTO`; 404 `session_not_found` (depends on T026)
- [X] T028 [US3] Implement `POST /clarification/sessions/{sessionId}/revert` in `api/features/requirements/routes/clarification.py`: restore the target `UserStory` to its pre-session snapshot via `apply_user_story_edit()`, mark the related `clarifications` log entry, return the refreshed summary; 409 `edit_conflict` on external change (depends on T026)
- [X] T029 [US3] Implement `GET /clarification/log` (query `scopeType`, `scopeId`) in `api/features/requirements/routes/clarification.py` returning `ClarificationLogResponse` via `read_scope_log` from T025 (depends on T025)
- [X] T030 [P] [US3] Create `frontend/src/features/requirements/ui/ClarificationSummary.vue`: before/after diff per changed requirement, per-change "되돌리기" action, and the per-category coverage table
- [X] T031 [P] [US3] Extend `frontend/src/features/requirements/requirements.store.js` with `fetchSummary`, `revertChange`, and `fetchClarificationLog` actions
- [X] T032 [P] [US3] Write `api/features/requirements/clarification_agent/tests/test_clarification_log.py`: log append/read round-trip, scope aggregation ordering, and revert restoring the pre-session snapshot

**Checkpoint**: All three user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, observability, and end-to-end validation.

- [X] T033 [P] Update `README.md`: add the `/api/requirements/clarification/*` endpoints to the API summary
- [X] T034 Ensure `requirements.clarification.*` phase-boundary logging (with correlation ID, via `SmartLogger`/`http_context`) is present in `api/features/requirements/routes/clarification.py` and `ambiguity_agent.py` (Constitution VII)
- [ ] T035 Validate SC-004 on the T015 benchmark fixture: after a full clarification session, a re-scan reports ≥70% fewer ambiguous requirements — record the measurement (requires live LLM + Neo4j; deferred to manual smoke)
- [ ] T036 Run the quickstart.md S1–S5 manual smoke scenarios end-to-end and fix any gaps (requires running uvicorn + frontend; deferred to manual smoke)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories.
- **User Stories (Phase 3–5)**: All depend on Foundational. US1 is the MVP; US2 builds on US1's session+questions; US3 builds on a session that US1/US2 produced.
- **Polish (Phase 6)**: Depends on the targeted user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Depends only on Foundational. Independently testable and shippable as MVP.
- **US2 (P2)**: Depends on Foundational; consumes the question queue produced by US1 (acknowledged layering — US2's independent test assumes a generated queue).
- **US3 (P3)**: Depends on Foundational; consumes a session produced by US1+US2.

### Within Each User Story

- Backend agent/service modules before the route endpoints that call them.
- Route endpoints that share `routes/clarification.py` (T009→T010→T011; T020→T021; T026→T027→T028→T029) are sequential — same file.
- Frontend store actions before the components/wiring that use them.
- Tests after the implementation they verify.

### Parallel Opportunities

- Setup: T001, T002, T003 all parallel.
- US1: T007, T015, T016, T017 parallel; T012 and T013 parallel (different files).
- US2: T018 and T019 parallel; T022, T023, T024 parallel.
- US3: T025, T030, T031, T032 parallel.
- Polish: T033 parallel with others.
- With multiple developers, after Foundational one can take backend agent modules while another takes the frontend panel.

---

## Parallel Example: User Story 1

```bash
# After T008 (agent) lands, run the independent US1 tasks together:
Task: "T007 Encode clarify methodology in clarification_agent/clarify_methodology.py"
Task: "T015 Benchmark fixture in clarification_agent/tests/fixtures/benchmark_requirements.py"
Task: "T012 Clarification store actions in frontend/.../requirements.store.js"
Task: "T013 ClarificationPanel.vue in frontend/.../ui/ClarificationPanel.vue"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup
2. Phase 2: Foundational (CRITICAL — blocks all stories)
3. Phase 3: User Story 1 — deep-agent scan → question queue
4. **STOP and VALIDATE**: Run the US1 independent test (vague scope → prioritized questions; clear scope → none)
5. Demo the MVP

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 → ambiguity detection & question queue → demo (MVP)
3. US2 → interactive answering & requirement updates → demo
4. US3 → summary, revert, traceable log → demo
5. Polish → docs, observability, SC-004 validation, quickstart smoke

---

## Notes

- `[P]` = different files, no dependency on incomplete tasks.
- `[Story]` label maps each task to a spec.md user story for traceability.
- Backend extends the existing `api/features/requirements/` feature — no new feature module, no `api/main.py` change (`requirements_router` is already registered).
- No new Neo4j node labels — only the `UserStory.clarifications` property (T003).
- Constitution IV: `/answer` proposes (zero mutation), `/apply` applies after review — keep this split intact.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
