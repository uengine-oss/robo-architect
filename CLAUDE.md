<!-- SPECKIT START -->
Active feature plan: [specs/043-task-ui-unification/plan.md](specs/043-task-ui-unification/plan.md)

**043 BPM·Event Modeling 단일 Process 탭 + task=UI 일관성** (started 2026-06-11) — spec-042 후속(읽기뷰어 → 구조통합). 실측상 두 뷰가 다른 앵커(BPM=`:BpmTask`, EM=`:BoundedContext`)·task↔UI 불일치(UI가 [ui_wireframes.py](api/features/ingestion/workflow/phases/ui_wireframes.py) "1 UI per Command/ReadModel"로 생성 → task당 0~2개). **UI를 공유 앵커로 task=UI 일관화**: (US1 P1) `Process`·`Event Modeling` 탭을 **단일 Process 탭+BPM⇄EM 토글**(신규 `ProcessPanel.vue`); (US2 P1) ES 승격 UI 생성을 **task당 1 트리거 UI**(Command를 `task_id`로 그룹→LLM이 사람-조작 Command 선택, entry 폴백; 기존 `:UI`/`ATTACHED_TO` 재사용=신규 라벨/관계 0); (US3 P2) ReadModel은 무조건 UI 제거→소비표시(`ATTACHED_TO {role:'display'}`)/조회화면이면 task-UI 승격(LLM); (US4 P2) task 포함요소를 **EM 형식 가로레인**(신규 `EventModelingLane.vue`, 042 trace 데이터 재사용; `DesignTraceCanvas`는 requirements 유지). Command/Event task귀속·A2A BPM **불변**. 인제스천 변경=**재인제스천 필요**. Phase 0/1 ✅. Phase 2 ⏸ `/speckit-tasks`. Constitution PASS(조건부 — ReadModel role 속성=라벨/관계 0, propose는 통합뷰 노출+수정).

---
이전 피처(039) 참고:
Active feature plan: [specs/042-bpm-event-unification/plan.md](specs/042-bpm-event-unification/plan.md)

**042 BPM↔Event Modeling 구조적 통합 (단일 그래프, 두 투영 뷰)** (started 2026-06-10) — BPM 뷰·Event Modeling 뷰를 **하나의 Neo4j 그래프의 두 투영**으로 통합. 그래프는 이미 그렇게 영속됨: 하이브리드(A2A→ES) 파이프라인이 `:BpmTask`를 척추로, ES 산출물을 `PROMOTED_FROM`으로, UI는 `(:UI)-[:ATTACHED_TO]->(:Command)-[:PROMOTED_FROM]->(:BpmTask)`로 연결([persistence.py](api/features/ingestion/hybrid/event_storming_bridge/persistence.py)·[design_trace.py](api/features/requirements/routes/design_trace.py)). **신규 스키마 0건의 읽기 전용 투영 + UI 정리**: (US2 P1) BPM task 인스펙터(`HybridTaskInspector.vue`)에 "포함 요소" 버튼→**모달**로 `(:BpmTask)<-[:PROMOTED_FROM]-(…)` 체인을 event-modeling 스티커로 표시; 백엔드는 `design_trace`를 일반화한 읽기 라우트 `GET /api/graph/bpm-task/{id}/design-trace`(frontier=task의 promoted Command), 프런트는 순수 컴포넌트 `DesignTraceCanvas.vue`(`trace` prop) **무수정 재사용**, **캔버스 불변**. BPM=A2A 단일 생성경로(011 process-flows는 생성원 아님). UI 없는 task="System". (US4 P2) "Big picture" 탭·패널·`bigpicture.store`·`/api/graph/bigpicture-timeline` 제거 + 비탭 소비자 정리(`TreeNode.vue` dead-branch, `ExportDocumentTemplate.vue` swimlanes 섹션). Phase 0/1 ✅(plan/research/data-model/contract/quickstart). Phase 2 ⏸ `/speckit-tasks`. Constitution PASS(신규 라벨/관계·LLM·SSE 0 → I·II·III·IV·VI 해당없음/충족).

---
이전 피처(036) 참고:
Active feature plan: [specs/036-bpmn-rule-mapping-recall/plan.md](specs/036-bpmn-rule-mapping-recall/plan.md)

**036 BPMN 룰 매핑 recall 개선 (용어 정규화)** (started 2026-06-04) — 평문 요구사항(한국어 GWT)↔레거시 코드 약어 어휘갭으로 임베딩 코사인이 0.45~0.55로 collapse → 매핑돼야 할 BL 룰이 retrieval floor(`agentic_retriever.MIN_BL_INCLUSION=0.45`)에서 LLM 검증기 도달 전 탈락(recall 손실). **해결**: 이미 추출되나 임베딩 단계 미사용인 glossary(`extract_glossary`)를 `run_agentic_retrieval`→`_candidates_for_task` 임베딩 입력에 **양방향 정규화** 주입(task query엔 code_candidates, rule blob엔 term/aliases append). **floor·후보예산(`bl_top_k`/`per_task_cap`) 불변** → 검증기 부하·사용자 화면 노출 불변(인지부하 최소화=최우선). 신규 모듈 `term_normalizer.py`(순수함수) + 배선 2곳. env `HYBRID_GLOSSARY_NORMALIZE`(기본1, 0=완전 무변경) A/B·회귀 안전망. 신규 노드/관계 0건. 측정=골든픽스처(input_resource 자동납부 본인확인 PDF 2종 + zapamcom 분석 그래프), 회귀0+회복≥1, 소요≤1.2x. Phase 0/1 ✅(plan/research/data-model/contract/quickstart). Phase 2 ⏸ `/speckit-tasks`. Constitution PASS(템플릿 미작성, 자체 게이트 통과).

---
이전 피처(035) 참고:
Active feature plan: [specs/035-ddd-discovery-canvases/plan.md](specs/035-ddd-discovery-canvases/plan.md)

**035 DDD 발견 마법사 & 도메인 캔버스** (started 2026-05-31) — `ddd-starter`(8단계) 스킬 통합: (US1) 요구사항 탭 맨땅/에픽 양쪽에서 프로파일링→옵트인 DDD 마법사(030 clarification 세션 + 034 이원화 엔진 + SSE 재사용); (US2) `Event.pivotal`/`hotspot` 속성 추가 → 피보탈 경계 서브도메인 도출; (US3) **BC 상세 화면 신설**(EpicDetail 탭화 + Canvas 탭, 설계 캔버스 BC 클릭 진입; `ddd_spec` `bc_canvas`/`BoundedContextProjection` 재사용); (US5) `AggregateViewerInspector`에 Aggregate Canvas 탭(spec 027 불변조건/`aggregate_spec` 재사용); (US6) `contexts` classification에 **generic 추가**(현재 core/supporting만); (US7) 그래프→`.ddd` 내보내기(`ddd_spec` 렌더러 경로 매개변수화). **진실의 원천=그래프**, 캔버스=투영, `.ddd`=보조. 신규 노드 라벨/관계 0건(속성 추가만). Phase 0/1 ✅(plan/research/data-model/3 contracts/quickstart). Phase 2 ⏸ `/speckit-tasks`. Constitution PASS. 의존: spec 034(미커밋 상태 — `generation/`·`local_tooling`·엔진 토글), 030, 027/028, 029 robo-spec, 004 change plan/apply, 031 언어정책.

---
이전 피처(034) 참고:
Active feature plan: [specs/034-requirement-epic-feature-units/plan.md](specs/034-requirement-epic-feature-units/plan.md)

Read the plan for technologies, project structure, constitution gates, and architectural constraints relevant to current work. Companion artifacts in the same directory:
- spec.md (what & why — 7개 User Story로 확장됨. US1 "+"를 **Epic/Feature/US 3-granularity** 등록(AI 제안+수동), US2 Epic·Feature 전용 **뷰 패널**, US3 **편집 패널**, US4 선택 범위에 따른 **clarification radar 필터링**, US5 Epic·Feature 등록 시 **하위 US 자동 생성**(제안→확인; 엔진은 Settings에서 **in-process LLM** 또는 **로컬 Claude IDE+speckit** 선택, 후자 미설치 시 설치 안내), US6 **DDD 적합성·입도·기존 spec 정합성 검증**(speckit 스킬, 없으면 robo-spec이 speckit-specify override/신규 `robo-validate`), US7 Event Modeling/Design 탭 진입 시 **미반영 US 식별→설계 자동 반영**(journey 추가/Aggregate 생성·변경, 제안→확인). 매핑: **Epic=`BoundedContext`, Feature=`Feature`, US=`UserStory`** — 신규 노드 라벨/관계 0건. 모든 LLM 변경 propose→confirm.)
- research.md (D1 Epic=기존 BC, D2 `PATCH /feature`·`/bounded-context`+ops `update_*`(속성만 SET, 관계 보존), D3 `POST /bounded-context`로 Epic 생성, D4 Epic/Feature propose=user-story propose 패턴, D5 radar=프런트 배선만(scope 이미 지원), D6 뷰/편집=탭 패널(URL 라우트 아님), D7 편집충돌=낙관적 안내. **D8 생성엔진 이원화**(in-process=spec008 `run_user_story_planning`/Settings 토글 vs claude-ide), **D9 claude-ide 호출+설치 preflight**(`shutil.which`+스킬존재, 현재 미구현; spec015/029 `claude_code` PTY/`_install_robo_spec`/robo-spec MCP 재사용), **D10 SSE 진행**(`sse_starlette`, 현 planning/change-plan은 동기→보강), **D11 DDD 검증 스킬**(robo-spec `robo-validate` 또는 speckit override + MCP 컨텍스트), **D12 미반영 US=`IMPLEMENTS→Command` 부재**, **D13 설계반영 오케스트레이션**(탭훅→pending→prompt→기존 change plan/apply), **D14 엔진설정=Settings 저장(그래프 아님).**)
- data-model.md (**Neo4j 스키마 0건.** 기존 노드 속성 갱신/생성만. 신규 Pydantic: `FeatureUpdate*`/`BoundedContextCreate·Update*`/`Epic·FeaturePropose*`(US1·3); `GenerateChildStoriesRequest/GeneratedStory/Confirm*`+`LocalToolingStatus`(US5); `ValidateRequest/ValidationFinding/CorrectionProposal`(US6); `PendingDesignResponse/DesignReflectRequest/Progress`(US7). 엔진값 `requirementGenerationEngine`은 Settings(프런트 Pinia + Electron `DesktopSettings`). 미반영 US=design-trace empty.)
- contracts/requirements-epic-feature-contract.md (US1–4: `PATCH /feature`, `POST·PATCH /bounded-context`, `POST /epic·/feature/propose`; 재사용 `GET /tree`·`POST /user-story/propose|confirm`·`POST /feature`·`GET /clarification/clarity`. UI 분기·radar scope 배선.)
- contracts/generation-validation-contract.md (US5–6: `POST /{epic|feature}/{id}/generate-stories`(SSE)+`/child-stories/confirm`+`GET /local-tooling/status`(claude/speckit preflight→설치안내); `POST /requirements/validate`(wrong_bc/oversized_feature/spec_conflict→교정안, 비차단); Settings 엔진 토글; robo-spec `robo-validate` 스킬 + MCP.)
- contracts/design-reflect-contract.md (US7: `GET /user-stories/pending-design`(IMPLEMENTS→Command 부재), `POST /design/reflect`(SSE, 내부적으로 기존 `/api/change/plan`)→확정은 기존 `/api/change/apply`(HITL). 프런트 `App.vue` `_onSwitchTab`('Event Modeling'→EventModelingPanel/'Design'→CanvasWorkspace)→DesignReflectPrompt.)
- quickstart.md (Q1–10 등록/뷰/편집/radar/회귀 + Q11 in-process 자동생성, Q12 Claude IDE+설치안내, Q13 DDD 검증, Q14 설계 자동 반영. Out-of-band: 언어 정책, 회귀 e2e, 스키마 diff 0건.)

**Phase progress (this branch, started 2026-05-30):**
- Phase 0 Research ✅ — D1–D14 decided.
- Phase 1 Design ✅ — data-model, 3 contracts, quickstart written.
- Phase 2 Tasks ⏸️ — pending `/speckit-tasks`.
- **Constitution Check PASS** — 신규 노드 라벨/관계 0건(I·II); 모든 LLM 변경 propose→confirm(IV); in-process는 `get_llm`(VI), claude-ide는 사용자 로컬 도구(설정 분리); **III(스트리밍)은 위반이 아닌 작업항목** — 자동생성·설계반영에 SSE 보강 필요(현 008/004는 동기). 재사용: spec008 planning agent(in-process US 생성), spec004 change plan/apply(설계 반영), spec015/029 claude_code+robo-spec MCP(claude-ide·DDD 검증).
<!-- SPECKIT END -->
