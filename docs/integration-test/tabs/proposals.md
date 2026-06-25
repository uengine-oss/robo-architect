# Proposals 탭 — 통합 검증

- **activeTab 값**: `Proposals`
- **패널 컴포넌트**: [`ProposalsPanel.vue`](../../../frontend/src/features/proposals/ui/ProposalsPanel.vue)
- **관련 스펙**: 039(Proposal Lifecycle) · 040(Impact Preview) · 041(Constitution/Plan, **미구현·Draft**)
- **백엔드**: [`api/features/proposal_lifecycle/`](../../../api/features/proposal_lifecycle/) (router → crud/intent/tasks/sandbox/testing/acceptance/preview/preview_edit)
- **프런트 store**: [`proposals.store.js`](../../../frontend/src/features/proposals/proposals.store.js)
- **상태**: 🟡 인벤토리 완료 / 라이브 검증 미실행

## 1. 탭의 의도/목표 (스펙 요약)

자연어 변경 요청을 **AI가 인텐트 분해**(Strategic/Tactical Diff + Impact Map)하고, **Git Worktree 샌드박스**에서 Claude Code 셀로 구현하며, **Dual Merge**(코드 머지 + Neo4j 그래프 보상 트랜잭션)로 라이브에 반영하는 **Proposal(PRO-NNN) 단위 생애주기**를 관리.

상태 전이:
```
DRAFT → SUBMITTED → IMPLEMENTING → TESTING → PENDING_ACCEPTANCE → ACCEPTED
                                                                 ↘ DESTROYED
   (머지 실패 시) → MERGE_FAILED → (retry-merge)
   (ACCEPTED 이후) → revoke → 코드/그래프 되돌리기
```

040은 그 위에, Impact/Diff 항목마다 **"열기"** 진입점을 달아 타입별 기존 뷰어(Data/Design/Process/Processes)를 **읽기 전용 오버레이 미리보기**로 여는 기능.

## 2. 보유 기능 목록 (코드 대조 완료)

| # | 기능 | 출처 | 컴포넌트 | 엔드포인트 |
|---|---|---|---|---|
| 1 | Proposal 목록·상태필터·활성 진행표시(폴링) | 039 | `ProposalsPanel.vue` | `GET /api/proposals/` |
| 2 | 새 Proposal 생성(자연어 프롬프트) | 039 | `ProposalCreate.vue` | `POST /api/proposals/` |
| 3 | 인텐트 분해 SSE(strategic/tactical diff, impact_map) | 039 | `IntentDecompositionView.vue` | `GET /stream/{id}/intent` |
| 4 | 인텐트 보정 피드백(DRAFT) | 039 | `IntentDecompositionView.vue` | `POST /{id}/intent/feedback` |
| 5 | Clarification 응답 | 039 | `IntentDecompositionView.vue` | `POST /{id}/clarify` |
| 6 | Diff 수동 편집 | 039 | `ProposalDiffVisualView.vue` | `PUT /{id}/diff` |
| 7 | Strategic/Tactical Diff 시각화 | 039 | `ProposalDiffVisualView.vue`, `IntentDecompositionView.vue` | — |
| 8 | Impact Map 시각화 | 039 | `ImpactMapView.vue` | — |
| 9 | Submit(DRAFT→SUBMITTED) | 039 | `ProposalDetail.vue` | `POST /{id}/submit` |
| 10 | 작업 분해 SSE + 저장본 조회 | 039 | `SandboxProgressView.vue` | `GET /stream/{id}/tasks`, `GET /{id}/tasks` |
| 11 | 샌드박스 구현(worktree + Code 셀 위임) | 039 | `SandboxProgressView.vue` | `POST /{id}/implement` |
| 12 | git init 동의 재시도(NOT_A_GIT_REPO) | 039 | `SandboxProgressView.vue` | `POST /{id}/implement {initGit}` |
| 13 | 구현 진행률 폴링(tasks.md 체크리스트) | 039 | `ProposalsPanel.vue`, `SandboxProgressView.vue` | `GET /{id}/progress` |
| 14 | 구현 완료(IMPLEMENTING→TESTING) | 039 | `SandboxProgressView.vue` | `POST /{id}/implement/complete` |
| 15 | 검증 실행 SSE(robo-sync 구조검증 + GWT) / 폴백 | 039 | `TestResultsView.vue` | `GET /stream/{id}/validate`, `POST /{id}/validate` |
| 16 | 검증 결과 조회 | 039 | `TestResultsView.vue` | `GET /{id}/test-results` |
| 17 | 승인(Dual Merge) / 실패강제 옵션 | 039 | `DualMergeView.vue` | `POST /{id}/accept` |
| 18 | 폐기(DESTROYED) | 039 | `ProposalDetail.vue` | `POST /{id}/destroy` |
| 19 | 철회/되돌리기(revoke, revertCode) | 039 | `ProposalDetail.vue` | `POST /{id}/revoke` |
| 20 | 머지 재시도(MERGE_FAILED) | 039 | `DualMergeView.vue` | `POST /{id}/retry-merge` |
| 21 | Impact/Diff 항목 → 뷰어 "열기"(읽기전용 미리보기) | 040 | `OpenInViewerLink.vue`, `proposalPreview.js` | `GET /{id}/preview/resolve`, `/preview/contexts/{bc}/full-tree` |
| 22 | 미리보기 편집 → diff 반영 | 040 | `proposalPreview.js` | `PUT /{id}/preview/aggregate/{node}`, `POST /{id}/preview/chat-confirm` |

> store ↔ 백엔드 라우트 1:1 대조 완료(불일치 없음). 040 미리보기는 App.vue의 `robo:open-preview` 이벤트 오케스트레이션으로 구동(직접 import 없음).

## 3. 검증 시나리오

> 깊이: 스펙+코드 인벤토리 우선. 아래는 라이브 구동 시 실행할 시나리오 설계(전제→조작→기대). 결과는 라이브 검증 단계에서 채움.

### S1. 목록·필터·빈 상태
- **Given**: 백엔드 기동, Proposal 0~N개
- **When**: Proposals 탭 진입, 상태 필터 칩 클릭
- **Then**: 상태별 count 배지 일치, 빈 상태 "Proposal이 없습니다", 활성(IMPLEMENTING/TESTING) 항목에 진행/정체/완료 인디케이터(8초 폴링, 90초 임계 정체)
- **결과**: ✅ (2026-06-12) — 상태 확인 정상

### S2. 생성 → 인텐트 분해
- **Given**: LLM 설정(`LLM_PROVIDER/MODEL`/key), `CLAUDE_CODE_PATH` 유효
- **When**: "+ 새 Proposal" → 자연어 프롬프트 제출 → SSE 구독
- **Then**: `phase`→`strategic_diff`→`tactical_diff`→`impact_map`→`done` 순서 수신, Diff/Impact 시각화 렌더, DRAFT 유지
- **결과**: ✅ (2026-06-12, I3 수정 후 재시도) — PRO-002 생성·DRAFT 유지. Strategic(Epic1/Feature1/US3/Process1) + Tactical 11건(MODIFY1+CREATE10) + **ImpactMap 12건(HIGH4/MED4/LOW4)**. 기존 모델 노드(Payment Aggregate·PaymentProcessing BC·US-002/008/012/013) 정확 참조 → ES 모델 기반 영향분석 동작 확인.
- **이력**: 최초 ❌ "Invalid API key · Fix external API key"(I3) → skill_runner 수정 후 ✅
- **메모**: clarification_needed 미발생(clarificationLog 0). 환경: S1 ✅, ES 셋 1개 시드 완료

### S3. Clarification / 인텐트 피드백 재생성
- **Given**: DRAFT, 인텐트 결과 존재
- **When**: clarification 응답(`/clarify`) 또는 보정 피드백(`/intent/feedback`) 후 재구독
- **Then**: 피드백+이전 diff 반영해 재생성, currentProposal 갱신
- **결과**: ✅ (2026-06-12) — 피드백("부분→전액환불, Order Aggregate 변경")이 strategic(US/Process 전부 전액환불)·tactical(Order MODIFY + FullRefund Cmd/Evt/Policy)에 정확 반영. intentFeedbackLog 기록·DRAFT 유지.
- **관찰**: 재생성 후 ImpactMap이 S2(12건 HIGH4/MED4/LOW4, 기존노드 풍부) → S3(11건 HIGH1+NONE10, 폴백 시그니처)로 품질 저하 → I4

### S4. Submit → 작업 분해 → 샌드박스 구현
- **Given**: DRAFT + diff 확정, 대상 `projectRoot`가 Git 저장소
- **When**: Submit → (작업 분해 SSE) → 구현 → Code 탭 셀 위임(`openClaudeCode(worktreePath, command)`)
- **Then**: 상태 IMPLEMENTING, `.sandbox/proposal/PRO-NNN` worktree 생성, `git worktree list`에 `proposal/PRO-NNN` 표시, Code 탭 셀에서 진행
- **결과**: ✅ (2026-06-12) — Submit→IMPLEMENTING 전환, worktree 생성·git 등록(`proposal/PRO-002` @ test-project/.sandbox/), tasks 체크리스트 18개 파싱(progress exists:true), projectRoot 격리(`.sandbox` 오염 없음) 모두 확인. 구현 셀(`/robo-implement`) 진행 중. (진행 중 I7/I8 발견·수정, projectRoot 미설정 시 "구현하기" 비활성=정상)
- **메모**: 멀티 세션(039) — proposal worktree 독립 세션, `claudeCodeWorkdir` 미오염 ✅. 구현 시작 전 Code 탭 projectRoot 설정 필수(인라인 ⚠ 안내 + 버튼 비활성). 대상 비-Git이면 S5(NOT_A_GIT_REPO→git init) 분기

### S5. git 비저장소 동의 흐름
- **Given**: `projectRoot`가 Git 저장소 아님
- **When**: 구현 시도
- **Then**: `NOT_A_GIT_REPO` → git init 다이얼로그 → 동의 시 `initGit=true` 재시도로 worktree 생성
- **결과**: ✅ (2026-06-13) — 비-Git 폴더(non-git-test) 대상 "구현하기" → **NOT_A_GIT_REPO 다이얼로그** ✅, 동의 시 **실제 `git init` + 초기커밋**(`robo-architect <robo-architect@localhost>`, identity 폴백) + **worktree `proposal/PRO-003` 생성** + IMPLEMENTING, projectRoot=non-git-test 정확. 전체 경로(FR-006) 검증.
- **메모(I17)**: "Claude Code 셀로 이동" 누르기 전엔 셀 세션 미생성인데 진행률이 "정체"로 표시 — 시작 전 상태가 "정체"로 오인됨(셀 진입 대기 표현 필요). I16(루트=활성세션) 우회로 main 세션 활성화 후 정상 진행.

### S6. 구현 완료 → 검증
- **Given**: IMPLEMENTING
- **When**: 구현 완료(`/implement/complete`) → 검증 SSE(`/stream/{id}/validate`)
- **Then**: TESTING 진입, 실행 로그 스트리밍·중지 가능, `results` 수신, 완료 시 PENDING_ACCEPTANCE
- **결과**: ✅ (2026-06-12) — 부분구현(8/18=44%, 사용자 중단)에서 "미구현부분 완료하기"→TESTING→검증→**PENDING_ACCEPTANCE**. GWT 인수 8 + 구조검증 13, **8 FAIL이 미구현분과 정확히 일치**(RejectFullRefund/ExecuteFullRefund/FullRefundExecuted/RefundHistory/Policy "파일 없음"). 코드 인지 분석(예 "markRefundFailed는 있으나 PG 실패경로 미연결") 확인 → 검증이 실제 코드 평가. I11(요약 총계 불일치) 외 정상.
- **메모**: 셀이 "구현 완료" 메시지를 냈으나 robo는 tasks.md 체크(8/18)로 부분 판단 — 부분 케이스 정상 처리. 검증 중지→서브프로세스 kill은 미검증(완주함)

### S7. 승인(Dual Merge)
- **Given**: PENDING_ACCEPTANCE, 자기승인 정책 확인
- **When**: 승인(실패 강제 옵션 별도)
- **Then**: 코드 머지 + Neo4j 그래프 업데이트, ACCEPTED. 충돌 시 MERGE_FAILED → retry-merge 동작
- **결과**: ✅ (2026-06-13) — "승인"은 기본 비활성, **실패항목 인지 동의(forceAcceptWithFailures) 후 활성**(좋은 가드). 승인 시: ①코드 머지 — test-project main에 `Accept PRO-002` 머지커밋 + 구현분(T002~T008) 파일 실재 ②그래프 반영 — Order Aggregate 8속성 + Command4/Event4/ReadModel1/Feature/Process 전부 반영 ③worktree 정리, sandboxStatus=DESTROYED, **ACCEPTED**.
- **관찰(I12)**: 그래프엔 설계 11종 전부 반영됐으나 코드는 44%만 머지 → 미구현 요소(Reject/ExecuteFullRefund·RefundHistory)가 **그래프엔 존재, 코드엔 부재**(force-accept 시 design>code divergence). `refundedAmount` Property 노드 **중복** 생성(경미). MERGE_FAILED/retry는 미발생(정상 머지).

### S8. 폐기 / 철회
- **When**: DRAFT~PENDING에서 destroy / ACCEPTED에서 revoke(revertCode)
- **Then**: DESTROYED, worktree 정리 / 코드·그래프 되돌리기
- **결과(revoke)**: ✅ (2026-06-13) — ACCEPTED PRO-002에서 "수거(그래프+코드)" → 코드 `Revert "Accept PRO-002"` 커밋+refund파일 제거, 그래프 환불노드 **0개**(완전 복원), 상태 ACCEPTED→**PENDING_ACCEPTANCE** 복귀. 역방향 Dual Merge 양쪽 정상. **관찰: `revokedAt` 미설정(None)**.
- **결과(destroy)**: ✅ (2026-06-13) — PENDING_ACCEPTANCE PRO-002 폐기 → 상태 **DESTROYED**, destroyedAt 기록, worktree 정리. revoke+destroy 모두 검증.
- **메모**: revoke UI는 "그래프만/그래프+코드" 라디오 선택 제공([DualMergeView.vue](../../../frontend/src/features/proposals/ui/DualMergeView.vue))

### S9. (040) Impact 항목 "열기" 미리보기
- **Given**: 인텐트 분해된 Proposal, Impact/Diff 항목
- **When**: 항목 "열기" → 타입별 뷰어(Data/Design/Process/Processes) 진입
- **Then**: 읽기 전용 배너(`PreviewBanner`) 표시, 대상 노드 포커스, **라이브 그래프 무변경**(US2/FR-006), 닫기 시 라이브 상태 복원
- **결과**: 🟡→✅대부분 (2026-06-13) — Aggregate·VO → data(오버레이로 신규도 보임) ✅, **Command/Event/ReadModel → processes(Event Modeling) 재매핑(I18)** — 기존/수정은 포커스, 신규는 플로우 맥락(오버레이 없음=C 후속). Policy 미매핑(설계상). 라이브 무오염 ✅. UI 캔버스 재확인 권장.
- **갱신(2026-06-15, I21)**: Command/Event/ReadModel "열기"를 **processes → Design 캔버스 오버레이 투영**으로 재매핑. 신규(CREATE) 요소도 라이브 BC 슬라이스+tacticalDiff 오버레이로 캔버스에 합성·포커스 + 인스펙터 오픈 → I18-C(이벤트모델링 오버레이 백로그)가 design 오버레이로 **대체 해소**. Impact Map의 nodeId 없는 항목 "열기"도 동작(I22).
- **메모**: 표현 불가 항목은 `robo:open-preview-failed` → alert. **다음**: Order Aggregate "열기"로 정상경로(배너/포커스/무변경) 확정 필요

### S10. (040) 미리보기 편집 반영
- **When**: 미리보기에서 Aggregate 편집(`PUT /preview/aggregate`) 또는 chat-confirm
- **Then**: 라이브엔 무변경, 제안 diff에만 반영, `robo:preview-updated`로 뷰어 트리 갱신
- **결과**: ✅ (2026-06-13, I13 수정 후) — 챗으로 "주소 VO 추가" → Order에 `address` 속성(type "Address(VO)") **diff 반영 확인**. 라이브 무변경 ✅. 혼동 3가지(해소): ①영어 명명("주소"→address) ②I20(standalone VO 노드 아닌 VO타입 속성) ③Data 미리보기는 BC 전체 Aggregate 트리를 그려 형제 Aggregate(Review 등 同 OrderManagement BC)가 함께 보임=정상. 최초 ❌는 부모해소가 aggregateId만 봐서(Property는 parentId) — 수정됨.
- **메모**: Inspector 직접편집 경로(`PUT /preview/aggregate`)는 미검증(챗 경로만 테스트). UX: 챗에서 Aggregate를 캔버스에서 한번 클릭해야 선택요소로 들어감(개선여지)
- **확장(2026-06-15~17, I24~I26)**: Inspector **직접편집 경로 정식화** — Property 추가/삭제 저장(I24, 라이브 오염 방지 위해 `/preview/chat-confirm` 라우팅 + 백엔드 자식 컬렉션 delete/update/rename 분기), Command/Event/Aggregate 세부속성·VO필드·Enum항목 편집(I26, `POST /preview/design/confirm`·`reconcile_design_edit`), AI 챗으로 VO/Enum 편집(react_prompt/streaming에 노드타입 추가). 캔버스·Proposals 상세 **즉시 반영**(I25, 내용 시그니처 재빌드 + `robo:proposal-diff-changed` 이벤트), 형제 Aggregate 오노출 차단(I25).

## 4. 발견 이슈

| # | 심각도 | 증상 | 원인(추정) | 후속 |
|---|---|---|---|---|
| I1 | 정보 | **041(Constitution/Plan 단계) 미구현** | spec.md만 존재(plan.md·tasks.md·코드 없음, Status: Draft). 현재 흐름은 intent→submit→implement 단일 분해로 plan 단계 부재 | 041은 검증 대상에서 제외 또는 구현 백로그로 분리. README 매핑에서 "미구현" 명시 |
| I2 | 확인필요 | quickstart(039)가 `services/migration`, `schema_migrator --feature=039` 등 참조 | 실제 구조는 `routes/`·`services/` 분리. 마이그레이션/스키마 스크립트 경로 실재 여부 라이브 확인 필요 | Step 1·2 스크립트 존재/동작 확인 |
| I4 | 품질 | 피드백 재생성(S3) 후 ImpactMap이 그래프기반 분석 대신 `_fallback_impact_map`(HIGH1+NONE10)으로 떨어짐 | 재생성 경로에서 `robo-proposal-context` 스킬이 빈 응답/JSON 실패/60s timeout → [impact_builder.py](../../../api/features/proposal_lifecycle/services/impact_builder.py) 폴백. (최초 S2에선 정상 12건) | 재현성 확인(일회성 timeout인지) → 필요시 context 스킬 timeout 상향 또는 폴백 진입 로깅 강화. 라이브에서 backend 로그 `proposal_lifecycle.impact.*`/`skill_runner.*` 확인 |
| I17 | **수정됨** | 구현 시작 전("Claude Code 셀로 이동" 미클릭)인데 진행률이 "정체 — N분 업데이트 없음"으로 표시. **✅ 수정(2026-06-13)**: progressState가 done=0+셀세션 없음이면 "시작 대기 — 셀로 이동" 표기 | progress가 tasks.md mtime 기반이라, 셋업만 되고 셀이 안 돌면 "정체"로 보임. 실제론 "아직 시작 안 됨" | actionMode/pendingLaunch 상태로 "셀 진입 대기"와 "진행 중 정체"를 구분 표기 |
| I16 | UX 혼동 | Code 탭 폴더 피커로 루트 변경해도 proposal 구현이 옛 루트로 진행 | [`onTerminalWorkdirPicked`](../../../frontend/src/features/claudeCode/ui/ClaudeCodeWorkspace.vue#L543)가 **활성 세션**의 workdir만 변경. proposal projectRoot는 **main("프로젝트") 세션** 기준(`syncMainRoot`→App `claudeCodeWorkdir`). 활성 세션이 main이 아니면(잔여 proposal/셸 세션) main 루트 안 바뀜 → I14와 겹치면 더 혼동 | 우회: main "프로젝트" 세션 활성화 후 폴더 선택. 개선: 폴더 피커가 main 루트를 바꾸는 동작임을 명확히(또는 "프로젝트 루트 변경" 별도 UI), 잔여 세션 정리(I14) |
| I14 | 경미(UX) | proposal 종료(ACCEPTED/DESTROYED, worktree 제거) 후에도 Code 탭 proposal 세션이 남아 `GET /api/claude-code/tree?root=.../.sandbox/proposal/PRO-002` 400 반복 | worktree 삭제됐는데 Code 탭 세션(localStorage `claude_code_workspace_sessions`)이 자동 정리 안 됨 → FileTreePane이 죽은 경로 폴링 → [router.py:71](../../../api/features/claude_code/router.py#L71) isdir 실패 400 | (a) proposal terminal 상태/worktree 제거 시 해당 Code 세션 prune (b) FileTreePane이 root 부재를 우아하게 처리(400 스팸 대신 "경로 없음"). 무해(콘솔 로그만). 즉시 우회: 세션 탭 × 종료 |
| I13 | **수정됨** | 미리보기 챗 편집(자식요소 추가)이 "반영했습니다" 메시지만 뜨고 제안 diff에 실제 미반영. **✅ 수정(2026-06-13)**: `apply_chat_drafts`가 ①create 자식요소(Property/VO/Enum)를 부모 항목에 병합 — 부모 식별은 `aggregateId` **또는 `updates.parentId`**(모델모디파이어 Property는 parentId 사용) ②top-level create(Command/Event/ReadModel/Policy)는 신규 tactical 항목 ③appliedCount 반환→0건이면 "반영 없음" 정직 표시. 합성 draft(VO형/Property형) 양쪽 검증. UI 재시도 시 반영됨 |
| I20 | **한계(별도)** | 챗으로 "VO 추가"하면 ValueObject가 아니라 Property로 들어감 | 모델모디파이어 `targetType` enum에 **ValueObject 없음**([react_streaming.py:652](../../../api/features/model_modifier/react_streaming.py#L652) Command\|Event\|Policy\|Aggregate\|ReadModel\|UI\|BC\|Property) → "VO 추가"가 Property로 변환 | ValueObject를 진짜 VO 노드로 추가하려면 모델모디파이어 targetType에 ValueObject 추가 + 생성/적용 핸들링(react_prompt·model_change_application·apply_chat_drafts는 이미 valueObjects 컬렉션 지원). 별도 작업 | ①[modelModifier.store.js:403](../../../frontend/src/features/modelModifier/modelModifier.store.js#L403) chat-confirm 200이면 변경 여부 무관하게 성공 메시지 ②[`apply_chat_drafts`](../../../api/features/proposal_lifecycle/services/preview_edit.py#L112)가 targetId=기존/신규 **Aggregate**만 반영, 자식요소 추가(VO/Property/Command 생성) draft는 처리분기 없어 드롭 | (a) `apply_chat_drafts`에 자식요소 add draft 처리(부모 Aggregate item의 valueObjects/properties에 병합 또는 신규 tactical item 생성) (b) 백엔드가 실제 반영분 반환→프런트 메시지를 그에 맞게(0건이면 "반영 없음"). draft 스키마(모델모디파이어 propose 출력) 확인 필요 |
| I12 | 관찰(설계) | force-accept-with-failures 시 그래프엔 설계 전부 반영, 코드는 부분만 머지 → design>code divergence. `refundedAmount` Property 중복 노드 | Dual Merge가 tacticalDiff 전체를 그래프에 적용(설계-우선). 코드 완성도와 무관. 중복은 apply의 property 노드 dedup 누락 추정 | divergence는 의도된 모델이나 사용자 인지 필요(검증 FAIL≠그래프 미반영). property 중복은 apply에서 dedup 검토 |
| I11 | **수정됨** | test-results 요약 헤더 총계가 항목 목록과 불일치. **✅ 수정(2026-06-13)**: `get_test_results`가 totalScenarios/passed/failed/skipped를 items로부터 재계산. PRO-002 21/13/8 일치 확인 | `totalScenarios=19, passed=11` vs 실제 항목 21개(PASS 13/FAIL 8). FAIL 수만 일치. 헤더 집계가 항목과 다른 기준(부분 카운트/스테일)으로 계산되는 듯 | `test-results` 응답에서 헤더 totalScenarios/passed를 items로부터 재계산하거나 집계 출처 일치시키기. 기능 영향은 없음(표시 수치만) |
| I10 | **수정됨(중대)** | 백엔드가 응답 정지 → claude 셀이 API 포트(8000) 리스닝 소켓을 붙잡음. reload/재시작해도 포트 wedge | [pty_backend.py](../../../api/features/claude_code/pty_backend.py) `_PosixPtyProcess`가 `os.fork()`+`execvpe` 시 부모(uvicorn) 상속 fd(리스닝 소켓 포함)를 안 닫음 → 자식 claude가 fd 상속. 셀이 백엔드 reload보다 오래 살면 포트 점유 | **✅ 수정(2026-06-12)**: exec 직전 `os.closerange(3, SC_OPEN_MAX)`로 stdio 외 모든 fd 닫음. (복구: leaked claude/stale python 강제 kill 후 포트 회수). 교훈: 테스트 중 `api/` 편집은 `--reload` churn 유발 → 백엔드 수정은 배치/중단상태에서 |
| I9 | **수정됨** | 새 프로젝트 첫 구현 시 `/robo-implement` 자동주입이 첫 실행 MCP 신뢰 프롬프트와 충돌해 명령 유실 → 셀 idle. **✅ 수정(2026-06-13)**: `prepare_implementation`이 worktree에 `_ensure_worktree_mcp` — `.mcp.json`(robo-spec, 없을 때만 생성·기존 보존) + `.claude/settings.local.json`에 서버 **사전신뢰** 기록 → 신뢰 프롬프트 자체가 안 떠 레이스 소멸. settings.local.json은 exclude로 커밋 제외. 헬퍼 2케이스 검증 | [ClaudeCodeTerminal.vue:210](../../../frontend/src/features/claudeCode/ui/ClaudeCodeTerminal.vue#L210) 고정 6초 setTimeout 주입이, claude가 MCP "use this mcp?" 프롬프트 대기 중일 때 발사돼 글자가 프롬프트에 먹힘 | (a) worktree 생성 시 `.claude/settings.local.json`에 `enabledMcpjsonServers:["robo-spec"]` 사전기록 → 신뢰 프롬프트 제거 (b) 고정 6초 대신 REPL 프롬프트 감지 후 주입. 임시 우회: 셀에 `/robo-implement <id>` 직접 입력 |
| I7 | **수정됨** | 작업목록 분해 중 detail 서브탭을 떠났다 오면 목록이 초기화됨 | `SandboxProgressView`는 `v-if="activeTab==='sandbox'"`로 렌더 → 떠나면 언마운트 → `onUnmounted`의 `store.stopTasks()`가 SSE를 끊음. 작업은 끝에 `tasks` 이벤트로 한 번에 와서, 중간에 끊기면 빈 채로 남고 복귀 시 저장본 없어 빈 목록 | **✅ 수정(2026-06-12)**: `onUnmounted`에서 `stopTasks()` 제거(폴링 타이머만 정리) → 분해 SSE를 store에서 계속 살려 내비게이션에도 진행 유지. 명시적 "중지"는 그대로 동작 |
| I8 | **수정됨** | Submit 후 "샌드박스 구현 열기" 버튼 무반응 | `submitProposal`이 이미 `activeTab='sandbox'`로 전환 → 액션바 버튼(`@click=activeTab='sandbox'`)이 no-op. 실제 시작은 뷰 내 "구현하기" | **✅ 수정(2026-06-12)**: 액션바 버튼을 `activeTab !== 'sandbox'`일 때만 표시(중복 no-op 제거). 구현 시작은 "구현하기"로 일원화 |
| I6 | **보완 완료** | "Diff 직접 수정"이 깨진 JSON 스키마를 검증 없이 저장 → 깨진 strategicDiff는 읽기 때 조용히 `None` 소실, 깨진 tacticalDiff 항목은 dual-merge `item.get()` 크래시. 게다가 프런트 `updateDiff`가 실패를 throw 안 해 편집기가 사유 없이 닫힘 | PUT /diff가 dict/list 여부만 보고 내용 미검증. `ProposalResponse.from_neo4j`는 방어적으로 `None` 폴백 | **✅ 수정(2026-06-12)**: ①백엔드 `_validate_diff_payload`([proposals_crud.py](../../../api/features/proposal_lifecycle/routes/proposals_crud.py)) — strategicDiff는 `StrategicDiff` 스키마(op enum·필수필드·타입), tacticalDiff는 항목 객체여부 검증 후 422+한국어 사유 ②프런트 `updateDiff` 실패 시 백엔드 detail로 rethrow → saveDiff가 사유 표시·편집기 유지. 라이브 422 확인, 정상 diff 무손상 |
| I5 | **수정됨** | 신규 Command/Event impact 항목 "열기" 시 ①BC 해소 실패 →②(해소 후) Data 뷰어가 Command/Event를 Aggregate로 포커스하려다 "Aggregate not found". **✅ 수정(2026-06-13)**: ①`_guess_bc_from_proposal`이 형제 tacticalDiff의 boundedContextId 추론 ②`_resolve_focus_aggregate`(VO/Enum용 폴백 유지). **단 I18로 Command/Event는 data가 아닌 processes 뷰어로 재매핑** → 아래 I18 참조 |
| I19 | **수정됨** | Processes(Event Modeling) 탭에서 캔버스 요소를 클릭해도 Chat에 선택 요소로 안 잡힘 | `EventModelingPanel`이 `store.selectItem`만 호출하고 `chatStore.setSelectedNodes`를 안 부름(AggregatePanel은 호출). **✅ 수정(2026-06-13)**: selectedItemId watch에서 선택 항목을 `{id,type,name,...}`로 chatStore에 전달(`pushSelectionToChat`), 해제 시 clearSelection |
| I18 | **수정됨(I21로 완결)** | Command/Event "열기"가 data 뷰어로 가 Aggregate 도메인만 보여줘 의미 약함. 매핑 불일치(Command/Event=data인데 ReadModel=processes) | Command/Event/ReadModel은 모두 Event Modeling 산출물. + **신규(CREATE) 요소 가시성 문제**: Data 뷰어는 040 오버레이로 신규가 보이지만, processes/design/process 뷰어는 오버레이 없어 라이브만 → 신규 Command/Event는 어디서도 안 보임 | **✅ A 적용(2026-06-13)**: Command/Event → `processes` 재매핑(ReadModel과 일관, 의미적 본거지). 기존/수정 요소는 포커스, **신규는 플로우 맥락만**. **C(이벤트모델링 오버레이, ~1040줄 투영 미러)는 백로그**(040 후속, speckit 권장). **대신 안내(2026-06-13)**: resolve가 신규(CREATE)+비-data 뷰어면 `notice` 반환 → PreviewBanner에 "⚠ 신규 요소라 이 뷰어엔 아직 표시 안 됨, 제안 Diff 확인" 표시(라이브 검증) | data 뷰어 BC 해소 3단계 모두 실패: ①인텐트 tactical의 Command/Event CREATE 항목에 `boundedContextId` 미포함(Agg/RM/Policy엔 있음) ②신규노드라 그래프에 없음 ③**I4 폴백 impactMap에 BoundedContext 항목 없음**. Aggregate/ReadModel은 정상 | (a) I4 해결 시 ③로 자동 완화 가능성 큼(정상 impactMap엔 BC 항목). (b) 근본: 인텐트 스킬이 Command/Event tactical에도 `boundedContextId` 부여하도록 보강. (c) UX: renderable=false는 FR-010대로 "열기" 비활성+사유 인라인 표시 검토 |
| I3 | **블로커→수정됨** | S2 인텐트 분해 시 "Invalid API key · Fix external API key" | `.env`의 무효 `ANTHROPIC_API_KEY`가 `load_dotenv()`로 프로세스 환경에 올라가고, [skill_runner.py](../../../api/platform/skill_runner.py)가 `env=` 없이 `subprocess` spawn → claude CLI가 로컬 로그인 대신 그 키로 인증 시도. 백엔드는 `LLM_PROVIDER=openai`라 이 키 불필요 | **✅ 수정(2026-06-12)**: skill_runner에 `_skill_env()` 추가 — 스킬 spawn 시 `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` 제거해 항상 로컬 Claude 로그인 사용. **백엔드 재시작 후 S2 재시도 필요** |

### 2026-06-15~17 전술적 미리보기 편집 라운드 (ShinSeongJin2)

> 040 미리보기를 **읽기 전용 → 인스펙터/AI챗 편집 가능**으로 확장하면서 발견·수정한 이슈. 모든 편집은 라이브 그래프가 아닌 `Proposal.tacticalDiff` 오버레이로 반영(Constitution I, 라이브 무오염). 커밋 매핑:
> - **I21** ← `5b57ec0`(Design 재매핑·오버레이 투영) + `d4da991`(라이브 MODIFY 오버레이 `overlay_live`) + `472a6d3`(애그리거트 디테일 버튼 재오픈)
> - **I22** ← `f1aa26e` · **I23** ← `063df6f` · **I24** ← `26c0abd`(추가)+`1db35e8`(삭제)+`d4da991`(미리보기 중 CQRS 참조검사 skip) · **I25** ← `86c54e7`+`a91059f` · **I26** ← `d4da991`+`472a6d3`(VO/Enum 챗)
> - GWT 관련 수정(`d4da991` 일부 · `472a6d3` 일부)은 Design 탭 소관 → [design.md](design.md) D1·D2 참조.

| # | 심각도 | 증상 | 원인 | 수정 |
|---|---|---|---|---|
| I21 | **수정됨(중요)** | Tactical Command/Event/ReadModel "열기"가 processes(Event Modeling) 뷰어로 가 신규(CREATE) 요소가 안 보이고(오버레이 없음) 의미 약함(I18) | `LABEL_TO_VIEWER`가 Command/Event/ReadModel→`processes` 매핑인데 processes 경로는 040 오버레이 미합성 → 신규 요소는 라이브에 없어 표시 불가. 자식 항목이 `boundedContextId`를 직접 안 들고 부모(`aggregateId`/`commandId`) 참조만 가짐 | **Design 캔버스로 재매핑** + 신규 투영 빌더 [`build_design_preview`](../../../api/features/proposal_lifecycle/services/preview_projection.py)(라이브 BC 슬라이스 `build_context_full_tree` + tacticalDiff 오버레이를 라이브 `expand-with-bc`와 **동형** `{nodes,relationships,bcContext}`로 합성, CREATE 요소를 정확한 부모에 배치). 부모체인 BC 해소 `_resolve_bc_via_parent`/`_resolve_owning_aggregate`, 라이브 MODIFY 오버레이 `overlay_live`. 신규 라우트 `GET /{pid}/preview/design/{bc}/graph`. 프런트: [`canvasPreviewRequest.store.js`](../../../frontend/src/features/canvas/canvasPreviewRequest.store.js) 브리지(proposals→뷰어 직접 import 회피, Principle V) + [`CanvasWorkspace.vue`](../../../frontend/src/features/canvas/ui/CanvasWorkspace.vue) `consumeCanvasPreviewRequest` + [`canvas.store.js`](../../../frontend/src/features/canvas/canvas.store.js) `beginPreview`/`endPreview`(라이브 스냅샷 후 복원, 잔존물 0). 애그리거트 디테일 버튼은 미리보기 중 Data 뷰어로 재오픈(404 무한루프는 `fetchAttemptedNodeId`로 차단). **테스트** `frontend/tests/verify-proposal-design-preview.spec.ts`(신규). **I18-C(이벤트모델링 오버레이 백로그)를 design 오버레이로 대체 해소** |
| I22 | **수정됨** | Impact Map(충돌 가능성 분석) 항목 "열기"가 무동작(빈 캔버스/"No aggregates") — Tactical Diff "열기"는 정상 | 충돌분석 항목은 `nodeId=null`(LLM `robo-proposal-context`가 신규 CREATE 노드를 라이브 그래프 id로 못 묶으면 SKILL 규칙상 null) → 포커스 대상 id 부재 | `resolve_open_target`에 `node_title` 추가 + 신규 `_match_tactical_by_label_title(proposal, label, title)`로 `nodeId` 없을 때 같은 제안 tacticalDiff에서 `(nodeLabel,nodeTitle)`로 동일 논리 노드의 합성 `nodeId` 복원 → I21 design/data 경로 재사용. 라우트·`proposalPreview.js`에 `nodeTitle` 쿼리 전달 |
| I23 | **수정됨** | 일부 VO·Enum이 Tactical Diff 표시(텍스트/시각 요약)에 아예 안 나타남 | VO/Enum이 `semanticDiff.ops`의 `obj_append` **또는** 항목 최상위 `valueObjects`/`enumerations` 배열(ops 빈 채) 두 형태로 실리는데, 프런트 두 뷰가 ops만 렌더(백엔드 overlay는 둘 다 흡수 → 프런트만 불일치) | [`IntentDecompositionView.vue`](../../../frontend/src/features/proposals/ui/IntentDecompositionView.vue) `itemLevelObjects(item)`·[`ProposalDiffVisualView.vue`](../../../frontend/src/features/proposals/ui/ProposalDiffVisualView.vue) `mergeItemLevelObjects(struct,item)` — 배열-레벨 VO/Enum을 ops에 이미 잡힌 이름 제외 후 의사 op로 변환·중복 없이 병합 |
| I24 | **수정됨** | Aggregate 미리보기에서 Property **추가/삭제** 후 "저장" 시 실패(+ 라이브 그래프 오염 위험) | ①[`AggregateViewerInspector.vue`](../../../frontend/src/features/canvas/ui/AggregateViewerInspector.vue) `saveAggregateProperties`가 미리보기 구분 없이 라이브 `/api/chat/confirm`로 저장 ②백엔드 `apply_chat_drafts`에 자식요소(Property/VO/Enum) delete/update/rename 분기 부재 ③삭제 draft가 부모식별자/이름 메타 누락(미리보기 속성은 Neo4j id 없음 `prop-noid-*`) | ①`isPreviewFor('data')` 분기 → `/api/proposals/{pid}/preview/chat-confirm` 라우팅 + `applyPreviewTree` 즉시반영 + 정직한 `appliedCount`(0건이면 "반영 없음", I13) ②[`preview_edit.py`](../../../api/features/proposal_lifecycle/services/preview_edit.py) `apply_chat_drafts`에 자식 컬렉션 delete/update/rename 분기(`_child_parent_id`/`_match_child_index` — targetId 우선·없으면 name 매칭) ③[`PropertyEditorTable.vue`](../../../frontend/src/features/canvas/ui/inspectors/PropertyEditorTable.vue) 삭제 draft에 `name`/`parentType`/`parentId` 동봉 + 미리보기 중 CQRS 참조검사(`/api/cqrs/...` 404) skip |
| I25 | **수정됨** | Aggregate 미리보기 편집 후 ①캔버스 즉시 미반영 ②Proposals 상세(Impact/Diff)가 재클릭 전까지 옛 상태 ③수정 안 한 형제 Aggregate까지 캔버스에 노출 | ①[`AggregatePanel.vue`](../../../frontend/src/features/canvas/ui/AggregatePanel.vue) watcher가 BC/aggregate **id 집합** 변화만 봐 in-place 내용변경(속성 추가·rename) 누락 ②tacticalDiff 갱신 후 `currentProposal` 재조회 트리거 없음 ③`applyPreviewTree`가 BC 갱신 시에도 트리의 모든 Aggregate를 `visibleAggregateIds`에 추가 | ①`computeAggSignature`(properties/enum/VO 내용 JSON 시그니처)로 재빌드 조건 추가 ②`applyPreviewTree` 끝에서 `robo:proposal-diff-changed` 발행 → [`App.vue`](../../../frontend/src/App.vue) `_onProposalDiffChanged`가 `currentProposal.id` 일치 시 `fetchProposal` 재적재(앱레벨 오케스트레이션) ③BC 갱신 경로는 기존 visible ∩ present만 유지(신규 노출 안 함) |
| I26 | **수정됨** | 미리보기에서 Command/Event/Aggregate **세부속성**·VO필드·Enum항목을 인스펙터/AI챗으로 수정 불가, 채팅 diff의 create/delete가 before/after '(empty)' 표시, Enum/VO 수정 시 캔버스 미반영·"Maximum recursive updates exceeded" | ①Design용 제안-diff 반영 라우트 부재(라이브 전용) ②AI챗 시스템 프롬프트에 ValueObject/Enumeration 노드타입·Property parentType 미정의 ③[`EnumItemsTable.vue`](../../../frontend/src/features/canvas/ui/inspectors/EnumItemsTable.vue)·[`VoFieldsTable.vue`](../../../frontend/src/features/canvas/ui/inspectors/VoFieldsTable.vue) 양방향 watcher 메아리 사이클 ④`computeAggSignature`가 enum/VO **개수**만 봐 내용 수정 미감지 ⑤`getDraftFields`가 존재하지 않는 리터럴 키 반환 | 신규 `POST /{pid}/preview/design/confirm` + [`reconcile_design_edit`](../../../api/features/proposal_lifecycle/services/preview_edit.py)(draft[]→tacticalDiff; `_resolve_tactical_index`·`_ensure_modify_item`). [`react_prompt.py`](../../../api/features/model_modifier/react_prompt.py)·[`react_streaming.py`](../../../api/features/model_modifier/react_streaming.py)에 VO/Enum 노드타입·인라인 fields/items 노출·`compute_draft_display_fields`(존재 키만), `apply_chat_drafts` VO필드/Enum항목 분기. `itemsEqual`/`fieldsEqual`로 메아리 차단, `computeAggSignature`에 enum item 값·VO `name:type` 포함, [`InspectorPanel.vue`](../../../frontend/src/features/canvas/ui/InspectorPanel.vue) `savePreviewDesign`, [`ChatPanel.vue`](../../../frontend/src/features/modelModifier/ui/ChatPanel.vue) `displayFields` 우선·VO/Enum 칩 |

> 비고: `472a6d3`는 [`env.py`](../../../api/platform/env.py) `get_llm_model` 기본값을 `gpt-4.1-2025-04-14`→`gpt-5.5`로 동반 변경(플랫폼 디폴트, 위 수정과는 부수적).

## 5. 결론

- **인벤토리**: store ↔ 백엔드 라우트 1:1 대조 완료, 039/040 기능 22종 식별·연결 확인. 구조적 불일치 없음.
- **생애주기 라이브 검증(2026-06-12~13)**: **S1~S10 전 시나리오 통과** — 생성→인텐트분해→피드백재생성→Submit→worktree구현(S4)→git init(S5)→검증(S6)→Dual Merge 코드+그래프(S7)→수거 역방향(S8)→폐기, + 미리보기 열기(S9, Command/Event는 processes 재매핑+신규 안내)·미리보기 챗 편집 반영(S10, Property 병합). 검증은 실제 코드 평가(미구현=FAIL), Dual Merge·역방향 양쪽 확인.
- **수정한 이슈(10건)**: I3(스킬 API key 누수), I5(Command/Event BC해소), I6(diff 직접수정 스키마검증), I7(작업목록 탭전환 초기화), I8(구현열기 no-op), I9(MCP 사전신뢰로 레이스 제거), I10(PTY fd 누수→포트 wedge, 중대), I11(검증 요약 총계), I13(미리보기 챗 편집 미반영·UI재검필요), I17(시작 대기 표시).
- **전술적 미리보기 편집 라운드(2026-06-15~17, ShinSeongJin2, 6건)**: I21(Command/Event/ReadModel → **Design 캔버스 오버레이 투영** 재매핑, I18-C 대체 해소), I22(Impact Map nodeId=null 항목 "열기"), I23(VO/Enum Tactical Diff 표시 누락), I24(Property 추가/삭제 저장 실패·라이브 오염 방지), I25(캔버스·상세 즉시반영·형제 Aggregate 오노출), I26(인스펙터/AI챗 미리보기 편집 확장 + Vue 반응성 함정). 040 미리보기를 **읽기전용 → 편집 가능**으로 확장(모든 편집은 tacticalDiff 오버레이, 라이브 무오염). GWT 관련 동반 수정은 [design.md](design.md) D1·D2.
- **미해결/후속(5건)**: I4(impactMap 재생성 시 폴백·간헐), I12(force-accept design>code divergence[설계상]·property 중복노드), I14(종료된 proposal의 Code 세션 잔존 400), I16(폴더피커=활성세션 혼동), **I18-C(이벤트모델링 미리보기 오버레이 — 신규 Command/Event/ReadModel 가시화; 040 후속)**.
- **미검증 시나리오**: S5(git init 흐름), S8(폐기/철회), S9 정상경로 일부, S10(미리보기 편집 반영).
- **미구현**: 041(Constitution/Plan)은 Draft 스펙만.
