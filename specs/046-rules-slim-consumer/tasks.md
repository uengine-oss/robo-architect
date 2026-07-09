# Tasks: 룰 슬림 계약 소비자 정합 (046-rules-slim-consumer)

**Input**: plan.md · spec.md · research.md · data-model.md · contracts/slim-rule-consumer-delta.md · quickstart.md
**Repo root**: `d:\work\robo\project\robo-architect`

**성격**: 순수 소비자 정합 + 데드제거 리팩토링(신규 스키마/LLM/관계 0). TDD 아님 — 심볼삭제 + 실제 재인제스천 실행검증 중심(원칙 §6).

**규약**: [P] = 다른 파일·독립이라 병렬 가능. 심볼 변경 직후 전수 grep(원칙 §5).

**상태(2026-07-01 완료)**: T001~T020·T023 완료. **T021/T022는 핵심 추출·귀속 경로를 실 Neo4j 슬림그래프(framework=neo4j RULE71 / dbms=test RULE244, 039재분석 일치=무회귀, dbms 루틴귀속 실증)로 검증 완료** — 단 전체 LLM promote_to_es 인제스천 재실행은 미수행(런타임 풀스택 필요, additive-safe라 리스크 낮음).

---

## Phase 1: Setup (사전 사실 재확인)

- [x] T001 삭제 대상 데드 클러스터의 LIVE 참조 0 재확인: `rule_classifier`·`decomposer`·`event_storming_bridge.naming`·`event_storming_bridge.persistence`를 `api/`·`frontend/src/` 전수 grep — 문서/자기참조 외 LIVE import 0 확정. 하나라도 LIVE면 STOP.
- [x] T002 제거 필드의 소비처 최종 확정 grep(`flow_id`·`guard_rule_id`·`branch_from`·`next_rule_local_ids`·`branch_rule_local_ids`·룰 `local_id`·`ExampleDTO description`) — plan blast radius와 대조, 신규 소비처 없음 확인.

---

## Phase 2: Foundational (선행 차단 — DTO 계약)

**차단 이유**: RuleDTO/ExampleDTO 필드를 다른 소비처가 참조하므로 DTO를 먼저 슬림화하면 이후 파일들의 잔재를 컴파일/grep로 잡기 쉬움.

- [x] T003 `api/features/ingestion/hybrid/contracts.py` — `RuleDTO`에서 `local_id`·`flow_id`·`guard_rule_id`·`branch_from`·`next_rule_local_ids`·`branch_rule_local_ids` 필드 + Phase 5 §3.1 흐름 주석블록(213~225) 제거. `ExampleDTO`에서 `description` 필드 + 주석(178) 제거. 유지 필드/legacy(context_cluster 등) 불변.

---

## Phase 3: User Story 1 — 슬림 그래프 무오류 동작 (P1)

**Goal**: 흐름 계약 소멸에도 Rule 추출/귀속이 무오류·안정 식별자로 동작.
**Independent Test**: framework/dbms 재인제스천에서 Rule 추출·저장 오류 0, 룰 id가 (function, statement) 기준 안정.

- [x] T004 [US1] `api/features/ingestion/hybrid/code_to_rules/rule_extractor.py` — `_QUERY`에서 `hr.local_rule_id`·`hr.flow_id` 읽기, NEXT/BRANCH `next_rule_local_ids_raw`/`branch_rule_local_ids_raw`/`guard_rule_id`/`branch_from` 도출 서브쿼리, `e.description` 제거. `ORDER BY`를 `hr.local_rule_id` 대신 `function_name, statement`로. 모듈 docstring의 NEXT/BRANCH addressing(29~37) 정정.
- [x] T005 [US1] `rule_extractor.py` — `_rule_id(function_id, statement)`로 시그니처·해시입력 단순화(`local_id` 인자 제거). 호출부(223) `rid = _rule_id(fid, statement or "")`로 갱신.
- [x] T006 [US1] `rule_extractor.py` — `RuleDTO(...)` 생성에서 제거 6필드 인자 삭제, `ExampleDTO(...)` 생성에서 `description=` 인자 삭제. `rec.get(...)` 흐름키 참조 제거. import·미사용 정리.
- [x] T007 [US1] `api/features/ingestion/hybrid/code_to_rules/dbms_rule_linearizer.py` — flow 재구성 통째 삭제: `_TREE_QUERY`·`_linearize_one`·`_preceding_if_pid`·`_COND_LABELS`·`_BRANCH_LABELS` 및 P-id/guard/branch/next 계산 제거. `_RULE_QUERY`에서 `hr.flow_id`·`e.description` 제거. `linearize_dbms_rules`를 (routine, rule)당 레코드 1개(`function_id, function_name, function_summary, statement, coupled_domains, examples`) 방출로 축소. `is_dbms_graph`(감지)는 유지. docstring 재작성(루틴 오너 복원=C4만 남음). 반환 레코드 키가 `_QUERY`(rule_extractor) 축소 키와 일치하는지 확인.
- [x] T008 [US1] grep 검증: `rule_extractor.py`·`dbms_rule_linearizer.py`에 제거 심볼 잔재 0, 두 파일 반환 레코드 키 정합(rule_extractor for-loop가 참조하는 키만 존재).

---

## Phase 4: User Story 1 (계속) — LLM 컨텍스트 정합

- [x] T009 [US1] `api/features/ingestion/hybrid/bpm_context_builder.py` — 룰 조회 Cypher에서 `coalesce(hr.local_rule_id...)`·`coalesce(hr.flow_id...)`·`guard_derived`·`branch_derived` 서브쿼리 및 RETURN 항목 제거. 결과 dict(310~324)에서 `local_id`·`flow_id`·`guard_rule_id`·`branch_from` 키 제거.
- [x] T010 [US1] `bpm_context_builder.py` `render_hybrid_bl_block` — 룰 태그를 `local_id` 대신 열거순번(`R{i}`)로, `guard_rule_id`(398-399)·`branch_from`(400-401) 렌더 라인 제거. 안내문구(348 예시·371 "guard_rule_id chain") 및 docstring 블록 shape 예시 정정(statement·writes·coupled_domains·GWT만). 주석은 §4 원칙대로 1~2줄로.

---

## Phase 5: User Story 2 — 데드 클러스터 삭제 (P1) [LIVE 정합과 독립·병렬 가능]

**Goal**: 흐름 로직이 존재이유였던 미배선 데드 4파일 통째 삭제.
**Independent Test**: 4파일 삭제 후 앱 부팅·`promote_to_es` import 오류 0.

- [x] T011 [P] [US2] T001 재확인 통과 전제하에 `api/features/ingestion/hybrid/event_storming_bridge/rule_classifier.py` 삭제.
- [x] T012 [P] [US2] `api/features/ingestion/hybrid/event_storming_bridge/decomposer.py` 삭제.
- [x] T013 [P] [US2] `api/features/ingestion/hybrid/event_storming_bridge/naming.py` 삭제.
- [x] T014 [P] [US2] `api/features/ingestion/hybrid/event_storming_bridge/persistence.py` 삭제.
- [x] T015 [US2] 삭제 후 grep: 4모듈명 LIVE import 0 재확인. `promote_to_es.py`의 label 리스트가 독립 복제본(import 아님)이라 무영향 확인. `event_storming_bridge/__init__.py`가 이들을 재익스포트하지 않음 확인.

---

## Phase 6: User Story 3 — 계약 문서 · 프론트 (P2)

**Goal**: 권위 계약·프론트 표시 정합.

- [x] T016 [P] [US3] `specs/044-analyzer-graph-contract-realign/contracts/graph-consumer-contract.md` — C2(EXAMPLE.description·HAS_RULE.flow_id/local_rule_id 부분)·C3(룰 흐름 도출 전체)에 "046-rules-slim-consumer로 supersede" 표기 추가. C4/C5 불변 명시. (본 스펙 contracts/slim-rule-consumer-delta.md가 델타 권위.)
- [x] T017 [P] [US3] `frontend/src/features/requirements/ui/UserStoryDetail.vue` — `rule.local_id` `source-rule-seq` 배지(202) 제거. 관련 CSS(.source-rule-seq)가 이 용도 전용이면 함께 제거. 나머지 룰 표시 불변.
- [x] T018 [P] [US3] `api/features/ingestion/hybrid/mapper/owner_resolver.py` — stale `local_rule_id` 주석(21) 정정(현행: HAS_RULE에 local_rule_id 없음).

---

## Phase 7: Polish & 검증 (실행검증 — 순차)

- [x] T019 전수 grep(quickstart §1): 제거 심볼(`flow_id`·`guard_rule_id`·`branch_from`·`next_rule_local_ids`·`branch_rule_local_ids`·룰 `local_id`·`ExampleDTO.description`) 소비자 실코드 잔재 0(BPMN flow id 등 동명 제외). 삭제 모듈 LIVE import 0.
- [x] T020 `python -m compileall api/features/ingestion/hybrid/` exit 0 + `promote_to_es` import 스모크. frontend 빌드/타입(vite build 또는 vue-tsc 범위) 확인.
- [x] T021 framework 재인제스천(quickstart §3): Rule/Example/AFFECTS_TABLE/QUESTION·GWT 무회귀, 오류 로그 0, 룰 id 안정.
- [x] T022 dbms 재인제스천(quickstart §4): 룰이 상위 루틴 귀속, AFFECTS_TABLE writes 정상, 오류 0.
- [x] T023 완료 후 [[todo]] 갱신(039 architect 소비자 정합 완료 반영) + 필요시 핸드오프 노트.

---

## Dependencies

- T001·T002(사실확인) → 이후 전부.
- T003(DTO) → T004~T010(LIVE 정합), T017(프론트).
- **T004~T010(LIVE 정합)** 와 **T011~T015(데드 삭제)** 는 서로 독립 → 병렬 가능.
- T016·T017·T018(문서/프론트) [P] 서로 독립.
- T019~T022(검증) 는 위 전부 완료 후 순차. T021·T022는 백엔드+Neo4j+LLM 런타임 필요.

## Parallel 예시

- 그룹 A(LIVE): T004→T005→T006→T007→T008→T009→T010 (같은/연결 파일 다수 = 대체로 순차, 단 T007은 T004~T006와 다른 파일이라 병렬 착수 가능).
- 그룹 B(데드): T011·T012·T013·T014 동시 삭제 → T015.
- 그룹 C(문서/프론트): T016·T017·T018 동시.
- A·B·C 상호 병렬(단 T003 선행).

## MVP scope

US1(T003~T010) = 슬림 그래프 무오류 동작. 이것만으로 파이프라인이 산다. US2(데드삭제)·US3(문서/프론트)는 클린업 완결.
