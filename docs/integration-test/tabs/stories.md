# Stories 탭 — 통합 검증 (초안)

> 다음 세션이 이어서 진행할 수 있도록 만든 **인벤토리·시나리오 초안**. 결과는 모두 ⬜(미실행).
> 진행 방식은 [proposals.md](proposals.md) 참고(스펙+코드 인벤토리 → 시나리오 → 라이브 검증 → 이슈 기록).

- **activeTab 값**: `Stories` (구 `Requirements`)
- **패널 컴포넌트**: [`RequirementsPanel.vue`](../../../frontend/src/features/requirements/ui/RequirementsPanel.vue) (026)
- **프런트 store**: [`requirements.store.js`](../../../frontend/src/features/requirements/requirements.store.js)
- **백엔드**: [`api/features/requirements/routes/`](../../../api/features/requirements/routes/) + [`requirementsIngestion`](../../../api/features/) (인제스천)
- **관련 스펙**: 001(인제스천 SSE) · 008(US 플래닝 에이전트) · 019(US 속성 패널) · 026(Requirements 탭) · 030(명확화 에이전트) · 031(생성 언어 정책) · 033(편집 이력) · 034(Epic/Feature 단위·하위 US 생성·DDD 검증) · 035(DDD 발견 마법사)
- **상태**: 🟡 진행중 — 인벤토리 store↔라우트 1:1 **확정**(불일치 없음), read 계열 API 레벨 검증 완료(2026-06-15). LLM/SSE/UI 흐름 라이브 검증 대기.

## 1. 탭의 의도/목표 (스펙 요약)

요구사항을 **Epic → Feature → UserStory** 계층으로 등록·조회·편집하는 파이프라인 **입구**. 자연어/문서를 **인제스천(SSE 진행 스트리밍)**으로 받아 트리화하고, **AI 플래닝**으로 Feature·하위 US를 생성하며, **명확화 에이전트**로 underspecified 항목을 보완하고, **DDD 적합성 검증**·**편집 이력**·**삭제 이력**을 제공한다. 이후 Design/Process/Data 탭이 이 요구사항을 전제로 동작.

> 주의: `Changes`(038, CHG-NNN) 관련 컴포넌트(`ChangesPanel`/`ChangeDetail` 등)는 **별도 탭(숨김)** 이므로 Stories 검증 범위에서 제외.

## 2. 보유 기능 목록 (코드 대조 초안)

| # | 기능 | 출처 스펙 | 컴포넌트 | 엔드포인트/액션 |
|---|---|---|---|---|
| 1 | Epic→Feature→US 트리 탐색·선택 | 026,034 | `RequirementsTree`, `EpicDetail`/`FeatureDetail`/`UserStoryDetail` | `fetchTree` |
| 2 | 요구사항 추가(자연어 → 인제스천) | 001 | `AddRequirementDialog` | 인제스천 SSE |
| 3 | 문서 업로드(인제스천 모달, 진행 스트리밍) | 001 | `RequirementsIngestionModal` | 인제스천 SSE |
| 4 | DDD 발견 마법사 | 035 | `DddWizardPanel` | `ddd_wizard` |
| 5 | 요구사항 명확화 — 전체/스코프(project/BC/Feature) | 030 | `ClarificationPanel`, `ClarityRadar`, `ClarificationSummary` | `fetchClarificationSession/Summary/Flags`, `fetchClarityScores`, `fetchClarificationLog` |
| 6 | 명확화 — UserStory 단위(상세 탭 내) | 030 | `UserStoryDetail`(명확화 탭) | clarification |
| 7 | Epic 생성/수정 | 034 | `EpicEditForm`, `EpicDetail` | `createEpic`, `updateEpic` |
| 8 | Feature 생성/수정 | 034 | `FeatureEditForm`, `FeatureDetail` | `createFeature`, `updateFeature` |
| 9 | Epic→Feature 자동 생성(각 Feature=spec.md) | 034 | `GeneratedFeaturesReview`, `FeatureGenStream` | `generateFeatures` |
| 10 | 하위 UserStory 자동 생성 | 008,034(US5) | `GeneratedStoriesReview` | `generateChildStories(scope, engine)` |
| 11 | UserStory 상세·속성 편집(통합 패널) | 019 | `UserStoryDetail` | `updateUserStory(fields, baseUpdatedAt)` |
| 12 | DDD 적합성 검증 | 034(US6) | `ValidationFindings` | `validateRequirement` |
| 13 | 편집 이력(직접 수정 추적) | 033 | `EditHistoryPanel` | `fetchItemHistory`, `fetchHistory` |
| 14 | 챗 편집(자연어 수정) + 로그 | — | `ChatEditPanel` | `chat_edit`, `fetchChatEditLog` |
| 15 | 삭제(US/Feature/Epic) + 디자인 동반 처리 옵션 | 034 | `DeleteConfirmDialog` | `deleteUserStory/Feature/Epic(removeDesign/disposition)` |
| 16 | 삭제 이력 | 034 | `DeletionHistoryPanel` | `fetchDeletionRecords` |
| 17 | 설계 미반영 US 식별 → 반영 요청 | 034(US7) | `DesignReflectPrompt`(App.vue) | `fetchPendingDesign`, `requestDesignForUserStories` |
| 18 | 설계 궤적(US→설계요소 trace) | 012,034 | `DesignTraceCanvas` | `fetchDesignTrace` |
| 19 | 임팩트 리포트 | — | `ImpactReportPanel` | `impact_report` |
| 20 | BC 캔버스 탭 | — | `BcCanvasTab`(**Epic 상세의 "Canvas" 탭** — US 상세 아님, 인벤토리 정정) | `fetchBcCanvas` |
| 21 | 생성 출력 언어 정책 | 031 | (생성 경로 공통) | LLM 언어 정책 |
| 22 | 전체 요구사항 데이터 삭제 | 026 | `RequirementsPanel` 툴바 | reset/clear |

> **store ↔ 백엔드 라우트 1:1 대조 확정(2026-06-15, 불일치 없음).** `requirements.store.js`의 모든 액션이 `api/features/requirements/routes/` 파일에 대응:
> tree→`requirements_tree.py` / propose·confirm·move·CRUD→`user_story_crud.py`·`feature_crud.py`·`bounded_context_crud.py` / generate-features·features/confirm→`feature_generation.py`·`epic_feature_propose.py` / generate-stories·child-stories/confirm→`child_story_generation.py` / validate→`ddd_validation.py` / ddd-wizard/*→`ddd_wizard.py` / clarification/*→`clarification.py` / chat-edit/*→`chat_edit.py`(scope ∈ `epic|feature|user-story`) / design-trace→`design_trace.py` / pending-design·user-stories/design→`design_reflect.py` / deletion-records/*→`deletion_history.py` / impact-report/*→`impact_report.py` / bounded-context·aggregate canvas→`canvas.py` / pivotal-events/*→`pivotal_events.py` / local-tooling/status. (`requestDesignForUserStories`만 `/api/ingest/...` 인제스천 라우트로 진입 — 의도된 설계.)

## 3. 검증 시나리오 (설계 — 다음 세션 실행)

> 전제: 백엔드/프런트 기동(`./dev.sh`), LLM·`CLAUDE_CODE_PATH` 설정. **인제스천이 핵심 입구라 빈 그래프에서 시작 가능**(다른 탭과 달리 Stories는 시드 불필요).

> **라이브 검증 환경(2026-06-15)**: 백엔드 :8000 / 프런트 :5173 가동 중. 그래프에 **시드 데이터 존재**(proposals 검증 잔존 — `DeliveryManagement` epic, US 14개, Payment 등). 빈 상태가 아니므로 read 계열은 실데이터로 검증. 아래 API 레벨(✅) = curl 직접 호출 확인, UI/SSE 흐름은 ⬜(브라우저 라이브 대기).

### S1. 트리 로드·탐색·빈 상태
- Stories 탭 진입 → Epic/Feature/US 트리 렌더, 빈 그래프면 빈 상태. 노드 선택 시 상세(Epic/Feature/US Detail) 표시. → ✅ (2026-06-15) **API ✅**(`/tree` 200, epic `DeliveryManagement`+US 14) + **UI ✅**(계층별 상세 표시 정상 — Epic/Feature/US Detail 전환 확인).

### S2. 요구사항 추가(자연어 propose→confirm)
- "+ 요구사항 추가" → 자연어 입력 → propose → 리뷰 → confirm → 트리 반영. (초안의 "phase SSE 인제스천"은 S3 문서 업로드. + 단위는 경량 propose/confirm) → ✅ (2026-06-15)
  - **Epic 수동/AI제안**: 기술명+표시명 2칸 정상(I1·I2 수정 후). AI 제안 영문 기술명+한글 표시명 생성 ✅
  - **Feature 수동/AI제안**: 소속 Epic 필수 강제 ✅(I3 수정). 제안 표시 시 입력란 유지 ✅(I4 수정)
  - **User Story 자연어**: 모호 입력("고객센터")은 분해 거부 + BC 자동분류 실패 graceful 폴백(경고 한국어=S14) ✅. 분해 가능 문장은 propose→confirm→트리 반영 happy path 정상 ✅
  - **발견·수정 버그**: I1·I2·I3·I4 (모두 수정완료)

### S3. 문서 업로드 인제스천 — **구조 검증**(기능은 상시 사용으로 신뢰)
- 4가지 아키텍처 관점 검증(2026-06-15) → ✅
  1. **코드분석 BPM-우선**: `run_hybrid_workflow`([hybrid_workflow_runner.py](../../../api/features/ingestion/hybrid/hybrid_workflow_runner.py)) DOCUMENT_BPM→CODE_RULES→MAPPING→ONTOLOGY로 BPM 먼저, ES는 Phase5 PENDING → 사용자 `promote-to-es`로 생성 ✅
  2. **단일 ES 파이프라인 재사용**: [ingestion_workflow_runner.py](../../../api/features/ingestion/ingestion_workflow_runner.py)가 `workflow/phases/*` 16 phase를 import 위임(재구현 0). `incremental_design_runner`도 동일 phase 재사용 ✅
  3. **소스별 분기 = User Stories 수렴점**: `extract_user_stories_phase`([user_stories.py](../../../api/features/ingestion/workflow/phases/user_stories.py))가 `source_type`로 figma/hybrid/rfp 분기 → 각 `*_to_user_stories.py` 변환기(입력형태 상이 = 정당한 분리) → US 이후 공유 phases ✅
  4. **중복**: 큰 중복 없음. 정리거리 2건 → I5·I6
- **발견 이슈**: I5(phases_langextract 빈 orphan 디렉터리), I6(stale `analyzer_graph` 주석)

### S4. Epic→Feature 자동 생성
- Epic 선택 → "Feature 자동 생성" → `FeatureGenStream` 진행 → `GeneratedFeaturesReview`로 후보 검토·반영. → ✅ (2026-06-15) 스트리밍 진행·후보 검토·반영 정상.

### S5. 하위 UserStory 자동 생성
- Feature/Epic 스코프 → "하위 US 생성" → `GeneratedStoriesReview` 후보 → 반영. (008 플래닝 에이전트) → ✅ (2026-06-15) 생성·후보검토·반영 정상.

### S6. UserStory 속성 편집(019)
- US 선택 → 속성 패널에서 필드 편집·저장(`updateUserStory`, `baseUpdatedAt` 낙관적 잠금) → 반영·충돌 처리. → ✅ (2026-06-15) 편집·저장·반영 정상.

### S7. 편집 이력(033)
- 직접 편집 후 `EditHistoryPanel`에 이력 표시(`fetchItemHistory`/`fetchHistory`). → ✅ (2026-06-15) **실데이터 확인**: S6 편집(US `c42f7582…` action "문의 등록 시 카테고리를 선택한다"→"고객이 문의 등록 시…")이 `/user-story/{id}/history`·`/chat-edit/user-story/{id}/history` 양쪽에 동일 레코드로 기록(before/after·timestamp). 관찰: 편집자 신원 `unknown user`(무인증 환경) → **I7 후속**([FOLLOW-UPS.md E-2](../FOLLOW-UPS.md)).

### S8. 챗 편집
- `ChatEditPanel`에서 자연어 수정 → 적용 → 로그(`fetchChatEditLog`). → ✅ (2026-06-15) **UI ✅ + 실데이터 교차검증**: US `837d56e8…`(FAQ 검색/조회) benefit을 챗으로 "더 구체적으로" 요청 → SSE 스트림·apply 정상. `/log`+`/history` 동일 기록(benefit before/after, feedback·rationale·summary), `source:"chat"`로 직접편집과 구분, 트리 benefit 실제 반영. 한국어 출력. (편집자 신원 unknown=I7)

### S9. 요구사항 명확화(030)
- "🔍 요구사항 명확화(전체)" → 세션 시작 → 트리 배지(flags) + `ClarityRadar` 점수. US 단위 명확화(상세 탭)도 확인. → ✅ (2026-06-15) **US/Feature/Epic/전체 스코프 모두 동작**. 스캔→질문→답변(추천/옵션/자유)→편집안→적용 흐름 정상. 백엔드 curl 검증(answer→apply 200, 중복=409 가드). **버그 다수 발견·수정**: I8(비-US 스코프 답변UI 부재)·I9(apply/answer 409 레이스)·I10(flagged US 상세 TDZ 크래시)·I11(인코딩 인디케이터)·I12(편집안 시 질문 사라짐)·I13(start 409 콘솔노이즈→200 resume)·I14(다중 US 편집안 표시 명확화).

### S10. DDD 적합성 검증(034 US6)
- "DDD 검증" → `validateRequirement` → `ValidationFindings` 결과. → ✅ (2026-06-15) **실데이터 교차검증**: 기존 Epic/Feature 전부 통과(진짜 결과). 검증 로직 동작 확인 — 의도적 오배치(배달 US→고객센터 BC)는 `wrong_bc` 검출, 중복 US는 `spec_conflict` 검출. `source:in-process`+findings 반환으로 LLM 실행 확인(예외 시 빈 findings degrade는 미발생). 한국어 출력. **+ I18 보강**: Epic/Feature 검증이 자식 US 오배치를 못 잡던 갭 수정(이제 자식 US도 wrong_bc 검사).

### S11. DDD 발견 마법사(035)
- "🧭 DDD 마법사" → `DddWizardPanel` 인터뷰 → 도메인 캔버스 산출. → ✅ (2026-06-15) 프로파일→단계추천→단계별 인터뷰(질문표시·답변/문서)→제안→확정→그래프 반영, 완료 후 Design 탭 이동+트리 펼침. 라이브 2개 도메인(음식배달·온라인강의) 검증. **버그 다수 발견·수정 I21~I31**: Event/Aggregate/Command 생성(체인), 입력란·질문 표시, 모달 보존, BC 이름 오염, Strategize 가드 등. **잔여 후속**: I32(classification 영속 LLM 불안정)·I22(BC 영문명) → [FOLLOW-UPS E-3](../FOLLOW-UPS.md). 핵심 생성(BC/Agg/Cmd/Event) 정상.

### S12. 삭제 + 디자인 동반 + 삭제 이력
- US/Feature/Epic 삭제(`removeDesign`/disposition 옵션) → `DeletionHistoryPanel` 기록. → ✅ (2026-06-15) **실데이터 검증**: Epic(수강관리) 삭제+removeDesign → BC4→3·Agg4→2·Cmd10→5·Event9→4 cascade(이력 nodes 13/rels 12), **복구 round-trip 완전 원복**(BC3→4·Agg2→4·…, restored=True). US/Feature 삭제는 소유구조상 동일 문제 없음(설계는 US 경유, `exclusive_design_ids`).
  - **발견·수정 I33**: Epic 삭제 `removeDesign`이 **US 배타 설계만** 제거 → US 없이 BC 직속(HAS_AGGREGATE)인 마법사 산출물(Aggregate/Command/Event)이 **orphan으로 잔존**(node 1만 삭제). `da.bc_design_ids`(BC 직속 Aggregate→Command→Event) 추가해 함께 제거 → 검증 후 node 13 삭제·복구 정상.

| 항목 | 출처 | 상태 |
|---|---|---|
| I33 Epic removeDesign이 BC 직속 설계 미제거(orphan) | S12 | ✅ 수정완료(2026-06-15) |

### S13. 설계 미반영 US 반영(034 US7)
- Design/Process 탭 진입 시 `DesignReflectPrompt`(미반영 US 감지) → "반영" → `requestDesignForUserStories` 인제스천 진행. (App.vue 오케스트레이션) → ✅ (2026-06-15) **실데이터 검증**: AI Feature 생성으로 US 13개 → Design 탭 진입 시 미반영 감지 모달 → 반영 → ES 인제스천 → Aggregate 8/Command 19/Event 31/ReadModel 3 생성, pending-design 0. **발견·수정 I34·I35**.

| 항목 | 출처 | 상태 |
|---|---|---|
| I34 반영 완료 시 문서 업로드 모달 멋대로 뜸 | S13 | ✅ 수정완료(2026-06-15) — 전체모달 `v-if`가 `isOpen && !isProcessing`라 완료(isProcessing→false) 시 업로드폼 노출 → `&& !summary` 추가 + `closeFloatingPanel`이 `update:modelValue false` emit |
| I35 완료 모달 카운트 전부 0 / Policy 빈칸 | S13 | ✅ 수정완료(2026-06-15) — reflect 러너가 그래프 집계로 snake_case 실카운트(user_stories/bounded_contexts/aggregates/commands/events/read_models/**policies/uis**) 전송 |

### S14. 생성 언어 정책(031)
- 생성(Feature/US/명확화) 출력 언어가 정책대로(한국어 등) 나오는지. → ✅ (2026-06-15) **코드+관찰 확인**: 인제스천 phase들이 `display_language`(기본 `ko`)를 프롬프트에 `"in Korean"` 지시로 주입(events/aggregates/commands/readmodels/properties/ui_wireframes/bounded_contexts), propose/마법사/명확화/검증은 `"SAME natural language as input"`. S2~S13 전 생성물 한국어 출력 관찰. 버그 없음.

### S15. 설계 궤적·임팩트·캔버스 탭
- US 상세에서 `DesignTraceCanvas`(설계 궤적), `ImpactReportPanel`, `BcCanvasTab` 동작. → ✅ (2026-06-15)
  - **설계 궤적 API ✅**: 액션 US→6노드(Command/Event/Aggregate), 조회 US는 (수정 전) empty.
  - **캔버스 탭**: US 상세엔 없음 → **Epic 상세 "Canvas" 탭**(`BcCanvasTab`)으로 인벤토리 정정(기능20). `AggregateCanvasTab`은 US 상세 미사용.
  - **발견·수정 I36**: 조회성(읽기측) US("...조회한다", command 없음)는 design_trace가 command-루트라 **궤적이 항상 empty**. → `(US)-[:IMPLEMENTS]->(ReadModel)`을 루트로 확장(`_expand_trace(extra_rm_ids=)` + 먹이는 Command 있으면 전체 읽기 레인). 검증: 조회 US 궤적 empty→ReadModel 노드 표시.

| 항목 | 출처 | 상태 |
|---|---|---|
| I36 조회 US 설계궤적 empty (읽기측 ReadModel 미표시) | S15 | ✅ 수정완료(2026-06-15) — ①백엔드: design_trace를 ReadModel-루트로 확장 ②프론트: `DesignTraceCanvas` `nodeTypes`/COLUMN에 **ReadModel 누락** → `ReadModelNode` 등록 + ReadModel 컬럼(4) 추가(이전엔 기본 노드로 그려져 스티커 안 됨) |

## 4. 발견 이슈

| # | 심각도 | 증상 | 원인(추정) | 후속 |
|---|---|---|---|---|
| I21 | **상** | DDD 마법사 confirm이 **Event/Aggregate/Feature 변경을 조용히 드롭**(BC/US만 적용, 나머지는 `errors`로 버리고 프런트가 미표시) — 마법사 끝내도 BC만 생기고 이벤트/애그리거트 0 | confirm 핸들러에 BC/US 핸들러만 존재; 엔진이 LLM에 기존 BC id 미전달이라 연결 불가; 프런트가 `errors` 무시 | **✅ 구현완료(2026-06-15)** — ①engine이 기존 BC(id,name)+연결 가이드를 LLM에 전달 ②confirm에 Feature/Aggregate/**Event(Aggregate→Command→Event 체인)** 핸들러 + BC id/이름 해석기(`_resolve_bc_id`) ③프런트가 미적용 변경을 alert로 노출. (체인 메서드는 인제스천이 쓰는 검증된 create_aggregate/command/event 재사용) **+ 순서 보정**: Discover(이벤트, 2단계)가 Decompose(BC)·Code(애그리거트)보다 먼저라 이른 이벤트는 BC/애그리거트가 없음 → **에러 대신 `deferred`(문서엔 기록, 이후 단계서 반영)**로 부드럽게 처리, 애그리거트명 미지정 시 BC 대표 애그리거트로 기본 연결 |
| I29 | 중 | 마법사 Strategize의 **BC update가 "대상 BC 못 찾음"으로 전부 보류**(domainType 미반영) + v-show 탓에 **재오픈 시 이전 보류 누적이 남음** | ①LLM이 BC update 대상을 targetId/boundedContextName이 아닌 `after.name`(BC 자기 이름)에 넣음 → `_resolve_bc_id`가 못 찾음 ②`beginSteps`가 deferredNotes 초기화 안 함 | **✅ 수정완료(2026-06-15)** — `_bc_id_by_name` 헬퍼로 BC update를 `after.name/displayName`으로도 해석 + `beginSteps`에서 deferredNotes 초기화. (검증: 현재 그래프 BC4/Agg4/Cmd7/Event6 — BC-only 아님. domainType은 재실행 시 반영) |
| I31 | **상** | 마법사 BC 이름이 라벨로 **오염**(`고객센터 → Supporting`·`배달관리 컨텍스트 정의`) + 엉뚱한 Aggregate `배달관리 → Core` | ① `_apply_bc_update`가 `name` 허용 → Strategize/Define의 `after.name`(라벨)이 BC명 덮어씀 ② Strategize에서 LLM이 분류 라벨을 Aggregate로 오발행 | **✅ 수정완료(2026-06-15)** — `_apply_bc_update`에서 name/displayName 제외(이름 불변, 분류·캔버스만), Strategize 단계는 BoundedContext 변경만 허용(그 외 deferred). 단 **기존 오염 그래프는 DB 재생성 필요** |
| I30 | UX | 마법사 완료 후 산출물(Aggregate/Command/Event)이 Stories엔 안 보임(BC=Epic만) → Design 탭으로 이동 필요 + 네비게이터 전체 펼침 희망 | `@done`이 Stories에 머묾; `expandAll`이 얕음(BC+Aggregate 1단계) | **✅ 수정완료(2026-06-15)** — 마법사 `@done`→`robo:switch-tab` 'Design'+`navigatorStore.refreshAll()`; navigator `expandAll`을 전 id 재귀 수집(US 그룹 `::userstories` 포함)으로 개선(기존 Expand All 버튼·refresh 자동펼침에 적용) |
| I28 | 중 | 마법사 Connect 단계의 **standalone Command 생성이 미지원**("미지원 변경(Command/create)") | I21이 Event 핸들러만 추가하고 Command create 핸들러 누락 | **✅ 수정완료(2026-06-15)** — Command create 핸들러 추가(Aggregate→BC 체인, BC 없으면 deferred, 애그리거트명 기본=BC명) + `_SYSTEM`에 Command 연결 규칙 |
| I27 | UX | 마법사 confirm 결과 노출 문제: ①보류(deferred)를 alert로 띄워 **오류처럼 보임** ②오류 alert 확인 누르면 **그대로 다음 단계로 넘어감** | I21 1차 구현이 errors·deferred를 한 alert로 묶고 무조건 advance | **✅ 수정완료(2026-06-15)** — deferred는 **인라인 누적 정보 안내**(회색), errors는 **인라인 빨간 메시지 + advance 중단**(수정 후 재확정/건너뛰기). alert 제거. **보류 안내는 `<details>`로 접기 가능**(기본 접힘) |
| I26 | 중 | 마법사 모달을 **닫으면 진행상황(세션·답변·현재단계) 소실** — 백엔드 세션·조회 API는 있으나 프런트가 sessionId 미보관 | 오버레이가 `v-if`라 닫힘 시 컴포넌트 파괴; localStorage 재접속 배선 없음 | **✅ 수정완료(2026-06-15, v-show)** — 오버레이 `v-if`→`v-show`로 변경해 닫아도 컴포넌트 유지(세션 내 진행상황 보존). 새로고침 대비 localStorage 재접속은 후속(백엔드 GET /ddd-wizard/{id} 존재) |
| I25 | 중 | 마법사 **Strategize(Core/Supporting/Generic 분류) 결과가 BC에 미반영** | ① `_apply_bc_update` 허용필드에 `domainType` 없음 ② BC update가 `targetId` 없으면 드롭 ③ 프롬프트가 Strategize→BC update 미지시 ④ **LLM이 `after.domainType`을 안 채우고 artifact에만 분류 기재** | **✅ 수정완료(2026-06-15)** — 근본원인: BC 분류 필드가 **`classification`(canvas/contexts UI가 읽음)** vs `domainType`(aggregates/viewer) 으로 **이원화(모델 불일치)** 였고 wizard가 `domainType`에만 기입 → canvas UI 미표시. 이제 `_apply_bc_update`가 분류를 **`classification`·`domainType` 둘 다** 동일값 세팅 + `_bc_id_by_name` 이름해석(I29) + `_SYSTEM` 프롬프트 `after.classification` 명시·JSON 예시. (라이브 재실행 시 표시 확인 필요) |
| I24 | **상** | 마법사 단계에 **인터뷰 질문이 화면에 표시 안 됨** — 단계 제목+답변/문서칸만 보여 "무엇에 답할지" 알 수 없음(백엔드 STEP_QUESTIONS가 프런트로 안 옴) | `WizardStepRef`에 questions 없음 → recommend_plan/응답에 미포함 → UI 미표시. 질문은 LLM 프롬프트에만 주입됨 | **✅ 수정완료(2026-06-15)** — `WizardStepRef.questions` 추가, `recommend_plan`이 STEP_QUESTIONS 동봉, running 단계 UI에 "이 단계에서 생각해볼 질문" 목록 표시. start 응답에 questions 실림 확인 |
| I23 | UX | 마법사 단계의 **답변/메모 vs 기존 문서 입력란 의도 구분 불명확** | 라벨 "답변/메모"·"또는 기존 문서 붙여넣기"만으론 용도 차이 안 드러남 | **✅ 개선완료(2026-06-15)** — 라벨을 "①질문에 대한 답변(직접 입력)"·"②기존 문서(선택·참고자료)"로 + 상단 도움말("직접 답변 vs 원본 문서 붙여넣기, 둘 중/둘 다") + 4000자 안내 |
| I22 | 경미 | 마법사 생성 BC가 `name=displayName`(한글)·`description` 빈값 | 마법사 BC create가 영문 기술명 미생성(서브도메인명이 한글) + LLM이 desc 미포함 | 후속/경미(마법사는 UI 입력칸 없어 자동·I1 패밀리). 필요 시 영문명 자동파생 |
| I20 | **상** | US 단위 DDD 검증 시 **거의 모든 US가 spec_conflict로 걸림**(false positive) — 메시지가 자기 자신을 "이미 동일 US 존재"로 지목 | `_build_prompt`의 기존 US 목록에 **검증 대상 US 자신이 포함**(이미 그래프에 존재) → LLM이 자기중복 판정. propose(신규)엔 없던 문제, I19(기존 US 검증)에서 노출 | **✅ 수정완료(2026-06-15)** — ValidateRequest에 `userStoryId` 추가, `_build_prompt`가 그 id를 기존 US 목록에서 제외. curl 검증: 정상 US ok=true/0건, 배달 US는 wrong_bc 유지 |
| I19 | 중 | **US 단위 DDD 검증이 UI에 없음** — 백엔드(`targetType=userStory`)는 지원하나 버튼은 Epic/Feature만 | UserStoryDetail에 validate 트리거 없음, `onValidate`도 epic/feature만 처리 | **✅ 추가완료(2026-06-15)** — UserStoryDetail에 `🔎 DDD 검증` 버튼(`@validate`) + RequirementsPanel `onValidate('userStory')`(트리에서 부모 BC/Feature id 도출). curl로 US 단위 wrong_bc 검출 확인 |
| I18 | 중 | **Epic/Feature DDD 검증이 그 안의 오배치 자식 US를 못 잡음** — 고객센터 Epic에 배달 US를 넣어도 Epic 검증은 통과(US 단위 검증만 wrong_bc 검출) | `_build_prompt`가 자식 US를 컨텍스트로만 나열하고 LLM에 target(epic/feature)만 검사 지시 → epic=BC라 wrong_bc 불성립 | **✅ 수정완료(2026-06-15)** — Epic/Feature target일 때 나열 US에 id 포함 + "각 자식 US의 BC 적합성도 검토, 오배치는 wrong_bc로 affected[]에 US id" 지시 추가. curl 검증: 고객센터의 배달 US `4421e314`를 wrong_bc(→DeliveryManagement)로 검출 |
| I17 | 정보 | 명확화 free_text가 5단어 초과 시 **조용히 앞 5단어만** 사용 | FR-005(명확화=짧은 결정값) 의도 — closed/추천수락엔 무관, free_text만 | **의도된 설계(현행 유지)**. 단 조용한 잘림 경고는 가벼운 후속 → [FOLLOW-UPS.md E-2 인접](../FOLLOW-UPS.md) (선택) |
| I16 | 중 | 명확화 질문을 **끝까지 답변·적용하면 빈 창**만 표시(툴바만 남고 본문 공백) | 마지막 적용 후 `currentQuestion=null`인데 `advance()`가 status를 `completed`로 안 바꿈(=`endSession` 때만) → 어떤 템플릿 분기도 안 잡힘 | **✅ 수정완료(2026-06-15)** — "모든 질문 처리됨" 완료 분기 추가(✓ + 세션 종료/닫기 버튼) |
| I15 | 중 | 명확화 apply가 **EditConflict("외부에서 변경됨, 재인코딩 필요")** 나면 **빠져나갈 수 없음**(편집안 적용 화면 반복) | 충돌 시 질문이 `answered`로 남아 `current_question`(첫 pending)에 안 잡힘 → 재답변 시 `question_not_current` 409. 충돌은 보통 같은 세션 선행 편집이 공유 US 변경으로 baseUpdatedAt 드리프트 | **✅ 수정완료(2026-06-15)** — apply 충돌 시 질문을 **pending으로 복귀** + stale proposal/answer 제거 → 같은 질문 재답변=재인코딩 가능. 메시지도 안내형으로 수정 |
| I14 | 정보/UX | Feature/Epic 스코프 명확화에서 편집안이 "두개씩" 보임 → **버그 아님**(스코프 질문이 여러 US에 영향 → US별 편집안 1건씩, curl로 중복 없음 확인) | 편집안 헤더가 UUID라 서로 다른 US가 같은 내용처럼 보여 혼동 | **✅ 명확화 개선(2026-06-15)** — 편집안 헤더에 **US 식별(역할: 행동)** + "영향받는 US N건에 적용" 안내 표시 |
| I13 | 하 | `POST /clarification/sessions` **409가 콘솔에 계속**(빨간 줄) — 기존 스코프 세션 resume 경로(정상 동작이나 노이즈) | 스코프당 1세션 가드가 409 반환 → 브라우저가 네트워크 에러로 로깅(JS로 억제 불가) | **✅ 수정완료(2026-06-15)** — 백엔드가 기존 세션 존재 시 **409 대신 200으로 기존 세션 반환**(resume, 스캔 미실행) → start 멱등·콘솔 409 제거 |
| I12 | 중 | 답변 후 "편집안 준비됨"이 뜨면서 **답변하던 질문이 사라짐**(다음 질문으로 즉시 advance되거나 마지막이면 사라져 혼란) | `currentQuestion`=첫 pending이라 답변 즉시 다음으로 이동, 편집안(이전 질문용)과 동시 표시 | **✅ 수정완료(2026-06-15)** — 편집안 미적용 대기 중엔 다음 질문 **숨김**(검토 집중) + 편집안 헤더에 **해당 질문 텍스트** 표시. 적용 후 다음 질문 노출 |
| I11 | 하 | 답변(수락/선택/제출) 후 편집안 생성까지 LLM 지연 동안 **진행 표시 없음**("답변 인코딩 중..." 미표시) → 멈춘 듯 보임 | SSE `encoding` 이벤트가 블로킹 인코딩과 같은 요청 내 push + 직후 `fetchClarificationSession`가 progress 덮어씀 → 표시 타이밍 상실 | **✅ 수정완료(2026-06-15)** — 패널에 로컬 `encoding` 상태 인디케이터(답변 액션 중 "⏳ 답변 인코딩 중..." 표시, SSE 타이밍 비의존) |
| I10 | **상** | **flagged된 US를 열면 상세가 안 열림**(셋업 크래시) + 이후 Epic/Feature 상세도 Vue 내부에러(`emitsOptions` null·`instance.update`) 연쇄 | UserStoryDetail의 `watch(immediate:true)`가 flagged US에서 `onSelectTab('clarification')` 호출 → `isCurrentSession`(const) **선언 전 접근(TDZ)**. 명확화 실행으로 flag 생기기 전엔 잠복 | **✅ 수정완료(2026-06-15)** — `isCurrentSession` computed를 watch 위로 이동(TDZ 제거). 셋업 정상화로 연쇄 에러도 해소 |
| I9 | 중 | 명확화 답변/적용 시 **409 콘솔에러**(`question_not_current`/`question_not_answered`) — 기능은 동작(질문 applied됨)하나 stale proposal 재클릭·더블클릭으로 오류 로그. 적용 여부 불확실하게 보임 | ① 패널 액션이 에러 미처리(uncaught) ② apply 후 SSE `edit_ready`가 이미 처리된 질문의 편집안을 **되살림** → 재클릭 → 409 (백엔드 409 가드는 중복적용 방지로 **정상**) | **✅ 수정완료(2026-06-15)** — store `answerQuestion`/`applyEdit` 409시 throw 대신 **세션 재동기화+proposal clear**, SSE `edit_ready`는 applied/skipped 질문이면 **무시**, 패널에 `busy` 가드+에러 catch+버튼 disabled. (curl로 answer→apply 200·중복=409 검증) |
| I8 | **상** | 요구사항 명확화 **전체(project)/Epic/Feature 스코프는 동작 불가** — 세션·질문은 백엔드에 생성되나 답변 UI가 렌더 안 됨. 재시도 시 `POST /clarification/sessions` **409**(고아 세션). US 스코프만 정상 | `ClarificationPanel`(전역 `clarificationSession` 읽는 scope-agnostic 패널)이 **`UserStoryDetail`에서 `user_story` 스코프일 때만** 렌더. 비-US 스코프 렌더 위치 부재(EpicDetail/FeatureDetail은 `ClarityRadar` 점수만) | **✅ 수정완료(2026-06-15)** — RequirementsPanel에 비-US 활성 세션일 때 standalone `ClarificationPanel` 오버레이 렌더 |
| I7 | 후속 | 편집 이력에 편집자 신원 미기록(`unknown user`, 호스트명 fallback) | 무인증 환경 — 사용자 컨텍스트 부재 | **후속/백로그** → [FOLLOW-UPS.md E-2](../FOLLOW-UPS.md)(인증 도입 시 개선) |
| I5 | 정리 | `workflow/phases_langextract/` 빈 orphan 디렉터리(`.py` 0개, import 0) | 미사용 잔존 디렉터리 | **보류(유지)** — 사용자 결정, 향후 작업 가능성 고려 |
| I6 | 정리 | `bpm_to_user_stories.py:3`·`code_to_rules/rule_filters.py:3`의 `"Mirrors analyzer_graph..."` 주석이 **존재하지 않는 모듈** 참조 | stale 문서 주석 | **✅ 정리완료(2026-06-15)** — 두 docstring에서 analyzer_graph 참조 제거 |
| I3 | 하 | Feature **AI 제안** 시 소속 Epic 미선택 상태에서도 "제안 받기" 가능(막혀야 함 — 수동 폼은 이미 BC 필수) | AI 제안 버튼 disabled 조건에 `featureForm.boundedContextId` 누락([AddRequirementDialog.vue](../../../frontend/src/features/requirements/ui/AddRequirementDialog.vue)) | **✅ 수정완료(2026-06-15)** — disabled에 `!featureForm.boundedContextId` 추가 + 미선택 안내문구 |
| I4 | 하 | Feature(및 Epic) AI 제안 결과가 뜨면 자연어 설명 textarea가 세로로 **수축**됨 | `.dialog__body` flex column에서 textarea가 flex item이라 형제(제안 카드) 추가 시 수축 | **✅ 수정완료(2026-06-15)** — textarea/`.nl-input`에 `flex-shrink:0`(본문 스크롤) |
| I2 | 중 | AI 제안 Epic이 영문 기술명을 생성하지 않음 — 제안 카드 `기술명` 칸이 한글(입력 언어)로 채워짐 | `EpicProposal` 스키마에 `displayName` 없음 + 프롬프트가 "입력 언어로 name 작성" 지시([epic_feature_propose.py](../../../api/features/requirements/routes/epic_feature_propose.py)) | **✅ 수정완료(2026-06-15)** — `EpicProposal.displayName` 추가 + 프롬프트를 `name=영문 PascalCase 식별자 / displayName=입력언어 라벨 / description=입력언어`로 변경. 카드(기술명/표시명/설명)·`addProposedEpic` 기존 배선 그대로 동작 |
| ※ | — | (비-버그) AI 제안/생성 시 **동일 프롬프트 즉답** = 전역 LangChain SQLite 캐시 기본 ON([langchain_cache.py](../../../api/features/ingestion/langchain_cache.py), `INGESTION_CACHE_DEFAULT` 기본 True). `/api/ingest/cache/*` 토글 가능 | 의도된 설계 | 조치 불필요 |
| I1 | 중 | 수동 Epic 추가/편집 시 기술명(`name`)·표시명(`displayName`) 구분 없이 단일 입력칸만 제공 → 한글 입력이 `name`·`key`에까지 들어가 인제스천 산출(영문 `name`+한글 `displayName`)과 데이터 형태 불일치. (Feature는 displayName 없음 → 무관) | 폼 입력 1칸, route가 `display_name` 미전달 → 백엔드 `display_name = display_name or name` fallback; update는 `displayName=name` 강제 | **✅ 수정완료(2026-06-15)** — 기술명+표시명 **2칸** 도입. 계약(`BoundedContextCreate/UpdateRequest.displayName`)·neo4j(`update_bounded_context(display_name=)` 독립)·route(create/update 전달)·store(`createEpic/updateEpic` displayName)·UI(AddRequirementDialog 수동+AI제안, EpicEditForm 2칸). 단위테스트 7 pass |

## 5. 결론

- **S1~S15 전 시나리오 라이브 검증 완료 (2026-06-15).** store↔라우트 인벤토리 1:1 확정. 핵심 생성/편집/명확화/DDD검증/마법사/삭제·복구/설계반영/궤적 모두 동작 확인(실데이터 교차검증 포함).
- **발견·수정 버그 36건 (I1~I36)** — 주요:
  - **명확화(030, S9)**: I8(비-US 스코프 답변 UI 부재)·I9(apply 409 레이스)·I10(flagged US 상세 TDZ 크래시)·I11~I16
  - **DDD 마법사(035, S11)**: I21(Event/Aggregate/Command 생성 체인)·I24(단계 질문 표시)·I26(모달 보존)·I28·I29·I31(BC 이름 오염)
  - **삭제(S12)**: I33(Epic removeDesign이 BC 직속 설계 미제거 → cascade)
  - **설계 반영(S13)**: I34(완료 시 업로드 모달 오픈)·I35(완료 카운트 0)
  - **설계 궤적(S15)**: I36(조회 US 읽기측 ReadModel 미표시)
  - **요구사항 추가(S2)**: I1~I4(기술명/표시명, Feature AI 가드, 입력란 수축)
- **후속/백로그**: I7(편집자 신원·무인증)·I22(마법사 BC 영문명)·I32(Strategize classification LLM 신뢰성) → [FOLLOW-UPS.md](../FOLLOW-UPS.md)
- 횡단(031 언어정책): 모든 생성 경로 한국어 출력 확인(S14).
