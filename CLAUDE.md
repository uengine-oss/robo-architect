<!-- SPECKIT START -->
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
