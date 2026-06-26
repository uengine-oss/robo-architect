# Tasks: analyzer↔architect 그래프 계약 정합

**Feature**: 044-analyzer-graph-contract-realign | **Input**: [spec.md](spec.md) · [plan.md](plan.md) · [research.md](research.md) · [data-model.md](data-model.md) · [contracts/graph-consumer-contract.md](contracts/graph-consumer-contract.md)

**범위**: 수정은 전부 `robo-architect`(api/ + frontend) + robo-data-frontend 표시 1곳. 생산자(analyzer) 변경 0. 신규 Neo4j 라벨/관계 0.

**규칙**: 같은 파일을 만지는 태스크는 [P] 금지(순차). 다른 파일 = [P] 병렬 가능. 모든 그래프 읽기는 [contracts/graph-consumer-contract.md](contracts/graph-consumer-contract.md) 준수.

---

## Phase 1: Setup

- [ ] T001 분석 그래프 샘플 준비 — `data/`에 framework·dbms 각 1 소스 분석·적재(없으면 `cd robo-data-analyzer && python cli_scripts/analyze_data_dir.py <name> --strategy dbms|framework`), Neo4j에 `:PROCEDURE-[:PARENT_OF*]->(:SELECT)-[:HAS_RULE]->(:RULE)` 깊은구조 존재 확인(quickstart 시나리오A 2단계 Cypher). 이후 모든 검증의 실데이터 기준.

## Phase 2: Foundational (모든 스토리 선행 — 블로킹)

- [ ] T002 신규 공용 헬퍼 `api/features/ingestion/hybrid/mapper/owner_resolver.py` 생성 — (a) `ROUTINE_LABELS={"FUNCTION","PROCEDURE","METHOD","TRIGGER"}` 상수, (b) Cypher 조각 빌더 `nearest_routine_match(var)`= `(op)-[:PARENT_OF*0..]->({var}) WHERE op:FUNCTION OR op:PROCEDURE OR op:METHOD OR op:TRIGGER` 형태로 "가장 가까운 루틴 op" 바인딩(0..=framework 자기자신), (c) `routine_table_effects(opVar)` Cypher 조각 = `(op)-[:PARENT_OF*0..]->(d)-[rw:READS|WRITES]->(t:TABLE)` 하향수집. data-model.md R1·R3 그대로. 순수 문자열/유틸, Neo4j 호출 없음(쿼리 조립용).
- [ ] T003 [P] `api/features/ingestion/hybrid/mapper/__init__.py`(또는 해당 위치)에 owner_resolver export 정리 + 헬퍼 단위테스트 `api/features/ingestion/hybrid/mapper/test_owner_resolver.py`(Cypher 조각 문자열·라벨집합 검증, Neo4j 불요).

---

## Phase 3: User Story 1 - 룰 실행흐름(NEXT/BRANCH) 주소 복구 (P1) 🎯 MVP

**목표**: `local_id→local_rule_id` 정합 + guard/branch를 NEXT/BRANCH에서 도출 → 룰 흐름·주소 복구.
**독립 테스트**: 룰 가진 그래프 인제스천 시 `local_id` NULL 0건, NEXT/BRANCH 흐름 배열 비어있음(실재 흐름 있는데) 0건, guard/branch 채워짐.

- [ ] T004 [US1] `api/features/ingestion/hybrid/code_to_rules/rule_extractor.py` `_QUERY`(L34-65): `hr.local_id`/`hrn.local_id`/`hrb.local_id`(L48,49,56,64) → `local_rule_id`. `ORDER BY hr.local_id` → `local_rule_id`.
- [ ] T005 [US1] 동 파일: `hr.guard_rule_id`(L58)·`hr.branch_from`(L59) 읽기 제거 → 도출로 대체. `(prev)-[:NEXT]->(r)<-[:HAS_RULE]-(f)` 의 prev `local_rule_id` = guard, `(parent)-[:BRANCH]->(r)<-[:HAS_RULE]-(f)` 의 parent `local_rule_id` = branch_from (data-model.md R2). 기존 next/branch 수집 패턴(L48-49) 재사용.
- [ ] T006 [US1] `api/features/ingestion/hybrid/bpm_context_builder.py`(L296,298,299): `hr.local_id`→`local_rule_id`, `guard_rule_id`·`branch_from` → R2 도출. (동일 쿼리 내 일관.)
- [ ] T007 [US1] `api/features/canvas_graph/routes/traceability.py`(L204,213,352): `hr.local_id`→`local_rule_id` + `ORDER BY` 정합.
- [ ] T008 [US1] `api/features/prd_generation/prd_model_data.py`(L150,272,289,309): `ahr.local_id`→`local_rule_id`.
- [ ] T009 [US1] 하류 `api/features/ingestion/hybrid/event_storming_bridge/rule_classifier.py`(L125-126,152) + `decomposer.py`(L350,369): `is_guarded/is_branched`·`(source_function, guard_rule_id|branch_from)` 인덱스가 T005 도출값으로 정상 구동되는지 정합(필드 출처만 바뀜, 로직 유지). 빈값/None 처리 확인.
- [ ] T010 [US1] 검증: dbms·framework 각 인제스천 재실행 → RuleDTO `local_id` NULL 0, next/branch 배열 정상, guard/branch 채워짐 대조(quickstart 시나리오 흐름 항목). 기존 `event_storming_bridge/test_*.py` 무회귀.

**Checkpoint**: 룰 흐름·주소 복구. US1 단독으로 BPM/ES 분해 입력 정상화.

---

## Phase 4: User Story 4 - dbms 오퍼레이션 단위 복원 (P1) 🎯 핵심

**목표**: 룰 오너가 구문이면 PARENT_OF↑ 루틴으로 복원(id·이름·source_function·요약), 테이블은 자식 하향수집. framework 0칸(무회귀).
**독립 테스트**: dbms 그래프에서 한 프로시저 룰이 그 프로시저 1개로 묶임(빈 source_function 0), 테이블 영향=자식 합집합.

- [ ] T011 [US4] `rule_extractor.py` `_QUERY`: 룰 오너 `(f)` 매칭을 owner_resolver `nearest_routine_match`로 교체 — `function_id`/`function_name`/`source_function`/`function_summary`를 **루틴 op**의 `op.id`/`op.name`/`op.summary`에서 취득(구문 `name=""` 회피). framework는 op=f(0칸)라 동작 불변. T004/T005와 같은 파일 → T004→T005→T011 순차.
- [ ] T012 [US4] `api/features/ingestion/hybrid/mapper/rule_context.py`: 오너 역조회(L14-17 `coalesce(f.procedure_name,f.name)=fn`)를 **id/루틴 기반**으로 정합 + READS/WRITES(L20-21)를 owner_resolver `routine_table_effects`로 **자식 하향수집**(루틴 own만 보지 않게). FR-014/R3.
- [ ] T013 [US4] `traceability.py`(L268 `(f{id})-[:READS|WRITES]->(:TABLE)`): 루틴 노드 + 자식 구문의 READS/WRITES 하향수집으로 교체(dbms 테이블효과 누락 방지). framework 무영향(자식 없음).
- [ ] T014 [US4] `api/features/ingestion/hybrid/mapper/agent_validator.py`(L130,139): 오너 식별/요약을 루틴 기준으로(FR-015 — 매칭요약=루틴요약). 같은 파일 단일 태스크.
- [ ] T015 [US4] 검증: dbms 인제스천 → 한 프로시저의 룰이 그 프로시저 1 source_function으로 묶임(빈 0), 테이블 영향=자식 DML 합집합 일치(quickstart 시나리오A 그룹·테이블). framework 시나리오B 무회귀 대조.

**Checkpoint**: dbms 분석결과가 framework와 동일 오퍼레이션 단위로 소비 가능.

---

## Phase 5: User Story 2 - 생산자 실제 속성만 소비 (P2)

**목표**: 미생산/오명 속성 읽기 정리.
**독립 테스트**: 소비 읽기 속성이 생산자 기록 키의 부분집합(불일치 0), canonical GWT 빈값 0.

- [ ] T016 [P] [US2] `traceability.py`(L192): 인라인 `(:EXAMPLE {is_boundary:false})` → `(:EXAMPLE)` (0-매칭 하드필터 제거, canonical GWT 복구). L211 `WHERE x.is_boundary` 필터·L259/290 `f.file_name`→`f.file_path` 동반. (T007/T013과 같은 파일 → traceability 태스크들 순차.)
- [ ] T017 [P] [US2] `rule_extractor.py`(L43) `is_boundary` 정리 + `_pick_canonical`(L114) example_id 정렬 폴백 유지 확인(동작 무손실). (rule_extractor 태스크군 순차.)
- [ ] T018 [P] [US2] `bpm_context_builder.py`(L276,284,295)·`prd_model_data.py`(L168,315) `is_boundary` 읽기 정리(전부 false라 무의미 → 제거/상수화). 각 파일 [P].
- [ ] T019 [P] [US2] `api/features/ingestion/hybrid/mapper/module_retriever.py`(L59,60) `:FILE` 폴백 `f.fqn`→`f.id`, `f.moduleStereotype`→`f.stereotype`.
- [ ] T020 [P] [US2] `mapper/glossary_extractor.py`(L89-90)·`ontology/neo4j_ops.py`(L850) bare/coalesce `procedure_name` 정리(자가치유 확인, 정합상 id/name 정돈). 각 파일 [P].
- [ ] T021 [US2] 검증: 소비 그래프 접점 전수 grep으로 옛속성(`local_id\b`,`is_boundary`,`f.fqn`,`moduleStereotype`,`file_name`,bare `procedure_name`) 잔존 0(생산자노드 한정). SC-002/008.

---

## Phase 6: User Story 5 - 프론트엔드 표시 정합 (P2)

**목표**: 통계 PascalCase 키 + 프로시저 룰표시.
**독립 테스트**: 모달 Rule/Example/Question 카운트 실값, 프로시저 노드상세에 하위 룰 모임.

- [ ] T022 [P] [US5] architect `frontend/src/.../RequirementsIngestionModal.vue`(~L2109,2113,2117): `counts.Rule/Example/Question` → `counts.RULE/EXAMPLE/QUESTION`(생산자 라벨). `FUNCTION/Table`은 OK 유지. `/api/ingest/stats`(`router.py:665-698`) 반환 키(`labels(n)[0]`)와 대조.
- [ ] T023 [P] [US5] robo-data-frontend `src/.../FunctionCard`/`getSemanticReport`: 루틴(프로시저) 노드 선택 시 HAS_RULE를 선택노드 id가 아니라 **자식 구문 포함**으로 조회(루틴 단위 집계 표시). robo-data-frontend 그래프 렌더·트리(이미 정합)는 불변(회귀금지).
- [ ] T024 [US5] 검증: dbms 인제스천 후 Playwright 헤드리스로 모달 카운트·프로시저 노드상세 캡처 → Read로 확인(카운트 실값·하위룰 표시). SC-010.

---

## Phase 7: User Story 3 - 죽은 패턴 정리 + 계약문서 정렬 (P3)

**목표**: 무효 패턴 제거 + 문서 단일진실화.
**독립 테스트**: 죽은 라벨/엣지 참조 0, 계약문서=생산자·코드 일치.

- [ ] T025 [P] [US3] `mapper/rule_context.py`(L19): `(a:Actor)-[:ROLE]->(f)` OPTIONAL MATCH 제거(생산자에 :Actor·ROLE 없음). (rule_context = T012와 같은 파일 → 순차.)
- [ ] T026 [P] [US3] `traceability.py`(L221): 죽은 `:HAS_BUSINESS_LOGIC`/`:BusinessLogic` 폴백 제거. (traceability 태스크군 순차.)
- [ ] T027 [P] [US3] stale 주석 정정: `event_storming_bridge/promote_to_es.py`(L104-109), `persistence.py`(L646), `api/features/ingestion/workflow/ingestion_workflow_context.py`(L71-81) — "FUNCTION 다중라벨/procedure_name/guard_rule_id/branch_from/is_boundary" 설명을 현행(단일라벨·local_rule_id·도출·미존재)으로. 각 파일 [P].
- [ ] T028 [US3] `specs/036-bpmn-rule-mapping-recall/contracts/internal-mapper-contract.md`: 본 계약을 [contracts/graph-consumer-contract.md](contracts/graph-consumer-contract.md)로 **대체**(상단에 supersede 표기 + 044 링크), 옛 `:FUNCTION/:MODULE`+`id`·`HAS_FUNCTION/BELONGS_TO_PACKAGE` 등 stale 명세 정정. SC-005.

---

## Phase 8: Polish & 자가검증 (Cross-Cutting)

- [ ] T029 0-match 관측성(FR-005): 소비자→생산자 엣지 MERGE 지점(persistence GROUNDED_IN/DERIVED_FROM/RAISED_IN, promote_to_es ATTACHED_TO) 매칭 0 시 경고 로그 추가(조용한 no-op 차단). SC-004.
- [ ] T030 풀스택 기동 + dbms·framework 각 1회 분석→인제스천 라이브 검증(quickstart 전 시나리오) — 내가 직접([[principles]]§6): NDJSON 스트림·Neo4j 직접쿼리·RuleDTO 대조 + 프론트 Playwright 캡처. framework 무회귀(SC-007) 확인.
- [ ] T031 기존 테스트 회귀: `cd robo-architect && uv run pytest api/features/ingestion -q` 등 무회귀 확인(특히 `event_storming_bridge/test_promote_to_es_traceability.py`).
- [ ] T032 메모리 갱신([[todo]]) — ①A 항목을 "044로 정합 구현완료"로, dbms 오너복원 사실 기록.

---

## Dependencies & 실행 순서

- **Setup(T001)** → **Foundational(T002-T003)** → 스토리들.
- **US1(P1, T004-T010)** 과 **US4(P1, T011-T015)** = MVP 핵심. 단 둘 다 `rule_extractor.py` 수정 → **T004→T005→T011 순차**(같은 파일). US4 T011은 T002(owner_resolver) 필요.
- **US2(T016-T021)**: traceability(T016)·rule_extractor(T017)는 각 파일이 US1/US4와 겹쳐 **그 파일 태스크 뒤 순차**. module_retriever/glossary 등은 [P].
- **US5(T022-T024)**: 프론트, 백엔드와 독립 [P]. 단 T023은 US4 개념(루틴 집계) 공유.
- **US3(T025-T028)**: rule_context(T025)·traceability(T026)는 해당 파일 태스크 뒤 순차. 주석/문서(T027-T028) [P].
- **Polish(T029-T032)**: 전 스토리 후.

**같은 파일 순차 클러스터**: `rule_extractor.py`={T004,T005,T011,T017} / `traceability.py`={T007,T013,T016,T026} / `rule_context.py`={T012,T025} / `bpm_context_builder.py`={T006,T018}.

## 병렬 기회 (예시)
- Foundational 후: T019, T022(프론트), T027(주석) 등 서로 다른 파일 동시.
- US2 내: T018(bpm/prd), T019(module_retriever), T020(glossary/neo4j_ops) 병렬.

## MVP 범위
**US1 + US4(P1)** = 최소 가치(룰 흐름 복구 + dbms 단위 정상화). 여기까지면 dbms/framework 양쪽 핵심 소비 정상. US2/US5(P2)·US3(P3)는 증분.

## Implementation Strategy
1. Foundational(owner_resolver) → 2. US1(흐름) → 3. US4(dbms 단위) = MVP 검증(T010/T015) → 4. US2(NULL정리)·US5(프론트) → 5. US3(청소/문서) → 6. Polish 라이브 자가검증(T030).
