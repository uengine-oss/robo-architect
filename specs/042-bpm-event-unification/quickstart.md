# Quickstart: BPM ↔ Event Modeling 통합 검증

전제: 하이브리드 인제스천이 완료된 세션(`:BpmTask`·`PROMOTED_FROM` 영속). spec 036의 input_resource PDF 자산을 골든 픽스처로 재사용.

## Q1. BPM task 포함 요소 모달 (US2, P1)

1. BPM 뷰를 열고 한 task를 클릭 → `HybridTaskInspector`가 뜬다.
2. 인스펙터의 **"포함 요소 / 설계 궤적 보기"** 버튼 클릭.
3. **기대**: 모달이 열려 그 task의 Command·Event·(있으면)UI·Policy·Aggregate가 event-modeling 스티커로 렌더된다.
4. 모달을 닫는다 → **기대**: BPM 캔버스가 처음과 동일(새 엣지/노드 0, 레이아웃 불변 — US2 AC2).

## Q2. 모달 = 그래프 조회 1:1 (SC-002)

1. `GET /api/graph/bpm-task/{task_id}/design-trace` 직접 호출.
2. Neo4j에서 `MATCH (c:Command)-[:PROMOTED_FROM]->(:BpmTask {id:$tid}) ...` bounded 확장 결과와 비교.
3. **기대**: 모달/응답 노드 집합 = 쿼리 결과(누락·과포함 0).

## Q3. Empty task (US2 AC3)

1. promoted Command가 없는 task에서 버튼 클릭.
2. **기대**: `empty:true` → "이 task에 귀속된 설계 요소가 없습니다" 비차단 안내. 오류·빈 모달 깨짐 없음.

## Q4. 두 뷰 동일 task 정합 (US1)

1. 같은 프로세스를 BPM 뷰와 Event Modeling 뷰에서 연다.
2. **기대**: BPM task에 귀속된 Command/Event가 Event Modeling 뷰의 **동일 식별자** 요소와 일치(한 뷰 전용 복제 0 — SC-001).

## Q5. A2A 척추 + task별 추출 회귀 (US3, P2)

1. 골든 픽스처 문서를 하이브리드 인제스천에 통과.
2. **기대**: 각 `:BpmTask` 아래에 그 task에서 추출된 Command/Event 체인이 `PROMOTED_FROM`으로 귀속. 같은 task가 두 뷰에서 일관 — 기준 대비 **회귀 0건**(SC-004). 재인제스천 시 task/체인 중복 0(멱등).

## Q6. Big picture 제거 회귀 (US4, P2)

1. 앱 실행 → 모든 탭/메뉴에 "Big picture" 진입점 없음.
2. `grep -ri "bigpicture\|big.picture\|BigPicture" frontend/src api` → **소스 0건**(스타일 잔재 포함, SC-005).
3. **export 회귀**: 문서 export 실행 → 오류 없이 생성(swimlane/빅픽처 섹션 제거 반영 — D5-3 컨펌 포인트).
4. **navigator 회귀**: TreeNode에서 BC 노드 클릭/추가(다른 탭) 정상.
5. **기대**: BPM/Event Modeling/Requirements/Aggregate 뷰 전부 정상.

## Out-of-band 체크

- 신규 Neo4j 노드 라벨/관계 **0건**(스키마 diff 0).
- trace 라우트 호출 전/후 그래프 노드·관계 수 동일(읽기 전용).
- 신규 LLM 호출·SSE·propose/confirm 경로 0(해당 없음).
- 언어 정책(생성물 한국어 등) 영향 없음(읽기 전용 투영).

## 컨펌 포인트 (비차단)

- **D5-3**: export 산출물에서 빅픽처(swimlane) 섹션 제거가 기본값. 만약 export에 해당 섹션을 유지하려면 대체 출처(canvas/event-modeling swimlane 투영)로 전환 — Q6-3에서 사용자 확인.
