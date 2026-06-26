# Phase 0 Research: analyzer↔architect 그래프 계약 정합

모든 결정은 생산자(analyzer, branch refactor)·소비자(architect, api/) **현행 코드 전수조사**에 근거. NEEDS CLARIFICATION 잔여 0.

## D1. 노드 식별 = `id` (이름 아님)

- **Decision**: 소비자는 노드를 **`id`로 식별**한다. 함수/루틴 매칭의 1차 키를 `f.id`로, 이름(`name`)은 표시·보조로만.
- **Rationale**: 생산자는 모든 노드 식별자를 단일 `id`로 통일(spec 017). dbms 구문 노드는 `name=""`이라 이름 기반 매칭이 깨짐. `id`는 항상 존재·고유(`주문처리:IF:128`).
- **근거 file:line**: 생산자 `shared/neo4j/edges/has_rule.py:17`(`MATCH (node {id: source_id})` 라벨무관), `shared/neo4j/nodes/code_node.py:41-52`(props에 procedure_name 없음). 소비자 `rule_extractor.py:51`(`coalesce(f.id, f.procedure_name, f.name)` — id 우선이라 대체로 OK이나, 이름 기반 역조회들이 문제).
- **Alternatives**: 구문에 합성이름(`IF[128]`) 부여 → **기각**: 이름은 생기나 구문별로 흩어져 한 프로시저가 여러 단위로 쪼개짐(D4 문제 미해결). 표시용 `타입[라인]`은 프론트가 이미 처리(`graphDisplay.ts`).

## D2. 룰 흐름 속성명 = `local_rule_id`

- **Decision**: 소비자의 `hr.local_id` 읽기를 모두 **`hr.local_rule_id`**로 교체(NEXT/BRANCH 크로스백 포함).
- **Rationale**: 생산자 HAS_RULE 엣지 속성 = `local_rule_id`/`flow_id`/`coupled_domains` 뿐. `local_id`는 미존재 → 현재 항상 NULL → NEXT/BRANCH 배열 빈값·룰주소 붕괴.
- **근거**: 생산자 `has_rule.py:19`, `data_models/graph_edges.py:220`. 소비자 `rule_extractor.py:48,49,56,64`, `bpm_context_builder.py:296`, `traceability.py:204,213,352`, `prd_model_data.py:150,272,289,309`.

## D3. guard(선행조건)/branch(분기부모) = NEXT/BRANCH 엣지에서 도출

- **Decision**: 폐기된 `hr.guard_rule_id`/`hr.branch_from` 읽기 제거. 대신 **도출**:
  - `branch_from` = 들어오는 **BRANCH 엣지의 부모 룰** `local_rule_id` (`(parent)-[:BRANCH]->(this)`).
  - `guard_rule_id`(선행조건) = 들어오는 **NEXT 엣지의 직전 룰** `local_rule_id` (`(prev)-[:NEXT]->(this)`).
- **Rationale**: 생산자가 `guard_rule_id/branch_from` 속성을 **flow_id 계층에서 도출 가능하므로 폐기**(명시 주석). 빌더가 flow_id `-` 계층으로 BRANCH를, 메인체인으로 NEXT를 생성. 그래프에 정보가 있으므로 소비자가 동일 도출로 의미 보존(생산자 변경 불필요).
- **근거**: 생산자 `data_models/code_analysis_output.py:90`(폐기 주석), `shared/example_mapping/builder.py:173-192`(flow_id→NEXT/BRANCH 도출 로직), `shared/neo4j/edges/rule_flow.py`(엣지 owner_id·local_rule_id 끝점). 소비자 하류 `rule_classifier.py:125-126,152`·`decomposer.py:350,369`가 이 값에 의존.
- **Alternatives**: guard 소비 완전 제거 → **기각**: rule_classifier `is_guarded`·decomposer precondition command가 load-bearing(spec 036 recall). NEXT-직전 도출이 옛 "predecessor가 먼저 성립" 의미와 합치.

## D4. dbms 오퍼레이션 단위 = 가장 가까운 루틴 (PARENT_OF 상승) ★핵심

- **Decision**: 룰/예시/질문 오너가 **호출 불가능 구문 노드**면, `PARENT_OF`를 따라 위로 올라가 **라벨 ∈ {FUNCTION, PROCEDURE, METHOD, TRIGGER}** 인 가장 가까운 노드를 찾아 그 **루틴을 오퍼레이션 단위**(식별 id·이름·요약·그룹핑 키 source_function)로 삼는다. framework는 오너가 이미 루틴 → 0칸 상승(무변화). **전략 분기 없는 단일 규칙.**
- **Rationale**: 생산자는 dbms 프로시저를 자식 구문(SELECT/IF/…)으로 분해하고 룰을 **각 자식에** 붙임(per-node example mapping). 자식은 이름 `""`·HAS_MEMBER 비대상. framework·dbms 공통 "호출 가능 루틴" = 비즈니스 오퍼레이션 단위(BPM task/command가 오퍼레이션 단위). architect는 source_function(=오너 이름)으로 룰을 user story로 그룹(`bpm_to_user_stories.py:34,38` "fn 묶음=1 UserStory"). dbms 자식은 이름 없어 그룹 붕괴 → 루틴으로 복원해야 framework와 동일 단위.
- **근거**: 생산자 분석단위=모든 CodeNode(`analyze_code_step.py:137-142,244` + `batch_analyze.py:135-137`), 자식 생성 `antlr_json_reader.py:333-372`, 루틴 라벨 집합 `antlr_json_reader.py:44`(`_ROUTINE_LABELS={FUNCTION,PROCEDURE,METHOD,TRIGGER}`), HAS_MEMBER=모듈→루틴만 `antlr_json_reader.py:489-491`. 소비자 그룹단위=함수 `bpm_to_user_stories.py:34`, parent_module(파일/클래스)=단순 메타 `contracts.py:296`.
- **단위 결정**: framework=함수/메서드 ⟷ dbms=프로시저/함수/트리거(같은 "호출 루틴" 줄). 모듈(파일/클래스)은 양쪽 메타로만, 구문은 단위 아님. → 프로시저 = 메서드와 동급(호출 1개), "파일 전체 묶기" 아님.
- **Alternatives**: (a) 구문 단위 유지 → 기각(이름 없음·그룹 붕괴). (b) 모듈(파일) 단위 → 기각(framework가 함수 단위라 불일치·과대그룹).

## D5. 테이블 영향(READS/WRITES) = 자식에서 하향 수집

- **Decision**: 한 오퍼레이션(루틴)의 테이블 읽기/쓰기 조회 시, 루틴 노드뿐 아니라 그 **PARENT_OF 자식 구문들의 READS/WRITES를 수집·집계**한다.
- **Rationale**: 생산자는 READS/WRITES를 DML이 실제 있는 **자식 구문 노드**(SELECT/UPDATE)에 붙임(`source_id=fn.id`, `_own_body` 자식범위 제외). 루틴 노드 자신엔 거의 없음 → 루틴에서만 조회하면 테이블 영향 누락("열화"). framework는 함수에 직접 → 자식 없어 동작 불변.
- **근거**: 생산자 `analysis_flow/step4_linking/link_dbms_tables_step.py:106-132`(`source_id=fn.id`, code_nodes 순회, own-body). 소비자 `traceability.py:268`(`(f{id})-[:READS|WRITES]->(:TABLE)` — 루틴 id면 자식 누락).
- **Alternatives**: 루틴 own-body만 → 기각(dbms 테이블 영향 0 유실).

## D6. `is_boundary`(경계 예시) = 폐기 정리, traceability 하드필터만 실수정

- **Decision**: 생산자가 안 쓰는 `is_boundary` 읽기를 정리. 대표예시 선택은 **example_id 정렬 폴백**으로 충분(이미 그렇게 degrade). **유일 실버그 = `traceability.py:192`의 인라인 매칭 `(:EXAMPLE {is_boundary:false})`** → 0-매칭으로 canonical GWT 빈값 → 매칭조건 제거(`(:EXAMPLE)`로).
- **Rationale**: 생산자 Example props = `id/description/given/when_/then_` 뿐, `is_boundary` 미존재(boundary 개념 코드 전체에서 폐기). 정렬용 `bool(is_boundary)`는 전부 false라 자동 example_id 폴백 → 기능 무손실. 인라인 `{is_boundary:false}`만 하드필터라 0-매칭.
- **근거**: 생산자 `shared/neo4j/nodes/example.py`(is_boundary 없음), analyzer 전체 `boundary` grep 0건. 소비자 `_pick_canonical` `rule_extractor.py:114`(정렬), `traceability.py:192`(하드필터 — 실버그).
- **Alternatives**: 경계 도출 → 기각(생산자에 정보 없음, 도출 불가).

## D7. 잔여 이름표 매핑 (단순 치환)

- `f.file_name` → `f.file_path` (`traceability.py:259,290`; 생산자는 file_path만).
- `:FILE` 폴백 `f.fqn`/`f.moduleStereotype` → `f.id`/`f.stereotype` (`module_retriever.py:59,60`).
- 죽은 패턴 제거: `(a:Actor)-[:ROLE]->(f)` (`rule_context.py:19`), `:HAS_BUSINESS_LOGIC/:BusinessLogic` (`traceability.py:221`, 가드된 레거시).
- 프론트 통계키 `counts.Rule/Example/Question` → `RULE/EXAMPLE/QUESTION` (`RequirementsIngestionModal.vue`).
- `procedure_name` ~14곳: 전부 `coalesce(...,name)` 자가치유 → 동작 유지, D4 오너복원으로 이름은 루틴에서 취득(개명 정리는 선택).

## D8. 소비자 자체 세션노드는 대상 아님

- **Decision**: `:Rule {session_id}`·`:Aggregate`·`:Command`·`:Event`·`:Policy` 등 **architect 자신이 만든 PascalCase 세션노드**는 본 작업 비대상(생산자 그래프 아님).
- **근거**: `neo4j_ops.py:68` 주석("hybrid PascalCase `:Rule`"), 일관 `session_id` 보유 / 생산자 노드는 `session_id IS NULL`.

## D9. ★실데이터 결론 (neo4j 두 DB 직접 조회) — framework vs dbms 인코딩 차이

| | `neo4j` DB = framework(C) | `test` DB = dbms(Oracle) |
|---|---|---|
| 룰 오너 | **FUNCTION 직접 100%**(76/76) | 자식 구문 90%(SELECT54·MERGE24·IF22…), 루틴 15 |
| 함수당 룰 | 1~5(avg2) 한 노드에 | 노드당 1, 흩어짐 |
| 제어흐름 위치 | **룰 레이어**(flow_id'1-1'+룰NEXT/BRANCH, 함수 위) | **구문 트리**(PARENT_OF 깊이8 + 구문NEXT) |
| PARENT_OF | 없음(평탄) | 깊이 8 |
| 구문오너 이름 | 해당없음 | 152/153 빈값 |

**결론**: 같은 것(루틴 제어흐름+룰)을 framework는 **룰 레이어**에, dbms는 **구문 트리**에 인코딩. → 목표 = **framework 모양**(decomposer가 소비하는 형태). framework=이미 그 모양(US1만), dbms=구문트리를 그 모양으로 **선형화**.

## D10. ★dbms 선형화 알고리즘 (test DB 실프로시저로 프로토타입 검증완료)

루틴 op 마다:
1. op 서브트리(op + PARENT_OF* 자손) 전 노드 + 룰 수집.
2. 실행순서(start_line) 정렬 → 각 룰에 **프로시저-전역 유니크 local_id(P1,P2…)** 부여(R1×29 충돌 해소).
3. **guard(중첩=조건종속)** = 룰 노드에서 PARENT_OF 위로, **조건/제어 라벨(IF/ELSIF/ELSE/LOOP/CASE/WHILE/FOR/EXCEPTION/TRY)** 이면서 룰 가진 가장 가까운 조상의 룰. (DML 내부 MERGE→SELECT 는 부분이라 guard 미부여.)
4. **branch_from** = ELSIF/ELSE 노드 룰 → 직전 IF/ELSIF 룰.
5. **next** = 실행순서 시퀀스.
6. source_function/요약 = op(루틴), 테이블 = 자손 하향수집.
- framework: op=자기자신, 트리 평탄 → 1~5룰이 flow_id/룰NEXT로 이미 연결 → 동작 불변(무회귀).

**프로토타입 검증(실데이터, scratchpad/linearizer_proto.py)**: TRG_INS_RDITAG_TB→INSERT가 IF guard 정확; PRC_DATA_ANALYSYS_TEST2→LOOP 내부 15룰 전부 루프 guard; 충돌 0. ✅ 알고리즘 타당 확인.

**구현 위치**: dbms 경로는 Cypher 단발이 아니라 **트리워크(Python)**가 필요 → rule_extractor에 dbms 전용 추출 경로 추가(framework 경로 불변=무회귀). 이미 작동하는 인제스천 보호.

## 미해결(NEEDS CLARIFICATION): 없음
모든 설계 결정이 생산자·소비자 현행 코드 + neo4j 실데이터로 확정됨.
