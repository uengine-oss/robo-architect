<!-- SPECKIT START -->
Active feature plan: [specs/043-task-ui-unification/plan.md](specs/043-task-ui-unification/plan.md)

**043 BPM·Event Modeling 단일 Process 탭 + task=UI 일관성** (started 2026-06-11, 구현·검증 완료) — spec-042 후속(읽기뷰어 → 구조통합). **UI를 공유 앵커로 task=UI 일관화**: (US1) `Process`(BPM)·`Processes`(Event Modeling) 탭을 **상단 `Process` 탭 + TopBar BPM⇄EM 서브토글**로 통합(activeTab을 `Process`⇄`Processes`로 바꿔 네비/캔버스/상단바 동반 전환), `Big picture` 비활성화; (US2) ES 승격 UI 생성 = **사람-조작(policy-invoked 아님) Command마다 액션 UI**(task당 1~N); (US3) ReadModel을 **screen/inline/system 3분류** — screen(조회/검색·**결과 화면**)→자체 결과 UI([task_ui_helpers.py](api/features/ingestion/workflow/phases/task_ui_helpers.py) `classify_readmodel`), inline→`ATTACHED_TO {role:'display'}`, system→없음; (US4) task 포함요소를 **EM 형식 가로레인**(신규 `EventModelingLane.vue`, `UI액션→Command→Event→ReadModel→UI결과`; [design_trace.py](api/features/requirements/routes/design_trace.py) `_expand_trace`에 ReadModel(FEEDS)·결과UI(RESULT_UI/DISPLAYED_ON, 비영속) 확장). 042 bpm-task trace 라우트·모달 재사용. **하이브리드 한정**(비-하이브리드 무변경), A2A BPM·Command/Event task귀속 **불변**, 신규 영속 라벨/관계 0(`ATTACHED_TO.role` 속성만). 인제스천 변경=**재인제스천 필요**. ES 승격 모달에 LLM 캐시 토글. 라이브 검증 완료(task 1~N UI, ReadModel 결과UI). Constitution PASS.

---
이전 피처(042) 참고:
Active feature plan: [specs/042-bpm-event-unification/plan.md](specs/042-bpm-event-unification/plan.md)

**042 BPM↔Event Modeling 구조적 통합 (단일 그래프, 두 투영 뷰)** (started 2026-06-10) — BPM 뷰·Event Modeling 뷰를 **하나의 Neo4j 그래프의 두 투영**으로 통합. 그래프는 이미 그렇게 영속됨: 하이브리드(A2A→ES) 파이프라인이 `:BpmTask`를 척추로, ES 산출물을 `PROMOTED_FROM`으로, UI는 `(:UI)-[:ATTACHED_TO]->(:Command)-[:PROMOTED_FROM]->(:BpmTask)`로 연결([persistence.py](api/features/ingestion/hybrid/event_storming_bridge/persistence.py)·[design_trace.py](api/features/requirements/routes/design_trace.py)). **신규 스키마 0건의 읽기 전용 투영 + UI 정리**: (US2 P1) BPM task 인스펙터(`HybridTaskInspector.vue`)에 "포함 요소" 버튼→**모달**로 `(:BpmTask)<-[:PROMOTED_FROM]-(…)` 체인을 event-modeling 스티커로 표시; 백엔드는 `design_trace`를 일반화한 읽기 라우트 `GET /api/graph/bpm-task/{id}/design-trace`(frontier=task의 promoted Command), 프런트는 순수 컴포넌트 `DesignTraceCanvas.vue`(`trace` prop) **무수정 재사용**, **캔버스 불변**. BPM=A2A 단일 생성경로(011 process-flows는 생성원 아님). UI 없는 task="System". (US4 P2) "Big picture" 탭·패널·`bigpicture.store`·`/api/graph/bigpicture-timeline` 제거 + 비탭 소비자 정리(`TreeNode.vue` dead-branch, `ExportDocumentTemplate.vue` swimlanes 섹션). Phase 0/1 ✅(plan/research/data-model/contract/quickstart). Phase 2 ⏸ `/speckit-tasks`. Constitution PASS(신규 라벨/관계·LLM·SSE 0 → I·II·III·IV·VI 해당없음/충족).

---
이전 피처(040) 참고:
Active feature plan: [specs/040-proposal-impact-preview/plan.md](specs/040-proposal-impact-preview/plan.md)

**040 Proposal Impact Artifact Preview** (started 2026-06-11) — 039 Proposal 의 Impact/Diff 항목마다 **"열기" 진입점**을 달아, 타입에 맞는 기존 뷰어(**Data** `AggregatePanel` · **Design** `CanvasWorkspace` · **Process** `BpmnPanel` · **Processes** `EventModelingPanel`)를 **읽기 전용 미리보기**로 열고 노드를 포커스. 핵심 결정: 복제 Neo4j·라이브 임시쓰기 모두 배제, **오버레이 투영(Overlay Projection)** — 백엔드가 (라이브 그래프 슬라이스 READ) + (`Proposal.strategicDiff/tacticalDiff` 오버레이)를 메모리 합성해 **라이브 read 엔드포인트와 동일 형태**로 반환(`/api/proposals/{pid}/preview/...`, read 트랜잭션 전용). 프런트는 뷰어 스토어에 **도메인 중립 `setPreviewSource`** 만 추가하고 proposals 는 직접 임포트 없이 `robo:open-preview` 앱 레벨 이벤트로 구동(App.vue 오케스트레이션, Principle V). 신규 노드(`id=null`)에 `PREVIEW:<pid>:<idx>` temp id. 신규 Neo4j 스키마·신규 Skill **없음**(순수 read/projection, Principle X N/A). 라이브 오염 0 강제(US2/Constitution I). Constitution PASS(I~X). Phase 0/1 ✅.

---
이전 피처(039) 참고:
Active feature plan: [specs/039-proposal-lifecycle/plan.md](specs/039-proposal-lifecycle/plan.md)

**039 Proposal Lifecycle Management** (started 2026-06-05) — 038 `RequirementChange(CHG-NNN)` 패러다임을 **Proposal(PRO-NNN) 기반 생애주기**로 진화. 핵심 3요소: ① AI 인텐트 분해(`robo-proposal-intent` 스킬) → Strategic Diff(Epic/Feature/UserStory) + Tactical Diff(Aggregate/Command/Event/VO). ② Git Worktree 샌드박스 — **원천은 robo-architect가 아니라 Claude Code 탭의 대상 프로젝트(`projectRoot`)**, `<projectRoot>/.sandbox/proposal/<PRO-NNN>` worktree. 구현은 헤드리스가 아니라 **Code 탭의 살아있는 Claude Code 셀(PTY) 재사용** — 중지·피드백 가능, worktree별 독립 세션을 상단 탭으로 동시 전환(멀티 세션), 백엔드 PTY 세션 레지스트리로 **새로고침에도 재어태치**(스크롤백 replay). IMPLEMENTING 이후 상태에서도 "다시 구현하기" 가능. ③ Dual Merge(코드 머지 + Neo4j 그래프 업데이트 보상 트랜잭션). 상태: `DRAFT→SUBMITTED→IMPLEMENTING→TESTING→PENDING_ACCEPTANCE→ACCEPTED/DESTROYED`(+`MERGE_FAILED`). 4개 신규 스킬(`robo-proposals/`). 038 EFFECT·SemanticDiff·SSE 재사용, 029 Claude Code 셀(`/api/claude-code/terminal`)·`openClaudeCode`/`<KeepAlive>` 재사용. Constitution PASS(I~VII+X). Phase 0/1 ✅, 인터랙티브 셀·멀티 세션·재어태치·다시 구현 구현 완료.

---
이전 피처(038) 참고:
Active feature plan: [specs/038-change-management/plan.md](specs/038-change-management/plan.md)

**038 Requirement Change Management** (started 2026-06-02) — Requirements 탭에 **Changes** 섹션 추가: `CHG-NNN` ID를 가진 `RequirementChange` Neo4j 노드 + `EFFECT` 관계(Change→UserStory/BC/Aggregate) + `ChangeSet`(묶음) + `CONTAINS` 관계. 3가지 Change 진입점(Changes 탭 직접, 자연어 프롬프트, 탭 내 직접 수정). 상태 전이 `DRAFT→SUBMITTED→APPROVED→IMPLEMENTED`. 자기 승인 방지. 구현 시 `robo-change-tasks` 스킬 PTY 호출(SSE). 회귀 테스트 영향도 그래프 트래버설로 산출. 기존 `RequirementChange` 노드 전체 초기화. Constitution PASS(I~VII+X). Phase 0/1/2 ✅. 구현 완료(65 태스크).
<!-- SPECKIT END -->
