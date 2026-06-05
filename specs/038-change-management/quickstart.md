# Quickstart: Requirement Change Management (038)

## 빠른 검증 시나리오 (Q1–Q10)

---

### Q1 — Change 생성 (MANUAL)

```bash
curl -X POST http://localhost:8000/api/requirement-changes/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "반품 기간 연장",
    "originalPrompt": "반품 기간을 7일에서 14일로 변경",
    "sourceType": "MANUAL"
  }'
# 기대값: HTTP 201, { "id": "CHG-001", "status": "DRAFT" }
```

---

### Q2 — Change 목록 조회

```bash
curl http://localhost:8000/api/requirement-changes/
# 기대값: List[ChangeResponse], createdAt 역순
```

---

### Q3 — DIRECT_EDIT Change (UserStoryDetail 수정)

1. UserStoryDetail.vue에서 스토리 내용 수정 후 저장
2. Changes 탭 열기
3. 기대값: `sourceType=DIRECT_EDIT` Change가 생성되어 목록에 표시

---

### Q4 — Change 영향도 분석 (EFFECT)

```bash
curl http://localhost:8000/api/requirement-changes/CHG-001/impact
# 기대값: { "effects": [...] }
# PROMPT 타입은 robo-change-specify 스킬 실행 후 EFFECT 생성됨 (비동기)
```

---

### Q5 — Change 승인 워크플로우

```bash
# 1. 제출
curl -X POST http://localhost:8000/api/requirement-changes/CHG-001/submit
# 기대값: { "status": "SUBMITTED" }

# 2. 승인 (다른 사용자)
curl -X POST http://localhost:8000/api/requirement-changes/CHG-001/approve \
  -d '{"comment": "확인 완료"}'
# 기대값: { "status": "APPROVED" }

# 3. 자기 승인 시도 → 에러
# 기대값: HTTP 403
```

---

### Q6 — 구현 전 사전 확인 (Preflight)

```bash
curl http://localhost:8000/api/requirement-changes/CHG-002/preflight
# 기대값: { "pendingPriorChanges": [...], "canProceed": true }
```

---

### Q7 — 구현 시작 (SSE)

```javascript
// 브라우저 DevTools Console
const source = new EventSource('/api/requirement-changes/CHG-001/implement');
source.onmessage = e => console.log(JSON.parse(e.data));
// 기대값: planning → executing → done 이벤트 순서로 수신
```

---

### Q8 — 회귀 테스트 목록 조회

```bash
curl http://localhost:8000/api/requirement-changes/CHG-001/regression
# 기대값: { "hasContractTests": true/false, "hasE2ETests": true/false, "regressionTests": [...] }
```

---

### Q9 — ChangeSet 생성 및 묶음 승인

```bash
# ChangeSet 생성
curl -X POST http://localhost:8000/api/requirement-changes/changesets/ \
  -d '{"title": "Q3 정책 묶음", "changeIds": ["CHG-001", "CHG-002"]}'

# 묶음 승인
curl -X POST http://localhost:8000/api/requirement-changes/changesets/CS-001/approve
# 기대값: CS-001 포함 CHG-001, CHG-002 모두 APPROVED
```

---

### Q10 — Change 삭제

```bash
curl -X DELETE http://localhost:8000/api/requirement-changes/CHG-001
# IMPLEMENTED 상태: HTTP 409
# DRAFT/SUBMITTED/REJECTED 상태: HTTP 204, EFFECT 관계 함께 삭제 확인
```

---

## 소스 파일 생성 순서 (구현자용)

1. `docs/cypher/schema/03_node_types.cypher` — RequirementChange, ChangeSet 노드 추가
2. `docs/cypher/schema/04_relationships.cypher` — EFFECT, CONTAINS 관계 추가
3. `api/features/requirement_changes/requirement_changes_contracts.py` — Pydantic 모델
4. `api/features/requirement_changes/__init__.py`, `router.py`
5. `api/features/requirement_changes/services/change_id_generator.py`
6. `api/features/requirement_changes/services/effect_analyzer.py`
7. `api/features/requirement_changes/services/skill_runner.py`
8. `api/features/requirement_changes/services/regression_analyzer.py`
9. `api/features/requirement_changes/routes/changes_crud.py`
10. `api/features/requirement_changes/routes/changes_approval.py`
11. `api/features/requirement_changes/routes/changes_impact.py`
12. `api/features/requirement_changes/routes/changes_tasks.py` (SSE)
13. `api/features/requirement_changes/routes/changes_changeset.py`
14. `api/main.py` — 신규 라우터 등록
15. `skills/robo-changes/robo-change-specify/SKILL.md`
16. `skills/robo-changes/robo-change-tasks/SKILL.md`
17. `frontend/src/features/requirements/ui/ChangesPanel.vue`
18. `frontend/src/features/requirements/ui/ChangeDetail.vue`
19. `frontend/src/features/requirements/ui/ChangeImpactView.vue`
20. `frontend/src/features/requirements/ui/ChangeTasksView.vue`
21. `frontend/src/features/requirements/requirements.store.js` — 신규 액션 추가
22. `frontend/src/features/requirements/ui/RequirementsPanel.vue` — Changes 탭 추가
23. 기존 UserStoryDetail.vue, EpicDetail.vue — 저장 시 DIRECT_EDIT Change 생성 추가

## 기존 데이터 초기화

```cypher
// 앱 시작 전 또는 마이그레이션 스크립트로 실행
MATCH (n:RequirementChange) DETACH DELETE n;
MATCH (n:ChangeSet) DETACH DELETE n;
```

## 회귀 체크 (Out-of-band)

- 기존 `/api/change/*` 엔드포인트 정상 동작 확인 (regression)
- `RequirementsPanel.vue` 기존 탭(Tree, Chat 등) 영향 없음 확인
- Neo4j `CHANGED_TO` 관계 미삭제 확인
