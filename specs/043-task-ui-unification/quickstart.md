# Quickstart: task=UI 통합 검증

전제: 프런트(5173)+백엔드(8000)+neo4j. 골든 픽스처(spec 036 input_resource) **재인제스천** 필요(인제스천 로직 변경).

## Q1. task당 1 트리거 UI (US2, SC-002)
1. 골든 문서를 인제스천(재실행).
2. 그래프: `MATCH (t:BpmTask) OPTIONAL MATCH (t)-[:PROMOTED_TO]->(:UserStory)-[:IMPLEMENTS]->(:Command)<-[:ATTACHED_TO]-(u:UI) RETURN t, count(DISTINCT u)`.
3. **기대**: 사람-트리거 task당 트리거 UI **1개**. Command 2개 task도 UI 1개. policy-invoked만인 task = 0.

## Q2. ReadModel 분기 (US3, SC-003)
1. 인제스천 후 ReadModel UI 확인.
2. **기대**: 무조건 생성된 ReadModel UI 0. 조회/검색 판정 ReadModel만 `(:UI)-[:ATTACHED_TO]->(:ReadModel)`(screen) 승격, 나머지는 `ATTACHED_TO {role:'display'}`로 소비 화면에 표시.

## Q3. Command/Event 불변 (SC-005)
1. 재인제스천 전후 `MATCH (c:Command) WHERE c.task_id IS NOT NULL RETURN count(c)` 및 task 귀속 비교.
2. **기대**: Command/Event의 task_id 귀속 회귀 0. A2A `:BpmTask`/`NEXT` 불변.

## Q4. 단일 Process 탭 토글 (US1, SC-001)
1. 앱에서 상단 탭 확인 → 'Event Modeling' 탭 없음.
2. Process 탭 → BPM⇄EM 토글.
3. **기대**: 토글 시 같은 UI 앵커 유지, 데이터 중복/불일치 0.

## Q5. EM 형식 뷰 (US4, SC-004)
1. Process 탭에서 task 포함요소 열기.
2. **기대**: 가로 레인(UI→Command→Event→ReadModel) 형식. requirements 설계-궤적은 기존 컬럼 형식 유지.

## Q6. 멱등 + 신규 스키마 0
1. 동일 문서 재인제스천 2회 → task당 UI 수 불변.
2. `CALL db.relationshipTypes()` / `db.labels()` 전후 비교 → **신규 라벨/관계 0**(ReadModel `ATTACHED_TO.role` 속성만).

## Out-of-band
- LLM 판정(트리거/조회) propose→통합 뷰 노출, 사용자 교정 경로(D4).
- 기존(재인제스천 전) 세션은 Command당 UI — 통합 뷰가 오류 없이 표시(FR-011).
