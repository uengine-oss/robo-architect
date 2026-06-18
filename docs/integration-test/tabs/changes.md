# Changes 탭 — 통합 검증 (초안)

> 다음 세션이 이어서 진행할 인벤토리·시나리오 **초안**. 결과는 모두 ⬜(미실행).
> 진행 방식은 [stories.md](stories.md)·[process-event-modeling.md](process-event-modeling.md) 참고(스펙+코드 인벤토리 → store↔라우트 확정 → 라이브 검증 → 실데이터 교차검증 → 이슈 기록).

- **activeTab 값**: `Changes` (**TopBar에서 숨김** — 노출 안 됨. 접근 경로 먼저 확정 필요: 디버그 플래그/직접 네비)
- **패널 컴포넌트**: [`ChangesRootPanel.vue`](../../../frontend/src/features/requirements/ui/ChangesRootPanel.vue) → [`ChangesPanel.vue`](../../../frontend/src/features/requirements/ui/ChangesPanel.vue) (+ `ChangeDetail.vue`, `RegressionTab.vue`)
- **프런트 store**: [`requirements.store.js`](../../../frontend/src/features/requirements/requirements.store.js) (Changes 전용 store 없음 — Requirements store에 통합)
- **백엔드**: [`api/features/requirement_changes/`](../../../api/features/requirement_changes/) (`routes/`, `requirement_changes_contracts.py`, `services/`)
- **관련 스펙**: 038(Requirement Change Management). 후속 039(Proposal)가 이 패러다임을 Proposal 기반으로 진화 → **Changes는 컴포넌트 유지하되 상단바에서 숨김**(README 참조)
- **상태**: 🟡 초안 (인벤토리 완료, 라이브 검증 대기)

## 1. 탭의 의도/목표 (스펙 요약)

요구사항 **변경**을 `CHG-NNN` ID를 가진 **`RequirementChange` Neo4j 노드**로 관리. 변경의 **영향도**를 그래프 트래버설로 산출(`EFFECT` 관계: Change→영향받는 UserStory/BC/Aggregate/Command/Event 등), 상태 전이로 생애주기 관리, 구현 시 `robo-change-tasks` 스킬 PTY 호출(SSE), 회귀 테스트 영향도 산출. 변경 묶음은 `ChangeSet`(`CONTAINS` 관계)으로 관리. 자기 승인 방지.

> ⚠️ 스펙 038은 상태 `DRAFT→SUBMITTED→APPROVED→IMPLEMENTED` 4단계로 기술하나, **실제 코드는 더 세분**: `DRAFT → SUBMITTED → PLAN_APPROVED → DESIGN_APPLIED → APPROVED → IMPLEMENTED`(+`REJECTED`). 라이브에서 실제 전이·UI 확정.
> ⚠️ Changes 탭은 **상단바에서 숨김**(039 Proposal로 대체). 검증하려면 접근 경로(예: `?debug=1`/직접 activeTab 설정)부터 확인.

## 2. 보유 기능 목록 (코드 대조 초안)

| # | 기능 | 출처 스펙 | 핵심 컴포넌트 | 엔드포인트/store액션 |
|---|---|---|---|---|
| 1 | Change 목록 조회 | 038 | `ChangesPanel` | `GET /api/requirement-changes/` ← `fetchChanges` |
| 2 | Change 생성(프롬프트/수동) | 038 | `ChangesPanel` 생성 다이얼로그 | `POST /api/requirement-changes/` ← `createChange` (originalPrompt·sourceType) |
| 3 | Change 상세 조회 | 038 | `ChangeDetail` | `GET /api/requirement-changes/{id}` ← `fetchChangeById` |
| 4 | 영향도(EFFECT) 분석·표시 | 038 | `ChangeDetail` 영향도 탭 | 생성 직후 자동 분석(`autoAnalyzeChangeId`), `effects`(EffectItem: nodeId·impactLevel·changeType MODIFY/CREATE·templateData) |
| 5 | 상태 전이(submit/approve/reject) | 038 | `ChangeDetail` 액션 | `POST /{id}/submit·/approve·/reject` ← `submitChange`/`approveChange`/`rejectChange` |
| 6 | 자기 승인 방지 | 038 | 백엔드 | `approve` 시 author==actor면 403 |
| 7 | 상태 이력(statusHistory) | 038 | `ChangeDetail` | 각 전이 시 `statusHistory` append(fromStatus·toStatus·at·actor·comment) |
| 8 | 구현(robo-change-tasks PTY/SSE) | 038 | `ChangeDetail` 구현 | `implementChange`(ImplementationProgress: phase·tasks·percentage), preflight(미완료 선행 Change 경고) |
| 9 | 회귀 테스트 영향도 | 038 | `RegressionTab` | `fetchRegression(changeId)` → `regressionTests`(testId·affectedNodeIds) |
| 10 | Change 삭제 | 038 | `ChangesPanel` 삭제확인 | `DELETE /api/requirement-changes/{id}` ← `deleteChange` |
| 11 | 상태 필터 | 038 | `ChangesPanel` | `filterStatus` computed |
| 12 | ChangeSet 생성·묶음 | 038 | (UI 확정 필요) | `POST /changesets/` (title·changeIds), `CONTAINS` |
| 13 | ChangeSet 전이/제거 | 038 | (UI 확정 필요) | `/changesets/{id}/submit·approve·reject`, `DELETE /changesets/{id}/changes/{id}` |
| 14 | 정규화/설계 반영(PLAN_APPROVED·DESIGN_APPLIED) | 038+ | `ChangeDetail`(onDesignApplied/onDesignUndone) | 라이브에서 전이·동작 확정 |

> store↔라우트 1:1 대조, 상태 전이 가드(어느 상태→어느 상태 허용), ChangeSet UI 진입점은 다음 세션에서 curl/코드로 확정.

## 3. 검증 시나리오 (설계 — 다음 세션 실행)

> 전제: 백엔드/프런트 기동. **Changes 탭 접근 경로 확보**(숨김 상태). 그래프에 UserStory/BC/Aggregate 등 설계 요소 존재(Stories·ES 승격 산출물).

### S0. Changes 탭 접근 — ⬜
- 숨김 탭을 어떻게 여는지 확정(디버그 플래그/직접 activeTab). 열리면 `ChangesPanel` 렌더.

### S1. Change 생성 + 자동 영향도 분석 — ⬜
- 생성 다이얼로그 → originalPrompt 입력 → 생성 → `CHG-NNN` 노드 생성 + 자동 선택 + 영향도 탭 포커스 → `EFFECT` 관계·impactLevel 표시.

### S2. Change 상세/영향도 교차검증 — ⬜
- effects의 nodeId·changeType(MODIFY/CREATE)·impactLevel이 그래프 `EFFECT` 관계와 일치. CREATE 항목의 templateData 표시.

### S3. 상태 전이(submit→approve) + 자기 승인 방지 — ⬜
- submit → SUBMITTED, 다른 actor approve → APPROVED. **본인 approve 시 403**. statusHistory 누적.

### S4. PLAN_APPROVED / DESIGN_APPLIED 전이 — ⬜
- 계획 승인·설계 반영 단계 UI·전이 확정(038 스펙엔 없던 세분 단계). onDesignApplied/Undone 동작.

### S5. 구현(robo-change-tasks PTY/SSE) — ⬜
- 구현 트리거 → preflight(미완료 선행 Change 경고) → SSE 진행상황(phase·tasks·percentage) → IMPLEMENTED. (Code 탭 PTY 재사용 여부 확인)

### S6. 회귀 테스트 영향도 — ⬜
- `RegressionTab` → 영향받는 테스트 목록(testId·affectedNodeIds). 그래프 트래버설 산출 교차검증.

### S7. ChangeSet 묶음 — ⬜
- 여러 Change를 ChangeSet으로 묶고(`CONTAINS`) 일괄 submit/approve. 제거 시 Change 노드 유지.

### S8. Change 삭제 — ⬜
- 삭제확인 → `DELETE` → 목록·그래프에서 제거. 연결 EFFECT 정리 확인.

## 4. 발견 이슈

| # | 심각도 | 증상 | 원인(추정) | 후속 |
|---|---|---|---|---|

## 5. 결론

- (초안) 다음 세션에서 **S0(접근 경로) 먼저 확정** → §2 인벤토리를 store↔라우트로 확정 → S1~S8 라이브 검증.
- **핵심 회귀 위험**: ① 숨김 탭이라 진입 경로·라우팅 ② 038→039(Proposal) 진화로 Changes가 deprecated 경로일 수 있음(실제 동작 여부부터 확인) ③ 자기 승인 방지 ④ 구현 PTY/SSE(029 Code 셀과 공유 여부) ⑤ 영향도/회귀 그래프 트래버설 정확도.
- 교차: 영향도 결과는 **Stories(UserStory)·Design(BC/Aggregate)·Data** 탭과, 구현은 **Code 탭(PTY)**·**Proposals(039)** 와 관계 확인.
