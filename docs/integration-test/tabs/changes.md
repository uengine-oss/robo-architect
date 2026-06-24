# Changes 탭 — 통합 검증 (초안)

> 다음 세션이 이어서 진행할 인벤토리·시나리오 **초안**. 결과는 모두 ⬜(미실행).
> 진행 방식은 [stories.md](stories.md)·[process-event-modeling.md](process-event-modeling.md) 참고(스펙+코드 인벤토리 → store↔라우트 확정 → 라이브 검증 → 실데이터 교차검증 → 이슈 기록).

- **activeTab 값**: `Changes` (**TopBar에서 숨김** — 노출 안 됨. 접근 경로 먼저 확정 필요: 디버그 플래그/직접 네비)
- **패널 컴포넌트**: [`ChangesRootPanel.vue`](../../../frontend/src/features/requirements/ui/ChangesRootPanel.vue) → [`ChangesPanel.vue`](../../../frontend/src/features/requirements/ui/ChangesPanel.vue) (+ `ChangeDetail.vue`, `RegressionTab.vue`)
- **프런트 store**: [`requirements.store.js`](../../../frontend/src/features/requirements/requirements.store.js) (Changes 전용 store 없음 — Requirements store에 통합)
- **백엔드**: [`api/features/requirement_changes/`](../../../api/features/requirement_changes/) (`routes/`, `requirement_changes_contracts.py`, `services/`)
- **관련 스펙**: 038(Requirement Change Management). 후속 039(Proposal)가 이 패러다임을 Proposal 기반으로 진화 → **Changes는 컴포넌트 유지하되 상단바에서 숨김**(README 참조)
- **상태**: 🟢 라이브 검증 중 (S0~S3 완료, 2건 P0 버그 발견·수정). 검증일 2026-06-24

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

### S0. Changes 탭 접근 — ✅
- 숨김 원인: [TopBar.vue](../../../frontend/src/app/layout/TopBar.vue)의 `tabs` 배열에서 제외(컴포넌트는 [App.vue:96](../../../frontend/src/App.vue#L96) `tabComponents`에 유지). 무수정 진입로: `window.dispatchEvent(new CustomEvent('robo:switch-tab',{detail:'Changes'}))`. 검증용으로 `tabs`에 'Changes' **임시 추가**(검증 후 제거 예정).

### S1. Change 생성 + 자동 영향도 분석 — ✅ (버그 C1 수정 후)
- 생성: CHG-001 DRAFT 정상. **초기 영향도 0건 → C1(무효 API키) 수정 후 9 effect**(US-007/009/010/012/013, Feature×2, Aggregate×1, BC×1). UI 영향도 트리 정상 표시 확인.

### S2. Change 상세/영향도 교차검증 — ✅
- 그래프 EFFECT 11건 영속 = MODIFY 9 + **CREATE 2**(CreationIntent 플레이스홀더, 신규 UserStory 제안). changeType MODIFY/CREATE·impactLevel 일치 확인.

### S3. 상태 전이(submit→approve) + 자기 승인 방지 — ✅
- submit DRAFT→SUBMITTED, 1차 approve SUBMITTED→**PLAN_APPROVED**(APPROVED 아님 — 2단계 승인). statusHistory 3건 누적(actor 기록). 자기승인 403은 비-ProductOwner 헤더로 확인(가드가 mutation 전 차단). → C3 참조.

### S4. PLAN_APPROVED / DESIGN_APPLIED 전이 — 🟡 진행중 (apply 재실행 대기)
- apply-design(PLAN_APPROVED→DESIGN_APPLIED) **버그 C2로 데이터 오염** → undo-design으로 정리(reverted 11). **C2 수정 후 재적용으로 클린 검증 예정**. undo(DESIGN_APPLIED→PLAN_APPROVED) 역적용 정상.

### S5. 구현(Code 탭 PTY 핸드오프) — 🟡 핸드오프✅ / 풀실행 보류
- "구현 시작" → `openClaudeCode(workdir, '/robo-implement CHG-001')` Code 탭 핸드오프(029 셀 재사용=039 패턴). `/robo-implement`에 **CHG-NNN 전용 모드**([robo-implement/SKILL.md:9](../../../skills/robo-spec/robo-implement/SKILL.md#L9)) 존재 → 구현 후 `POST /implement`로 IMPLEMENTED 전이. **핸드오프 검증 완료.** 풀 실행은 C6(명령 미자동실행)·**C7(workdir이 빈 폴더=실제 코드베이스 아님)** 선결 필요 → Code 탭(그룹 C) 검증 시. status는 APPROVED 유지.

### S6. 회귀 테스트 영향도 — ✅ (C8 수정 후)
- 백엔드 `GET /{id}/regression` = impactedDesignNodes 11 + regressionTests 2(BC 계약테스트·UI스토리 E2E, 트래버설 기반). UI는 **C8**(계약 드리프트로 행 공백) 수정 후 2건 정상 표시. testId=None은 그래프에 Test 노드 없어 정상.

### S7. ChangeSet 묶음 — 🟠 백엔드만 (UI 전무, C9)
- curl 검증: 생성·CONTAINS·changeSetId·일괄 submit·멤버 제거(노드 보존) ✅ / 일괄 approve 영구 403(C9: ProductOwner 무시+1단계 전이) / changeset 자체 DELETE 엔드포인트 없음(405). **생성/관리 UI 부재 — UI로 검증 불가.**

### S8. Change 삭제 — ✅
- 목록 X 삭제 → `DELETE` → 노드 404(제거 확인). **반려(REJECTED) 분기도 함께 검증** — 노드 보존+statusHistory `DRAFT→SUBMITTED→REJECTED`. (S3 reject 분기 보강)

## 4. 발견 이슈

| # | 심각도 | 증상 | 원인(확정) | 후속 |
|---|---|---|---|---|
| C1 | 🔴 P0 | **자동 영향도 분석 0건**("결과 안나옴"). Change 생성은 정상이나 effects=0 | [.env:26](../../../.env#L26)의 **무효(만료) `ANTHROPIC_API_KEY`**를 백엔드가 `os.environ`에 로드 → 영향도 스킬이 띄우는 헤드리스 `claude -p`가 그 키로 인증 시도 → `Invalid API key`로 ~2초 즉시 실패 → JSON 없음 → effects 0. (claude.ai 로그인이 있어도 API키가 우선) | **수정함**: [skill_runner.py](../../../api/features/requirement_changes/services/skill_runner.py) 서브프로세스 env에서 `ANTHROPIC_API_KEY` 제거(`_skill_env`) → claude.ai 로그인 폴백. `run_specify_skill`·`run_skill_lines` 양쪽. 재분석 32초/9 effect 정상. **근본원인 정정**: `api/platform/skill_runner.py`(플랫폼 공용)에는 **이미 이 픽스가 존재**(`ANTHROPIC_API_KEY`+`ANTHROPIC_AUTH_TOKEN` 제거, 주석까지)인데, **Changes는 공용 러너를 안 쓰고 자체 복제본(`requirement_changes/services/skill_runner.py`)을 써서 픽스를 빠뜨림**. 내 수정도 둘 다 제거하도록 정렬. **권장 영구픽스**: 코드 유지(+가능하면 Changes를 platform/skill_runner로 통합), `.env` 키는 백엔드 SDK(langchain)용이라 별개. **C11(타 스폰 지점) 점검 필요** |
| C2 | 🔴 P0 | **데이터 오염**: apply-design(설계 반영)이 `"Invalid API key · Fix external API key"` 문자열을 US-007 등 acceptanceCriteria에 list_append하고 정크 UserStory 2개(us-289978f1, us-6ef1dade)를 실그래프에 생성 | [design_applier.py](../../../api/features/requirement_changes/services/design_applier.py#L352) `_call_claude`가 ① C1과 동일 env 버그(별도 spawn 경로) + ② `return result if result else None` — **에러 stdout을 정상 LLM 출력으로 오인**해 검증 없이 그래프에 적용 | **수정함**: `_call_claude`에 `env=_claude_env()` + 에러문구 가드(`_CLAUDE_ERROR_MARKERS`, returncode≠0 → None). 오염은 `undo-design`(reverted 11/errors 0)으로 정리 완료(정크 노드 삭제·diff 클리어 확인) |
| C4 | 🟠 | **design-reflect 모달이 SSE attach 실패 시 fresh 업로드 폼으로 degrade**. apply-design이 만든 신규 UserStory(CREATE)가 pending-design으로 잡혀 Design/Processes/EM 탭 진입 시 `DesignReflectPrompt`→확인→`requestDesignForUserStories`(`POST /api/ingest/user-stories/design`, US id만 설계 생성)로 attach 모달이 열려야 하나, **SSE 연결 실패 시** [Modal onerror L1056-1073](../../../frontend/src/features/requirementsIngestion/ui/RequirementsIngestionModal.vue#L1056)가 `isProcessing=false`로 만들어 모달이 **"요구사항 문서 업로드"(파일 드롭+분석 시작) 폼으로 표시**됨. "기존 데이터 974개 노드" 경고와 함께 떠 **우발적 재인제스천을 유발할 수 있는 위험한 degrade**. (이번엔 검증 중 백엔드 파일 편집→uvicorn `--reload`가 진행 SSE를 끊은 게 트리거. 단 네트워크 블립·백엔드 재시작 등 **어떤 SSE 드롭에도 재현되는 standing fragility**) | **안전성은 확인됨**: 설령 그 폼에서 분석 시작해도 인제스천은 **증분 upsert(wipe 아님)** — 기존 데이터 자동삭제 X, 전체삭제는 별도 `/api/ingest/clear-all`만([Modal:608-610](../../../frontend/src/features/requirementsIngestion/ui/RequirementsIngestionModal.vue#L608)). **후속**: attach 실패 시 업로드 폼이 아니라 **재연결/닫기 상태**를 보여야 함(degrade 가드). Design/Stories 탭 정식 검증 시 처리. |
| C5 | 🟠 **(UX 신뢰성)** | **design-reflect 모달이 원천 인제스천과 픽셀 동일 UI라 "전체 재인제스천" 오해 유발**. (사용자 지적) 안전성(증분 upsert)과 무관하게, ① 모달 제목이 **하드코딩 "요구사항 문서 업로드"**([Modal:1690](../../../frontend/src/features/requirementsIngestion/ui/RequirementsIngestionModal.vue#L1690), 맥락 무관 고정) → **정상 attach/진행 모드에서도** 헤더가 "문서 업로드"로 표시 ② 파일 드롭존·"분석 시작"·UI생성/언어 옵션·"기존 데이터 974개 노드" 배너가 원천 인제스천과 동일 → 사용자는 기존 설계를 덮어쓰는 줄로 오해. 034 US7이 DRY 목적("기존 인제스천 진행 다이얼로그/SSE 재사용")으로 모달을 통째로 재사용했으나 **맥락 리라벨을 안 함**. | **후속**: design-reflect/설계 갭 메우기 맥락에 ① **제목·문구를 맥락별로**(예: "설계 보강 진행 중 — 신규 스토리 N건") ② attach 모드에선 **업로드 컨트롤 자체를 렌더하지 않음**(prop로 progress-only) ③ "기존 데이터 N개 노드"는 병합 안내임을 명시. C4와 같은 컴포넌트라 함께 처리. Design/Stories 탭 정식 검증 시. |
| C6 | 🟡 | **구현 시작 → Code 탭 명령 자동실행 안 됨**(미리입력만). "구현 시작"이 `openClaudeCode(workdir, '/robo-implement CHG-001')`→Code탭 핸드오프는 정상이나, **메인 세션을 새로 열 때** 명령이 실행되지 않고 입력창에만 남음 | [ClaudeCodeWorkspace.vue:350·357](../../../frontend/src/features/claudeCode/ui/ClaudeCodeWorkspace.vue#L350): 새 메인 세션을 `initialCommand:''`로 만들고 즉시 `nextTick`에 `sendInput(cmd+'\n')` 호출 → **claude PTY 부팅(~수초) 전에 전송돼 Enter가 안 먹음**(콜드스타트 레이스). proposal 세션은 `initialCommand`(지연 실행) 사용하나 메인 경로는 미사용. | **후속**: 메인 세션도 신규 생성 시 `initialCommand`(claude ready 후 실행) 경로를 타게 하거나, 세션 ready 이벤트 후 sendInput. 현재 워크어라운드=사용자가 Enter. Code 탭 검증(그룹 C) 시 처리. |
| C7 | 🟠 | **구현 target workdir이 빈 폴더**(Explorer에 README만). Changes 구현은 `claudeCodeWorkdir`=`localStorage['claude_code_workspace_root']`(메인 워크스페이스 루트)를 그대로 사용([ChangeDetail.vue:134](../../../frontend/src/features/requirements/ui/ChangeDetail.vue#L134))하는데, 그 루트가 실제 대상 코드베이스가 아니라 거의 빈 폴더(PRD 생성 홈 추정)라 **`/robo-implement CHG-001`이 수정할 코드가 없음** | FOLLOW-UPS [I16](../FOLLOW-UPS.md)(폴더피커=활성세션, 메인 루트가 실제 프로젝트를 안 가리킴)과 동일 근원. 구현 핸드오프 자체는 정상, **target 프로젝트 지정이 빠짐**. | **후속**: 구현 전 Code 탭을 실제 대상 프로젝트 루트로 지정 필요. Changes/Proposals 구현은 "대상 프로젝트 루트"를 명시적으로 받아야(039 proposal의 projectRoot처럼). Code 탭 검증(그룹 C) 시. |
| C8 | 🟠 | **회귀 테스트 탭 행 내용이 전부 빈 박스**. "영향받는 테스트: 2개" 카운트는 맞으나 각 행이 비어 보임 | 프런트↔백엔드 **계약 드리프트**: [RegressionTab.vue](../../../frontend/src/features/requirements/ui/RegressionTab.vue)가 구 스키마(`testId`·`testName`·`affectedNodeIds[]`)를 렌더하나 백엔드는 `testType`·`description`·`affectedNodeId`(단수)·`affectedNodeLabel` 반환. `testId`=null(테스트 노드 없음)이라 id span 빈칸, `testName`/`affectedNodeIds` 필드 부재로 v-if 미표시 → 행 전체 공백 | **수정함**: RegressionTab을 실제 필드(`description` 본문·`testType` 배지·`affectedNodeLabel/Id` 대상)로 렌더, key를 testId 부재 시 합성. 백엔드 산출=11 impacted nodes + 2 test 추천(BC 계약테스트·UI스토리 E2E, 트래버설 기반)은 정상. |
| C9 | 🟠 | **ChangeSet: 생성/관리 UI 전무 + 일괄 approve 불일치**. (a) `createChangeSet`/`fetchChangeSet` store 함수는 있으나 **어떤 .vue도 호출 안 함** — ChangesPanel에 다중선택/묶기/일괄전이 UI 없음. 유일한 ChangeSet UI는 [ChangeDetail.vue:225](../../../frontend/src/features/requirements/ui/ChangeDetail.vue#L225) `changeSetId` **읽기전용 표시**. (b) 백엔드는 정상 동작(curl 검증: 생성·CONTAINS·changeSetId 세팅·일괄 submit·멤버 제거 후 노드 보존 모두 ✅) 단 **일괄 approve가 영구 403** | (a) UI 미구현(038 백엔드만). (b) [changes_changeset.py:117-130](../../../api/features/requirement_changes/routes/changes_changeset.py#L117) approve가 `author==actor`만 보고 **ProductOwner 우회 무시**(개별 approve `_check_self_approval`과 불일치) → 무인증 단일사용자 환경서 묶음 approve 영구 차단. 또 `SUBMITTED→APPROVED` **1단계 전이**로 개별의 2단계(PLAN_APPROVED/DESIGN_APPLIED) 건너뜀. (c) **changeset 자체 DELETE 엔드포인트 없음**(`DELETE /changesets/{id}`→405) → 빈 묶음(CS-001) 정리 불가 | **후속**: ① ChangeSet 생성/관리 UI 신설(다중선택→묶기, 일괄 전이) 또는 feature 폐기 결정 ② 일괄 approve도 `_check_self_approval`(ProductOwner 허용) 재사용 + 2단계 전이 정합. 038 재방문 시. |
| C10 | 🟡 | GET `/changesets/{id}` 응답에서 **묶음 자체 `createdAt`이 Neo4j DateTime 원시객체로 직렬화**(`_DateTime__date`…). 멤버 change의 createdAt은 ISO 정상 | changeset 직렬화 경로가 datetime→ISO 변환 누락 | 경미(표시용). changeset 직렬화에 ISO 변환 추가. |
| C11 | 🟠 **(횡단, 미검증)** | **동일 헤드리스-claude env 버그가 다른 스폰 지점에도 잠재**. `api/features/claude_code/pty_backend.py:139`는 `os.environ.copy()` 후 `ANTHROPIC_API_KEY` **미제거** → **Code 탭 인터랙티브 claude 세션도 무효 키 상속 가능**(S5 `/robo-implement`·Proposals 039 구현이 터미널에서 인증 실패할 수 있음). 그 외 `requirements/routes/child_story_generation.py`·`requirements/ddd_wizard/engine.py`·`change_management/planning_agent`도 claude 스폰 — 공용 러너 사용 여부 미확인. | **후속**: pty_backend 및 기타 스폰 지점이 platform/skill_runner의 env 정화를 쓰는지 점검. Code 탭(그룹 C)·DDD 마법사·Proposals 검증 시 동일 증상 의심. |
| C3 | 🟡 | 무인증 환경에서 **자기승인 방지가 기본 무력화** — 기본 actor 역할 `{ProductOwner}`([models.py:47](../../../api/platform/identity/models.py#L47))가 자기승인 제한을 우회. UI로는 403 재현 불가(curl 비-ProductOwner 헤더로만 확인됨) | 설계상 의도(무인증 단일사용자 편의). | 인증 도입 시 자연 해소([Stories I7]과 동일 맥락). 기록만. |

## 5. 결론 (라이브 검증 2026-06-24)

**검증 범위**: S0~S8 라이브 진행(사용자 UI 조작 + 그래프/API 교차검증). 대상 Change=CHG-001("본인확인 시도 3회 제한·자동면제", 자동납부 도메인 합성 그래프).

**통과**: S0(접근)·S1(생성+영향도)·S2(영향도 그래프)·S3(상태전이+자기승인)·S4(설계반영+2차승인)·S6(회귀)·S8(삭제+반려). **핸드오프만 검증**: S5(구현). **백엔드만**: S7(ChangeSet, UI 없음).

**발견·수정한 P0/주요 버그**:
- **C1 🔴(수정)** — 무효 `ANTHROPIC_API_KEY`(.env)가 헤드리스 스킬 인증 실패 유발 → 영향도 0건. skill_runner env 정화.
- **C2 🔴(수정)** — apply-design의 `_call_claude`가 같은 키 버그 + 에러문구를 정상출력으로 오인해 **그래프 데이터 오염**. env 정화 + 에러 가드. undo-design으로 오염 정리.
- **C8 🟠(수정)** — RegressionTab 프런트↔백엔드 계약 드리프트로 행 공백. 실제 필드 렌더.
- **C4/C5 🟠** — design-reflect 모달이 SSE 실패 시 fresh 업로드 폼으로 degrade(C4) + 원천 인제스천과 동일 UI/제목이라 오해 유발(C5). (업로드는 증분 upsert라 wipe는 아님 — 안전성 확인)
- **C6 🟡 / C7 🟠** — 구현 명령 미자동실행(콜드스타트) / workdir이 빈 폴더(실제 코드베이스 아님, I16).
- **C9 🟠 / C10 🟡** — ChangeSet UI 전무 + 일괄 approve 영구 403(ProductOwner 무시) + 묶음 DELETE 엔드포인트 없음(405) / createdAt 직렬화.
- **C3 🟡** — 무인증 환경 ProductOwner 기본부여로 자기승인 방지 무력화(설계상 의도).

**남은 작업**: ① 임시 노출한 'Changes' 탭(TopBar) 원복 ② API키 영구픽스 결정(.env 교체/제거 vs skill_runner 정화 유지) — **동일 패턴 타기능(Proposals 039 헤드리스 스킬) 점검 필요** ③ S5 풀 구현 = 실제 대상 프로젝트 지정 후(C7) Code 탭 검증과 함께.

**교차 영향**: C4/C5/C6/C7→Code·Design/Stories 탭(그룹 C/B), C1/C2 env 버그→Proposals 039 헤드리스 스킬 동일 가능성, 영향도 결과→Stories/Design/Data 탭.
