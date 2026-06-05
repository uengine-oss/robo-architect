<!-- SPECKIT START -->
Active feature plan: [specs/038-change-management/plan.md](specs/038-change-management/plan.md)

**038 Requirement Change Management** (started 2026-06-02) — Requirements 탭에 **Changes** 섹션 추가: `CHG-NNN` ID를 가진 `RequirementChange` Neo4j 노드 + `EFFECT` 관계(Change→UserStory/BC/Aggregate) + `ChangeSet`(묶음) + `CONTAINS` 관계. 3가지 Change 진입점(Changes 탭 직접, 자연어 프롬프트, 탭 내 직접 수정). 상태 전이 `DRAFT→SUBMITTED→APPROVED→IMPLEMENTED`. 자기 승인 방지. 구현 시 `robo-change-tasks` 스킬 PTY 호출(SSE). 회귀 테스트 영향도 그래프 트래버설로 산출. 기존 `RequirementChange` 노드 전체 초기화. Constitution PASS(I~VII+X). Phase 0/1/2 ✅. 구현 완료(65 태스크).

---
이전 피처(037) 참고:
Active feature plan: [specs/037-requirement-changes-propagation/plan.md](specs/037-requirement-changes-propagation/plan.md)

**037 Requirement Changes Propagation** (started 2026-06-01) — Requirements 탭에 "Changes" 섹션 추가: 자연어 요구사항 변경을 `CHG-NNN` ID를 가진 Change 레코드로 관리, US 제안/확정 → 설계 영향도 분석 → 설계 변경 계획 → 코드 태스크 생성 순으로 전파. OpenSpec "spec-as-diff" 패러다임. 신규 `RequirementChange` Neo4j 노드 + `PRODUCES` 관계 + `UserStory.originChangeId` 속성. **Constitution X(Skill-First)**: AI 처리는 `skills/robo-changes/` 스킬(robo-change-specify/plan/tasks, extends: speckit-*/robo-*)이 수행하고, 백엔드(`skill_runner.py` + 파서들)는 PTY 실행 + stdout 파싱 + Neo4j 반영만 담당. LangChain/LangGraph 신규 코드 없음. SSE = PTY stdout → SSE 프록시(Constitution III). 스킬 충돌 = `extends:` Override 패턴으로 전부 해결(완전 새 스킬 없음). Phase 0/1 ✅(plan/research/data-model/contracts/quickstart + 3 SKILL.md). Phase 2 ⏸ `/speckit-tasks`. Constitution PASS(I~VII + X).
<!-- SPECKIT END -->
